from dotenv import load_dotenv
load_dotenv()  # Load environment variables from .env file
import os
from fastapi import FastAPI, HTTPException, Security, Depends
from fastapi.security.api_key import APIKeyHeader
import mysql.connector
from pydantic import BaseModel
from typing import List


# Load the API key from env var
API_KEY = os.getenv("API_KEY")
api_key_header = APIKeyHeader(name="X-API-KEY")

# Dependency to verify API key
def verify_api_key(key: str = Security(api_key_header)):
    if key != API_KEY:
        raise HTTPException(status_code=403, detail="Invalid API Key")
    return key

app = FastAPI(dependencies=[Depends(verify_api_key)])

def get_db():
    return mysql.connector.connect(
        host="localhost",
        user="root",
        password="",
        database="mtg_inventory"
    )

# Import individual cards
@app.post("/import/card")
def add_card(text: str, user_id: int, quantity: int = 1):
    db = get_db()
    with db.cursor(dictionary=True) as cursor:
        try:
            # Find card in reference table
            query_ref = "SELECT * FROM ref_cards WHERE card_name = %s LIMIT 1"
            cursor.execute(query_ref, (text,))
            ref_entry = cursor.fetchone()

            if not ref_entry:
                # Card not found
                raise HTTPException(status_code=404, detail=f"Card '{text}' not found.")
            
            oracle_id = ref_entry['oracle_id']

            sql = """
                INSERT INTO inventory (
                user_id, 
                oracle_id, 
                quantity
                ) 
                VALUES (%s, %s, %s)
                ON DUPLICATE KEY UPDATE quantity = quantity + VALUES(quantity)
            """

            cursor.execute(sql, (
                user_id,
                oracle_id,
                quantity
            ))

            db.commit()

            return {
                "status": "success",
                "message": f"Added {quantity}x '{text}' to inventory for user {user_id}."
            }
        
        except Exception as e:
            db.rollback()
            raise HTTPException(status_code=500, detail="Database update failed.")
        finally:
            db.close()

# Move a card between users
@app.post("/move/card")
def move_card(text: str, from_user_id: int, to_user_id: int, quantity: int = 1):
    db = get_db()
    with db.cursor(dictionary=True) as cursor:
        try:
            # Get current quantity for from_user
            query_from = """
                SELECT i.oracle_id, i.quantity 
                FROM inventory i
                JOIN ref_cards r ON i.oracle_id = r.oracle_id
                WHERE r.card_name = %s AND i.user_id = %s
            """
            cursor.execute(query_from, (text, from_user_id))
            item_from = cursor.fetchone()

            if not item_from or item_from['quantity'] < quantity:
                raise HTTPException(status_code=400, detail="Not enough cards.")

            oracle_id = item_from['oracle_id']

            # Decrement from_user
            cursor.execute(
                "UPDATE inventory SET quantity = quantity - %s WHERE user_id = %s AND oracle_id = %s",
                (quantity, from_user_id, oracle_id)
            )

            # Increment to_user
            sql_to = """
                INSERT INTO inventory (user_id, oracle_id, quantity) 
                VALUES (%s, %s, %s)
                ON DUPLICATE KEY UPDATE quantity = quantity + VALUES(quantity)
            """
            cursor.execute(sql_to, (to_user_id, oracle_id, quantity))

            db.commit()
            return {"status": "success", "message": f"Moved {quantity}x '{text}' from {from_user_id} to {to_user_id}."}

        except Exception as e:
            db.rollback()
            raise HTTPException(status_code=500, detail="Database update failed.")
        finally:
            db.close()

# Remove individual cards
@app.post("/remove/card")
def remove_card(text: str, user_id: int, quantity: int = 1):
    db = get_db()
    cursor = db.cursor(dictionary=True)

    try:
        # Get current quantity
        query = """
            SELECT i.oracle_id, i.quantity 
            FROM inventory i
            JOIN ref_cards r ON i.oracle_id = r.oracle_id
            WHERE r.card_name = %s AND i.user_id = %s
        """
        cursor.execute(query, (text, user_id))
        item = cursor.fetchone()

        if not item:
            raise HTTPException(status_code=404, detail="Card not found in your inventory.")

        current_qty = item['quantity']
        oracle_id = item['oracle_id']

        # Check if need to remove row
        if current_qty <= quantity:
            cursor.execute(
                "DELETE FROM inventory WHERE user_id = %s AND oracle_id = %s",
                (user_id, oracle_id)
            )
            message = f"Removed all copies of '{text}' from inventory."
        else:
            # Decrement
            cursor.execute(
                "UPDATE inventory SET quantity = quantity - %s WHERE user_id = %s AND oracle_id = %s",
                (quantity, user_id, oracle_id)
            )
            message = f"Removed {quantity}x '{text}'. New total: {current_qty - quantity}."

        db.commit()
        return {"status": "success", "message": message}

    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail="Database update failed.")
    finally:
        cursor.close()
        db.close()

class CardRequest(BaseModel):
    name: str
    quantity: int = 1

class BulkCardRequest(BaseModel):
    user_id: int
    cards: List[CardRequest]

# Import bulk cards
@app.post("/import/bulk")
def add_bulk(request: BulkCardRequest):
    db = get_db()
    with db.cursor(dictionary=True) as cursor:
        count = 0

        try:
            for card in request.cards:
                # Find the oracle_id
                cursor.execute("SELECT oracle_id FROM ref_cards WHERE card_name = %s LIMIT 1", (card.name,))
                ref = cursor.fetchone()
                
                if ref:
                    sql = """
                        INSERT INTO inventory (user_id, oracle_id, quantity) 
                        VALUES (%s, %s, %s)
                        ON DUPLICATE KEY UPDATE quantity = quantity + VALUES(quantity)
                    """
                    cursor.execute(sql, (request.user_id, ref['oracle_id'], card.quantity))
                    count += 1
            
            db.commit()
            return {"status": "success", "message": f"Added {count} cards."}
        except Exception as e:
            db.rollback()
            raise HTTPException(status_code=500, detail="Database update failed.")
        finally:
            db.close()

# Move bulk cards between users
@app.post("/move/bulk")
def move_bulk(request: BulkCardRequest, to_user_id: int):
    db = get_db()
    with db.cursor(dictionary=True) as cursor:
        count = 0
        try:
            for card in request.cards:
                # Get current quantity for from_user
                query_from = """
                    SELECT i.oracle_id, i.quantity 
                    FROM inventory i
                    JOIN ref_cards r ON i.oracle_id = r.oracle_id
                    WHERE r.card_name = %s AND i.user_id = %s
                """
                cursor.execute(query_from, (card.name, request.user_id))
                item_from = cursor.fetchone()

                if item_from and item_from['quantity'] >= card.quantity:
                    oracle_id = item_from['oracle_id']

                    # Decrement from_user
                    cursor.execute(
                        "UPDATE inventory SET quantity = quantity - %s WHERE user_id = %s AND oracle_id = %s",
                        (card.quantity, request.user_id, oracle_id)
                    )

                    # Increment to_user
                    sql_to = """
                        INSERT INTO inventory (user_id, oracle_id, quantity) 
                        VALUES (%s, %s, %s)
                        ON DUPLICATE KEY UPDATE quantity = quantity + VALUES(quantity)
                    """
                    cursor.execute(sql_to, (to_user_id, oracle_id, card.quantity))
                    count += 1

            db.commit()
            return {"status": "success", "message": f"Moved {count} cards."}
        except Exception as e:
            db.rollback()
            raise HTTPException(status_code=500, detail="Database update failed.")
        finally:
            db.close()

# Remove bulk cards
@app.post("/remove/bulk")
def remove_bulk(request: BulkCardRequest):
    db = get_db()
    cursor = db.cursor(dictionary=True)
    removed_count = 0

    try:
        for card in request.cards:
            # Get current quantity
            query = """
                SELECT i.oracle_id, i.quantity FROM inventory i
                JOIN ref_cards r ON i.oracle_id = r.oracle_id
                WHERE r.card_name = %s AND i.user_id = %s
            """
            cursor.execute(query, (card.name, request.user_id))
            item = cursor.fetchone()

            if item:
                if item['quantity'] <= card.quantity:
                    cursor.execute("DELETE FROM inventory WHERE user_id = %s AND oracle_id = %s", 
                                   (request.user_id, item['oracle_id']))
                else:
                    cursor.execute("UPDATE inventory SET quantity = quantity - %s WHERE user_id = %s AND oracle_id = %s", 
                                   (card.quantity, request.user_id, item['oracle_id']))
                removed_count += 1

        db.commit()
        return {"status": "success", "message": f"Removed {removed_count} cards."}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail="Database update failed.")
    finally:
        db.close()

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)