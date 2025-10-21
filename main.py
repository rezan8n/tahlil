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

def ask_gemini(message):
    """ارتباط با Gemini با مدل صحیح"""
    if not GEMINI_API_KEY:
        return "❌ Gemini API Key تنظیم نشده"
    
    # استفاده از مدل‌های جدید Gemini
    url = f'https://generativelanguage.googleapis.com/v1/models/gemini-1.5-flash:generateContent?key={GEMINI_API_KEY}'
    
    payload = {
        "contents": [{
            "parts": [{"text": message}]
        }],
        "generationConfig": {
            "temperature": 0.7,
            "maxOutputTokens": 1000,
        }
    }
    
    try:
        logger.info(f"📤 ارسال به Gemini: {message}")
        response = requests.post(url, json=payload, timeout=30)
        
        logger.info(f"📥 وضعیت: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            if 'candidates' in result and result['candidates']:
                reply = result['candidates'][0]['content']['parts'][0]['text']
                logger.info(f"✅ پاسخ موفق")
                return reply
            else:
                return "❌ ساختار پاسخ نامعتبر"
                
        elif response.status_code == 404:
            return "❌ مدل پیدا نشد. مشکل از نسخه API است."
            
        elif response.status_code == 400:
            error_info = response.json().get('error', {})
            return f"❌ خطای درخواست: {error_info.get('message', 'خطای نامشخص')}"
            
        elif response.status_code == 429:
            return "❌ سقف استفاده روزانه تمام شده"
            
        else:
            return f"❌ خطا: {response.status_code}"
            
    except requests.exceptions.Timeout:
        return "❌ timeout - سرور Gemini پاسخ نداد"
    except Exception as e:
        return f"❌ خطای غیرمنتظره: {str(e)}"

def ask_gemini_pro(message):
    """تلاش با مدل gemini-pro (برای تست)"""
    if not GEMINI_API_KEY:
        return "❌ API Key تنظیم نشده"
    
    url = f'https://generativelanguage.googleapis.com/v1/models/gemini-pro:generateContent?key={GEMINI_API_KEY}'
    
    payload = {
        "contents": [{
            "parts": [{"text": message}]
        }]
    }
    
    try:
        response = requests.post(url, json=payload, timeout=20)
        
        if response.status_code == 200:
            result = response.json()
            return result['candidates'][0]['content']['parts'][0]['text']
        else:
            return f"❌ خطا در gemini-pro: {response.status_code}"
            
    except Exception as e:
        return f"❌ خطا: {str(e)}"

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
            reply = ask_gemini(text)
        
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

@app.route('/test-gemini-flash', methods=['GET'])
def test_gemini_flash():
    """تست با مدل Gemini Flash"""
    test_message = "سلام! لطفاً فقط بگو 'Flash Model Works'"
    result = ask_gemini(test_message)
    
    return jsonify({
        "model": "gemini-1.5-flash",
        "test_message": test_message,
        "response": result,
        "status": "success" if not result.startswith('❌') else "error"
    })

@app.route('/test-gemini-pro', methods=['GET'])
def test_gemini_pro():
    """تست با مدل Gemini Pro"""
    test_message = "سلام! لطفاً فقط بگو 'Pro Model Works'"
    result = ask_gemini_pro(test_message)
    
    return jsonify({
        "model": "gemini-pro", 
        "test_message": test_message,
        "response": result,
        "status": "success" if not result.startswith('❌') else "error"
    })

@app.route('/list-models', methods=['GET'])
def list_models():
    """لیست مدل‌های در دسترس"""
    if not GEMINI_API_KEY:
        return jsonify({"error": "API Key تنظیم نشده"})
    
    url = f'https://generativelanguage.googleapis.com/v1/models?key={GEMINI_API_KEY}'
    
    try:
        response = requests.get(url, timeout=20)
        if response.status_code == 200:
            models = response.json()
            return jsonify({
                "status": "success",
                "models": [model['name'] for model in models.get('models', [])]
            })
        else:
            return jsonify({
                "status": "error",
                "code": response.status_code,
                "message": response.text
            })
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port)
