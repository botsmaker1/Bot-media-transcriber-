import telebot
import subprocess
import os
import uuid
import shutil
import time
from faster_whisper import WhisperModel
import requests

DOWNLOAD_DIR = "downloads"
if os.path.exists(DOWNLOAD_DIR):
    shutil.rmtree(DOWNLOAD_DIR)
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

model = WhisperModel(
    model_size_or_path="tiny",
    device="cpu",
    compute_type="int8"
)

TOKEN = "7232125515:AAFAEwM8wItfAqlM7bFP45x7D51ZCmCG9O4"  # Moved token to environment variable
bot = telebot.TeleBot(TOKEN)

REQUIRED_CHANNEL = "@qolkaqarxiska2"
ADMIN_ID = int(os.getenv("ADMIN_ID", "123456789"))  # Replace default with your actual admin ID

def check_subscription(user_id):
    try:
        member = bot.get_chat_member(REQUIRED_CHANNEL, user_id)
        return member.status in ['member', 'administrator', 'creator']
    except:
        return False

def send_subscription_message(chat_id):
    message = f"⚠️ You must join {REQUIRED_CHANNEL} to use this bot!\n\nJoin the channel and try again."
    markup = telebot.types.InlineKeyboardMarkup()
    markup.add(telebot.types.InlineKeyboardButton(text="Join Channel", url=f"https://t.me/{REQUIRED_CHANNEL[1:]}"))
    bot.send_message(chat_id, message, reply_markup=markup)

@bot.message_handler(commands=['start'])
def start_handler(message):
    if not check_subscription(message.from_user.id):
        return send_subscription_message(message.chat.id)
    first_name = message.from_user.first_name or "there"
    username = f"@{message.from_user.username}" if message.from_user.username else first_name
    text = f"👋 Salom {username}\n•Send me any of these types of files:\n"            "• Voice message 🎤\n• Video message 🎥\n• Audio file 🎵\n• Video file 📹\n\n"            "I will convert them to text!"
    bot.send_message(message.chat.id, text, parse_mode="Markdown")

def is_admin(user_id: int) -> bool:
    return user_id == ADMIN_ID

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
        "Send me only any of these types of files:\n"
        "• Voice message 🎤\n"
        "• Video message 🎥\n"
        "• Audio file 🎵\n"
        "• Video file 📹\n\n"
        "I will convert them to text!"
    )

def transcribe_audio(file_path: str) -> str | None:
    try:
        segments, _ = model.transcribe(file_path, beam_size=1)
        return " ".join(segment.text for segment in segments)
    except Exception:
        return None

if __name__ == "__main__":
    bot.delete_webhook()
    bot.remove_webhook()
    while True:
        try:
            bot.polling(none_stop=True, interval=2, timeout=20, long_polling_timeout=20)
        except requests.exceptions.ConnectionError:
            time.sleep(5)
            continue
        except Exception:
            time.sleep(5)
            continue
