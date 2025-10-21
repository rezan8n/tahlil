from flask import Flask, request, jsonify
import requests
import pandas as pd
from io import BytesIO
import os
from dotenv import load_dotenv
import mimetypes
import logging
import sys
import time

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

# دیکشنری برای ذخیره آخرین فایل هر کاربر
user_sessions = {}

def ask_gemini_simple(message):
    """نسخه ساده‌تر برای تست"""
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
        logger.info(f"ارسال درخواست به Gemini: {message}")
        response = requests.post(url, json=payload, timeout=20)
        
        logger.info(f"Status Code: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            if 'candidates' in result and result['candidates']:
                reply = result['candidates'][0]['content']['parts'][0]['text']
                logger.info(f"✅ پاسخ: {reply}")
                return reply
            else:
                return "❌ ساختار پاسخ نامعتبر"
        else:
            error_msg = f"❌ خطا: {response.status_code}"
            if response.text:
                error_msg += f" - {response.text}"
            return error_msg
            
    except Exception as e:
        return f"❌ خطا: {str(e)}"

def get_user_session(chat_id):
    """دریافت یا ایجاد سشن کاربر"""
    if chat_id not in user_sessions:
        user_sessions[chat_id] = {
            'current_df': None,
            'last_activity': time.time(),
            'file_name': None
        }
    return user_sessions[chat_id]

def analyze_data_with_ai(question, df, file_name):
    """تحلیل داده‌ها با هوش مصنوعی"""
    try:
        # خلاصه ساده از داده‌ها
        data_info = f"""
        کاربر این سوال را پرسیده: {question}

        داده‌های فایل {file_name}:
        - تعداد سطرها: {len(df)}
        - تعداد ستون‌ها: {len(df.columns)} 
        - ستون‌ها: {', '.join(df.columns.tolist())}

        لطفاً با توجه به این داده‌ها پاسخ دهید.
        اگر اطلاعات کافی نیست، بگویید چه داده‌ای نیاز است.
        """
        
        return ask_gemini_simple(data_info)
        
    except Exception as e:
        return f"❌ خطا در تحلیل داده: {str(e)}"

def ask_ai(message, chat_id):
    """دستیار هوشمند"""
    session = get_user_session(chat_id)
    
    # اگر کاربر فایل دارد و سوال مربوط به داده‌هاست
    if session['current_df'] is not None:
        data_keywords = ['تحلیل', 'فروش', 'کالا', 'مشتری', 'داده', 'اکسل', 'چقدر', 'چند', 'کدوم', 'آمار']
        message_lower = message.lower()
        
        if any(keyword in message_lower for keyword in data_keywords):
            logger.info(f"تحلیل داده برای کاربر {chat_id}")
            return analyze_data_with_ai(message, session['current_df'], session['file_name'])
    
    # سوال عمومی
    result = ask_gemini_simple(message)
    
    if result.startswith('❌'):
        # پاسخ fallback
        if session['current_df'] is not None:
            return f"""📊 در حال کار بر روی فایل: {session['file_name']}

می‌تونی در مورد این فایل سوال بپرسی:
• "پرفروش‌ترین کالا چیه؟"
• "مجموع فروش چقدره؟" 
• "آمار مشتریان رو بگو"

یا هر سوال عمومی‌ای داری بپرس!"""
        else:
            return """🤖 به ربات خوش اومدی!

می‌تونی:
📁 فایل اکسل بفرستی تا تحلیلش کنم
💬 سوالات متنی ازم بپرسی

فایل اکسل رو بفرست یا سوالت رو بپرس!"""
    
    return result

def analyze_excel_basic(df, file_name):
    """تحلیل پایه فایل اکسل"""
    try:
        df.columns = df.columns.str.strip()
        
        analysis = [
            f"📋 فایل '{file_name}' دریافت شد!",
            f"تعداد ردیف‌ها: {len(df):,}",
            f"تعداد ستون‌ها: {len(df.columns)}",
            "",
            "📊 ستون‌ها:",
        ]
        
        for i, col in enumerate(df.columns.tolist(), 1):
            analysis.append(f"{i}. {col}")
            
        analysis.extend([
            "",
            "💡 حالا می‌تونی در مورد داده‌ها سوال کنی:",
            "• 'پرفروش‌ترین کالا کدومه؟'",
            "• 'مجموع فروش چقدر شده؟'", 
            "• 'آمار مشتریان رو بگو'",
            "• 'تعداد تراکنش‌ها چقدره؟'"
        ])
        
        return '\n'.join(analysis)
        
    except Exception as e:
        return f'❌ خطا در تحلیل فایل: {str(e)}'

@app.route('/', methods=['POST'])
def webhook():
    """Webhook اصلی تلگرام"""
    try:
        data = request.get_json()
        logger.info(f"دریافت داده از تلگرام")
        
        message = data.get('message') or data.get('edited_message')
        if not message:
            return 'no message', 400

        chat_id = message['chat']['id']
        text = message.get('text', '')
        reply = '❓ پیام نامشخص بود.'

        session = get_user_session(chat_id)

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
                    reply = "❌ لطفاً فایل اکسل (.xls یا .xlsx) بفرستید."
                    requests.post(f'https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage',
                                  data={'chat_id': chat_id, 'text': reply})
                    return 'ok'
            except Exception as e:
                reply = f"❌ خطا در خواندن فایل: {str(e)}"
                requests.post(f'https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage',
                              data={'chat_id': chat_id, 'text': reply})
                return 'ok'

            if df is not None:
                session['current_df'] = df
                session['file_name'] = file_name
                session['last_activity'] = time.time()
                reply = analyze_excel_basic(df, file_name)

        else:
            # پردازش پیام متنی
            reply = ask_ai(text, chat_id)

        # ارسال پاسخ
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
    """صفحه دیباگ"""
    debug_info = {
        "status": "active",
        "telegram_token_set": bool(TELEGRAM_TOKEN),
        "gemini_key_set": bool(GEMINI_API_KEY),
        "active_sessions": len(user_sessions),
        "message": "سیستم آماده است"
    }
    return jsonify(debug_info)

@app.route('/test-gemini', methods=['GET'])
def test_gemini():
    """تست Gemini API"""
    test_message = "سلام! لطفاً فقط بگو 'ربات فعال است'"
    result = ask_gemini_simple(test_message)
    
    return jsonify({
        "test_message": test_message,
        "gemini_response": result,
        "status": "success" if not result.startswith('❌') else "error",
        "gemini_key_set": bool(GEMINI_API_KEY)
    })

@app.route('/test-simple', methods=['GET'])
def test_simple():
    """تست ساده"""
    return jsonify({
        "status": "active",
        "message": "سرور کار می‌کند",
        "timestamp": time.time()
    })

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port)
