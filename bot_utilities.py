import requests

def notify_me(message: str, severity: int = 3) -> None:
    WEBHOOK_URL = ""

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