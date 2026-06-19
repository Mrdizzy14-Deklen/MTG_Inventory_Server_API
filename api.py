from dotenv import load_dotenv
load_dotenv()  # Load environment variables from .env file

from datetime import datetime, timedelta, UTC
import os
import secrets
from typing import List, Optional

from fastapi import FastAPI, HTTPException, Request, Security, Depends, BackgroundTasks, APIRouter
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.security import OAuth2PasswordBearer
from fastapi.security.api_key import APIKeyHeader
from fastapi.staticfiles import StaticFiles
import httpx
from jose import jwt
import mysql.connector
from mysql.connector import pooling
from passlib.context import CryptContext
from pydantic import BaseModel, Field
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from bot_utilities import print_notify

# --- Configure App ---

API_KEY = os.getenv("API_KEY")
api_key_header = APIKeyHeader(name="X-API-KEY")

SECRET_KEY = os.getenv("JWT_SECRET_KEY")
ALGORITHM = "HS256"

app = FastAPI()

# Mount static files and configure CORS
app.mount("/images", StaticFiles(directory="images"), name="images")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://mtg.deklenn.dev"], # Frontend origin
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Add limiter to prevent registration spam
limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Dependency to verify API key for router calls
def verify_api_key(key: str = Security(api_key_header)):

    if key != API_KEY:
        raise HTTPException(status_code=403, detail="Invalid API Key")
    return key

# Define a router for protected routes
api_router = APIRouter(dependencies=[Depends(verify_api_key)])

# --- DB Setup ---

db_pool = pooling.MySQLConnectionPool(
    pool_name="mtg_pool",
    pool_size=5,
    host="localhost",
    user="root",
    password="",
    database="mtg_inventory"
)

def get_db():
    return db_pool.get_connection()

# --- Security ---

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="login")

# Hashes a password to store to db
def hash_password(password: str):
    return pwd_context.hash(password)

# Cross check password against stored hash
def verify_password(plain_password: str, hashed_password: str):
    return pwd_context.verify(plain_password, hashed_password)

# Creates a JWT access token for saved login sessions
def create_JWT(data: dict):

    to_encode = data.copy()
    expire = datetime.now(UTC) + timedelta(hours=2) # Tokens valid for 2 hours
    to_encode.update({"exp": expire})

    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

# Get user from JWT token
def JWT_get_user(token: str = Depends(oauth2_scheme)):

    try:

        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id: int = payload.get("user_id")

        if user_id is None:
            raise HTTPException(status_code=401, detail="Invalid token")
        
        return user_id
    
    except:
        raise HTTPException(status_code=401, detail="Could not validate credentials")

# Gets a user by username
def username_get_user(username: str):

    db = get_db()
    cursor = db.cursor(dictionary=True)

    cursor.execute(
        """
        SELECT * 
        FROM users 
        WHERE username = %s
        """, 
        (username,)
    )
    user = cursor.fetchone()

    cursor.close()
    db.close()

    return user

# Sends a verification DM via discord
async def trigger_discord_bot(discord_handle: str, token: str, username: str):

    try:
        async with httpx.AsyncClient() as client:

            response = await client.post(
                "http://localhost:8001/send_verify_dm", 
                json={"discord_handle": discord_handle, "token": token},
                timeout=5.0
            )
            
            data = response.json()
            print_notify(f"Discord verification DM sent to {discord_handle} for user {username}.", severity=3)

            db = get_db()
            with db.cursor() as cursor:

                if data.get("status") == "success":

                    discord_id = data.get("discord_id")

                    cursor.execute(
                        """
                        UPDATE pending_users 
                        SET discord_id = %s 
                        WHERE verify_token = %s
                        """,
                        (discord_id, token)
                    )

                else:

                    cursor.execute(
                        """
                        DELETE FROM pending_users 
                        WHERE verify_token = %s
                        """, 
                        (token,)
                    )
                    print_notify(f"Failed to DM {discord_handle} for user {username}. Pending user deleted.", severity=1)
                
                db.commit()
            db.close()
                
    except Exception as e:
        print_notify(f"Failed to communicate with Discord bot: {e}", severity=1)
        raise HTTPException(status_code=500, detail="Failed to communicate with Discord bot.")

# --- Account Routes ---

class UserCreateRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=20, pattern="^[a-zA-Z0-9_]+$")
    password: str = Field(..., min_length=8, max_length=100)
    discord: str = Field(..., max_length=32)

class UserLoginRequest(BaseModel):
    username: str
    password: str

# Register a user account
@app.post("/register_user")
@limiter.limit("5/hour") # Limit to 5 requests per hour
def register_user(user: UserCreateRequest, request: Request, background_tasks: BackgroundTasks):
    
    if user.username.strip().lower() in ["admin", "root", "system", "api"]:
        raise HTTPException(status_code=400, detail="Invalid username.")

    if username_get_user(user.username):
        raise HTTPException(status_code=409, detail="Username already taken.")

    # Hash the password before it touches the database
    hashed_pass = hash_password(user.password)
    verify_token = secrets.token_hex(8)
    
    db = get_db()
    with db.cursor(dictionary=True) as cursor:
        try:

            cursor.execute(
                """
                INSERT INTO pending_users (verify_token, username, password_hash, discord_handle) 
                VALUES (%s, %s, %s, %s)
                """, 
                (verify_token, user.username, hashed_pass, user.discord)
            )

            db.commit()

            # Send discord verification DM in the background
            background_tasks.add_task(trigger_discord_bot, user.discord, verify_token, user.username)

            return {
                "status": "success", 
                "message": "Account pending, please check Discord for your verification link."
            }
        
        except mysql.connector.Error as e:

            print(f"Register error: {e}")

            if e.errno == 1062: # Duplicate entry error
                raise HTTPException(status_code=409, detail="Username already taken.")
            
            raise HTTPException(status_code=500, detail="Database error.")
        
        finally:
            db.close()

# Verify a new account
@app.get("/verify", response_class=HTMLResponse)
def verify(token: str):

    db = get_db()
    with db.cursor(dictionary=True) as cursor:
        try:

            cursor.execute(
                """
                SELECT * 
                FROM pending_users 
                WHERE verify_token = %s
                """, 
                (token,)
            )
            pending_user = cursor.fetchone()

            if not pending_user:
                return """
                <html><body style="background-color: #09090b; color: white; text-align: center; padding-top: 50px;">
                    <h2>Verification Failed</h2>
                    <p>Invalid or expired verification link.</p>
                </body></html>
                """

            cursor.execute(
                """
                INSERT INTO users (username, password_hash, discord_handle, discord_id, is_active)
                VALUES (%s, %s, %s, %s, 1)
                """, 
                (
                pending_user['username'], 
                pending_user['password_hash'], 
                pending_user['discord_handle'], 
                pending_user['discord_id']
            ))

            cursor.execute(
                """
                DELETE FROM pending_users 
                WHERE verify_token = %s
                """,
                (token,)
            )

            db.commit()
            
            print_notify(f"User verified: {pending_user['username']}", severity=0)
            
            return f"""
            <html>
                <head>
                    <meta http-equiv="refresh" content="3;url=https://mtg.deklenn.dev" />
                </head>
                <body style="background-color: #09090b; color: white; font-family: sans-serif; text-align: center; padding-top: 50px;">
                    <h2>Account Verified!</h2>
                    <p>Welcome to MTG Inventory, {pending_user['username']}. Redirecting you to login...</p>
                </body>
            </html>
            """

        except mysql.connector.Error as e:

            db.rollback()

            print(f"Verification error: {e}")

            if e.errno == 1062:
                return "<html><body style='color: white; background: #09090b'><h2>Error</h2><p>This username was taken while you were pending.</p></body></html>"
            
            return "<html><body style='color: white; background: #09090b'><h2>Error</h2><p>Database error during verification.</p></body></html>"
        
        finally:
            db.close()

# Start a user session
@api_router.post("/login_user")
def login_user(request: UserLoginRequest):

    user = username_get_user(request.username)

    if not user:
        raise HTTPException(status_code=404, detail="User not found.")

    if not user.get('is_active'):
        raise HTTPException(status_code=403, detail="Account is suspended or inactive.")

    if not verify_password(request.password, user['password_hash']):
        raise HTTPException(status_code=401, detail="Invalid password.")
    
    token = create_JWT(data={"user_id": user['id']})

    print_notify(f"User logged in: {request.username}")

    return {"access_token": token, "token_type": "bearer", "user_id": user['id']}

# --- Inventory Routes ---

class CardRequest(BaseModel):
    name: str
    quantity: int = 1

class BulkCardRequest(BaseModel):
    cards: List[CardRequest]

# Fetch a user's entire inventory
@api_router.get("/get_inventory")
def get_inventory(user_id: int = Depends(JWT_get_user)):

    db = get_db()
    with db.cursor(dictionary=True) as cursor:
        try:

            cursor.execute(
                """
                SELECT r.oracle_id, r.card_name, i.quantity 
                FROM inventory i
                JOIN ref_cards r ON i.oracle_id = r.oracle_id
                WHERE i.user_id = %s
                """, 
                (user_id,)
            )
            items = cursor.fetchall()

            return {"status": "success", "inventory": items}
        
        except Exception as e:
            print(f"Inventory fetch failed: {e}")
            raise HTTPException(status_code=500, detail="Database query failed.")
        
        finally:
            db.close()

# Add individual cards
@api_router.post("/add_card")
def add_card(request: CardRequest, user_id: int = Depends(JWT_get_user)):

    db = get_db()
    with db.cursor(dictionary=True) as cursor:
        try:

            if request.quantity < 1:
                raise HTTPException(status_code=400, detail="Quantity must be at least 1.")

            # Find card in reference table
            cursor.execute(
                """
                SELECT * 
                FROM ref_cards 
                WHERE card_name = %s 
                LIMIT 1
                """, 
                (request.name,)
            )
            ref_entry = cursor.fetchone()

            if not ref_entry:
                raise HTTPException(status_code=400, detail=f"Card '{request.name}' not found.")
            
            oracle_id = ref_entry['oracle_id']

            cursor.execute(
                """
                INSERT INTO inventory (
                user_id, 
                oracle_id, 
                quantity
                ) 
                VALUES (%s, %s, %s)
                ON DUPLICATE KEY UPDATE quantity = quantity + VALUES(quantity)
                """, 
                (
                user_id,
                oracle_id,
                request.quantity
            ))

            db.commit()

            print_notify(f"User {user_id} added {request.quantity}x '{request.name}' to inventory.")

            return {
                "status": "success",
                "message": f"Added {request.quantity}x '{request.name}' to inventory for user {user_id}."
            }
        
        except Exception as e:

            db.rollback()

            print(f"Add card failed: {e}")

            raise HTTPException(status_code=500, detail="Database update failed.")
        
        finally:
            db.close()

# Remove individual cards
@api_router.post("/remove_card")
def remove_card(request: CardRequest, user_id: int = Depends(JWT_get_user)):

    db = get_db()
    with db.cursor(dictionary=True) as cursor:
        try:

            # Get current quantity
            cursor.execute(
                """
                SELECT i.oracle_id, i.quantity 
                FROM inventory i
                JOIN ref_cards r ON i.oracle_id = r.oracle_id
                WHERE r.card_name = %s AND i.user_id = %s
                """, 
                (request.name, user_id)
            )
            item = cursor.fetchone()

            if not item:
                raise HTTPException(status_code=404, detail="Card not found in your inventory.")

            current_qty = item['quantity']
            oracle_id = item['oracle_id']

            # Check if need to remove row
            if current_qty <= request.quantity:

                cursor.execute(
                    """
                    DELETE FROM inventory 
                    WHERE user_id = %s AND oracle_id = %s
                    """,
                    (user_id, oracle_id)
                )

                message = f"Removed all copies of '{request.name}' from inventory."
                print_notify(f"User {user_id} removed all copies of '{request.name}' from inventory.")

            else:
                cursor.execute(
                    "UPDATE inventory SET quantity = quantity - %s WHERE user_id = %s AND oracle_id = %s",
                    (request.quantity, user_id, oracle_id)
                )

                message = f"Removed {request.quantity}x '{request.name}'. New total: {current_qty - request.quantity}."
                print_notify(f"User {user_id} removed {request.quantity}x '{request.name}' from inventory. New total: {current_qty - request.quantity}.")

            db.commit()

            return {"status": "success", "message": message}

        except Exception as e:

            db.rollback()

            print(f"Remove card failed: {e}")

            raise HTTPException(status_code=500, detail="Database update failed.")
        
        finally:
            db.close()

# Add bulk cards
@api_router.post("/add_bulk")
def add_bulk(request: BulkCardRequest, user_id: int = Depends(JWT_get_user)):

    db = get_db()
    with db.cursor(dictionary=True) as cursor:
        try:

            card_quantities = {}
            for card in request.cards:
                card_quantities[card.name] = card_quantities.get(card.name, 0) + card.quantity
            
            card_names = list(card_quantities.keys())

            if not card_names:
                return {"status": "success", "message": "No cards provided."}

            placeholders = ', '.join(['%s'] * len(card_names))
            
            cursor.execute(
                f"""
                SELECT card_name, oracle_id 
                FROM ref_cards 
                WHERE card_name IN ({placeholders})
                """, 
                tuple(card_names))
            ref_map = {row['card_name']: row['oracle_id'] for row in cursor.fetchall()}

            missing_cards = [name for name in card_names if name not in ref_map]

            if missing_cards:
                raise HTTPException(
                    status_code=404, 
                    detail=f"Import aborted. Cards not found in database: {', '.join(missing_cards)}"
                )

            insert_data = []
            total_cards_added = 0
            
            for name, qty in card_quantities.items():

                if name in ref_map:

                    insert_data.append((user_id, ref_map[name], qty))
                    total_cards_added += qty

            if not insert_data:
                 return {"status": "success", "message": "No valid cards found to add."}
            
            cursor.executemany(
                """
                INSERT INTO inventory (user_id, oracle_id, quantity) 
                VALUES (%s, %s, %s)
                ON DUPLICATE KEY UPDATE quantity = quantity + VALUES(quantity)
                """, 
                insert_data
            )

            db.commit()

            print_notify(f"User {user_id} added {total_cards_added} cards in bulk.")

            return {"status": "success", "message": f"Added {total_cards_added} cards."}
        
        except Exception as e:

            db.rollback()

            print(f"Bulk add failed: {e}")

            raise HTTPException(status_code=500, detail="Database update failed.")
        
        finally:
            db.close()

# Remove bulk cards
@api_router.post("/remove_bulk")
def remove_bulk(request: BulkCardRequest, user_id: int = Depends(JWT_get_user)):

    requested_cards = {}
    for card in request.cards:
        requested_cards[card.name] = requested_cards.get(card.name, 0) + card.quantity
    
    card_names = list(requested_cards.keys())
        
    if not card_names:
        return {"status": "success", "message": "No cards provided."}
    
    db = get_db()
    with db.cursor(dictionary=True) as cursor:
        try:

            placeholders = ', '.join(['%s'] * len(card_names))
            
            params = [user_id] + card_names
            cursor.execute(
                f"""
                SELECT r.card_name, i.oracle_id, i.quantity 
                FROM inventory i
                JOIN ref_cards r ON i.oracle_id = r.oracle_id
                WHERE i.user_id = %s AND r.card_name IN ({placeholders})
                """, 
                tuple(params)
            )
            current_inventory = cursor.fetchall()

            to_delete = []
            to_update = []
            removed_count = 0

            for item in current_inventory:

                name = item['card_name']
                requested_qty = requested_cards[name]
                current_qty = item['quantity']
                oracle_id = item['oracle_id']

                if current_qty <= requested_qty:
                    to_delete.append((user_id, oracle_id))
                    removed_count += current_qty
                else:
                    to_update.append((requested_qty, user_id, oracle_id))
                    removed_count += requested_qty
                
            if to_delete:
                cursor.executemany(
                    """
                    DELETE FROM inventory 
                    WHERE user_id = %s AND oracle_id = %s
                    """, 
                    to_delete
                )
            
            if to_update:
                cursor.executemany(
                    """
                    UPDATE inventory 
                    SET quantity = quantity - %s 
                    WHERE user_id = %s AND oracle_id = %s
                    """, 
                    to_update
                )

            db.commit()
            
            print_notify(f"User {user_id} removed {removed_count} cards in bulk.")

            return {"status": "success", "message": f"Removed {removed_count} cards."}
        except Exception as e:

            db.rollback()

            print(f"Bulk remove error: {e}")

            raise HTTPException(status_code=500, detail="Database update failed.")
        
        finally:
            db.close()

# --- Trade Routes ---

class MoveCardRequest(BaseModel):
    name: str
    to_username: str
    quantity: int = 1

class MoveBulkCardRequest(BaseModel):
    to_username: str
    cards: List[CardRequest]

class TradePreferenceRequest(BaseModel):
    oracle_id: str = None   # Specific card
    tag: str = None         # Title for preference
    status: str             # 'for_trade', 'looking_for', 'not_for_trade'
    notes: str = ""

# Move a card between users
@api_router.post("/move_card")
def move_card(request: MoveCardRequest, user_id: int = Depends(JWT_get_user)):

    db = get_db()
    with db.cursor(dictionary=True) as cursor:
        try:

            # Get current quantity for from_user
            cursor.execute(
                """
                SELECT i.oracle_id, i.quantity 
                FROM inventory i
                JOIN ref_cards r ON i.oracle_id = r.oracle_id
                WHERE r.card_name = %s AND i.user_id = %s
                """, 
                (request.name, user_id)
            )
            item_from = cursor.fetchone()

            if not item_from or item_from['quantity'] < request.quantity:
                raise HTTPException(status_code=400, detail="Not enough cards.")

            oracle_id = item_from['oracle_id']

            # Decrement from_user
            cursor.execute(
                """
                UPDATE inventory 
                SET quantity = quantity - %s 
                WHERE user_id = %s AND oracle_id = %s
                """,
                (request.quantity, user_id, oracle_id)
            )

            # Increment to_user
            cursor.execute(
                """
                INSERT INTO inventory (user_id, oracle_id, quantity) 
                VALUES (%s, %s, %s)
                ON DUPLICATE KEY UPDATE quantity = quantity + VALUES(quantity)
                """, 
                (username_get_user(request.to_username)['id'], oracle_id, request.quantity)
            )

            db.commit()

            print_notify(f"Moved {request.quantity}x '{request.name}' from {user_id} to {request.to_username}.")

            return {"status": "success", "message": f"Moved {request.quantity}x '{request.name}' to {request.to_username}."}

        except Exception as e:

            db.rollback()

            print(f"Trade failed: {e}")

            raise HTTPException(status_code=500, detail="Database update failed.")
        
        finally:
            db.close()

# Move bulk cards between users
@api_router.post("/move_bulk")
def move_bulk(request: MoveBulkCardRequest, user_id: int = Depends(JWT_get_user)):

    to_user = username_get_user(request.to_username)
    if not to_user:
        raise HTTPException(status_code=400, detail="Recipient not found.")
    to_user_id = to_user['id']

    requested_cards = {}
    for card in request.cards:
        requested_cards[card.name] = requested_cards.get(card.name, 0) + card.quantity
    
    card_names = list(requested_cards.keys())
    
    if not card_names:
        return {"status": "success", "message": "No cards provided."}

    db = get_db()
    with db.cursor(dictionary=True) as cursor:
        try:

            placeholders = ', '.join(['%s'] * len(card_names))
            
            params = [user_id] + card_names
            cursor.execute(
                f"""
                SELECT r.card_name, i.oracle_id, i.quantity 
                FROM inventory i
                JOIN ref_cards r ON i.oracle_id = r.oracle_id
                WHERE i.user_id = %s AND r.card_name IN ({placeholders})
                """, 
                tuple(params)
            )
            current_inventory = cursor.fetchall()

            to_decrement = []
            to_increment = []
            moved_count = 0

            for item in current_inventory:
                name = item['card_name']
                requested_qty = requested_cards[name]
                available_qty = item['quantity']
                oracle_id = item['oracle_id']

                # Check if sender has enough cards
                if available_qty >= requested_qty:
                    to_decrement.append((requested_qty, user_id, oracle_id))
                    to_increment.append((to_user_id, oracle_id, requested_qty))
                    moved_count += requested_qty

            if not to_decrement:
                return {"status": "success", "message": "No cards moved (insufficient quantities)."}

            # Decrement sender
            cursor.executemany(
                """
                UPDATE inventory 
                SET quantity = quantity - %s 
                WHERE user_id = %s AND oracle_id = %s
                """,
                to_decrement
            )

            # Increment recipient
            cursor.executemany(
                """
                INSERT INTO inventory (user_id, oracle_id, quantity) 
                VALUES (%s, %s, %s)
                ON DUPLICATE KEY UPDATE quantity = quantity + VALUES(quantity)
                """, 
                to_increment
            )

            db.commit()

            print_notify(f"Moved {moved_count} cards in bulk from {user_id} to {request.to_username}.")

            return {"status": "success", "message": f"Moved {moved_count} cards."}
        
        except Exception as e:

            db.rollback()

            print(f"Failed bulk move: {e}")

            raise HTTPException(status_code=500, detail="Database update failed.")
        
        finally:
            db.close()

# Fetches all of a user's trade preferences
@api_router.get("/get_preferences")
def get_preferences(user_id: int = Depends(JWT_get_user)):

    db = get_db()
    with db.cursor(dictionary=True) as cursor:
        try:

            cursor.execute(
                """
                SELECT oracle_id, tag, trade_status as status, notes 
                FROM trade_preferences 
                WHERE user_id = %s
                """, 
                (user_id,)
            )
            preferences = cursor.fetchall()

            return {"status": "success", "preferences": preferences}
        
        except Exception as e:

            print(f"Fetch preferences failed: {e}")

            raise HTTPException(status_code=500, detail="Failed to fetch preferences.")
        
        finally:
            db.close()

# Sets a user's trade preference
@api_router.post("/set_preference")
def set_preference(request: TradePreferenceRequest, user_id: int = Depends(JWT_get_user)):

    db = get_db()
    with db.cursor() as cursor:
        try:

            cursor.execute(
                """
                INSERT INTO trade_preferences (user_id, oracle_id, tag, trade_status, notes)
                VALUES (%s, %s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE oracle_id = VALUES(oracle_id), tag = VALUES(tag), trade_status = VALUES(trade_status), notes = VALUES(notes)
                """, 
                (user_id, request.oracle_id, request.tag, request.status, request.notes)
            )

            db.commit()

            return {"status": "success", "message": "Trade preference updated."}
        
        except Exception as e:

            db.rollback()

            print(f"Preference update failed: {e}")

            raise HTTPException(status_code=500, detail="Database update failed.")
        
        finally:
            db.close()

# Removes a user's trade preference
@api_router.post("/remove_preference")
def remove_preference(request: TradePreferenceRequest, user_id: int = Depends(JWT_get_user)):

    db = get_db()
    with db.cursor() as cursor:
        try:

            cursor.execute(
                """
                DELETE FROM trade_preferences 
                WHERE user_id = %s AND (oracle_id <=> %s) AND (tag <=> %s)
                """, 
                (user_id, request.oracle_id, request.tag)
            )
            
            db.commit()
            
            return {"status": "success", "message": "Trade preference removed."}
        
        except Exception as e:

            db.rollback()

            print(f"Remove preference failed: {e}")

            raise HTTPException(status_code=500, detail="Database update failed.")
        
        finally:
            db.close()

# --- Card Search Route ---

class CardSearchRequest(BaseModel):
    card_name: Optional[str] = None
    text_box: Optional[str] = None
    type_line: Optional[str] = None
    w: Optional[bool] = None
    u: Optional[bool] = None
    b: Optional[bool] = None
    r: Optional[bool] = None
    g: Optional[bool] = None
    commander_identity: Optional[List[str]] = None
    mana_cost: Optional[int] = None
    power: Optional[str] = None
    toughness: Optional[str] = None
    rarity: Optional[str] = None
    owned: Optional[bool] = False

# Search's the db with given params
@api_router.post("/search_cards")
def search_cards(request: CardSearchRequest, user_id: int = Depends(JWT_get_user)):

    db = get_db()
    with db.cursor(dictionary=True) as cursor:
        try:
            
            query = """
                SELECT 
                    r.oracle_id, r.card_name, r.type_line, r.mana_cost, 
                    r.rarity, r.text_box, r.power, r.toughness, 
                    r.w, r.u, r.b, r.r, r.g, 
                    COALESCE(i.quantity, 0) as quantity 
                FROM ref_cards r
                LEFT JOIN inventory i ON r.oracle_id = i.oracle_id AND i.user_id = %s
                WHERE 1=1
                """
            
            params = [user_id]

            # Check if owned
            if request.owned:
                query += " AND i.quantity > 0"

            # Fuzzy search params

            if request.card_name:

                tokens = request.card_name.split()

                for token in tokens:
                    query += " AND r.card_name LIKE %s"
                    params.append(f"%{token}%")
            
            if request.type_line:

                tokens = request.type_line.split()

                for token in tokens:
                    query += " AND r.type_line LIKE %s"
                    params.append(f"%{token}%")

            if request.text_box:

                tokens = request.text_box.split()

                for token in tokens:
                    query += " AND r.text_box LIKE %s"
                    params.append(f"%{token}%")

            # Exact search params

            if request.mana_cost is not None:
                query += " AND r.mana_cost = %s"
                params.append(request.mana_cost)

            if request.rarity:
                query += " AND r.rarity = %s"
                params.append(request.rarity)

            if request.power:
                query += " AND r.power = %s"
                params.append(request.power)

            if request.toughness:
                query += " AND r.toughness = %s"
                params.append(request.toughness)

            # Color identity

            if request.w is not None:
                query += " AND r.w = %s"
                params.append(request.w)

            if request.u is not None:
                query += " AND r.u = %s"
                params.append(request.u)

            if request.b is not None:
                query += " AND r.b = %s"
                params.append(request.b)

            if request.r is not None:
                query += " AND r.r = %s"
                params.append(request.r)

            if request.g is not None:
                query += " AND r.g = %s"
                params.append(request.g)

            if request.commander_identity is not None:

                allowed_colors = set([c.upper() for c in request.commander_identity])

                for color in ['W', 'U', 'B', 'R', 'G']:
                    if color not in allowed_colors:
                        query += f" AND r.{color.lower()} = 0"

            cursor.execute(query, tuple(params))
            results = cursor.fetchall()

            return {"status": "success", "cards": results}

        except Exception as e:

            print(f"Search failed: {e}")

            raise HTTPException(status_code=500, detail=f"Database query failed.")
        
        finally:
            db.close()

# Attach protected routes
app.include_router(api_router)

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
