import requests
import mysql.connector
import time

def fix_card_art():
    # Connect to db
    db = mysql.connector.connect(
        host="localhost",
        user="root",
        password="",
        database="mtg_inventory"
    )
    cursor = db.cursor()

    # Scryfall strictly requires a custom User-Agent to prevent anonymous bot spam
    headers = {
        'User-Agent': 'DeklenInventoryApp/1.0',
        'Accept': 'application/json;q=0.9,*/*;q=0.8'
    }

    print("Fetching Scryfall's canonical Oracle Cards list...")
    
    # 1. Get the download URI for the canonical cards list
    response = requests.get("https://api.scryfall.com/bulk-data/oracle-cards", headers=headers)
    bulk_info = response.json()
    
    # Catch Scryfall API errors gracefully
    if bulk_info.get('object') == 'error':
        print(f"Scryfall API Error: {bulk_info.get('details')}")
        return

    download_uri = bulk_info['download_uri']

    print("Downloading canonical data map (this takes a moment)...")
    bulk_data = requests.get(download_uri, headers=headers).json()

    # 2. Build a fast dictionary mapping oracle_id -> canonical_image_url
    canonical_urls = {}
    for card in bulk_data:
        oracle_id = card.get('oracle_id')
        
        # Safely extract the image URL
        image_url = card.get('image_uris', {}).get('large')
        if not image_url and 'card_faces' in card:
            image_url = card['card_faces'][0].get('image_uris', {}).get('large')

        if oracle_id and image_url:
            canonical_urls[oracle_id] = image_url

    # 3. Find all cards currently in your database
    print("Finding cards in your database to fix...")
    cursor.execute("SELECT oracle_id, card_name FROM ref_cards")
    db_cards = cursor.fetchall()

    print(f"Found {len(db_cards)} cards. Starting image downloads...")
    print("Respecting Scryfall's 10 req/sec limit. Grab a coffee! ☕\n")

    update_sql = "UPDATE ref_cards SET image_data = %s WHERE oracle_id = %s"
    count = 0

    # 4. Overwrite your database art with the canonical art
    for oracle_id, card_name in db_cards:
        canonical_url = canonical_urls.get(oracle_id)
        
        if canonical_url:
            for attempt in range(3):
                try:
                    # Pass the headers to the image download as well
                    img_response = requests.get(canonical_url, headers=headers, timeout=10)
                    if img_response.status_code == 200:
                        cursor.execute(update_sql, (img_response.content, oracle_id))
                        db.commit()
                        count += 1
                        
                        if count % 100 == 0:
                            print(f"Fixed {count} cards...")
                        break # Success, break out of retry loop
                    else:
                        time.sleep(1)
                except Exception as e:
                    if attempt == 2:
                        print(f"Failed to fetch art for {card_name}: {e}")
                    time.sleep(1)
            
            # Scryfall strictly enforces a rate limit of 10 requests per second (100ms between calls)
            time.sleep(0.1) 

    print(f"\n✅ Finished! Replaced art for {count} cards with canonical Scryfall printings.")
    cursor.close()
    db.close()

if __name__ == "__main__":
    fix_card_art()
