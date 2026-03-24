import requests
import mysql.connector
import ijson
from datetime import date
import urllib.parse

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
    last_update_date = cursor.fetchone()

    if last_update_date is None:
        last_update_date = "0000-00-00"
    else:        
        last_update_date = last_update_date.isoformat()

    encoded_query = urllib.parse.quote(f'date>"{last_update_date}" date<="{today}"')

    # Get bulk data since last sync
    bulk = requests.get(f"https://api.scryfall.com/cards/search?q={encoded_query}", stream=True)
    

    print(f"Syncing {len(bulk)} cards to database...")
    
    sql = """
        INSERT INTO ref_cards (oracle_id, card_name, type_line, mana_cost, rarity, text_box, power, toughness, w, u, b, r, g)
        VALUES (%s, %s, %s, %d, %s, %s, %d, %d, %d, %d, %d, %d, %d)
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
            g = VALUES(g)
    """

    # Batch upload cards
    cards_generator = ijson.items(bulk.raw, 'item')
    
    batch = []
    count = 0

    for card in cards_generator:

        colors = card.get('color_identity', [])

        w = 1 if 'W' in colors else 0
        u = 1 if 'U' in colors else 0
        b = 1 if 'B' in colors else 0
        r = 1 if 'R' in colors else 0
        g = 1 if 'G' in colors else 0

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
            w, u, b, r, g
        )

        batch.append(card_data)
        
        # Insert in batches
        if len(batch) >= 1000:
            cursor.executemany(sql, batch)
            db.commit()
            count += len(batch)
            print(f"Synced {count} cards...")
            batch = []

    # Insert remaining cards
    if batch:
        cursor.executemany(sql, batch)
        db.commit()
        count += len(batch)

    # Update last sync date in db
    sql = "UPDATE meta_data SET meta_value = %s WHERE meta_key = 'last_scryfall_sync'"
    cursor.execute(sql, today)
    db.commit()

    cursor.close()
    db.close()
    print(f"Total cards synced: {count}")

if __name__ == "__main__":
    scryfall_sync()