from flask import Flask, request
import requests
import pandas as pd
from io import BytesIO
import os
from dotenv import load_dotenv

load_dotenv()
app = Flask(__name__)

TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')

def ask_chatgpt(message, system_prompt=None):
    url = 'https://api.openai.com/v1/chat/completions'
    headers = {'Authorization': f'Bearer ' + OPENAI_API_KEY}
    messages = []
    if system_prompt:
        messages.append({'role': 'system', 'content': system_prompt})
    messages.append({'role': 'user', 'content': message})
    payload = {'model': 'gpt-3.5-turbo', 'messages': messages}
    response = requests.post(url, json=payload, headers=headers)
    return response.json()['choices'][0]['message']['content']

def analyze_excel(file_bytes):
    df = pd.read_excel(BytesIO(file_bytes))
    df.columns = df.columns.str.strip()
    df['جمع کل خالص'] = df['جمع کل خالص'].replace(',', '', regex=True).astype(float)

    total_sales = df['جمع کل خالص'].sum()
    top_item = df.groupby('شرح کالا')['جمع کل خالص'].sum().idxmax()
    return f'📊 مجموع فروش: {int(total_sales):,} تومان\n🏆 پرفروش‌ترین کالا: {top_item}'

def suggest_customers_for_new_drug(drug_name, df):
    df.columns = df.columns.str.strip()
    system_prompt = "شما یک تحلیل‌گر دارویی هستید. وظیفه شما تشخیص کاربرد داروی جدید و یافتن داروهای مشابه است."
    description = ask_chatgpt(f"داروی جدید: {drug_name}", system_prompt)
    similar_rows = df[df['شرح کالا'].str.contains(drug_name.split()[0], case=False, na=False)]
    customers = similar_rows['نام مشتری'].value_counts().head(5).index.tolist()
    return f"📦 داروی جدید: {drug_name}\n🔍 مشابه‌ها: {description}\n👥 مشتریان بالقوه:\n" + "\n".join(customers)

@app.route('/', methods=['POST'])
def webhook():
    data = request.get_json()
    if not data or 'message' not in data:
        return 'no message', 400

    chat_id = data['message']['chat']['id']
    text = data['message'].get('text', '')
    reply = '❓ پیام نامشخص بود.'

    if 'document' in data['message']:
        file_id = data['message']['document']['file_id']
        file_info = requests.get(f'https://api.telegram.org/bot{TELEGRAM_TOKEN}/getFile?file_id={file_id}').json()
        file_path = file_info['result']['file_path']
        file_url = f'https://api.telegram.org/file/bot{TELEGRAM_TOKEN}/{file_path}'
        file_bytes = requests.get(file_url).content
        df = pd.read_excel(BytesIO(file_bytes))

        system_prompt = """
        شما یک ربات فروش هوشمند هستید. وظیفه شما تشخیص نیت کاربر از پیام اوست.
        اگر پیام مربوط به تحلیل فروش از فایل اکسل بود، فقط نوع تحلیل را به‌صورت یک کلمه برگردان (مثلاً: مجموع، پرفروش، تاریخ، مشتری، داروی جدید).
        اگر پیام عمومی بود، فقط بنویس: عمومی.
        """
        intent = ask_chatgpt(text, system_prompt).strip()

        if intent == 'عمومی':
            reply = ask_chatgpt(text)
        elif intent == 'مجموع':
            reply = analyze_excel(file_bytes)
        elif intent == 'داروی جدید':
            reply = suggest_customers_for_new_drug(text, df)
        else:
            reply = '❓ نیت شما مشخص نشد. لطفاً واضح‌تر بنویسید.'
    else:
        reply = ask_chatgpt(text)

    requests.post(f'https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage',
                  data={'chat_id': chat_id, 'text': reply})
    return 'ok'

@app.route('/', methods=['GET'])
def home():
    return 'Bot is running'

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port)
