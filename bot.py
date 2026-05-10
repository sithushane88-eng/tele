
"""
Gemini AI Telegram Chatbot
- Telegram ကနေ Gemini AI နဲ့ chat နိုင်တဲ့ bot
- Render.com (free tier) မှာ deploy လုပ်ရန်
"""

import os
import logging
from flask import Flask, request
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
import google.generativeai as genai

# ============================================
# CONFIGURATION - Environment variables မှ ရယူပါ
# ============================================
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
RENDER_EXTERNAL_URL = os.getenv("RENDER_EXTERNAL_URL")
PORT = int(os.getenv("PORT", "8080"))

# Gemini Model (free tier)
MODEL_NAME = "gemini-2.0-flash"

# ============================================
# SETUP
# ============================================
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Gemini setup
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel(MODEL_NAME)

# Chat history storage (per user)
chat_sessions = {}

# ============================================
# BOT COMMANDS
# ============================================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Bot စဖွင့်တဲ့အခါ"""
    user = update.effective_user
    await update.message.reply_text(
        f"မင်္ဂလာပါ {user.first_name}! 👋\n\n"
        f"ကျွန်တော်က Gemini AI Chatbot ပါ။\n"
        f"ဘာမဆို မေးနိုင်ပါတယ်။\n\n"
        f"Commands:\n"
        f"/start - Bot စဖွင့်ရန်\n"
        f"/new - Chat အသစ်စရန် (history ရှင်းမယ်)\n"
        f"/help - အကူအညီ"
    )

async def new_chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Chat history ရှင်းပြီး အသစ်စ"""
    user_id = update.effective_user.id
    if user_id in chat_sessions:
        del chat_sessions[user_id]
    await update.message.reply_text("✅ Chat အသစ် စပါပြီ!")

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Help message"""
    await update.message.reply_text(
        "🤖 Gemini AI Chatbot\n\n"
        "📝 စကားပြောရန် - message ရိုက်ပို့ပါ\n"
        "🔄 /new - Chat အသစ်စရန်\n"
        "❓ /help - ဒီ message ပြရန်\n\n"
        "💡 ဘာမဆို မေးနိုင်ပါတယ် - မြန်မာလိုရော English လိုရော!"
    )

# ============================================
# MESSAGE HANDLER (Main chat function)
# ============================================
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """User message ကို Gemini ဆီပို့ပြီး reply ပြန်"""
    user_id = update.effective_user.id
    user_message = update.message.text

    # Typing indicator ပြ
    await update.message.chat.send_action("typing")

    try:
        # Chat session ရှိ/မရှိ စစ်
        if user_id not in chat_sessions:
            chat_sessions[user_id] = model.start_chat(history=[])

        chat = chat_sessions[user_id]

        # Gemini ဆီ message ပို့
        response = chat.send_message(user_message)

        # Reply ပြန်
        reply_text = response.text

        # Telegram message limit (4096 chars)
        if len(reply_text) > 4096:
            # Split into chunks
            for i in range(0, len(reply_text), 4096):
                await update.message.reply_text(reply_text[i:i+4096])
        else:
            await update.message.reply_text(reply_text)

    except Exception as e:
        logger.error(f"Error: {e}")
        await update.message.reply_text(
            f"❌ Error ဖြစ်သွားပါတယ်:\n{str(e)}\n\n"
            f"/new နဲ့ chat အသစ်စကြည့်ပါ။"
        )

# ============================================
# ERROR HANDLER
# ============================================
async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Error handling"""
    logger.error(f"Update {update} caused error {context.error}")

# ============================================
# MAIN
# ============================================
if __name__ == "__main__":
    print("🤖 Gemini Telegram Bot starting...")
    print(f"📡 Model: {MODEL_NAME}")

    # Bot application ဆောက်
    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    # Commands
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("new", new_chat))
    app.add_handler(CommandHandler("help", help_command))

    # Message handler
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    # Error handler
    app.add_error_handler(error_handler)

    # Flask app for webhook and health check
    flask_app = Flask(__name__)

    @flask_app.route("/")
    async def telegram_webhook():
        update = Update.de_json(request.get_json(force=True), app.bot)
        await app.update_queue.put(update)
        return "ok"

    @flask_app.route("/health")
    def health_check():
        return "OK", 200

    # Set webhook
    app.bot.set_webhook(url=f"{RENDER_EXTERNAL_URL}/")

    # Start the bot's update processing in a separate thread
    import threading
    threading.Thread(target=app.run_polling, daemon=True).start()

    # Run Flask app
    print(f"✅ Bot is running on port {PORT}!")
    flask_app.run(host="0.0.0.0", port=PORT)
