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

def ask_gemini(message, system_prompt=None):
    """Google Gemini API"""
    if not GEMINI_API_KEY:
        return "❌ Gemini API Key تنظیم نشده"
    
    url = f'https://generativelanguage.googleapis.com/v1/models/gemini-pro:generateContent?key={GEMINI_API_KEY}'
    
    contents = []
    if system_prompt:
        contents.append({
            "parts": [{"text": system_prompt}],
            "role": "user"
        })
    
    contents.append({
        "parts": [{"text": message}],
        "role": "user"
    })
    
    payload = {
        "contents": contents,
        "generationConfig": {
            "temperature": 0.7,
            "maxOutputTokens": 2000
        }
    }
    
    try:
        logger.info(f"ارسال درخواست به Gemini: {message[:100]}...")
        response = requests.post(url, json=payload, timeout=45)
        
        if response.status_code == 200:
            result = response.json()
            if 'candidates' in result and len(result['candidates']) > 0:
                if 'content' in result['candidates'][0] and 'parts' in result['candidates'][0]['content']:
                    reply = result['candidates'][0]['content']['parts'][0]['text']
                    return reply
        elif response.status_code == 429:
            return "❌ سقف استفاده رایگان تمام شده. لطفاً فردا مجدد تلاش کنید."
        
        return f"❌ خطا از Gemini: {response.status_code}"
            
    except Exception as e:
        return f"❌ خطا در اتصال: {str(e)}"

def get_user_session(chat_id):
    """دریافت یا ایجاد سشن کاربر"""
    if chat_id not in user_sessions:
        user_sessions[chat_id] = {
            'current_df': None,
            'last_activity': time.time(),
            'file_name': None
        }
    return user_sessions[chat_id]

def cleanup_old_sessions():
    """پاک کردن سشن‌های قدیمی (24 ساعت)"""
    current_time = time.time()
    expired_users = []
    
    for chat_id, session in user_sessions.items():
        if current_time - session['last_activity'] > 24 * 60 * 60:  # 24 ساعت
            expired_users.append(chat_id)
    
    for chat_id in expired_users:
        del user_sessions[chat_id]
        logger.info(f"سشن کاربر {chat_id} پاک شد")

def analyze_data_with_ai(question, df, file_name):
    """تحلیل داده‌ها با هوش مصنوعی"""
    try:
        # خلاصه‌ای از داده‌ها برای AI
        data_summary = f"""
        کاربر یک سوال درباره داده‌های اکسل دارد:

        مشخصات فایل: {file_name}
        تعداد ردیف‌ها: {len(df)}
        تعداد ستون‌ها: {len(df.columns)}
        نام ستون‌ها: {', '.join(df.columns.tolist())}
        
        نمونه‌ای از داده‌ها (3 ردیف اول):
        {df.head(3).to_string()}

        سوال کاربر: {question}

        لطفاً بر اساس داده‌های فوق به سوال کاربر پاسخ دقیق و مفید دهید.
        اگر اطلاعات کافی در داده‌ها نیست، صادقانه بگویید.
        از اعداد و ارقام دقیق استفاده کنید.
        """
        
        system_prompt = """
        شما یک تحلیل‌گر داده حرفه‌ای هستید. وظیفه شما تحلیل داده‌های اکسل و پاسخ به سوالات کاربر است.

        ویژگی‌های شما:
        - پاسخ‌های دقیق بر اساس داده‌ها
        - استفاده از اعداد و ارقام واقعی
        - توضیحات واضح و قابل فهم
        - پیشنهادات عملی برای تحلیل بیشتر

        اگر سوال کاربر نیاز به محاسبه خاصی دارد، آن را انجام دهید.
        اگر داده‌ها ناقص هستند، صادقانه بیان کنید.
        """
        
        return ask_gemini(data_summary, system_prompt)
        
    except Exception as e:
        return f"❌ خطا در تحلیل داده: {str(e)}"

def ask_ai(message, chat_id):
    """دستیار هوشمند با در نظر گرفتن سشن کاربر"""
    session = get_user_session(chat_id)
    session['last_activity'] = time.time()
    
    # اگر کاربر فایل اکسل دارد
    if session['current_df'] is not None:
        df = session['current_df']
        file_name = session['file_name']
        
        # کلمات کلیدی مربوط به تحلیل داده
        data_keywords = [
            'تحلیل', 'آنالیز', 'فروش', 'کالا', 'محصول', 'مشتری', 'داده', 'اکسل',
            'فایل', 'جدول', 'آمار', 'گزارش', 'نتایج', 'تحلیل کن', 'چند تا', 
            'چقدر', 'میانگین', 'مجموع', 'مقدار', 'تعداد', 'کدوم', 'چه', 'چگونه',
            'نمایش', 'نشان', 'بگو', 'بفرما', 'محاسبه', 'محاسبه کن'
        ]
        
        message_lower = message.lower()
        
        # اگر سوال مربوط به داده‌هاست
        if any(keyword in message_lower for keyword in data_keywords):
            logger.info(f"تحلیل داده برای کاربر {chat_id}")
            return analyze_data_with_ai(message, df, file_name)
        
        # اگر کاربر می‌خواهد فایل جدید بفرستد
        if any(word in message_lower for word in ['فایل جدید', 'اکسل جدید', 'فایل دیگه']):
            session['current_df'] = None
            session['file_name'] = None
            return "✅ فایل قبلی پاک شد. می‌تونی فایل اکسل جدید رو برام بفرستی."
    
    # سوال عمومی
    system_prompt = """
    شما یک دستیار هوشمند و مفید هستید. به زبان فارسی روان و سلیس پاسخ دهید.
    
    اگر کاربر سوالی درباره داده‌های اکسل دارد اما فایلی ارسال نکرده است، 
    به او یادآوری کنید که ابتدا فایل اکسل را ارسال کند.
    """
    
    result = ask_gemini(message, system_prompt)
    
    # اگر Gemini خطا داد
    if result.startswith('❌'):
        if session['current_df'] is not None:
            return f"""🤔 سوال جالبی پرسیدی!

برای تحلیل داده‌ها، می‌تونی سوالاتت رو در مورد فایل "{session['file_name']}" بپرسی.

مثلاً:
• "پرفروش‌ترین کالا کدومه؟"
• "مجموع فروش چقدر شده؟" 
• "آمار مشتریان رو بگو"

یا اگر می‌خوای فایل جدید بفرستی، بگو: "فایل جدید" """
        else:
            return f"""🤖 سوال جالبی پرسیدی: "{message}"

برای استفاده از قابلیت تحلیل داده‌ها، لطفاً اول یک فایل اکسل برام بفرست.

پس از ارسال فایل، می‌تونی هر سوالی در مورد داده‌هات ازم بپرسی!"""

    return result

def analyze_excel_basic(df, file_name):
    """تحلیل پایه فایل اکسل"""
    try:
        df.columns = df.columns.str.strip()
        
        analysis_parts = []
        analysis_parts.append(f"📋 فایل '{file_name}' دریافت شد!")
        analysis_parts.append(f"تعداد ردیف‌ها: {len(df):,}")
        analysis_parts.append(f"تعداد ستون‌ها: {len(df.columns)}")
        analysis_parts.append(f"📊 ستون‌های موجود:")
        
        for i, col in enumerate(df.columns.tolist(), 1):
            analysis_parts.append(f"  {i}. {col}")
        
        analysis_parts.append("\n💡 حالا می‌تونی در مورد این داده‌ها ازم سوال کنی!")
        analysis_parts.append("مثلاً:")
        analysis_parts.append("• 'پرفروش‌ترین کالا کدومه؟'")
        analysis_parts.append("• 'مجموع فروش چقدر شده؟'")
        analysis_parts.append("• 'آمار مشتریان رو بگو'")
        analysis_parts.append("• 'تعداد تراکنش‌ها چقدره؟'")
        
        return '\n'.join(analysis_parts)
        
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

        # دریافت سشن کاربر
        session = get_user_session(chat_id)
        session['last_activity'] = time.time()

        if message.get('document'):
            # پردازش فایل اکسل
            file_id = message['document']['file_id']
            file_name = message['document']['file_name']
            
            logger.info(f"دریافت فایل از کاربر {chat_id}: {file_name}")
            
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
                # ذخیره فایل در سشن کاربر
                session['current_df'] = df
                session['file_name'] = file_name
                session['last_activity'] = time.time()
                
                reply = analyze_excel_basic(df, file_name)

        else:
            # پردازش پیام متنی
            reply = ask_ai(text, chat_id)

        # پاکسازی سشن‌های قدیمی
        cleanup_old_sessions()

        # ارسال پاسخ به کاربر
        requests.post(f'https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage',
                      data={'chat_id': chat_id, 'text': reply})
        return 'ok'
        
    except Exception as e:
        logger.error(f"خطا در webhook: {str(e)}")
        return 'error', 500

@app.route('/', methods=['GET'])
def home():
    return '🤖 دستیار هوشمند با حافظه جلسه فعال است!'

@app.route('/debug', methods=['GET'])
def debug():
    """صفحه دیباگ"""
    cleanup_old_sessions()
    debug_info = {
        "status": "active",
        "telegram_token_set": bool(TELEGRAM_TOKEN),
        "gemini_key_set": bool(GEMINI_API_KEY),
        "active_sessions": len(user_sessions),
        "active_users": list(user_sessions.keys())
    }
    return jsonify(debug_info)

@app.route('/test-session', methods=['GET'])
def test_session():
    """تست سشن"""
    test_chat_id = 12345
    session = get_user_session(test_chat_id)
    session['current_df'] = "TEST_DF"
    session['file_name'] = "test.xlsx"
    
    return jsonify({
        "session_created": True,
        "chat_id": test_chat_id,
        "file_name": session['file_name']
    })

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port)
