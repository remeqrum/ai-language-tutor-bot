import os
import logging
import random
import threading
import requests
from datetime import datetime
from dotenv import load_dotenv
import google.generativeai as genai
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes
from flask import Flask

# Настройки логирования
logging.basicConfig(level=logging.WARNING)

# 1. Загрузка переменных окружения
load_dotenv()
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

NATIVE_LANGUAGE = os.getenv("NATIVE_LANGUAGE", "Русский")
TARGET_LANGUAGE = os.getenv("TARGET_LANGUAGE", "Словацкий")

if not SUPABASE_URL or not SUPABASE_KEY:
    raise ValueError("Missing Supabase credentials in .env")

# 2. Инициализация API Gemini
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-2.15-flash') # gemini-2.5-flash -> Wait, the model is gemini-2.5-flash.
# Let's just fix the prompt
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-2.5-flash')

# 3. Dummy-сервер Flask (для обмана Render Web Service)
app = Flask(__name__)

@app.route('/')
def home():
    return "Bot is alive and running multi-user cloud DB!"

def run_server():
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port, debug=False, use_reloader=False)

# 4. Логика бота
user_states = {}

BASE_PROMPT = f"""
Ты — профессиональный репетитор языка для ученика (уровень B2-C1). 
Твоя задача — общаться с учеником на языке: {NATIVE_LANGUAGE} (объяснять правила, хвалить, указывать на ошибки), а все примеры, слова и задания давать на изучаемом языке: {TARGET_LANGUAGE}.
ОБЯЗАТЕЛЬНО исправляй грамматику и порядок слов, если ученик пишет на изучаемом языке ({TARGET_LANGUAGE}) с ошибкой. 
Всегда выделяй ошибку КАПСОМ (БЕЗ использования звездочек) и коротко объясняй правило.
ИНСТРУКЦИЯ К ФОРМАТИРОВАНИЮ: НИКОГДА НЕ ИСПОЛЬЗУЙ markdown-разметку! Не ставь звездочки (** или *), подчеркивания (_), решетки (#). Выдавай только простой чистый текст, как в обычной SMS.
"""

def clean_md(text):
    return text.replace('*', '').replace('_', '').replace('#', '')

def get_random_words(user_id, limit=3):
    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}"
    }
    try:
        url = f"{SUPABASE_URL}/rest/v1/words?telegram_id=eq.{user_id}&select=*"
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        words = response.json()
        if not words: return []
        random.shuffle(words)
        return words[:limit]
    except Exception as e:
        print(f"Supabase GET Error: {e}")
        return []

def add_word(user_id, word, translation="<из чата>"):
    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "return=minimal"
    }
    data = {
        "telegram_id": user_id,
        "word": word,
        "translation": translation,
        "level": 0
    }
    try:
        url = f"{SUPABASE_URL}/rest/v1/words"
        response = requests.post(url, headers=headers, json=data)
        if response.status_code >= 400:
            print(f"Supabase ERROR REASON: {response.text}")
        response.raise_for_status()
        return True
    except Exception as e:
        print(f"Supabase INSERT Error: {e}")
        return False

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_states[user_id] = "free_chat"
    
    keyboard = [
        [InlineKeyboardButton("🧠 Vocabulary Boost (Старые слова)", callback_data="vocab_boost")],
        [InlineKeyboardButton("🧩 Sentence Builder (Перевод фраз)", callback_data="sentence_builder")],
        [InlineKeyboardButton("🗣️ Добавить слово", callback_data="free_chat")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    msg = (f"Ahoj! Добро пожаловать.\n\n"
           f"Выбирай режим тренировки кнопками ниже, либо просто напиши новое "
           f"слово на изучаемом языке ({TARGET_LANGUAGE}) в чат, и я закину его в твою личную базу.")
           
    if update.message:
        await update.message.reply_text(msg, reply_markup=reply_markup)
    else:
        await update.callback_query.message.reply_text(msg, reply_markup=reply_markup)

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    action = query.data
    
    try:
        if action == "vocab_boost":
            words = get_random_words(user_id, 3)
            if not words:
                await query.message.reply_text("В твоей локальной базе пока нет слов! Скинь мне пару слов в чат.")
                return
                
            word_list = ", ".join([w['word'] for w in words])
            user_states[user_id] = f"vocab_waiting_{word_list}"
            
            prompt = f"{BASE_PROMPT}\n\nПопроси ученика составить ОДНО сложное предложение (уровень B2-C1) НА ИЗУЧАЕМОМ ЯЗЫКЕ ({TARGET_LANGUAGE}), используя сразу все три этих слова: {word_list}."
            resp = model.generate_content(prompt)
            await query.message.reply_text(clean_md(f"🧠 Vocabulary Boost\n\n{resp.text}"))
            
        elif action == "sentence_builder":
            user_states[user_id] = "sentence_waiting"
            prompt = f"{BASE_PROMPT}\n\nПридумай одно сложное предложение на базовом языке ({NATIVE_LANGUAGE}) с продвинутой лексикой. Предложи ученику перевести его НА ИЗУЧАЕМЫЙ ЯЗЫК ({TARGET_LANGUAGE}). Не давай подсказок."
            resp = model.generate_content(prompt)
            await query.message.reply_text(clean_md(f"🧩 Sentence Builder\n\n{resp.text}"))
            
        elif action == "free_chat":
            user_states[user_id] = "free_chat"
            await query.message.reply_text("🗣️ Свободный режим! Пиши слова на добавление в твою личную базу.")
    except Exception as e:
        await query.message.reply_text(f"⚠️ Произошла ошибка связи с Google API: {str(e)[:150]}\nНажми /start и попробуй снова.")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text
    state = user_states.get(user_id, "free_chat")
    
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action='typing')
    
    prompt = None

    if state == "free_chat":
        success = add_word(user_id, text)
        if not success:
            await update.message.reply_text("⚠️ Ошибка: слово не сохранилось в Supabase! Проверь, правильно ли создана таблица с колонкой telegram_id в SQL Editor.")
            return

        prompt = f"{BASE_PROMPT}\n\nУченик только что узнал/написал новое слово на изучаемом языке ({TARGET_LANGUAGE}): '{text}'. Ответь: 1. Дай перевод этого слова на язык ({NATIVE_LANGUAGE}). 2. Приведи сложный пример использования (B2-C1) на изучаемом языке с переводом. 3. Попроси ученика перевести ДРУГУЮ новую фразу НА ИЗУЧАЕМЫЙ ЯЗЫК ({TARGET_LANGUAGE}), используя это же слово."
        user_states[user_id] = "free_chat_waiting" # ЗАПОМИНАЕМ, что ждем перевод от ученика
        
    elif state == "free_chat_waiting":
        prompt = f"{BASE_PROMPT}\n\nТы ранее попросил ученика перевести фразу на изучаемый язык ({TARGET_LANGUAGE}). Вот его ответ: '{text}'. \nЕсли он ответил на родном языке ({NATIVE_LANGUAGE}), мягко скажи, что нужно было перевести на изучаемый язык ({TARGET_LANGUAGE}), и попроси попробовать еще раз.\nЕсли он ответил на изучаемом языке: Проверь правильность, синтаксис. Напиши верный вариант и объясни ошибки на языке {NATIVE_LANGUAGE}. В конце предложи нажать /start."
        user_states[user_id] = "free_chat" # Возвращаем в дефолт
        
    elif state.startswith("vocab_waiting_"):
        expected_words = state.replace("vocab_waiting_", "")
        prompt = f"{BASE_PROMPT}\n\nУченик выполнял Vocabulary Boost со словами: {expected_words}. Вот его ответ НА ИЗУЧАЕМОМ ЯЗЫКЕ ({TARGET_LANGUAGE}): '{text}'. Проверь правильность использования слов, синтаксиса и грамматики. Заставь исправить, если есть ошибки. Предложи /start."
        user_states[user_id] = "free_chat"
        
    elif state == "sentence_waiting":
        prompt = f"{BASE_PROMPT}\n\nУченик переводил фразу с языка {NATIVE_LANGUAGE} на {TARGET_LANGUAGE}: '{text}'. Проверь правильность, обрати особое внимание на порядок слов и предлоги. Оцени ответы на языке {NATIVE_LANGUAGE}, объясни ошибки, дай правильный вариант. Предложи /start."
        user_states[user_id] = "free_chat"

    if prompt:
        try:
            resp = model.generate_content(prompt)
            if not resp.text:
                raise ValueError("Пустой ответ от Gemini (вероятна блокировка по цензуре).")
            reply = clean_md(resp.text)
        except Exception as e:
            reply = f"⚠️ Ошибка ответа нейросети или слишком много запросов: {str(e)[:150]}\nНажми /start."
            user_states[user_id] = "free_chat"
        
        await update.message.reply_text(reply)

if __name__ == '__main__':
    import logging
    log = logging.getLogger('werkzeug')
    log.setLevel(logging.ERROR)
    
    print("REST-клиент Supabase активен. Запуск мультиплеер-бота с защитой от сбоев...")
    threading.Thread(target=run_server, daemon=True).start()
    
    application = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    application.add_handler(CommandHandler('start', start))
    application.add_handler(CallbackQueryHandler(button_callback))
    application.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))
    
    application.run_polling()
