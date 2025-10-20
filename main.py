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
    
    # ساختار پیام
    full_message = message
    if system_prompt:
        full_message = f"{system_prompt}\n\n{message}"
    
    payload = {
        "contents": [{
            "parts": [{"text": full_message}]
        }],
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
                logger.info(f"✅ پاسخ موفق از Gemini")
                return reply
            else:
                return "❌ ساختار پاسخ Gemini نامعتبر است"
        elif response.status_code == 429:
            return "❌ سقف استفاده رایگان تمام شده (60 درخواست/روز)"
        else:
            return f"❌ خطا از Gemini: {response.status_code}"
            
    except Exception as e:
        return f"❌ خطا در اتصال به Gemini: {str(e)}"

def ask_ai(message, system_prompt=None):
    """سیستم پاسخ‌دهی هوشمند"""
    message_lower = message.lower().strip()
    
    # تشخیص نیت کاربر و پاسخ هوشمند
    if message_lower in ['سلام', 'hello', 'hi', 'سلامی', 'salam']:
        return 'سلام! خوش اومدی! 🙏\nمن ربات تحلیل فایل‌های اکسل هستم.\nمی‌تونی فایل اکسل رو برام بفرستی یا از راهنما استفاده کنی.'
    
    elif any(word in message_lower for word in ['چطوری', 'حالت', 'چخبر', 'خوبی']):
        return 'خوبم ممنون! 😊\nآماده‌ام که فایل اکسلتو تحلیل کنم.'
    
    elif any(word in message_lower for word in ['تحلیل', 'آنالیز', 'analys']):
        return '📊 می‌تونی فایل اکسل رو برام بفرستی تا:\n• جمع فروش رو محاسبه کنم\n• پرفروش‌ترین کالاها رو پیدا کنم\n• مشتریان بالقوه رو شناسایی کنم'
    
    elif any(word in message_lower for word in ['فروش', 'sale', 'فروش']):
        return '💰 برای تحلیل فروش، فایل اکسل حاوی اطلاعات فروش رو برام بفرست.'
    
    elif any(word in message_lower for word in ['کالا', 'محصول', 'product', 'item']):
        return '🏆 می‌تونم پرفروش‌ترین کالاها رو از فایل اکسلت پیدا کنم.'
    
    elif any(word in message_lower for word in ['مشتری', 'customer', 'client']):
        return '👥 برای شناسایی مشتریان بالقوه، فایل اکسل رو برام بفرست.'
    
    elif any(word in message_lower for word in ['دارو', 'داروی جدید', 'drug', 'medicine']):
        if 'داروی جدید' in message_lower:
            drug_name = message.replace('داروی جدید', '').strip()
            if drug_name:
                return f'💊 برای داروی "{drug_name}" می‌تونم مشتریان بالقوه رو پیدا کنم. فایل اکسل رو برام بفرست.'
            else:
                return '💊 نام داروی جدید رو بنویس تا مشتریان بالقوه رو پیشنهاد بدم.\nمثال: "داروی جدید پنی سیلین"'
        else:
            return '💊 در مورد داروها می‌تونم کمک کنم. از "داروی جدید" استفاده کن.'
    
    elif any(word in message_lower for word in ['کمک', 'راهنما', 'help', 'راهنمایی']):
        return '''🤖 راهنمای ربات:

📁 **ارسال فایل اکسل:**
• فایل اکسل فروش رو بفرست تا خودکار تحلیل کنم

💬 **دستورات متنی:**
• "تحلیل فروش" - اطلاعات کلی
• "پرفروش‌ترین کالا" - کالاهای پرطرفدار  
• "داروی جدید [نام]" - مشتریان بالقوه

🎯 **کارهایی که می‌تونم انجام بدم:**
• محاسبه جمع فروش
• پیدا کردن پرفروش‌ترین کالاها
• شناسایی مشتریان بالقوه
• تحلیل داده‌های دارویی

فایل اکسلت رو بفرست شروع کنیم! 📊'''
    
    elif any(word in message_lower for word in ['تشکر', 'ممنون', 'مرسی', 'thanks', 'thank you']):
        return 'خوشحالم که مفید بودم! 😊\nاگر سوال دیگه‌ای داری در خدمتم.'
    
    elif any(word in message_lower for word in ['خداحافظ', 'بای', 'bye', 'goodbye']):
        return 'خداحافظ! 🙋‍♂️\nاگر فایل اکسل داری، خوشحال می‌شم تحلیلش کنم.'
    
    else:
        # برای سوالات دیگر، از Gemini استفاده کن
        gemini_result = ask_gemini(message, system_prompt)
        if not gemini_result.startswith('❌'):
            return gemini_result
        else:
            return f'''🤔 سوال جالبی پرسیدی!

در حال حاضر سرویس پاسخ به سوالات متنی موقتاً در دسترس نیست. اما می‌تونم:

📊 فایل اکسلتو تحلیل کنم
💰 گزارش فروش برات تهیه کنم  
🏆 پرفروش‌ترین کالاها رو پیدا کنم
👥 مشتریان بالقوه رو شناسایی کنم

فایل اکسلت رو برام بفرست یا از "راهنما" استفاده کن!'''

def analyze_excel(df):
    """تحلیل فایل اکسل"""
    try:
        df.columns = df.columns.str.strip()
        
        analysis_parts = []
        analysis_parts.append("📋 فایل اکسل دریافت شد!")
        analysis_parts.append(f"تعداد ردیف‌ها: {len(df):,}")
        analysis_parts.append(f"تعداد ستون‌ها: {len(df.columns)}")
        analysis_parts.append(f"ستون‌ها: {', '.join(df.columns.tolist())}")
        
        # تحلیل ستون‌های خاص
        if 'جمع کل خالص' in df.columns:
            try:
                df['جمع کل خالص'] = df['جمع کل خالص'].replace(',', '', regex=True).astype(float)
                total_sales = df['جمع کل خالص'].sum()
                analysis_parts.append(f"💰 مجموع فروش: {int(total_sales):,} تومان")
            except:
                analysis_parts.append("⚠️ ستون 'جمع کل خالص' قابل تحلیل نیست")
        
        if 'شرح کالا' in df.columns:
            try:
                top_items = df['شرح کالا'].value_counts().head(3)
                analysis_parts.append("🏆 پرتکرارترین کالاها:")
                for item, count in top_items.items():
                    analysis_parts.append(f"  • {item}: {count} بار")
            except:
                pass
        
        if 'نام مشتری' in df.columns:
            try:
                top_customers = df['نام مشتری'].value_counts().head(3)
                analysis_parts.append("👥 پرتکرارترین مشتریان:")
                for customer, count in top_customers.items():
                    analysis_parts.append(f"  • {customer}: {count} بار")
            except:
                pass
        
        return '\n'.join(analysis_parts)
        
    except Exception as e:
        return f'❌ خطا در تحلیل فایل: {str(e)}'

def suggest_customers_for_new_drug(drug_name, df):
    """پیشنهاد مشتریان برای داروی جدید"""
    try:
        df.columns = df.columns.str.strip()
        
        # پیدا کردن مشتریان مرتبط
        similar_rows = df[df['شرح کالا'].str.contains(drug_name.split()[0], case=False, na=False)]
        
        if len(similar_rows) == 0:
            return f"📦 برای داروی '{drug_name}' مشابهی در داده‌ها پیدا نشد."
        
        customers = similar_rows['نام مشتری'].value_counts().head(5).index.tolist()
        
        result = [
            f"💊 داروی جدید: {drug_name}",
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
        
        message = data.get('message') or data.get('edited_message')
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
                # تشخیص نیت کاربر از متن
                if 'داروی جدید' in text.lower():
                    drug_name = text.replace('داروی جدید', '').strip()
                    if drug_name:
                        reply = suggest_customers_for_new_drug(drug_name, df)
                    else:
                        reply = "لطفاً نام داروی جدید را بنویسید. مثال: 'داروی جدید پنی سیلین'"
                else:
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
    """صفحه دیباگ"""
    debug_info = {
        "status": "active",
        "telegram_token_set": bool(TELEGRAM_TOKEN),
        "gemini_key_set": bool(GEMINI_API_KEY),
        "message": "ربات با پاسخ‌های هوشمند فعال است"
    }
    return jsonify(debug_info)

@app.route('/test-gemini', methods=['GET'])
def test_gemini():
    """تست Gemini API"""
    test_message = "سلام، لطفاً فقط بگو 'API فعال است'"
    result = ask_gemini(test_message)
    return jsonify({
        "test_message": test_message,
        "gemini_response": result,
        "status": "success" if not result.startswith('❌') else "error"
    })

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port)
