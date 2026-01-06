import requests
import os
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

NOTIF_TEXT = """
🚨 *Chatbot Alert:* `{namespace}`
*Reason:* {reason}

*Conversation History:*
```
{conv_history}
```

*Question:*
{question}

*Given Answer:*
{answer}
"""

def create_alert(name_space, question, response, conv_history):
    send_telegram_message( NOTIF_TEXT.format(
        namespace=name_space,
        reason=response.reason,
        conv_history=conv_history,
        question=question,
        answer=response.answer,
    ) )


def send_telegram_message(text):
    """
    Send a message via Telegram Bot API.
    
    Args:
        text (str): The message text to send
    
    Returns:
        dict: Response from Telegram API
    """
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    
    payload = {
        "chat_id": CHAT_ID,
        "text": text,
        "parse_mode": "Markdown"  # Optional: supports Markdown formatting
    }
    
    try:
        response = requests.post(url, json=payload)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Error sending message: {e}")
        return None