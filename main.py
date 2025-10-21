from flask import Flask, request
import requests
import os
from dotenv import load_dotenv

load_dotenv()
app = Flask(__name__)

TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')

def send_telegram(chat_id, text):
    """ارسال پیام به تلگرام"""
    try:
        requests.post(
            f'https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage',
            data={'chat_id': chat_id, 'text': text}
        )
    except Exception as e:
        print(f"❌ خطا در ارسال پیام به تلگرام: {str(e)}")

def ask_gemini(message):
    """ارسال پیام به Gemini و دریافت پاسخ"""
    url = f'https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-pro-latest:generateContent?key={GEMINI_API_KEY}'
    headers = {'Content-Type': 'application/json'}
    payload = {
        "contents": [
            {"parts": [{"text": message}]}
        ]
    }
    try:
        response = requests.post(url, json=payload, headers=headers, timeout=20)
        result = response.json()

        if response.status_code != 200:
            error_msg = result.get('error', {}).get('message', response.text)
            return f"❌ خطا از سمت Gemini:\n{error_msg}"

        return result['candidates'][0]['content']['parts'][0]['text']
    except Exception as e:
        return f"❌ خطا در اتصال به Gemini:\n{str(e)}"

@app.route('/', methods=['POST'])
def webhook():
    try:
        data = request.get_json()
        message = data.get('message')
        if not message or 'text' not in message:
            return 'no message', 400

        chat_id = message['chat']['id']
        text = message['text']

        reply = ask_gemini(text)
        send_telegram(chat_id, reply)
        return 'ok'

    except Exception as e:
        chat_id = data.get('message', {}).get('chat', {}).get('id')
        if chat_id:
            send_telegram(chat_id, f"❌ خطای داخلی:\n{str(e)}")
        return 'error', 500

@app.route('/', methods=['GET'])
def home():
    return '✅ ربات فعال است!'
