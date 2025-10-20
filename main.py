from flask import Flask, request
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

# بارگذاری environment variables
load_dotenv()

app = Flask(__name__)

TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
DEEPSEEK_API_KEY = os.getenv('DEEPSEEK_API_KEY')  # تغییر نام متغیر

# لاگ برای بررسی توکن‌ها
logger.info(f"TELEGRAM_TOKEN تنظیم شده: {bool(TELEGRAM_TOKEN)}")
logger.info(f"DEEPSEEK_API_KEY تنظیم شده: {bool(DEEPSEEK_API_KEY)}")
if DEEPSEEK_API_KEY:
    logger.info(f"پیشوند API Key: {DEEPSEEK_API_KEY[:10]}...")

def ask_deepseek(message, system_prompt=None):
    """استفاده از DeepSeek API به جای OpenAI"""
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
        'max_tokens': 1000,
        'stream': False
    }

    try:
        logger.info(f"ارسال درخواست به DeepSeek: {message[:100]}...")
        
        response = requests.post(url, json=payload, headers=headers, timeout=30)
        
        # لاگ کامل پاسخ
        logger.info(f"DeepSeek Status Code: {response.status_code}")
        
        if response.status_code != 200:
            error_msg = f"HTTP {response.status_code}: {response.text}"
            logger.error(f"خطای DeepSeek: {error_msg}")
            return f"❌ خطا از سمت DeepSeek: {error_msg}"
            
        result = response.json()
        logger.info(f"DeepSeek Response: {result}")
        
        if 'choices' in result and len(result['choices']) > 0:
            reply = result['choices'][0]['message']['content']
            logger.info(f"پاسخ موفق از DeepSeek: {reply[:100]}...")
            return reply
        elif 'error' in result:
            error_msg = result['error'].get('message', 'خطای نامشخص')
            logger.error(f"خطای DeepSeek API: {error_msg}")
            return f"❌ خطا از سمت DeepSeek: {error_msg}"
        else:
            logger.error("پاسخ نامعتبر از DeepSeek")
            return "❌ پاسخ نامعتبر از DeepSeek دریافت شد."
            
    except requests.exceptions.Timeout:
        logger.error("Timeout در ارتباط با DeepSeek")
        return "❌ timeout در ارتباط با DeepSeek"
    except Exception as e:
        logger.error(f"خطا در اتصال به DeepSeek: {str(e)}")
        return f"❌ خطا در اتصال به DeepSeek: {str(e)}"

def analyze_excel(df):
    df.columns = df.columns.str.strip()
    df['جمع کل خالص'] = df['جمع کل خالص'].replace(',', '', regex=True).astype(float)
    total_sales = df['جمع کل خالص'].sum()
    top_item = df.groupby('شرح کالا')['جمع کل خالص'].sum().idxmax()
    return f'📊 مجموع فروش: {int(total_sales):,} تومان\n🏆 پرفروش‌ترین کالا: {top_item}'

def suggest_customers_for_new_drug(drug_name, df):
    df.columns = df.columns.str.strip()
    system_prompt = "شما یک تحلیل‌گر دارویی هستید. وظیفه شما تشخیص کاربرد داروی جدید و یافتن داروهای مشابه است."
    description = ask_deepseek(f"داروی جدید: {drug_name}", system_prompt)
    similar_rows = df[df['شرح کالا'].str.contains(drug_name.split()[0], case=False, na=False)]
    customers = similar_rows['نام مشتری'].value_counts().head(5).index.tolist()
    return f"📦 داروی جدید: {drug_name}\n🔍 مشابه‌ها: {description}\n👥 مشتریان بالقوه:\n" + "\n".join(customers)

@app.route('/', methods=['POST'])
def webhook():
    data = request.get_json()
    message = data.get('message') or data.get('edited_message') or data.get('callback_query')
    if not message:
        return 'no message', 400

    chat_id = message['chat']['id']
    text = message.get('text', '')
    reply = '❓ پیام نامشخص بود.'

    if message.get('document') and 'file_id' in message['document']:
        file_id = message['document']['file_id']
        file_name = message['document']['file_name']
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
                reply = (
                    "❌ فرمت فایل اکسل قابل شناسایی نیست.\n"
                    "لطفاً فایل را با یکی از فرمت‌های زیر ارسال کنید:\n"
                    "• ‎.xls (Excel 97-2003)\n"
                    "• ‎.xlsx (Excel 2007 به بعد)"
                )
                requests.post(f'https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage',
                              data={'chat_id': chat_id, 'text': reply})
                return 'ok'
        except Exception:
            reply = (
                "❌ خطا در خواندن فایل اکسل.\n"
                "ممکن است فایل خراب باشد یا فرمت آن پشتیبانی نشود.\n"
                "لطفاً فایل را با یکی از فرمت‌های زیر ارسال کنید:\n"
                "• ‎.xls (Excel 97-2003)\n"
                "• ‎.xlsx (Excel 2007 به بعد)"
            )
            requests.post(f'https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage',
                          data={'chat_id': chat_id, 'text': reply})
            return 'ok'

        if df is not None:
            system_prompt = """
            شما یک ربات فروش هوشمند هستید. وظیفه شما تشخیص نیت کاربر از پیام اوست.
            اگر پیام مربوط به تحلیل فروش از فایل اکسل بود، فقط نوع تحلیل را به‌صورت یک کلمه برگردان (مثلاً: مجموع، پرفروش، تاریخ، مشتری، داروی جدید).
            اگر پیام عمومی بود، فقط بنویس: عمومی.
            """
            intent = ask_deepseek(text, system_prompt).strip()

            if intent == 'عمومی':
                reply = ask_deepseek(text)
            elif intent == 'مجموع':
                reply = analyze_excel(df)
            elif intent == 'داروی جدید':
                reply = suggest_customers_for_new_drug(text, df)
            else:
                reply = '❓ نیت شما مشخص نشد. لطفاً واضح‌تر بنویسید.'
    else:
        reply = ask_deepseek(text)

    requests.post(f'https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage',
                  data={'chat_id': chat_id, 'text': reply})
    return 'ok'

@app.route('/', methods=['GET'])
def home():
    return 'Bot is running'

@app.route('/test')
def test():
    """Endpoint برای تست DeepSeek"""
    test_message = "سلام، این یک تست است. لطفاً پاسخ بده 'تست موفق'"
    result = ask_deepseek(test_message)
    return {
        "status": "success",
        "test_result": result,
        "deepseek_key_prefix": DEEPSEEK_API_KEY[:10] + "..." if DEEPSEEK_API_KEY else "Not set"
    }

@app.route('/env-check')
def env_check():
    """بررسی تنظیمات محیطی"""
    return {
        "telegram_token_set": bool(TELEGRAM_TOKEN),
        "deepseek_key_set": bool(DEEPSEEK_API_KEY),
        "deepseek_key_prefix": DEEPSEEK_API_KEY[:10] + "..." if DEEPSEEK_API_KEY else "Not set"
    }

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port)
