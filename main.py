from flask import Flask, request, jsonify
import requests
import os
from dotenv import load_dotenv
import logging
import sys
import google.generativeai as genai

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

# پیکربندی Gemini
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)
    logger.info("✅ Gemini پیکربندی شد")
else:
    logger.warning("❌ Gemini API Key تنظیم نشده")

def ask_gemini_official(message):
    """استفاده از کتابخانه رسمی Google"""
    if not GEMINI_API_KEY:
        return "❌ Gemini API Key تنظیم نشده"
    
    try:
        # استفاده از مدل پیش‌فرض
        model = genai.GenerativeModel('gemini-pro')
        
        logger.info(f"📤 ارسال به Gemini: {message}")
        response = model.generate_content(message)
        
        logger.info("✅ پاسخ دریافت شد")
        return response.text
        
    except Exception as e:
        error_msg = f"❌ خطا در Gemini: {str(e)}"
        logger.error(error_msg)
        return error_msg

def ask_gemini_direct(message):
    """استفاده مستقیم از API (برای تست)"""
    if not GEMINI_API_KEY:
        return "❌ Gemini API Key تنظیم نشده"
    
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-pro:generateContent?key={GEMINI_API_KEY}"
    
    headers = {
        'Content-Type': 'application/json',
    }
    
    data = {
        "contents": [{
            "parts": [{"text": message}]
        }]
    }
    
    try:
        logger.info(f"📤 ارسال مستقیم به Gemini: {message}")
        response = requests.post(url, json=data, headers=headers, timeout=30)
        
        logger.info(f"📥 وضعیت: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            if 'candidates' in result and result['candidates']:
                reply = result['candidates'][0]['content']['parts'][0]['text']
                logger.info("✅ پاسخ مستقیم دریافت شد")
                return reply
            else:
                return "❌ ساختار پاسخ نامعتبر"
        else:
            return f"❌ خطا: {response.status_code} - {response.text}"
            
    except Exception as e:
        return f"❌ خطا در ارتباط: {str(e)}"

@app.route('/', methods=['POST'])
def webhook():
    """وب‌هوک اصلی تلگرام"""
    try:
        data = request.get_json()
        logger.info(f"📩 دریافت از تلگرام")
        
        message = data.get('message') or data.get('edited_message')
        if not message:
            return 'no message', 400

        chat_id = message['chat']['id']
        text = message.get('text', '')
        
        if text == '/start':
            reply = '''🤖 سلام! من یک چت‌بات هوشمندم که با Google Gemini کار می‌کنم.

می‌تونی هر سوالی ازم بپرسی:
• سوالات علمی
• کمک در نوشتن  
• توضیح مفاهیم
• و هر چیز دیگه‌ای!

یه سوال بپرس شروع کنیم...'''
        else:
            # اول از کتابخانه رسمی استفاده می‌کنیم
            reply = ask_gemini_official(text)
            
            # اگر خطا داد، از API مستقیم استفاده می‌کنیم
            if reply.startswith('❌'):
                reply = ask_gemini_direct(text)
        
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
    """تست سلامت"""
    return jsonify({
        "status": "active", 
        "telegram_token": "SET" if TELEGRAM_TOKEN else "NOT SET",
        "gemini_key": "SET" if GEMINI_API_KEY else "NOT SET"
    })

@app.route('/test-gemini-official', methods=['GET'])
def test_gemini_official():
    """تست با کتابخانه رسمی"""
    test_message = "سلام! لطفاً فقط بگو 'Official Library Works'"
    result = ask_gemini_official(test_message)
    
    return jsonify({
        "method": "official_library",
        "test_message": test_message,
        "response": result,
        "status": "success" if not result.startswith('❌') else "error"
    })

@app.route('/test-gemini-direct', methods=['GET'])
def test_gemini_direct():
    """تست با API مستقیم"""
    test_message = "سلام! لطفاً فقط بگو 'Direct API Works'"
    result = ask_gemini_direct(test_message)
    
    return jsonify({
        "method": "direct_api", 
        "test_message": test_message,
        "response": result,
        "status": "success" if not result.startswith('❌') else "error"
    })

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port)
