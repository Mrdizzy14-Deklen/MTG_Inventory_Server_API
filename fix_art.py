import os
import requests
import time

from bot_utilities import notify_me

IMAGE_DIR = "images/"
os.makedirs(IMAGE_DIR, exist_ok=True)

def fix_card_art():
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

    print("Downloading canonical data map...")
    bulk_data = requests.get(bulk_info['download_uri'], headers=headers).json()

    count = 0
    print(f"Force-overwriting art for all {len(bulk_data)} cards...")
    
    for card in bulk_data:
        oracle_id = card.get('oracle_id')
        if not oracle_id:
            continue

        image_path = os.path.join(IMAGE_DIR, f"{oracle_id}.jpg")

        image_url = card.get('image_uris', {}).get('large')
        if not image_url and 'card_faces' in card:
            image_url = card['card_faces'][0].get('image_uris', {}).get('large')
        
        if image_url:
            for attempt in range(3):
                try:
                    img_response = requests.get(image_url, headers=headers, timeout=10)
                    if img_response.status_code == 200:
                        with open(image_path, 'wb') as f:
                            f.write(img_response.content)
                        
                        count += 1
                        if count % 100 == 0:
                            print(f"Overwritten {count} cards...")
                        break
                except Exception as e:
                    time.sleep(1)
            
            # Enforce Scryfall's 10 requests per second limit
            time.sleep(0.1) 

    print(f"\nDownloaded and overwrote art for {count} cards.")
    notify_me(f"Replaced art for {count} cards", severity=0)

if __name__ == "__main__":
    fix_card_art()