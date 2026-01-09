import os
import logging
import threading
import subprocess
from flask import Flask
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# --- CONFIGURATION ---
ALLOWED_USER_ID = 5206554804 
BASE_WORKSPACES_DIR = "/home/data/workspaces"

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- HEALTH CHECK FOR AZURE ---
flask_app = Flask(__name__)
@flask_app.route('/')
def home(): return "VPS Bot is Online", 200

def run_web_server():
    port = int(os.environ.get('PORT', 8000))
    flask_app.run(host='0.0.0.0', port=port)

# --- SECURITY GATE ---
async def is_authorized(update: Update):
    if update.effective_user.id != ALLOWED_USER_ID:
        await update.message.reply_text("❌ Access Denied.")
        return False
    return True

# --- NEW FEATURES ---

# 1. Download File from VPS
async def download_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_authorized(update): return
    if not context.args:
        await update.message.reply_text("Usage: /download <filename>")
        return
    
    file_path = os.path.join(BASE_WORKSPACES_DIR, context.args[0])
    if os.path.exists(file_path):
        await update.message.reply_document(document=open(file_path, 'rb'))
    else:
        await update.message.reply_text("❌ File not found.")

# 2. Upload File to VPS
async def handle_upload(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_authorized(update): return
    file = await update.message.document.get_file()
    file_path = os.path.join(BASE_WORKSPACES_DIR, update.message.document.file_name)
    await file.download_to_drive(file_path)
    await update.message.reply_text(f"✅ Saved to {file_path}")

# --- TERMINAL LOGIC ---
async def handle_terminal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_authorized(update): return
    cmd = update.message.text
    try:
        process = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        stdout, stderr = process.communicate(timeout=30)
        await update.message.reply_text(f"```\n{(stdout or stderr)[:4000]}\n```", parse_mode="MarkdownV2")
    except Exception as e:
        await update.message.reply_text(f"Error: {str(e)}")

def main():
    token = os.environ.get("8523876686:AAF6oR1YHBWlpFO8H4L-zj5v6EsQr-puyXk")
    if not token: return

    os.makedirs(BASE_WORKSPACES_DIR, exist_ok=True)
    threading.Thread(target=run_web_server, daemon=True).start()

    app = Application.builder().token(token).build()
    
    # Handlers
    app.add_handler(CommandHandler("download", download_file))
    app.add_handler(MessageHandler(filters.Document.ALL, handle_upload))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_terminal))
    
    app.run_polling()

if __name__ == '__main__':
    main()
