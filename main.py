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
import json

# Configure logger
logging.basicConfig(level=logging.INFO)

# Replace with your actual token
TOKEN = "7920977306:AAFRR5ZIaPcD1rbmjSKxsNisQZZpPa7zWPs"
bot = telebot.TeleBot(TOKEN)

# Replace with your channel
REQUIRED_CHANNEL = "@qolkaqarxiska2"

# Initialize Flask app
app = Flask(__name__)

# User language preferences
user_languages = {}
if os.path.exists('user_languages.json'):
    with open('user_languages.json', 'r') as f:
        try:
            user_languages = json.load(f)
        except json.JSONDecodeError:
            user_languages = {}

def save_user_languages():
    with open('user_languages.json', 'w') as f:
        json.dump(user_languages, f)

# Available languages with flag emojis
LANGUAGES = {
    "en": "English 🇬🇧",
    "tr": "Turkish 🇹🇷",
    "es": "Spanish 🇪🇸",
    "uz": "Uzbek 🇺🇿",
    "ru": "Russian 🇷🇺",
    "hi": "Hindi 🇮🇳",
    "auto": "🧠 Auto Detect"
}

# Whisper model
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
        logging.error(f"Error checking subscription: {e}")
        return False

def send_subscription_message(chat_id):
    message = f"⚠️ Fadlan ku biir {REQUIRED_CHANNEL} si aad u isticmaasho bot-kan!\n\nKu biir channel-ka kadibna isku day mar kale."
    markup = telebot.types.InlineKeyboardMarkup()
    markup.add(telebot.types.InlineKeyboardButton(
        text="Ku Biir Channel-ka",
        url=f"https://t.me/{REQUIRED_CHANNEL[1:]}"
    ))
    bot.send_message(chat_id, message, reply_markup=markup)

@bot.message_handler(commands=['start'])
def start_handler(message):
    if not check_subscription(message.from_user.id):
        return send_subscription_message(message.chat.id)

    user_id = str(message.from_user.id)
    if user_id not in user_languages:
        user_languages[user_id] = "auto"  # Default to auto-detect
        save_user_languages()

    first_name = message.from_user.first_name or "there"
    username = f"@{message.from_user.username}" if message.from_user.username else first_name
    text = (
        f"👋 Salaam {username}\n• Fadlan ii soo dir mid ka mid ah noocyada faylalka soo socda:\n"
        "• Farriin cod ah 🎤\n• Farriin muuqaal ah 🎥\n"
        "• Fayl maqal ah 🎵\n• Fayl muuqaal ah 📹\n\n"
        "Waan kuu qori doonaa qoraal!"
    )
    bot.send_message(message.chat.id, text)

@bot.message_handler(commands=['language'])
def language_handler(message):
    markup = telebot.types.InlineKeyboardMarkup(row_width=3)
    buttons = [telebot.types.InlineKeyboardButton(text=lang_name, callback_data=f"set_lang:{lang_code}")
               for lang_code, lang_name in LANGUAGES.items()]
    markup.add(*buttons)
    bot.send_message(message.chat.id, "Fadlan dooro luqadda aad rabto:", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith('set_lang:'))
def set_language_callback(call):
    user_id = str(call.from_user.id)
    lang_code = call.data.split(':')[1]
    user_languages[user_id] = lang_code
    save_user_languages()
    if lang_code == "auto":
        bot.answer_callback_query(call.id, "Luqadda si toos ah ayaa loo ogaan doonaa.")
        bot.send_message(call.message.chat.id, "Luqadda si toos ah ayaa loo ogaan doonaa.")
    else:
        language_name = LANGUAGES.get(lang_code, "Unknown")
        bot.answer_callback_query(call.id, f"Luqaddaada waxaa loo dejiyay: {language_name}")
        bot.send_message(call.message.chat.id, f"Luqaddaada waxaa loo dejiyay: {language_name}")

@bot.message_handler(content_types=['voice', 'video_note', 'audio', 'video'])
def handle_audio_message(message):
    if not check_subscription(message.from_user.id):
        return send_subscription_message(message.chat.id)

    user_id = str(message.from_user.id)
    preferred_language = user_languages.get(user_id, "auto")
    transcribe_language = None if preferred_language == "auto" else preferred_language

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
        transcription = transcribe_audio(file_path, language=transcribe_language)
        if transcription:
            if len(transcription) > 4000:
                with open("transcription.txt", "w") as f:
                    f.write(transcription)
                with open("transcription.txt", "rb") as f:
                    bot.reply_to(message, document=f)
                os.remove("transcription.txt")
            else:
                bot.reply_to(message, transcription)
        else:
            bot.send_message(message.chat.id, "Ma awoodin inaan qoro codka.")

    except Exception as e:
        bot.send_message(message.chat.id, f"Khalad: {e}")
    finally:
        if file_path and os.path.exists(file_path):
            os.remove(file_path)

@bot.message_handler(func=lambda m: True, content_types=['text', 'sticker', 'document', 'photo'])
def handle_other_messages(message):
    if not check_subscription(message.from_user.id):
        return send_subscription_message(message.chat.id)
    bot.send_message(
        message.chat.id,
        " sorry Fadlan ii soo dir mid ka mid ah noocyada faylalka soo socda:\n"
        "• Farriin cod ah 🎤\n• Farriin muuqaal ah 🎥\n"
        "• Fayl maqal ah 🎵\n• Fayl muuqaal ah 📹\n\n"
        "Waan kuu qori doonaa qoraal!"
    )

def transcribe_audio(file_path: str, language: str = None) -> str | None:
    try:
        segments, _ = model.transcribe(file_path, beam_size=1, language=language)
        return " ".join(segment.text for segment in segments)
    except Exception as e:
        logging.error(f"Khalad ku yimid qoraalka faylka {file_path}: {e}")
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
        return f'Webhook waxaa lagu dejiyay: {webhook_url}', 200
    else:
        return 'Fadlan ku dar URL-ka webhook-kaaga query parameter ahaan.', 400

@app.route('/delete_webhook', methods=['GET', 'POST'])
def delete_webhook_route():
    bot.delete_webhook()
    return 'Webhook waa la tirtiray', 200

def set_telegram_webhook(webhook_url, bot_token):
    """Wuxuu dejiyaa webhook-ka Telegram bot."""
    url = f"https://api.telegram.org/bot{bot_token}/setWebhook?url={webhook_url}"
    try:
        response = requests.get(url)
        response.raise_for_status()  # Wuxuu soo saaraa exception haddii status code uu xumaado
        result = response.json()
        if result.get('ok'):
            print(f"Webhook si guul leh ayaa loo dejiyay: {webhook_url}")
        else:
            print(f"Wuu ku guuldareystay dejinta webhook-ka: {result}")
    except requests.exceptions.RequestException as e:
        print(f"Khalad ku yimid dejinta webhook-ka: {e}")

if __name__ == "__main__":
    if os.path.exists(DOWNLOAD_DIR):
        shutil.rmtree(DOWNLOAD_DIR)
    os.makedirs(DOWNLOAD_DIR, exist_ok=True)

    bot.delete_webhook()
    WEBHOOK_URL = "https://bot-media-transcriber-i923.onrender.com/"
    set_telegram_webhook(WEBHOOK_URL, TOKEN)
    app.run(host="0.0.0.0", port=int(os.environ.get('PORT', 8080))




