"""
Gemini AI Telegram Chatbot - Render.com Version
- Webhook mode for Render.com free tier
- Flask web server for health check + webhook
"""

import os
import logging
import asyncio
from threading import Thread
from flask import Flask, request, jsonify
import google.generativeai as genai
import requests as http_requests

# ============================================
# CONFIGURATION
# ============================================
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
RENDER_EXTERNAL_URL = os.getenv("RENDER_EXTERNAL_URL", "")
PORT = int(os.getenv("PORT", "10000"))

# Gemini Model
MODEL_NAME = "gemini-2.0-flash"

# ============================================
# SETUP
# ============================================
logging.basicConfig(
    format='%(asctime)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Validate config
if not TELEGRAM_BOT_TOKEN:
    logger.error("TELEGRAM_BOT_TOKEN not set!")
    exit(1)
if not GEMINI_API_KEY:
    logger.error("GEMINI_API_KEY not set!")
    exit(1)

# Gemini setup
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel(MODEL_NAME)

# Chat history storage (per user)
chat_sessions = {}

# Telegram API base URL
TG_API = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"

# ============================================
# TELEGRAM HELPER FUNCTIONS
# ============================================
def send_message(chat_id, text):
    """Send message via Telegram API"""
    url = f"{TG_API}/sendMessage"
    # Split long messages
    if len(text) > 4096:
        chunks = [text[i:i+4096] for i in range(0, len(text), 4096)]
        for chunk in chunks:
            http_requests.post(url, json={"chat_id": chat_id, "text": chunk})
    else:
        http_requests.post(url, json={"chat_id": chat_id, "text": text})

def send_typing(chat_id):
    """Send typing action"""
    url = f"{TG_API}/sendChatAction"
    http_requests.post(url, json={"chat_id": chat_id, "action": "typing"})

# ============================================
# MESSAGE PROCESSING
# ============================================
def process_message(chat_id, user_id, user_message, first_name):
    """Process incoming message with Gemini"""
    
    # Handle commands
    if user_message == "/start":
        reply = (
            f"မင်္ဂလာပါ {first_name}! 👋\n\n"
            f"ကျွန်တော်က Gemini AI Chatbot ပါ။\n"
            f"ဘာမဆို မေးနိုင်ပါတယ်။\n\n"
            f"/start - Bot စဖွင့်ရန်\n"
            f"/new - Chat အသစ်စရန်\n"
            f"/help - အကူအညီ"
        )
        send_message(chat_id, reply)
        return
    
    if user_message == "/new":
        if user_id in chat_sessions:
            del chat_sessions[user_id]
        send_message(chat_id, "✅ Chat အသစ် စပါပြီ!")
        return
    
    if user_message == "/help":
        reply = (
            "🤖 Gemini AI Chatbot\n\n"
            "📝 စကားပြောရန် - message ရိုက်ပို့ပါ\n"
            "🔄 /new - Chat အသစ်စရန်\n"
            "❓ /help - ဒီ message ပြရန်\n\n"
            "💡 ဘာမဆို မေးနိုင်ပါတယ် - မြန်မာလိုရော English လိုရော!"
        )
        send_message(chat_id, reply)
        return
    
    # Send typing indicator
    send_typing(chat_id)
    
    try:
        # Get or create chat session
        if user_id not in chat_sessions:
            chat_sessions[user_id] = model.start_chat(history=[])
        
        chat = chat_sessions[user_id]
        
        # Send to Gemini
        response = chat.send_message(user_message)
        reply_text = response.text
        
        # Send reply
        send_message(chat_id, reply_text)
        
    except Exception as e:
        logger.error(f"Error: {e}")
        send_message(chat_id, f"❌ Error ဖြစ်သွားပါတယ်:\n{str(e)}\n\n/new နဲ့ chat အသစ်စကြည့်ပါ။")

# ============================================
# FLASK APP
# ============================================
app = Flask(__name__)

@app.route("/")
def home():
    return "Bot is running!", 200

@app.route("/health")
def health():
    return "OK", 200

@app.route("/webhook", methods=["POST"])
def webhook():
    """Handle incoming Telegram updates"""
    try:
        data = request.get_json()
        
        if "message" in data and "text" in data["message"]:
            chat_id = data["message"]["chat"]["id"]
            user_id = data["message"]["from"]["id"]
            first_name = data["message"]["from"].get("first_name", "User")
            text = data["message"]["text"]
            
            # Process in background thread
            thread = Thread(target=process_message, args=(chat_id, user_id, text, first_name))
            thread.start()
        
        return jsonify({"ok": True})
    
    except Exception as e:
        logger.error(f"Webhook error: {e}")
        return jsonify({"ok": False}), 200

# ============================================
# SET WEBHOOK & START
# ============================================
def set_webhook():
    """Set Telegram webhook URL"""
    if RENDER_EXTERNAL_URL:
        webhook_url = f"{RENDER_EXTERNAL_URL}/webhook"
        url = f"{TG_API}/setWebhook"
        resp = http_requests.post(url, json={"url": webhook_url})
        logger.info(f"Webhook set: {resp.json()}")
    else:
        logger.warning("RENDER_EXTERNAL_URL not set - webhook not configured")

if __name__ == "__main__":
    print("🤖 Gemini Telegram Bot starting...")
    print(f"📡 Model: {MODEL_NAME}")
    print(f"🌐 Port: {PORT}")
    
    # Set webhook
    set_webhook()
    
    # Run Flask
    print("✅ Bot is running!")
    app.run(host="0.0.0.0", port=PORT)
    
