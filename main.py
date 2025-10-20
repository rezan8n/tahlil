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
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')

# لاگ برای دیباگ
logger.info("=" * 50)
logger.info("بررسی توکن‌ها:")
logger.info(f"TELEGRAM_TOKEN: {'✅ SET' if TELEGRAM_TOKEN else '❌ NOT SET'}")
logger.info(f"GEMINI_API_KEY: {'✅ SET' if GEMINI_API_KEY else '❌ NOT SET'}")
logger.info("=" * 50)

def ask_gemini(message, system_prompt=None):
    """Google Gemini API - برای همه نوع سوال"""
    if not GEMINI_API_KEY:
        return "❌ Gemini API Key تنظیم نشده"
    
    url = f'https://generativelanguage.googleapis.com/v1/models/gemini-pro:generateContent?key={GEMINI_API_KEY}'
    
    # ساختار پیام برای Gemini
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
            "maxOutputTokens": 2000,
            "topP": 0.8,
            "topK": 40
        }
    }
    
    try:
        logger.info(f"ارسال درخواست به Gemini: {message[:100]}...")
        response = requests.post(url, json=payload, timeout=45)
        
        logger.info(f"Gemini Status Code: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            if 'candidates' in result and len(result['candidates']) > 0:
                if 'content' in result['candidates'][0] and 'parts' in result['candidates'][0]['content']:
                    reply = result['candidates'][0]['content']['parts'][0]['text']
                    logger.info(f"✅ پاسخ موفق از Gemini")
                    return reply
                else:
                    return "❌ ساختار پاسخ Gemini نامعتبر است"
            else:
                return "❌ پاسخی از Gemini دریافت نشد"
        elif response.status_code == 429:
            return "❌ سقف استفاده رایگان تمام شده (60 درخواست/روز). لطفاً فردا مجدد تلاش کنید."
        elif response.status_code == 400:
            error_msg = response.json().get('error', {}).get('message', 'خطای نامشخص')
            return f"❌ خطا در درخواست: {error_msg}"
        else:
            return f"❌ خطا از Gemini: {response.status_code}"
            
    except requests.exceptions.Timeout:
        return "❌ timeout در ارتباط با Gemini"
    except Exception as e:
        return f"❌ خطا در اتصال: {str(e)}"

def detect_intent(text, df=None):
    """تشخیص نیت کاربر"""
    text_lower = text.lower()
    
    # کلمات کلیدی مربوط به تحلیل داده
    data_keywords = [
        'تحلیل', 'آنالیز', 'فروش', 'کالا', 'محصول', 'مشتری', 'داده', 'اکسل',
        'فایل', 'جدول', 'آمار', 'آمارها', 'گزارش', 'نتایج', 'تحلیل کن',
        'چند تا', 'چقدر', 'میانگین', 'مجموع', 'مقدار', 'تعداد'
    ]
    
    # اگر فایل اکسل داریم و سوال مربوط به داده‌هاست
    if df is not None and any(keyword in text_lower for keyword in data_keywords):
        return "data_analysis"
    
    # اگر سوال عمومی است
    return "general_question"

def analyze_data_with_ai(question, df):
    """تحلیل داده‌ها با هوش مصنوعی"""
    try:
        # خلاصه‌ای از داده‌ها برای AI
        data_summary = f"""
        داده‌های موجود:
        - تعداد ردیف‌ها: {len(df)}
        - تعداد ستون‌ها: {len(df.columns)}
        - نام ستون‌ها: {', '.join(df.columns.tolist())}
        - نمونه‌ای از داده‌ها: {df.head(3).to_string()}
        
        سوال کاربر: {question}
        
        لطفاً بر اساس داده‌های فوق به سوال کاربر پاسخ دهید.
        اگر اطلاعات کافی نیست، بگویید چه داده‌ای نیاز دارید.
        """
        
        return ask_gemini(data_summary, "شما یک تحلیل‌گر داده هستید.")
        
    except Exception as e:
        return f"❌ خطا در تحلیل داده: {str(e)}"

def ask_ai(message, df=None):
    """دستیار هوشمند اصلی"""
    
    # تشخیص نیت کاربر
    intent = detect_intent(message, df)
    
    if intent == "data_analysis" and df is not None:
        # تحلیل داده‌های اکسل با AI
        logger.info("تشخیص: تحلیل داده‌های اکسل")
        return analyze_data_with_ai(message, df)
    
    else:
        # سوال عمومی - پاسخ با AI
        logger.info("تشخیص: سوال عمومی")
        
        # پرامپت برای دستیار همه‌کاره
        system_prompt = """
        شما یک دستیار هوشمند و مفید هستید. به کاربر با زبانی دوستانه و محترمانه پاسخ دهید.
        
        ویژگی‌های شما:
        - پاسخ‌های دقیق و مفید
        - زبان فارسی روان و سلیس
        - توضیحات کامل اما مختصر
        - در صورت نیاز، پیشنهادات عملی
        - برای سوالات تخصصی، توضیح ساده و قابل فهم
        
        اگر سوالی خارج از تخصص شماست، صادقانه بگویید و راهنمایی کنید.
        """
        
        result = ask_gemini(message, system_prompt)
        
        # اگر Gemini خطا داد، پاسخ fallback
        if result.startswith('❌'):
            return f"""🤖 سوال جالبی پرسیدی: "{message}"

متأسفانه سرویس هوش مصنوعی در حال حاضر در دسترس نیست. 
اما هنوز می‌تونم فایل‌های اکسل تو رو تحلیل کنم!

📁 فایل اکسل رو برام بفرست تا:
• داده‌هات رو تحلیل کنم
• به سوالاتت در مورد داده‌ها پاسخ بدم
• گزارش‌های مفید برات تهیه کنم"""

        return result

def analyze_excel_basic(df):
    """تحلیل پایه فایل اکسل"""
    try:
        df.columns = df.columns.str.strip()
        
        analysis_parts = []
        analysis_parts.append("📋 فایل اکسل دریافت شد!")
        analysis_parts.append(f"تعداد ردیف‌ها: {len(df):,}")
        analysis_parts.append(f"تعداد ستون‌ها: {len(df.columns)}")
        analysis_parts.append(f"ستون‌ها: {', '.join(df.columns.tolist())}")
        
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

        # ذخیره فایل اکسل برای تحلیل‌های بعدی
        current_df = None

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
                current_df = df
                reply = analyze_excel_basic(df)
                reply += "\n\n💡 حالا می‌تونی در مورد داده‌ها سوال کنی! مثلاً:"
                reply += "\n• 'پرفروش‌ترین کالا کدومه؟'"
                reply += "\n• 'مجموع فروش چقدر شده؟'"
                reply += "\n• 'آمار مشتریان رو بگو'"

        else:
            # پردازش پیام متنی
            reply = ask_ai(text, current_df)

        # ارسال پاسخ به کاربر
        requests.post(f'https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage',
                      data={'chat_id': chat_id, 'text': reply})
        return 'ok'
        
    except Exception as e:
        logger.error(f"خطا در webhook: {str(e)}")
        return 'error', 500

@app.route('/', methods=['GET'])
def home():
    return '🤖 دستیار هوشمند فعال است!'

@app.route('/debug', methods=['GET'])
def debug():
    """صفحه دیباگ"""
    debug_info = {
        "status": "active",
        "telegram_token_set": bool(TELEGRAM_TOKEN),
        "gemini_key_set": bool(GEMINI_API_KEY),
        "message": "دستیار هوشمند کامل فعال است"
    }
    return jsonify(debug_info)

@app.route('/test-ai', methods=['GET'])
def test_ai():
    """تست دستیار هوشمند"""
    test_questions = [
        "سلام! چطوری می‌تونی بهم کمک کنی؟",
        "آیا می‌تونی در مورد هوش مصنوعی توضیح بدی؟",
        "یک داستان کوتاه بنویس"
    ]
    
    results = []
    for question in test_questions:
        result = ask_ai(question)
        results.append({
            "question": question,
            "response": result[:200] + "..." if len(result) > 200 else result
        })
    
    return jsonify({"tests": results})

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port)
