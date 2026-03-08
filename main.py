import uuid
import shutil
import threading
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes
from flask import Flask, send_from_directory, abort

BOT_TOKEN = "8447530035:AAGNdtpNZB0LaBYZXWesRIKFvTy_5ivAHpc"
UPLOAD_FOLDER = "uploads"
hosted_files = {}
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

app = Flask(__name__)
PORT = int(os.environ.get("PORT", 5000))
HOST = os.environ.get("RENDER_EXTERNAL_HOSTNAME", "localhost")

@app.route("/site/<int:user_id>/<file_id>/<path:filename>")
def serve_file(user_id, file_id, filename):
    directory = os.path.join(UPLOAD_FOLDER, str(user_id), file_id)
    if not os.path.exists(os.path.join(directory, filename)):
        abort(404)
    return send_from_directory(directory, filename)

@app.route("/")
def home():
    return "<html><body style='background:#1a1a2e;color:white;text-align:center;padding-top:100px;font-family:sans-serif;'><h1>🌐 HTML Hosting Bot</h1><p>Bot is running!</p></body></html>"

@app.route("/health")
def health():
    return "OK", 200

def run_flask():
    app.run(host="0.0.0.0", port=PORT)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🌐 *HTML Hosting Bot*\n\n📌 HTML ফাইল পাঠান, লিংক পান!\n\n/myfiles - ফাইল দেখুন\n/delete - ফাইল মুছুন", parse_mode="Markdown")

async def handle_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    doc = update.message.document
    user_id = update.message.from_user.id
    fname = doc.file_name
    ext = os.path.splitext(fname)[1].lower()
    allowed = [".html", ".htm", ".css", ".js", ".zip", ".png", ".jpg", ".jpeg", ".gif", ".svg", ".ico"]
    if ext not in allowed:
        await update.message.reply_text(f"❌ `{ext}` সাপোর্ট করে না!", parse_mode="Markdown")
        return
    if doc.file_size > 20 * 1024 * 1024:
        await update.message.reply_text("❌ 20MB এর বেশি!")
        return
    msg = await update.message.reply_text("⏳ আপলোড হচ্ছে...")
    try:
        uid = str(uuid.uuid4())[:8]
        file_dir = os.path.join(UPLOAD_FOLDER, str(user_id), uid)
        os.makedirs(file_dir, exist_ok=True)
        if ext == ".zip":
            import zipfile
            zip_path = os.path.join(file_dir, "temp.zip")
            tg_file = await context.bot.get_file(doc.file_id)
            await tg_file.download_to_drive(zip_path)
            with zipfile.ZipFile(zip_path, "r") as z:
                z.extractall(file_dir)
            os.remove(zip_path)
            main_file = "index.html"
            for root, dirs, files in os.walk(file_dir):
                for f in files:
                    if f.lower() == "index.html":
                        main_file = os.path.relpath(os.path.join(root, f), file_dir)
                        break
            url = f"https://{HOST}/site/{user_id}/{uid}/{main_file}"
        else:
            tg_file = await context.bot.get_file(doc.file_id)
            await tg_file.download_to_drive(os.path.join(file_dir, fname))
            url = f"https://{HOST}/site/{user_id}/{uid}/{fname}"
        if user_id not in hosted_files:
            hosted_files[user_id] = []
        hosted_files[user_id].append({"id": uid, "name": fname, "url": url})
        keyboard = [[InlineKeyboardButton("🌐 দেখুন", url=url)], [InlineKeyboardButton("🗑️ ডিলিট", callback_data=f"del_{user_id}_{uid}")]]
        await msg.edit_text(f"✅ *হোস্ট সফল!*\n\n🔗 `{url}`", parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))
    except Exception as e:
        await msg.edit_text(f"❌ এরর: {e}")

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    checks = ["<!doctype", "<html", "<head", "<body"]
    if not any(text.lower().startswith(c) for c in checks):
        return
    user_id = update.message.from_user.id
    uid = str(uuid.uuid4())[:8]
    file_dir = os.path.join(UPLOAD_FOLDER, str(user_id), uid)
    os.makedirs(file_dir, exist_ok=True)
    with open(os.path.join(file_dir, "index.html"), "w", encoding="utf-8") as f:
        f.write(text)
    url = f"https://{HOST}/site/{user_id}/{uid}/index.html"
    if user_id not in hosted_files:
        hosted_files[user_id] = []
    hosted_files[user_id].append({"id": uid, "name": "index.html", "url": url})
    keyboard = [[InlineKeyboardButton("🌐 দেখুন", url=url)]]
    await update.message.reply_text(f"✅ *হোস্ট হয়েছে!*\n\n🔗 `{url}`", parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))

async def myfiles(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    if user_id not in hosted_files or not hosted_files[user_id]:
        await update.message.reply_text("📭 কোনো ফাইল নেই!")
        return
    text = "📂 *আপনার ফাইল:*\n\n"
    for f in hosted_files[user_id]:
        text += f"📄 `{f['name']}`\n🔗 `{f['url']}`\n\n"
    await update.message.reply_text(text, parse_mode="Markdown")

async def delete_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    if user_id not in hosted_files or not hosted_files[user_id]:
        await update.message.reply_text("📭 ফাইল নেই!")
        return
    keyboard = [[InlineKeyboardButton(f"🗑️ {f['name']}", callback_data=f"del_{user_id}_{f['id']}")] for f in hosted_files[user_id]]
    await update.message.reply_text("🗑️ কোনটা ডিলিট?", reply_markup=InlineKeyboardMarkup(keyboard))

async def delete_btn(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    parts = query.data.split("_")
    user_id, file_id = int(parts[1]), parts[2]
    if query.from_user.id != user_id:
        return
    path = os.path.join(UPLOAD_FOLDER, str(user_id), file_id)
    if os.path.exists(path):
        shutil.rmtree(path)
    if user_id in hosted_files:
        hosted_files[user_id] = [f for f in hosted_files[user_id] if f["id"] != file_id]
    await query.edit_message_text("✅ ডিলিট!")

if __name__ == "__main__":
    flask_thread = threading.Thread(target=run_flask)
    flask_thread.daemon = True
    flask_thread.start()
    print("🌐 Server Running!")
    
    application = Application.builder().token(BOT_TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("myfiles", myfiles))
    application.add_handler(CommandHandler("delete", delete_cmd))
    application.add_handler(MessageHandler(filters.Document.ALL, handle_file))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    application.add_handler(CallbackQueryHandler(delete_btn, pattern="^del_"))
    print("🤖 Bot Running!")
    application.run_polling(drop_pending_updates=Tru
