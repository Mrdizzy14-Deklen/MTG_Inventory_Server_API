from dotenv import load_dotenv
load_dotenv()  # Load environment variables from .env file
import os
from fastapi import FastAPI, HTTPException, Request, Security, Depends
from fastapi.security.api_key import APIKeyHeader
import mysql.connector
from pydantic import BaseModel
from typing import List
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from passlib.context import CryptContext

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

def get_user(username: str):
    db = get_db()
    cursor = db.cursor(dictionary=True)
    cursor.execute("SELECT * FROM users WHERE username = %s", (username,))
    user = cursor.fetchone()
    cursor.close()
    db.close()
    return user

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Hashes a password to store
def get_password_hash(password: str):
    return pwd_context.hash(password)

# Check if password valid
def verify_password(plain_password: str, hashed_password: str):
    return pwd_context.verify(plain_password, hashed_password)

limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

class UserCreateRequest(BaseModel):
    username: str
    password: str

# Register a user account
@app.post("/users/register")
@limiter.limit("1/hour")
def register_user(user: UserCreateRequest, request: Request):
    
    # Hash the password before it touches the database
    hashed_pass = get_password_hash(user.password)
    
    db = get_db()
    cursor = db.cursor()
    try:
        sql = "INSERT INTO users (username, password_hash) VALUES (%s, %s)"
        cursor.execute(sql, (user.username, hashed_pass))
        db.commit()
        return {"status": "success", "message": f"User {user.username} created."}
    except mysql.connector.Error as err:
        if err.errno == 1062: # Duplicate entry error
            raise HTTPException(status_code=400, detail="Username already taken.")
        raise HTTPException(status_code=500, detail="Database error.")
    finally:
        cursor.close()
        db.close()

class UserLoginRequest(BaseModel):
    username: str
    password: str

@app.post("/users/login")
def login_user(request: UserLoginRequest):

    user = get_user(request.username)

    if not user:
        raise HTTPException(status_code=404, detail="User not found.")

    if not verify_password(request.password, user['password_hash']):
        raise HTTPException(status_code=400, detail="Invalid password.")

    return {"status": "success", "message": "Login successful."}

class SingleCardRequest(BaseModel):
    text: str
    user_id: int
    quantity: int = 1

# Import individual cards
@app.post("/import/card")
def add_card(request: SingleCardRequest):
    db = get_db()
    with db.cursor(dictionary=True) as cursor:
        try:
            # Find card in reference table
            query_ref = "SELECT * FROM ref_cards WHERE card_name = %s LIMIT 1"
            cursor.execute(query_ref, (request.text,))
            ref_entry = cursor.fetchone()

            if not ref_entry:
                # Card not found
                raise HTTPException(status_code=404, detail=f"Card '{request.text}' not found.")
            
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
                request.user_id,
                oracle_id,
                request.quantity
            ))

            db.commit()

            return {
                "status": "success",
                "message": f"Added {request.quantity}x '{request.text}' to inventory for user {request.user_id}."
            }
        
        except Exception as e:
            db.rollback()
            raise HTTPException(status_code=500, detail="Database update failed.")
        finally:
            db.close()

class MoveCardRequest(BaseModel):
    text: str
    from_user_id: int
    to_user_id: int
    quantity: int = 1

# Move a card between users
@app.post("/move/card")
def move_card(request: MoveCardRequest):
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
            cursor.execute(query_from, (request.text, request.from_user_id))
            item_from = cursor.fetchone()

            if not item_from or item_from['quantity'] < request.quantity:
                raise HTTPException(status_code=400, detail="Not enough cards.")

            oracle_id = item_from['oracle_id']

            # Decrement from_user
            cursor.execute(
                "UPDATE inventory SET quantity = quantity - %s WHERE user_id = %s AND oracle_id = %s",
                (request.quantity, request.from_user_id, oracle_id)
            )

            # Increment to_user
            sql_to = """
                INSERT INTO inventory (user_id, oracle_id, quantity) 
                VALUES (%s, %s, %s)
                ON DUPLICATE KEY UPDATE quantity = quantity + VALUES(quantity)
            """
            cursor.execute(sql_to, (request.to_user_id, oracle_id, request.quantity))

            db.commit()
            return {"status": "success", "message": f"Moved {request.quantity}x '{request.text}' from {request.from_user_id} to {request.to_user_id}."}

        except Exception as e:
            db.rollback()
            raise HTTPException(status_code=500, detail="Database update failed.")
        finally:
            db.close()

# Remove individual cards
@app.post("/remove/card")
def remove_card(request: SingleCardRequest):
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
        cursor.execute(query, (request.text, request.user_id))
        item = cursor.fetchone()

        if not item:
            raise HTTPException(status_code=404, detail="Card not found in your inventory.")

        current_qty = item['quantity']
        oracle_id = item['oracle_id']

        # Check if need to remove row
        if current_qty <= request.quantity:
            cursor.execute(
                "DELETE FROM inventory WHERE user_id = %s AND oracle_id = %s",
                (request.user_id, oracle_id)
            )
            message = f"Removed all copies of '{request.text}' from inventory."
        else:
            # Decrement
            cursor.execute(
                "UPDATE inventory SET quantity = quantity - %s WHERE user_id = %s AND oracle_id = %s",
                (request.quantity, request.user_id, oracle_id)
            )
            message = f"Removed {request.quantity}x '{request.text}'. New total: {current_qty - request.quantity}."

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

# Honey pot to detect bots
@app.get("/.env")
@app.get("/wp-admin")
def honey_pot(request: Request):
    print(f"SUSPICIOUS ACTIVITY: {request.client.host} tried to access a hidden file.")

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)