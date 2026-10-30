import os
from flask import Flask
import threading
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

# Get token from Render env
TOKEN = os.environ.get("BOT_TOKEN") or os.environ.get("TELEGRAM_BOT_TOKEN") or os.environ.get("TELEGRAM_TOKEN")

flask_app = Flask(__name__)

@flask_app.route('/')
def home():
    return "Tiker AI Bot LIVE 24/7 - OK"

def run_web():
    port = int(os.environ.get("PORT", 10000))
    flask_app.run(host='0.0.0.0', port=port)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🚀 Tiker AI is LIVE 24/7!\n\n"
        "✅ Bot running on Render\n"
        "✅ Auto-uptime enabled\n\n"
        "Send /help for commands"
    )

async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Use /start to check if I'm alive!")

# Start Flask in background
threading.Thread(target=run_web, daemon=True).start()

# Start Telegram Bot
if TOKEN:
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_cmd))
    print("Bot polling started...")
    app.run_polling()
else:
    print("ERROR: BOT_TOKEN not found in env vars!")
    # Keep Flask running even without token
    run_web()
