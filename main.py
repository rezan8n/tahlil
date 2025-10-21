from flask import Flask, request, jsonify
import requests
import os
from dotenv import load_dotenv
import logging
import sys

# تنظیمات لاگ
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    stream=sys.stdout
)
logger = logging.getLogger(__name__)

load_dotenv()
app = Flask(__name__)

TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')

def ask_gemini_simple(message):
    """ساده‌ترین نسخه ارتباط با Gemini"""
    if not GEMINI_API_KEY:
        return "❌ Gemini API Key تنظیم نشده"
    
    url = f'https://generativelanguage.googleapis.com/v1/models/gemini-pro:generateContent?key={GEMINI_API_KEY}'
    
    # ساده‌ترین ساختار ممکن
    payload = {
        "contents": [{
            "parts": [{"text": message}]
        }]
    }
    
    try:
        logger.info(f"📤 ارسال به Gemini: {message}")
        response = requests.post(url, json=payload, timeout=30)
        
        logger.info(f"📥 وضعیت: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            reply = result['candidates'][0]['content']['parts'][0]['text']
            logger.info(f"✅ پاسخ: {reply}")
            return reply
            
        elif response.status_code == 400:
            error_info = response.json().get('error', {})
            return f"❌ خطای 400: {error_info.get('message', 'خطای نامشخص')}"
            
        elif response.status_code == 429:
            return "❌ سقف استفاده روزانه تمام شده (60 درخواست رایگان)"
            
        else:
            return f"❌ خطا: {response.status_code} - {response.text}"
            
    except requests.exceptions.Timeout:
        return "❌ timeout - سرور Gemini پاسخ نداد"
    except Exception as e:
        return f"❌ خطای غیرمنتظره: {str(e)}"

@app.route('/', methods=['POST'])
def webhook():
    """وب‌هوک اصلی تلگرام"""
    try:
        data = request.get_json()
        
        # لاگ ساده برای دیباگ
        logger.info(f"📩 دریافت از تلگرام: {data}")
        
        message = data.get('message') or data.get('edited_message')
        if not message:
            return 'no message', 400

        chat_id = message['chat']['id']
        text = message.get('text', '')
        
        # پاسخ به دستور start
        if text == '/start':
            reply = '''🤖 سلام! من یک چت‌بات هوشمندم که با Google Gemini کار می‌کنم.

می‌تونی هر سوالی ازم بپرسی:
• سوالات علمی
• کمک در نوشتن
• توضیح مفاهیم
• و هر چیز دیگه‌ای!

یه سوال بپرس شروع کنیم...'''
        else:
            # ارسال به Gemini
            reply = ask_gemini_simple(text)
        
        # ارسال پاسخ به کاربر
        requests.post(
            f'https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage',
            data={'chat_id': chat_id, 'text': reply}
        )
        
        return 'ok'
        
    except Exception as e:
        logger.error(f"🔥 خطا در وب‌هوک: {str(e)}")
        return 'error', 500

@app.route('/', methods=['GET'])
def home():
    return '🤖 چت‌بات هوشمند فعال است!'

@app.route('/test', methods=['GET'])
def test():
    """تست ساده سلامت"""
    return jsonify({
        "status": "active", 
        "telegram_token": "SET" if TELEGRAM_TOKEN else "NOT SET",
        "gemini_key": "SET" if GEMINI_API_KEY else "NOT SET"
    })

@app.route('/test-gemini', methods=['GET'])
def test_gemini():
    """تست مستقیم Gemini"""
    test_message = "سلام! لطفاً فقط بگو 'Connection Successful'"
    result = ask_gemini_simple(test_message)
    
    return jsonify({
        "test_message": test_message,
        "response": result,
        "status": "success" if not result.startswith('❌') else "error"
    })

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port)
