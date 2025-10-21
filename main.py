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
# استفاده مستقیم از API Key برای تست
GEMINI_API_KEY = "AIzaSyC9GffwbFXMLR_oHhdYwlnsyOs8I3YDbyc"

def test_gemini_detailed():
    """تست دقیق Gemini با لاگ کامل"""
    models = [
        "gemini-1.5-flash",
        "gemini-1.5-flash-latest", 
        "gemini-1.5-pro",
        "gemini-pro"
    ]
    
    results = []
    
    for model in models:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
        headers = {
            'Content-Type': 'application/json',
            'x-goog-api-key': GEMINI_API_KEY
        }
        
        data = {
            "contents": [{
                "parts": [{"text": "سلام! لطفاً فقط بگو 'موفق'"}]
            }]
        }
        
        try:
            logger.info(f"🔍 تست مدل: {model}")
            response = requests.post(url, json=data, headers=headers, timeout=15)
            
            result = {
                "model": model,
                "status_code": response.status_code,
                "success": False
            }
            
            if response.status_code == 200:
                response_data = response.json()
                if 'candidates' in response_data and response_data['candidates']:
                    reply = response_data['candidates'][0]['content']['parts'][0]['text']
                    result["success"] = True
                    result["response"] = reply
                    logger.info(f"✅ {model} - موفق: {reply}")
                else:
                    result["error"] = "ساختار پاسخ نامعتبر"
                    logger.error(f"❌ {model} - ساختار پاسخ نامعتبر")
            else:
                error_info = response.json().get('error', {})
                result["error"] = error_info.get('message', 'خطای نامشخص')
                logger.error(f"❌ {model} - خطا: {result['error']}")
                
        except Exception as e:
            result = {
                "model": model,
                "status_code": 0,
                "success": False,
                "error": str(e)
            }
            logger.error(f"🔥 {model} - خطای ارتباط: {str(e)}")
        
        results.append(result)
    
    return results

def ask_gemini_simple(message):
    """ساده‌ترین نسخه Gemini"""
    url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent"
    headers = {
        'Content-Type': 'application/json',
        'x-goog-api-key': GEMINI_API_KEY
    }
    
    data = {
        "contents": [{
            "parts": [{"text": message}]
        }]
    }
    
    try:
        response = requests.post(url, json=data, headers=headers, timeout=20)
        
        if response.status_code == 200:
            result = response.json()
            return result['candidates'][0]['content']['parts'][0]['text']
        else:
            return f"❌ خطا: {response.status_code} - {response.text}"
            
    except Exception as e:
        return f"❌ خطای ارتباط: {str(e)}"

@app.route('/', methods=['POST'])
def webhook():
    """وب‌هوک اصلی"""
    try:
        data = request.get_json()
        logger.info("📩 دریافت از تلگرام")
        
        message = data.get('message') or data.get('edited_message')
        if not message:
            return 'no message', 400

        chat_id = message['chat']['id']
        text = message.get('text', '')
        
        if text == '/start':
            reply = '''🤖 به ربات تست Gemini خوش اومدی!

دستورات:
/test - تست کامل API
/simple [متن] - تست ساده
/status - وضعیت'''
            
        elif text == '/test':
            reply = "🔍 در حال تست API... لطفاً صبر کن"
            # تست کامل در پس‌زمینه
            test_results = test_gemini_detailed()
            
            # ساخت گزارش
            report = ["📊 نتیجه تست Gemini API:"]
            for result in test_results:
                if result["success"]:
                    report.append(f"✅ {result['model']}: موفق")
                else:
                    report.append(f"❌ {result['model']}: {result.get('error', 'خطا')}")
            
            reply = "\n".join(report)
            
        elif text.startswith('/simple '):
            user_message = text.replace('/simple ', '')
            reply = ask_gemini_simple(user_message)
            
        elif text == '/status':
            reply = f"""🔧 وضعیت سرویس:
            
API Key: {'✅ تنظیم شده' if GEMINI_API_KEY else '❌ تنظیم نشده'}
تلگرام: {'✅ فعال' if TELEGRAM_TOKEN else '❌ غیرفعال'}

برای تست از /test استفاده کن"""
            
        else:
            reply = ask_gemini_simple(text)
        
        requests.post(
            f'https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage',
            data={'chat_id': chat_id, 'text': reply}
        )
        
        return 'ok'
        
    except Exception as e:
        logger.error(f"خطا در وب‌هوک: {str(e)}")
        return 'error', 500

@app.route('/', methods=['GET'])
def home():
    return '🤖 ربات تست Gemini فعال است'

@app.route('/api-test', methods=['GET'])
def api_test():
    """تست API از طریق مرورگر"""
    results = test_gemini_detailed()
    return jsonify({"test_results": results})

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port)
