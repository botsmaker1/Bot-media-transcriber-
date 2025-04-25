import os
import re
import uuid
import logging
import shutil
import requests
from flask import Flask, request, abort
import telebot
from faster_whisper import WhisperModel
import yt_dlp

# Config
TOKEN = "7920977306:AAFRR5ZIaPcD1rbmjSKxsNisQZZpPa7zWPs"
REQUIRED_CHANNEL = "@qolkaqarxiska2"
ADMIN_ID = 6964068910  # beddel ID-ga admin

# Setup
bot = telebot.TeleBot(TOKEN)
app = Flask(__name__)
DOWNLOAD_DIR = "downloads"
FILE_SIZE_LIMIT = 50 * 1024 * 1024  # 50MB
existing_users = set()
admin_state = {}
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

# Load old users
if os.path.exists('users.txt'):
    with open('users.txt') as f:
        existing_users = set(line.strip() for line in f)

# Whisper Model
model = WhisperModel("tiny", device="cpu", compute_type="int8")

URL_PATTERN = re.compile(
    r'(https?://(?:www\.)?(?:youtube\.com/watch\?v=|youtu\.be/|youtube\.com/shorts/|vm\.tiktok\.com/|tiktok\.com/)[^\s]+)'
)

def check_subscription(user_id):
    try:
        member = bot.get_chat_member(REQUIRED_CHANNEL, user_id)
        return member.status in ['member', 'administrator', 'creator']
    except Exception:
        return False

def send_subscription_message(chat_id):
    markup = telebot.types.InlineKeyboardMarkup()
    markup.add(telebot.types.InlineKeyboardButton("Join Channel", url=f"https://t.me/{REQUIRED_CHANNEL[1:]}"))
    bot.send_message(chat_id, f"⚠️ Please join {REQUIRED_CHANNEL} to use the bot!", reply_markup=markup)

@bot.message_handler(commands=['start'])
def handle_start(message):
    if not check_subscription(message.from_user.id):
        return send_subscription_message(message.chat.id)

    user_id = str(message.from_user.id)
    if user_id not in existing_users:
        existing_users.add(user_id)
        with open('users.txt', 'a') as f:
            f.write(f"{user_id}\n")

    if message.from_user.id == ADMIN_ID:
        markup = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True)
        markup.add("Send Ads (Broadcast)", "Total Users")
        bot.send_message(message.chat.id, "Welcome to Admin Panel", reply_markup=markup)
    else:
        bot.send_message(
            message.chat.id,
            "Send me:\n• Voice 🎤\n• Audio 🎵\n• Video 📹\n• YouTube/TikTok Link\nI'll transcribe it!"
        )

@bot.message_handler(func=lambda msg: msg.text == "Total Users" and msg.from_user.id == ADMIN_ID)
def show_total_users(message):
    bot.send_message(message.chat.id, f"Total users: {len(existing_users)}")

@bot.message_handler(func=lambda msg: msg.text == "Send Ads (Broadcast)" and msg.from_user.id == ADMIN_ID)
def ask_for_broadcast(message):
    admin_state[message.from_user.id] = 'awaiting_broadcast'
    bot.send_message(message.chat.id, "Send your broadcast message.")

@bot.message_handler(func=lambda msg: admin_state.get(msg.from_user.id) == 'awaiting_broadcast', content_types=['text', 'photo', 'video'])
def do_broadcast(message):
    admin_state[message.from_user.id] = None
    success, failure = 0, 0
    for user_id in existing_users:
        try:
            bot.copy_message(user_id, message.chat.id, message.message_id)
            success += 1
        except:
            failure += 1
    bot.send_message(message.chat.id, f"Broadcast done. Success: {success}, Failures: {failure}")

@bot.message_handler(func=lambda m: m.content_type in ['voice', 'audio', 'video'])
def handle_media(message):
    if not check_subscription(message.from_user.id):
        return send_subscription_message(message.chat.id)

    file_info = bot.get_file(message.audio.file_id if message.audio else message.voice.file_id if message.voice else message.video.file_id)
    file_path = os.path.join(DOWNLOAD_DIR, f"{uuid.uuid4()}.ogg")
    try:
        file_data = bot.download_file(file_info.file_path)
        with open(file_path, "wb") as f:
            f.write(file_data)
        transcription = transcribe_audio(file_path)
        bot.send_message(message.chat.id, transcription or "Error during transcription.")
    except Exception as e:
        bot.send_message(message.chat.id, f"Error: {e}")
    finally:
        if os.path.exists(file_path):
            os.remove(file_path)

@bot.message_handler(func=lambda m: URL_PATTERN.search(m.text))
def handle_video_url(message):
    if not check_subscription(message.from_user.id):
        return send_subscription_message(message.chat.id)

    url = message.text.strip()
    out_path = os.path.join(DOWNLOAD_DIR, f"{uuid.uuid4()}.mp4")

    ydl_opts = {
        'format': 'best',
        'outtmpl': out_path,
        'quiet': True,
        'max_filesize': FILE_SIZE_LIMIT,
        'http_headers': {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/122.0.0.0 Safari/537.36'
        }
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])
        transcription = transcribe_audio(out_path)
        bot.send_message(message.chat.id, transcription or "Transcription failed.")
    except Exception as e:
        bot.send_message(message.chat.id, f"❌ error: {e}")
    finally:
        if os.path.exists(out_path):
            os.remove(out_path)

@bot.message_handler(func=lambda m: True)
def default_response(message):
    bot.send_message(message.chat.id, "Send voice/audio/video or YouTube/TikTok link.")

def transcribe_audio(file_path):
    try:
        segments, _ = model.transcribe(file_path)
        return " ".join(segment.text for segment in segments)
    except Exception as e:
        logging.error(f"Transcription error: {e}")
        return None

@app.route('/', methods=['POST'])
def webhook():
    if request.headers.get('content-type') == 'application/json':
        update = telebot.types.Update.de_json(request.data.decode('utf-8'))
        bot.process_new_updates([update])
        return '', 200
    else:
        abort(403)

@app.route('/set_webhook', methods=['GET'])
def set_webhook():
    url = request.args.get("url")
    if url:
        bot.set_webhook(url=url)
        return f"Webhook set to: {url}", 200
    return "Missing URL", 400

@app.route('/delete_webhook', methods=['GET'])
def delete_webhook():
    bot.delete_webhook()
    return "Webhook deleted", 200

if __name__ == '__main__':
    if os.path.exists(DOWNLOAD_DIR):
        shutil.rmtree(DOWNLOAD_DIR)
    os.makedirs(DOWNLOAD_DIR, exist_ok=True)
    WEBHOOK_URL = "https://bot-media-transcriber.onrender.com"
    bot.delete_webhook()
    bot.set_webhook(url=WEBHOOK_URL)
    app.run(host="0.0.0.0", port=int(os.environ.get('PORT', 8080)))


