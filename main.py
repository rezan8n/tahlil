from flask import Flask, request, jsonify
import requests
import os
from dotenv import load_dotenv
import logging
import sys
import json

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

def ask_gemini_new_api(message):
    """استفاده از API جدید Google AI"""
    if not GEMINI_API_KEY:
        return "❌ Gemini API Key تنظیم نشده"
    
    # استفاده از endpoint جدید
    url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash-latest:generateContent"
    
    headers = {
        'Content-Type': 'application/json',
        'x-goog-api-key': GEMINI_API_KEY
    }
    
    data = {
        "contents": [{
            "parts": [{"text": message}]
        }],
        "generationConfig": {
            "temperature": 0.7,
            "maxOutputTokens": 1000,
        }
    }
    
    try:
        logger.info(f"📤 ارسال به Gemini جدید: {message}")
        response = requests.post(url, json=data, headers=headers, timeout=30)
        
        logger.info(f"📥 وضعیت: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            if 'candidates' in result and result['candidates']:
                reply = result['candidates'][0]['content']['parts'][0]['text']
                logger.info("✅ پاسخ از API جدید دریافت شد")
                return reply
            else:
                return "❌ ساختار پاسخ نامعتبر"
                
        else:
            error_info = response.json().get('error', {})
            error_msg = error_info.get('message', 'خطای نامشخص')
            return f"❌ خطا: {response.status_code} - {error_msg}"
            
    except Exception as e:
        return f"❌ خطا در ارتباط: {str(e)}"

def ask_gemini_old_api(message):
    """استفاده از API قدیمی برای تست"""
    if not GEMINI_API_KEY:
        return "❌ Gemini API Key تنظیم نشده"
    
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-pro:generateContent?key={GEMINI_API_KEY}"
    
    data = {
        "contents": [{
            "parts": [{"text": message}]
        }]
    }
    
    try:
        response = requests.post(url, json=data, timeout=20)
        
        if response.status_code == 200:
            result = response.json()
            return result['candidates'][0]['content']['parts'][0]['text']
        else:
            return f"❌ خطا در API قدیمی: {response.status_code}"
            
    except Exception as e:
        return f"❌ خطا: {str(e)}"

def get_available_models():
    """دریافت لیست مدل‌های در دسترس"""
    if not GEMINI_API_KEY:
        return []
    
    url = "https://generativelanguage.googleapis.com/v1beta/models"
    headers = {'x-goog-api-key': GEMINI_API_KEY}
    
    try:
        response = requests.get(url, headers=headers, timeout=20)
        if response.status_code == 200:
            models_data = response.json()
            return [model['name'] for model in models_data.get('models', [])]
        return []
    except:
        return []

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
            reply = '''🤖 سلام! من یک چت‌بات هوشمندم.

در حال تست اتصال به سرویس‌های هوش مصنوعی هستم.

لطفاً کمی صبر کن...'''
        else:
            # استفاده از API جدید
            reply = ask_gemini_new_api(text)
            
            # اگر خطا داد، از پاسخ ثابت استفاده کن
            if reply.startswith('❌'):
                reply = f'''🤖 سوال جالبی پرسیدی: "{text}"

در حال حاضر سرویس هوش مصنوعی در دسترس نیست.

اما به زودی این قابلیت اضافه خواهد شد!'''
        
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
    return '🤖 چت‌بات در حال توسعه'

@app.route('/test-new-api', methods=['GET'])
def test_new_api():
    """تست API جدید"""
    test_message = "سلام! لطفاً فقط بگو 'API New Works'"
    result = ask_gemini_new_api(test_message)
    
    return jsonify({
        "api_version": "v1beta (new)",
        "model": "gemini-1.5-flash-latest", 
        "test_message": test_message,
        "response": result,
        "status": "success" if not result.startswith('❌') else "error"
    })

@app.route('/test-old-api', methods=['GET'])
def test_old_api():
    """تست API قدیمی"""
    test_message = "سلام! لطفاً فقط بگو 'API Old Works'"
    result = ask_gemini_old_api(test_message)
    
    return jsonify({
        "api_version": "v1beta (old)",
        "model": "gemini-pro",
        "test_message": test_message, 
        "response": result,
        "status": "success" if not result.startswith('❌') else "error"
    })

@app.route('/list-models', methods=['GET'])
def list_models():
    """لیست مدل‌های در دسترس"""
    models = get_available_models()
    return jsonify({
        "status": "success" if models else "error",
        "available_models": models
    })

@app.route('/debug', methods=['GET'])
def debug():
    """صفحه دیباگ"""
    return jsonify({
        "status": "active",
        "telegram_token_set": bool(TELEGRAM_TOKEN),
        "gemini_key_set": bool(GEMINI_API_KEY),
        "message": "سیستم پایه فعال است"
    })

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port)
