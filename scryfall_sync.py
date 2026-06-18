import requests
import mysql.connector
import ijson
from datetime import date
import urllib.parse
import gzip
import time
from bot_utilities import notify_me

def scryfall_sync():

    # Connect to db
    db = mysql.connector.connect(
        host="localhost",
        user="root",
        password="",
        database="mtg_inventory"
    )

    cursor = db.cursor()

    today = date.today().isoformat()

    # Get the last sync date from db
    cursor.execute("SELECT meta_value FROM meta_data WHERE meta_key = 'last_scryfall_sync'")
    row = cursor.fetchone()

    last_update_date = row[0] if row else "0000-00-00"

    encoded_query = urllib.parse.quote(f'date>"{last_update_date}" date<="{today}"')

    next_page_url = f"https://api.scryfall.com/cards/search?q={encoded_query}"

    print(f"Syncing cards to database...")
    
    sql = """
        INSERT INTO ref_cards (oracle_id, card_name, type_line, mana_cost, rarity, text_box, power, toughness, w, u, b, r, g, image_data)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON DUPLICATE KEY UPDATE 
            card_name = VALUES(card_name),
            type_line = VALUES(type_line),
            mana_cost = VALUES(mana_cost),
            rarity = VALUES(rarity),
            text_box = VALUES(text_box),
            power = VALUES(power),
            toughness = VALUES(toughness),
            w = VALUES(w),
            u = VALUES(u),
            b = VALUES(b),
            r = VALUES(r),
            g = VALUES(g),
            image_data = VALUES(image_data)
    """

    count = 0

    while next_page_url:
        print(f"Fetching: {next_page_url}")
        bulk = requests.get(next_page_url, stream=True)

        if bulk.headers.get('Content-Encoding') == 'gzip':
            stream = gzip.GzipFile(fileobj=bulk.raw)
        else:
            stream = bulk.raw
        parser = ijson.parse(stream)
        next_page_url = None

        # Batch upload cards
        cards_generator = ijson.items(stream, 'data.item')
    
        batch = []

        for card in cards_generator:

            colors = card.get('color_identity', [])

            w = 1 if 'W' in colors else 0
            u = 1 if 'U' in colors else 0
            b = 1 if 'B' in colors else 0
            r = 1 if 'R' in colors else 0
            g = 1 if 'G' in colors else 0

            image_url = card.get('image_uris', {}).get('large')
            
            if not image_url and 'card_faces' in card:
                image_url = card['card_faces'][0].get('image_uris', {}).get('large')

            image_data = b''
            if image_url:
                for attempt in range(3):
                    try:
                        img_response = requests.get(image_url, timeout=10)
                        if img_response.status_code == 200:
                            image_data = img_response.content
                            break
                        else:
                            print(f"Attempt {attempt+1}: Received status {img_response.status_code}")
                    except Exception as e:
                        if attempt < 2:
                            time.sleep(1)
                        else:
                            print(f"Failed to download image for {card.get('name')} after 3 attempts: {e}")

            # Trim card data
            card_data = (
                card.get('oracle_id'),
                card.get('name'),
                card.get('type_line'),
                card.get('cmc'),
                card.get('rarity'),
                card.get('oracle_text'),
                card.get('power'),
                card.get('toughness'),
                w, u, b, r, g,
                image_data
            )

            batch.append(card_data)
        
            # Insert in batches
            if len(batch) >= 1000:
                cursor.executemany(sql, batch)
                db.commit()
                count += len(batch)
                batch = []

        # Insert remaining cards
        if batch:
            cursor.executemany(sql, batch)
            db.commit()
            count += len(batch)
        
        meta_resp = requests.get(bulk.url).json() 
        next_page_url = meta_resp.get('next_page') if meta_resp.get('has_more') else None
        time.sleep(0.1)

    # Update last sync date in db
    cursor.execute("""
                   INSERT INTO meta_data (meta_key, meta_value) 
                   VALUES ('last_scryfall_sync', %s) 
                   ON DUPLICATE KEY UPDATE meta_value = VALUES(meta_value)""", (today,))
    db.commit()
    cursor.close()
    db.close()
    print(f"Total cards synced: {count}")
    if count > 0:
        notify_me(f"Cards synced: {count}")

if __name__ == "__main__":
    scryfall_sync()
