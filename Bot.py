import os
import subprocess
import logging
import threading
from flask import Flask
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# --- CONFIGURATION ---
# Replace with your actual ID to keep the bot private
ALLOWED_USER_ID = 5206554804 

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- WEB SERVER FOR RENDER ---
flask_app = Flask(__name__)

@flask_app.route('/')
def health_check():
    return "Bot is Online", 200

def run_web_server():
    # Render provides the PORT environment variable automatically
    port = int(os.environ.get('PORT', 8000))
    flask_app.run(host='0.0.0.0', port=port)

# --- SECURITY CHECK ---
async def is_authorized(update: Update):
    if update.effective_user.id != ALLOWED_USER_ID:
        await update.message.reply_text("❌ Unauthorized: Access Denied.")
        return False
    return True

# --- BOT COMMANDS ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_authorized(update): return
    await update.message.reply_text("✅ VPS Terminal Online. Send me any command.")

async def handle_terminal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_authorized(update): return
    command = update.message.text
    try:
        # Executes the command and captures the output
        process = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        stdout, stderr = process.communicate(timeout=30)
        output = stdout if stdout else stderr
        await update.message.reply_text(f"```\n{output[:3900]}\n```", parse_mode="Markdown")
    except Exception as e:
        await update.message.reply_text(f"Error: {str(e)}")

def main():
    # Get token from Render's Environment Variables
    token = os.environ.get("8523876686:AAF6oR1YHBWlpFO8H4L-zj5v6EsQr-puyXk")
    if not token:
        logger.error("No BOT_TOKEN found!")
        return

    # Start Flask in background to satisfy Render's port requirement
    threading.Thread(target=run_web_server, daemon=True).start()

    # Initialize Telegram Bot
    app = Application.builder().token(token).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_terminal))
    
    logger.info("Bot started...")
    app.run_polling()

if __name__ == '__main__':
    main()
