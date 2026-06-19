from dotenv import load_dotenv
load_dotenv()

import os
import requests

WEBHOOK_URL = os.getenv("WEBHOOK_URL")

def notify_me(message: str, severity: int = 3) -> None:

    match severity:
        case 0:
            # Good
            message = f"✅ {message}"
        case 1:
            # Bad
            message = f"‼️ {message}"
        case 2:
            # Warning
            message = f"⚠️ {message}"
        case 3:
            # Logs
            message = f"🪵 {message}"
    
    requests.post(WEBHOOK_URL, json={"content": message})

def print_notify(message: str, severity: int = 3) -> None:
    print(message)
    notify_me(message, severity)