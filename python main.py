import telebot
import subprocess
import os
import uuid
import shutil
import time
from faster_whisper import WhisperModel
import requests
from flask import Flask, request, abort
import logging

# Configure logger
logging.basicConfig(level=logging.INFO)

# Ku beddelo TOKEN-kaaga dhabta ah
TOKEN = "7232125515:AAFAEwM8wItfAqlM7bFP45x7D51ZCmCG9O4"
bot = telebot.TeleBot(TOKEN)

# Ku beddelo channel-kaaga dhabta ah
REQUIRED_CHANNEL = "@qolkaqarxiska2"

# Initialize Flask app
app = Flask(__name__)

# Meesha faylalka la soo dejiyey lagu kaydin doono
DOWNLOAD_DIR = "downloads"
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

# Load modelka Whisper
model = WhisperModel(
    model_size_or_path="tiny",
    device="cpu",
    compute_type="int8"
)

def check_subscription(user_id):
    try:
        member = bot.get_chat_member(REQUIRED_CHANNEL, user_id)
        return member.status in ['member', 'administrator', 'creator']
    except telebot.apihelper.ApiTelegramException as e:
        logging.error(f"Error checking subscription for user {user_id}: {e}")
        return False

def send_subscription_message(chat_id):
    message = f"⚠️ Waxaad ku biirtaa {REQUIRED_CHANNEL} si aad u isticmaasho botkaan!\n\nKu biir channel-ka kadibna isku day mar kale."
    markup = telebot.types.InlineKeyboardMarkup()
    markup.add(telebot.types.InlineKeyboardButton(text="Ku Biir Channel-ka", url=f"https://t.me/{REQUIRED_CHANNEL[1:]}"))
    bot.send_message(chat_id, message, reply_markup=markup)

@bot.message_handler(commands=['start'])
def start_handler(message):
    if not check_subscription(message.from_user.id):
        return send_subscription_message(message.chat.id)
    first_name = message.from_user.first_name or "there"
    username = f"@{message.from_user.username}" if message.from_user.username else first_name
    text = f"👋 Salom {username}\n• ii soo dir mid ka mid ah faylasha noocaan ah:\n" \
           "• Farriin cod ah 🎤\n• Farriin muuqaal ah 🎥\n• Fayl maqal ah 🎵\n• Fayl muuqaal ah 📹\n\n" \
           "Waan u rogi doonaa qoraal!"
    bot.send_message(message.chat.id, text, parse_mode="Markdown")

@bot.message_handler(content_types=['voice', 'video_note', 'audio', 'video'])
def handle_audio_message(message):
    if not check_subscription(message.from_user.id):
        return send_subscription_message(message.chat.id)
    file_path = None
    try:
        if message.voice:
            file_info = bot.get_file(message.voice.file_id)
        elif message.video_note:
            file_info = bot.get_file(message.video_note.file_id)
        elif message.video:
            file_info = bot.get_file(message.video.file_id)
        else:
            file_info = bot.get_file(message.audio.file_id)

        unique_id = str(uuid.uuid4())
        file_path = os.path.join(DOWNLOAD_DIR, f"{unique_id}.ogg")
        downloaded_file = bot.download_file(file_info.file_path)
        with open(file_path, 'wb') as new_file:
            new_file.write(downloaded_file)

        bot.send_chat_action(message.chat.id, 'typing')
        transcription = transcribe_audio(file_path)
        if transcription:
            if len(transcription) > 4000:
                with open("transcription.txt", "w", encoding="utf-8") as f:
                    f.write(transcription)
                with open("transcription.txt", "rb") as f:
                    bot.reply_to(message, document=f)
                os.remove("transcription.txt")
            else:
                bot.reply_to(message, transcription)
        else:
            bot.send_message(message.chat.id, "Ma awoodo inaan qoro qoraalka.")

    except Exception as e:
        bot.send_message(message.chat.id, f"Error: {e}")

    finally:
        if file_path and os.path.exists(file_path):
            os.remove(file_path)

@bot.message_handler(func=lambda m: True, content_types=['text', 'sticker', 'document', 'photo'])
def handle_other_messages(message):
    if not check_subscription(message.from_user.id):
        return send_subscription_message(message.chat.id)
    bot.send_message(
        message.chat.id,
        "ii soo dir mid ka mid ah faylasha noocaan ah:\n"
        "• Farriin cod ah 🎤\n"
        "• Farriin muuqaal ah 🎥\n"
        "• Fayl maqal ah 🎵\n"
        "• Fayl muuqaal ah 📹\n\n"
        "Waan u rogi doonaa qoraal!"
    )

def transcribe_audio(file_path: str) -> str | None:
    try:
        segments, _ = model.transcribe(file_path, beam_size=1)
        return " ".join(segment.text for segment in segments)
    except Exception as e:
        logging.error(f"Error during transcription of {file_path}: {e}")
        return None

@app.route('/', methods=['POST'])
def webhook():
    if request.headers.get('content-type') == 'application/json':
        json_string = request.get_data().decode('utf-8')
        update = telebot.types.Update.de_json(json_string)
        bot.process_new_updates([update])
        return '', 200
    else:
        abort(403)

@app.route('/set_webhook', methods=['GET', 'POST'])
def set_webhook_route():
    webhook_url = request.args.get('url')
    if webhook_url:
        bot.set_webhook(url=webhook_url)
        return f'Webhook set to: {webhook_url}', 200
    else:
        return 'Please provide a webhook URL as a query parameter.', 400

@app.route('/delete_webhook', methods=['GET', 'POST'])
def delete_webhook_route():
    bot.delete_webhook()
    return 'Webhook deleted', 200

def set_telegram_webhook(webhook_url, bot_token):
    url = f"https://api.telegram.org/bot{bot_token}/setWebhook?url={webhook_url}"
    try:
        response = requests.get(url)
        response.raise_for_status()  # Kor u qaad khalad haddii codsigu xumaado
        result = response.json()
        if result.get('ok'):
            print(f"Webhook successfully set to: {webhook_url}")
        else:
            print(f"Failed to set webhook: {result}")
    except requests.exceptions.RequestException as e:
        print(f"Error setting webhook: {e}")

if __name__ == "__main__":
    # Hubi in DOWNLOAD_DIR la tirtiro marka la bilaabo (ikhtiyaari)
    if os.path.exists(DOWNLOAD_DIR):
        shutil.rmtree(DOWNLOAD_DIR)
    os.makedirs(DOWNLOAD_DIR, exist_ok=True)

    # Ka saar webhook-kii hore haddii uu jiro
    bot.delete_webhook()

    # Deji webhook-ka marka app-ka la bilaabo
    WEBHOOK_URL = "https://bot-media-transcriber-i923.onrender.com/"
    set_telegram_webhook(WEBHOOK_URL, TOKEN)

    # Bilow app-ka Flask
    app.run(host="0.0.0.0", port=int(os.environ.get('PORT', 8080)))


