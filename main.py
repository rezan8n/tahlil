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

def get_ai_response(message):
    """پاسخ‌های هوشمند ساده بدون API خارجی"""
    message_lower = message.lower().strip()
    
    # پاسخ‌های از پیش تعریف شده
    responses = {
        'سلام': 'سلام! خوش اومدی! 🤖\nمن یه ربات ساده‌ام که می‌تونه بهت کمک کنه.',
        
        'چطوری': 'خوبم ممنون! 😊\nچطور می‌تونم کمک کنم؟',
        
        'کمک': '''📋 راهنمای ربات:

🤖 **درباره من:**
• یه ربات ساده و مفید
• آماده پاسخ به سوالاتت
• در حال توسعه قابلیت‌های بیشتر

💡 **کارهایی که می‌تونم انجام بدم:**
• پاسخ به سوالات متداول
• ارائه اطلاعات مفید
• راهنمایی در استفاده از ربات

🔜 **به زودی:**
• تحلیل فایل‌های اکسل
• اتصال به هوش مصنوعی
• قابلیت‌های پیشرفته‌تر

سوالت رو بپرس!''',
        
        'خداحافظ': 'خداحافظ! 🙋‍♂️\nامیدوارم مفید بوده باشم.',
        
        'اسمت چیه': 'من یه ربات تلگرامی هستم که دوست دارم به کاربران کمک کنم! 🤖',
        
        'چیکار میتونی بکنی': 'میتونم:\n• راهنمایی کنم\n• اطلاعات مفید بدم\n• به سوالاتت پاسخ بدم\n• و به زودی خیلی چیزای دیگه! 🚀'
    }
    
    # جستجوی پاسخ در دیکشنری
    for key, response in responses.items():
        if key in message_lower:
            return response
    
    # پاسخ پیش‌فرض برای سوالات دیگر
    return f'''🤔 سوال جالبی پرسیدی: "{message}"

در حال حاضر من یک ربات پایه‌ام و قابلیت پاسخ به سوالات پیچیده رو ندارم.

اما می‌تونی ازم بپرسی:
• "کمک" - راهنمای کامل
• "چیکار میتونی بکنی" - قابلیت‌های من

به زودی هوش مصنوعی قدرتمندی به ربات اضافه میشه! 💪'''

@app.route('/', methods=['POST'])
def webhook():
    """وب‌هوک اصلی تلگرام"""
    try:
        data = request.get_json()
        logger.info(f"📩 دریافت از تلگرام: {data}")
        
        message = data.get('message') or data.get('edited_message')
        if not message:
            return 'no message', 400

        chat_id = message['chat']['id']
        text = message.get('text', '')
        
        if text == '/start':
            reply = '''🤖 سلام! به ربات من خوش اومدی!

من در حال حاضر یک ربات پایه‌ام که می‌تونه:
• به سوالات ساده پاسخ بده
• راهنمایی کنه
• اطلاعات مفید ارائه بده

💡 **دستورات سریع:**
"کمک" - راهنمای کامل
"چیکار میتونی بکنی" - قابلیت‌ها

به زودی قابلیت‌های پیشرفته‌تری اضافه میشه! 🚀'''
        else:
            reply = get_ai_response(text)
        
        # ارسال پاسخ به کاربر
        requests.post(
            f'https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage',
            data={'chat_id': chat_id, 'text': reply}
        )
        
        logger.info(f"✅ پاسخ ارسال شد: {reply[:50]}...")
        return 'ok'
        
    except Exception as e:
        logger.error(f"🔥 خطا در وب‌هوک: {str(e)}")
        return 'error', 500

@app.route('/', methods=['GET'])
def home():
    return '🤖 ربات پایه فعال است!'

@app.route('/test', methods=['GET'])
def test():
    """تست سلامت"""
    return jsonify({
        "status": "active", 
        "telegram_token": "SET" if TELEGRAM_TOKEN else "NOT SET",
        "message": "ربات پایه فعال است"
    })

@app.route('/test-response', methods=['GET'])
def test_response():
    """تست سیستم پاسخ‌دهی"""
    test_messages = [
        "سلام",
        "کمک", 
        "چیکار میتونی بکنی",
        "سوال تست"
    ]
    
    results = []
    for msg in test_messages:
        response = get_ai_response(msg)
        results.append({
            "question": msg,
            "response": response[:100] + "..." if len(response) > 100 else response
        })
    
    return jsonify({"tests": results})

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port)
