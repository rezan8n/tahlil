from flask import Flask, request, jsonify
import requests
import pandas as pd
from io import BytesIO
import os
from dotenv import load_dotenv
import mimetypes
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
DEEPSEEK_API_KEY = os.getenv('DEEPSEEK_API_KEY')

# لاگ برای دیباگ
logger.info("=" * 50)
logger.info("بررسی توکن‌ها:")
logger.info(f"TELEGRAM_TOKEN: {'✅ SET' if TELEGRAM_TOKEN else '❌ NOT SET'}")
logger.info(f"DEEPSEEK_API_KEY: {'✅ SET' if DEEPSEEK_API_KEY else '❌ NOT SET'}")
if DEEPSEEK_API_KEY:
    logger.info(f"پیشوند API Key: {DEEPSEEK_API_KEY[:10]}...")
logger.info("=" * 50)

def ask_deepseek(message, system_prompt=None):
    """DeepSeek API"""
    if not DEEPSEEK_API_KEY:
        return "❌ DeepSeek API Key تنظیم نشده"
    
    url = 'https://api.deepseek.com/v1/chat/completions'
    headers = {
        'Authorization': f'Bearer {DEEPSEEK_API_KEY}',
        'Content-Type': 'application/json'
    }
    
    messages = []
    if system_prompt:
        messages.append({'role': 'system', 'content': system_prompt})
    messages.append({'role': 'user', 'content': message})
    
    payload = {
        'model': 'deepseek-chat',
        'messages': messages,
        'max_tokens': 1000
    }

    try:
        logger.info(f"ارسال درخواست به DeepSeek: {message[:50]}...")
        response = requests.post(url, json=payload, headers=headers, timeout=20)
        
        logger.info(f"DeepSeek Status Code: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            reply = result['choices'][0]['message']['content']
            logger.info(f"✅ پاسخ موفق از DeepSeek")
            return reply
        else:
            error_msg = f"❌ خطا از DeepSeek: {response.status_code} - {response.text}"
            logger.error(error_msg)
            return error_msg
            
    except Exception as e:
        error_msg = f"❌ خطا در اتصال به DeepSeek: {str(e)}"
        logger.error(error_msg)
        return error_msg

def ask_ai(message, system_prompt=None):
    """سیستم هوشمند با fallback"""
    # اول DeepSeek رو امتحان کن
    deepseek_result = ask_deepseek(message, system_prompt)
    if not deepseek_result.startswith('❌'):
        return deepseek_result
    
    # اگر DeepSeek خطا داد، از پاسخ ثابت استفاده کن
    logger.warning("DeepSeek failed, using fallback response")
    return generate_fallback_response(message)

def generate_fallback_response(message):
    """پاسخ fallback برای وقتی که API در دسترس نیست"""
    message_lower = message.lower()
    
    if 'سلام' in message_lower:
        return 'سلام! خوش اومدی! 🙏\n\nمتأسفانه سرویس هوش مصنوعی موقتاً در دسترس نیست، اما می‌تونم فایل‌های اکسل تو رو تحلیل کنم.'
    elif 'تحلیل' in message_lower or 'اکسل' in message_lower:
        return 'می‌تونی فایل اکسل رو برام بفرستی تا تحلیلش کنم 📊\n\nفرمت‌های قابل پشتیبانی:\n• .xls (Excel 97-2003)\n• .xlsx (Excel 2007 به بعد)'
    elif 'help' in message_lower or 'راهنما' in message_lower:
        return '🤖 راهنما:\n\n• فایل اکسل بفرست برای تحلیل فروش\n• سلام کن برای شروع\n• در حال حاضر سرویس پیام‌های متنی موقتاً در دسترس نیست'
    else:
        return '🤖 در حال حاضر سرویس پیام‌های متنی موقتاً در دسترس نیست.\n\nاما می‌تونم فایل‌های اکسل رو تحلیل کنم! فایل اکسل خودت رو بفرست.'

def analyze_excel(df):
    """تحلیل فایل اکسل"""
    try:
        df.columns = df.columns.str.strip()
        # فرض می‌کنیم ستون‌ها به این نام هستند
        if 'جمع کل خالص' in df.columns:
            df['جمع کل خالص'] = df['جمع کل خالص'].replace(',', '', regex=True).astype(float)
            total_sales = df['جمع کل خالص'].sum()
            top_item = df.groupby('شرح کالا')['جمع کل خالص'].sum().idxmax()
            return f'📊 مجموع فروش: {int(total_sales):,} تومان\n🏆 پرفروش‌ترین کالا: {top_item}'
        else:
            return f'📋 فایل اکسل دریافت شد!\nستون‌های موجود: {", ".join(df.columns.tolist())}'
    except Exception as e:
        return f'❌ خطا در تحلیل فایل: {str(e)}'

@app.route('/', methods=['POST'])
def webhook():
    """Webhook اصلی تلگرام"""
    try:
        data = request.get_json()
        logger.info(f"دریافت داده از تلگرام: {data}")
        
        message = data.get('message') or data.get('edited_message') or data.get('callback_query')
        if not message:
            return 'no message', 400

        chat_id = message['chat']['id']
        text = message.get('text', '')
        reply = '❓ پیام نامشخص بود.'

        if message.get('document'):
            # پردازش فایل اکسل
            file_id = message['document']['file_id']
            file_name = message['document']['file_name']
            
            logger.info(f"دریافت فایل: {file_name}")
            
            file_info = requests.get(f'https://api.telegram.org/bot{TELEGRAM_TOKEN}/getFile?file_id={file_id}').json()
            file_path = file_info['result']['file_path']
            file_url = f'https://api.telegram.org/file/bot{TELEGRAM_TOKEN}/{file_path}'
            file_bytes = requests.get(file_url).content

            mime_type = mimetypes.guess_type(file_name)[0]
            df = None

            try:
                if mime_type == 'application/vnd.ms-excel':
                    df = pd.read_excel(BytesIO(file_bytes), engine='xlrd')
                elif mime_type == 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet':
                    df = pd.read_excel(BytesIO(file_bytes), engine='openpyxl')
                else:
                    reply = "❌ فرمت فایل پشتیبانی نمی‌شه. لطفاً فایل اکسل (.xls یا .xlsx) بفرستید."
                    requests.post(f'https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage',
                                  data={'chat_id': chat_id, 'text': reply})
                    return 'ok'
            except Exception as e:
                reply = f"❌ خطا در خواندن فایل: {str(e)}"
                requests.post(f'https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage',
                              data={'chat_id': chat_id, 'text': reply})
                return 'ok'

            if df is not None:
                reply = analyze_excel(df)
        else:
            # پردازش پیام متنی
            reply = ask_ai(text)

        # ارسال پاسخ به کاربر
        requests.post(f'https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage',
                      data={'chat_id': chat_id, 'text': reply})
        return 'ok'
        
    except Exception as e:
        logger.error(f"خطا در webhook: {str(e)}")
        return 'error', 500

@app.route('/', methods=['GET'])
def home():
    return '🤖 ربات فعال است!'

@app.route('/debug', methods=['GET'])
def debug():
    """صفحه دیباگ برای بررسی تنظیمات"""
    debug_info = {
        "status": "active",
        "telegram_token_set": bool(TELEGRAM_TOKEN),
        "deepseek_key_set": bool(DEEPSEEK_API_KEY),
        "deepseek_key_preview": DEEPSEEK_API_KEY[:10] + "..." if DEEPSEEK_API_KEY else "None",
        "message": "بررسی محیط اجرا"
    }
    return jsonify(debug_info)

@app.route('/test', methods=['GET'])
def test():
    """تست ساده"""
    return jsonify({"status": "success", "message": "سرور کار می‌کند!"})

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port)
