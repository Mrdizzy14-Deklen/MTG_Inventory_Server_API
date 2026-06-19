import requests
import mysql.connector
import time
from bot_utilities import notify_me

def fix_card_art():
    db = mysql.connector.connect(
        host="localhost",
        user="root",
        password="",
        database="mtg_inventory"
    )
    cursor = db.cursor()

    headers = {
        'User-Agent': 'MTG-Inventory/1.0',
        'Accept': 'application/json;q=0.9,*/*;q=0.8'
    }

    print("Fetching Scryfall's canonical card art...")
    
    response = requests.get("https://api.scryfall.com/bulk-data/oracle-cards", headers=headers)
    bulk_info = response.json()
    
    if bulk_info.get('object') == 'error':
        print(f"Scryfall API Error: {bulk_info.get('details')}")
        return

    download_uri = bulk_info['download_uri']

    print("Downloading canonical data map...")
    bulk_data = requests.get(download_uri, headers=headers).json()

    canonical_urls = {}
    for card in bulk_data:
        oracle_id = card.get('oracle_id')
        
        # Extract image URL
        image_url = card.get('image_uris', {}).get('large')
        if not image_url and 'card_faces' in card:
            image_url = card['card_faces'][0].get('image_uris', {}).get('large')

        if oracle_id and image_url:
            canonical_urls[oracle_id] = image_url

    print("Finding cards to fix...")
    cursor.execute("SELECT oracle_id, card_name FROM ref_cards")
    db_cards = cursor.fetchall()

    print(f"Found {len(db_cards)} cards. Starting downloads...")

    update_sql = "UPDATE ref_cards SET image_data = %s WHERE oracle_id = %s"
    count = 0

    for oracle_id, card_name in db_cards:
        canonical_url = canonical_urls.get(oracle_id)
        
        if canonical_url:
            for attempt in range(3):
                try:
                    img_response = requests.get(canonical_url, headers=headers, timeout=10)
                    if img_response.status_code == 200:
                        cursor.execute(update_sql, (img_response.content, oracle_id))
                        db.commit()
                        count += 1
                        
                        if count % 100 == 0:
                            print(f"Fixed {count} cards...")
                        break
                    else:
                        time.sleep(1)
                except Exception as e:
                    if attempt == 2:
                        print(f"Failed to fetch art for {card_name}: {e}")
                    time.sleep(1)
            
            time.sleep(0.1) 

    cursor.close()
    db.close()

    print(f"\nReplaced art for {count} cards")
    notify_me(f"Replaced art for {count} cards", severity=0)

if __name__ == "__main__":
    fix_card_art()