from dotenv import load_dotenv
load_dotenv()  # Load environment variables from .env file
import os
from fastapi import FastAPI, HTTPException, Request, Security, Depends
from fastapi.security.api_key import APIKeyHeader
from fastapi.security import OAuth2PasswordBearer
import mysql.connector
from mysql.connector import pooling
from pydantic import BaseModel, Field
from typing import List
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from passlib.context import CryptContext
from jose import jwt
from datetime import datetime, timedelta, UTC

# Load the API key from env var
API_KEY = os.getenv("API_KEY")
api_key_header = APIKeyHeader(name="X-API-KEY")

SECRET_KEY = os.getenv("JWT_SECRET_KEY")
ALGORITHM = "HS256"

# Dependency to verify API key
def verify_api_key(key: str = Security(api_key_header)):
    if key != API_KEY:
        raise HTTPException(status_code=403, detail="Invalid API Key")
    return key

app = FastAPI(dependencies=[Depends(verify_api_key)])

# Create a pool of connections
db_pool = pooling.MySQLConnectionPool(
    pool_name="mtg_pool",
    pool_size=5,
    host="localhost",
    user="root",
    password="",
    database="mtg_inventory"
)

# Gets a database connector
def get_db():
    return db_pool.get_connection()

# Gets a user by username
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

# Creates a JWT access token
def create_access_token(data: dict):
    to_encode = data.copy()
    expire = datetime.now(UTC) + timedelta(hours=2)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="login")

# Get user from JWT token
def get_current_user(token: str = Depends(oauth2_scheme)):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id: int = payload.get("user_id")
        if user_id is None:
            raise HTTPException(status_code=401, detail="Invalid token")
        return user_id
    except:
        raise HTTPException(status_code=401, detail="Could not validate credentials")

# Used to limit API usage to prevent abuse
limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

class UserCreateRequest(BaseModel):
    # Min 3 chars, Max 20, only alphanumeric/underscores
    username: str = Field(..., min_length=3, max_length=20, pattern="^[a-zA-Z0-9_]+$")
    # Enforce a minimum password length for security
    password: str = Field(..., min_length=8, max_length=100)

# Register a user account
@app.post("/users/register")
@limiter.limit("1/hour")
def register_user(user: UserCreateRequest, request: Request):
    
    if user.username.strip().lower() in ["admin", "root", "system", "api"]:
        raise HTTPException(status_code=400, detail="Invalid username.")

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
    
    token = create_access_token(data={"user_id": user['id']})
    return {"access_token": token, "token_type": "bearer", "user_id": user['id']}

class SingleCardRequest(BaseModel):
    text: str
    quantity: int = 1

# Import individual cards
@app.post("/import/card")
def add_card(request: SingleCardRequest, user_id: int = Depends(get_current_user)):
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
                user_id,
                oracle_id,
                request.quantity
            ))

            db.commit()

            return {
                "status": "success",
                "message": f"Added {request.quantity}x '{request.text}' to inventory for user {user_id}."
            }
        
        except Exception as e:
            db.rollback()
            raise HTTPException(status_code=500, detail="Database update failed.")
        finally:
            db.close()

class MoveCardRequest(BaseModel):
    text: str
    to_username: str
    quantity: int = 1

# Move a card between users
@app.post("/move/card")
def move_card(request: MoveCardRequest, user_id: int = Depends(get_current_user)):
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
            cursor.execute(query_from, (request.text, user_id))
            item_from = cursor.fetchone()

            if not item_from or item_from['quantity'] < request.quantity:
                raise HTTPException(status_code=400, detail="Not enough cards.")

            oracle_id = item_from['oracle_id']

            # Decrement from_user
            cursor.execute(
                "UPDATE inventory SET quantity = quantity - %s WHERE user_id = %s AND oracle_id = %s",
                (request.quantity, user_id, oracle_id)
            )

            # Increment to_user
            sql_to = """
                INSERT INTO inventory (user_id, oracle_id, quantity) 
                VALUES (%s, %s, %s)
                ON DUPLICATE KEY UPDATE quantity = quantity + VALUES(quantity)
            """
            cursor.execute(sql_to, (get_user(request.to_username)['id'], oracle_id, request.quantity))

            db.commit()
            return {"status": "success", "message": f"Moved {request.quantity}x '{request.text}' to {request.to_username}."}

        except Exception as e:
            db.rollback()
            raise HTTPException(status_code=500, detail="Database update failed.")
        finally:
            db.close()

# Remove individual cards
@app.post("/remove/card")
def remove_card(request: SingleCardRequest, user_id: int = Depends(get_current_user)):
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
        cursor.execute(query, (request.text, user_id))
        item = cursor.fetchone()

        if not item:
            raise HTTPException(status_code=404, detail="Card not found in your inventory.")

        current_qty = item['quantity']
        oracle_id = item['oracle_id']

        # Check if need to remove row
        if current_qty <= request.quantity:
            cursor.execute(
                "DELETE FROM inventory WHERE user_id = %s AND oracle_id = %s",
                (user_id, oracle_id)
            )
            message = f"Removed all copies of '{request.text}' from inventory."
        else:
            # Decrement
            cursor.execute(
                "UPDATE inventory SET quantity = quantity - %s WHERE user_id = %s AND oracle_id = %s",
                (request.quantity, user_id, oracle_id)
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
    cards: List[CardRequest]

# Import bulk cards
@app.post("/import/bulk")
def add_bulk(request: BulkCardRequest, user_id: int = Depends(get_current_user)):
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
                    cursor.execute(sql, (user_id, ref['oracle_id'], card.quantity))
                    count += 1
            
            db.commit()
            return {"status": "success", "message": f"Added {count} cards."}
        except Exception as e:
            db.rollback()
            raise HTTPException(status_code=500, detail="Database update failed.")
        finally:
            db.close()

class MoveBulkCardRequest(BaseModel):
    to_username: str
    cards: List[CardRequest]

# Move bulk cards between users
@app.post("/move/bulk")
def move_bulk(request: MoveBulkCardRequest, user_id: int = Depends(get_current_user)):
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
                cursor.execute(query_from, (card.name, user_id))
                item_from = cursor.fetchone()

                if item_from and item_from['quantity'] >= card.quantity:
                    oracle_id = item_from['oracle_id']

                    # Decrement from_user
                    cursor.execute(
                        "UPDATE inventory SET quantity = quantity - %s WHERE user_id = %s AND oracle_id = %s",
                        (card.quantity, user_id, oracle_id)
                    )

                    # Increment to_user
                    sql_to = """
                        INSERT INTO inventory (user_id, oracle_id, quantity) 
                        VALUES (%s, %s, %s)
                        ON DUPLICATE KEY UPDATE quantity = quantity + VALUES(quantity)
                    """
                    cursor.execute(sql_to, (get_user(request.to_username)['id'], oracle_id, card.quantity))
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
def remove_bulk(request: BulkCardRequest, user_id: int = Depends(get_current_user)):
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
            cursor.execute(query, (card.name, user_id))
            item = cursor.fetchone()

            if item:
                if item['quantity'] <= card.quantity:
                    cursor.execute("DELETE FROM inventory WHERE user_id = %s AND oracle_id = %s", 
                                   (user_id, item['oracle_id']))
                else:
                    cursor.execute("UPDATE inventory SET quantity = quantity - %s WHERE user_id = %s AND oracle_id = %s", 
                                   (card.quantity, user_id, item['oracle_id']))
                removed_count += 1

        db.commit()
        return {"status": "success", "message": f"Removed {removed_count} cards."}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail="Database update failed.")
    finally:
        db.close()

@app.get("/inventory/user")
def view_inventory(user_id: int = Depends(get_current_user)):
    db = get_db()
    cursor = db.cursor(dictionary=True)

    try:
        query = """
            SELECT r.card_name, i.quantity 
            FROM inventory i
            JOIN ref_cards r ON i.oracle_id = r.oracle_id
            WHERE i.user_id = %s
        """
        cursor.execute(query, (user_id,))
        items = cursor.fetchall()
        return {"status": "success", "inventory": items}
    except Exception as e:
        raise HTTPException(status_code=500, detail="Database query failed.")
    finally:
        cursor.close()
        db.close()

# Honey pot to detect bots
@app.get("/.env")
@app.get("/wp-admin")
def honey_pot(request: Request):
    print(f"SUSPICIOUS ACTIVITY: {request.client.host} tried to access a hidden file.")

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)