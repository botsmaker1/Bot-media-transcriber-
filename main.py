 

import os
import re
import uuid
import shutil
import logging
import requests
import telebot
import yt_dlp
from flask import Flask, request, abort
from faster_whisper import WhisperModel

# Logging
logging.basicConfig(level=logging.INFO)

# ENV variables
TOKEN = os.environ.get"7920977306:AAFRR5ZIaPcD1rbmjSKxsNisQZZpPa7zWPs"
WEBHOOK_URL = os.environ.get("https://bot-media-transcriber.onrender.com")

bot = telebot.TeleBot(TOKEN)
REQUIRED_CHANNEL = "@qolkaqarxiska2"
ADMIN_ID = 5240873494
DOWNLOAD_DIR = "downloads"
FILE_SIZE_LIMIT = 50 * 1024 * 1024  # 50MB

# Flask
app = Flask(__name__)

# Model
model = WhisperModel("tiny", device="cpu", compute_type="int8")

# User tracking
existing_users = set()
if os.path.exists('users.txt'):
    with open('users.txt') as f:
        existing_users.update(line.strip() for line in f)

admin_state = {}
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

# Regex for video links
URL_PATTERN = re.compile(
    r'(https?://(?:www\.)?(?:youtube\.com/watch\?v=|youtu\.be/|youtube\.com/shorts/|vm\.tiktok\.com/|tiktok\.com/)[^\s]+)'
)

# --- Utils ---
def check_subscription(user_id):
    try:
        member = bot.get_chat_member(REQUIRED_CHANNEL, user_id)
        return member.status in ['member', 'administrator', 'creator']
    except telebot.apihelper.ApiTelegramException as e:
        logging.error(f"Subscription check error: {e}")
        return False

def send_subscription_message(chat_id):
    markup = telebot.types.InlineKeyboardMarkup()
    markup.add(telebot.types.InlineKeyboardButton("Join Channel", url=f"https://t.me/{REQUIRED_CHANNEL[1:]}"))
    bot.send_message(chat_id, f"⚠️ Please join {REQUIRED_CHANNEL} to use this bot!", reply_markup=markup)

def transcribe_audio(file_path):
    try:
        segments, _ = model.transcribe(file_path, beam_size=1)
        return " ".join(segment.text for segment in segments)
    except Exception as e:
        logging.error(f"Transcription error: {e}")
        return None

# --- Bot Handlers ---
@bot.message_handler(commands=['start'])
def start_handler(message):
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
        bot.send_message(message.chat.id, "Admin Panel", reply_markup=markup)
    else:
        username = f"@{message.from_user.username}" if message.from_user.username else message.from_user.first_name
        bot.send_message(message.chat.id,
            f"👋 Salam {username}\n"
            "Please send:\n• Voice 🎤\n• Video 🎥\n• Audio 🎵\n• Video file 📹\n"
            "Or a YouTube/TikTok link.\nI'll transcribe it to text for free!"
        )

@bot.message_handler(func=lambda m: m.text == "Total Users" and m.from_user.id == ADMIN_ID)
def show_total_users(message):
    bot.send_message(message.chat.id, f"Total users: {len(existing_users)}")

@bot.message_handler(func=lambda m: m.text == "Send Ads (Broadcast)" and m.from_user.id == ADMIN_ID)
def start_broadcast(message):
    admin_state[message.from_user.id] = 'awaiting_broadcast'
    bot.send_message(message.chat.id, "Send the message you want to broadcast:")

@bot.message_handler(func=lambda m: m.from_user.id == ADMIN_ID and admin_state.get(m.from_user.id) == 'awaiting_broadcast',
                     content_types=['text', 'photo', 'video', 'audio', 'document', 'voice', 'sticker'])
def handle_broadcast(message):
    admin_state[message.from_user.id] = None
    success, failure = 0, 0
    for user_id in existing_users:
        try:
            bot.copy_message(user_id, message.chat.id, message.message_id)
            success += 1
        except:
            failure += 1
    bot.send_message(message.chat.id, f"Broadcast done!\n✅ Success: {success}\n❌ Failed: {failure}")

@bot.message_handler(content_types=['voice', 'video_note', 'audio', 'video'])
def handle_media(message):
    if not check_subscription(message.from_user.id):
        return send_subscription_message(message.chat.id)

    file_id = (message.voice or message.video_note or message.audio or message.video).file_id
    file_size = (message.voice or message.video_note or message.audio or message.video).file_size

    if file_size > FILE_SIZE_LIMIT:
        return bot.send_message(message.chat.id, "❌ File size exceeds 50MB. Send a smaller one.")

    file_info = bot.get_file(file_id)
    file_path = os.path.join(DOWNLOAD_DIR, f"{uuid.uuid4()}.ogg")

    with open(file_path, 'wb') as f:
        f.write(bot.download_file(file_info.file_path))

    bot.send_chat_action(message.chat.id, 'typing')
    transcription = transcribe_audio(file_path)
    os.remove(file_path)

    if transcription:
        if len(transcription) > 2000:
            with open("transcription.txt", "w") as f:
                f.write(transcription)
            with open("transcription.txt", "rb") as f:
                bot.send_document(message.chat.id, f)
            os.remove("transcription.txt")
        else:
            bot.send_message(message.chat.id, transcription)
    else:
        bot.send_message(message.chat.id, "❌ Could not transcribe audio.")

@bot.message_handler(func=lambda m: m.text and URL_PATTERN.search(m.text))
def handle_url(message):
    if not check_subscription(message.from_user.id):
        return send_subscription_message(message.chat.id)

    url = message.text.strip()
    out_path = os.path.join(DOWNLOAD_DIR, f"{uuid.uuid4()}.mp4")
    bot.send_chat_action(message.chat.id, 'typing')

    try:
        ydl_opts = {
            'format': 'best',
            'outtmpl': out_path,
            'quiet': True,
            'max_filesize': FILE_SIZE_LIMIT,
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            if info.get('filesize', 0) > FILE_SIZE_LIMIT:
                return bot.send_message(message.chat.id, "❌ Video size exceeds 50MB.")
            ydl.download([url])

        transcription = transcribe_audio(out_path)
        os.remove(out_path)

        if transcription:
            if len(transcription) > 2000:
                with open("transcription.txt", "w") as f:
                    f.write(transcription)
                with open("transcription.txt", "rb") as f:
                    bot.send_document(message.chat.id, f)
                os.remove("transcription.txt")
            else:
                bot.send_message(message.chat.id, transcription)
        else:
            bot.send_message(message.chat.id, "❌ Could not transcribe video.")

    except Exception as e:
        logging.error(f"Download error: {e}")
        bot.send_message(message.chat.id, "❌ Error processing the video.")

@bot.message_handler(func=lambda m: True)
def handle_others(message):
    if not check_subscription(message.from_user.id):
        return send_subscription_message(message.chat.id)
    bot.send_message(message.chat.id, "Send audio, video, or link to transcribe.")

# --- Flask Webhook ---
@app.route('/', methods=['POST'])
def webhook():
    if request.headers.get('content-type') == 'application/json':
        update = telebot.types.Update.de_json(request.data.decode("utf-8"))
        bot.process_new_updates([update])
        return '', 200
    abort(403)

@app.route('/set_webhook')
def set_webhook():
    if WEBHOOK_URL:
        bot.set_webhook(url=WEBHOOK_URL)
        return f"Webhook set to {WEBHOOK_URL}"
    return "Webhook URL not found", 400

@app.route('/delete_webhook')
def delete_webhook():
    bot.delete_webhook()
    return "Webhook deleted"

# --- Run App ---
if __name__ == '__main__':
    if os.path.exists(DOWNLOAD_DIR):
        shutil.rmtree(DOWNLOAD_DIR)
    os.makedirs(DOWNLOAD_DIR)

    bot.delete_webhook()
    if WEBHOOK_URL:
        requests.get(f"https://api.telegram.org/bot{TOKEN}/setWebhook?url={WEBHOOK_URL}")
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))





