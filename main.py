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
    """Google Gemini API"""
    if not GEMINI_API_KEY:
        return "❌ Gemini API Key تنظیم نشده"
    
    url = f'https://generativelanguage.googleapis.com/v1/models/gemini-pro:generateContent?key={GEMINI_API_KEY}'
    
    # ترکیب system prompt با message
    full_message = message
    if system_prompt:
        full_message = f"{system_prompt}\n\nUser: {message}"
    
    payload = {
        "contents": [
            {
                "parts": [
                    {"text": full_message}
                ]
            }
        ],
        "generationConfig": {
            "temperature": 0.7,
            "maxOutputTokens": 1000
        }
    }
    
    try:
        logger.info(f"ارسال درخواست به Gemini: {message[:50]}...")
        response = requests.post(url, json=payload, timeout=30)
        
        logger.info(f"Gemini Status Code: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            if 'candidates' in result and len(result['candidates']) > 0:
                reply = result['candidates'][0]['content']['parts'][0]['text']
                logger.info(f"✅ پاسخ موفق از Gemini: {reply[:100]}...")
                return reply
            else:
                return "❌ ساختار پاسخ Gemini نامعتبر است"
        elif response.status_code == 429:
            return "❌ سقف استفاده رایگان Gemini تمام شده. لطفاً فردا مجدد تلاش کنید."
        else:
            error_msg = f"❌ خطا از Gemini: {response.status_code} - {response.text}"
            logger.error(error_msg)
            return error_msg
            
    except requests.exceptions.Timeout:
        return "❌ timeout در ارتباط با Gemini"
    except Exception as e:
        error_msg = f"❌ خطا در اتصال به Gemini: {str(e)}"
        logger.error(error_msg)
        return error_msg

def ask_ai(message, system_prompt=None):
    """سیستم هوشمند با fallback"""
    gemini_result = ask_gemini(message, system_prompt)
    
    # اگر Gemini جواب داد
    if not gemini_result.startswith('❌'):
        return gemini_result
    
    # اگر Gemini خطا داد، از پاسخ ثابت استفاده کن
    logger.warning("Gemini failed, using fallback response")
    return generate_fallback_response(message)

def generate_fallback_response(message):
    """پاسخ fallback برای وقتی که API در دسترس نیست"""
    message_lower = message.lower()
    
    if 'سلام' in message_lower or 'hello' in message_lower:
        return 'سلام! خوش اومدی! 🙏\n\nمن می‌تونم فایل‌های اکسل تو رو تحلیل کنم. یه فایل اکسل برام بفرست!'
    elif 'تحلیل' in message_lower or 'اکسل' in message_lower or 'excel' in message_lower:
        return '📊 می‌تونی فایل اکسل رو برام بفرستی تا تحلیلش کنم!\n\nفرمت‌های قابل پشتیبانی:\n• .xls (Excel 97-2003)\n• .xlsx (Excel 2007 به بعد)'
    elif 'help' in message_lower or 'راهنما' in message_lower:
        return '🤖 راهنما:\n\n• فایل اکسل بفرست برای تحلیل فروش\n• می‌تونم پرفروش‌ترین کالاها رو پیدا کنم\n• می‌تونم مشتریان بالقوه برای داروهای جدید رو پیشنهاد بدم'
    elif 'تشکر' in message_lower or 'ممنون' in message_lower:
        return 'خوشحالم که مفید بودم! 😊\nاگر سوال دیگه‌ای داری در خدمتم.'
    else:
        return '🤔 متوجه نشدم! می‌تونی:\n• فایل اکسل برام بفرستی\n• یا از من در مورد تحلیل داده‌ها سوال کنی'

def analyze_excel(df):
    """تحلیل فایل اکسل"""
    try:
        df.columns = df.columns.str.strip()
        
        # تحلیل داده‌ها
        analysis_parts = []
        
        # اطلاعات کلی
        analysis_parts.append(f"📋 فایل اکسل دریافت شد!")
        analysis_parts.append(f"تعداد ردیف‌ها: {len(df):,}")
        analysis_parts.append(f"تعداد ستون‌ها: {len(df.columns)}")
        analysis_parts.append(f"ستون‌های موجود: {', '.join(df.columns.tolist())}")
        
        # اگر ستون فروش وجود دارد
        if 'جمع کل خالص' in df.columns:
            try:
                df['جمع کل خالص'] = df['جمع کل خالص'].replace(',', '', regex=True).astype(float)
                total_sales = df['جمع کل خالص'].sum()
                analysis_parts.append(f"📊 مجموع فروش: {int(total_sales):,} تومان")
            except:
                analysis_parts.append("⚠️ ستون 'جمع کل خالص' قابل تحلیل نیست")
        
        # اگر ستون شرح کالا وجود دارد
        if 'شرح کالا' in df.columns:
            try:
                item_counts = df['شرح کالا'].value_counts()
                top_items = item_counts.head(3)
                analysis_parts.append("🏆 پرتکرارترین کالاها:")
                for item, count in top_items.items():
                    analysis_parts.append(f"  • {item}: {count} بار")
            except:
                analysis_parts.append("⚠️ ستون 'شرح کالا' قابل تحلیل نیست")
        
        return '\n'.join(analysis_parts)
        
    except Exception as e:
        return f'❌ خطا در تحلیل فایل: {str(e)}'

def suggest_customers_for_new_drug(drug_name, df):
    """پیشنهاد مشتریان برای داروی جدید"""
    try:
        df.columns = df.columns.str.strip()
        
        # پیدا کردن مشتریانی که کالاهای مشابه خریده‌اند
        similar_rows = df[df['شرح کالا'].str.contains(drug_name.split()[0], case=False, na=False)]
        
        if len(similar_rows) == 0:
            return f"📦 برای داروی '{drug_name}' مشابهی در داده‌ها پیدا نشد."
        
        customers = similar_rows['نام مشتری'].value_counts().head(5).index.tolist()
        
        result = [
            f"📦 داروی جدید: {drug_name}",
            f"🔍 {len(similar_rows)} تراکنش مشابه پیدا شد",
            "👥 مشتریان بالقوه:"
        ]
        
        for i, customer in enumerate(customers, 1):
            result.append(f"  {i}. {customer}")
            
        return '\n'.join(result)
        
    except Exception as e:
        return f"❌ خطا در تحلیل دارو: {str(e)}"

@app.route('/', methods=['POST'])
def webhook():
    """Webhook اصلی تلگرام"""
    try:
        data = request.get_json()
        logger.info(f"دریافت داده از تلگرام")
        
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
                # تشخیص نیت کاربر
                system_prompt = """
                شما یک ربات فروش هوشمند هستید. وظیفه شما تشخیص نیت کاربر از پیام اوست.
                اگر پیام مربوط به تحلیل فروش از فایل اکسل بود، فقط نوع تحلیل را به‌صورت یک کلمه برگردان (مثلاً: مجموع، پرفروش، تاریخ، مشتری، داروی جدید).
                اگر پیام عمومی بود، فقط بنویس: عمومی.
                """
                intent = ask_ai(text, system_prompt).strip().lower()

                if intent == 'عمومی':
                    reply = ask_ai(text)
                elif intent == 'مجموع' or 'فروش' in intent:
                    reply = analyze_excel(df)
                elif intent == 'داروی جدید':
                    drug_name = text.replace('داروی جدید', '').strip()
                    if drug_name:
                        reply = suggest_customers_for_new_drug(drug_name, df)
                    else:
                        reply = "لطفاً نام داروی جدید را بنویسید. مثال: 'داروی جدید پنی سیلین'"
                else:
                    reply = analyze_excel(df)  # تحلیل پیش‌فرض
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
    return '🤖 ربات فعال است! از Google Gemini استفاده می‌کند.'

@app.route('/debug', methods=['GET'])
def debug():
    """صفحه دیباگ برای بررسی تنظیمات"""
    debug_info = {
        "status": "active",
        "telegram_token_set": bool(TELEGRAM_TOKEN),
        "gemini_key_set": bool(GEMINI_API_KEY),
        "gemini_key_preview": GEMINI_API_KEY[:10] + "..." if GEMINI_API_KEY else "None",
        "message": "ربات با Google Gemini فعال است"
    }
    return jsonify(debug_info)

@app.route('/test-gemini', methods=['GET'])
def test_gemini():
    """تست Gemini API"""
    test_message = "سلام، لطفاً فقط بگو 'ربات فعال است'"
    result = ask_gemini(test_message)
    return jsonify({
        "test_message": test_message,
        "gemini_response": result,
        "status": "success" if not result.startswith('❌') else "error"
    })

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port)
