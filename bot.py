# bot.py - ГОЛОВНИЙ ФАЙЛ БОТА (ВЕРСІЯ ДЛЯ GEMINI - БЕЗКОШТОВНО!)

import os
import logging
import asyncio
import re
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
import aiohttp
import json
from system_prompt import SYSTEM_PROMPT

# ===== НАЛАШТУВАННЯ =====
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")  # Токен від @BotFather
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")  # Ключ від Google AI Studio
GEMINI_API_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent"

# Словники для зберігання даних
user_types = {}  # типи користувачів
protected_users = set()  # юзери під захистом
VLAK_USERNAME = "@kexxynd"  # юзернейм Влада
VLAK_ID = None  # айді Влада (буде визначено пізніше)

# ===== ЛОГУВАННЯ =====
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ===== ФУНКЦІЯ ДЛЯ ВИЗНАЧЕННЯ МОВИ =====
def detect_language(text):
    """Визначає мову тексту (українська, російська, англійська)"""
    ukr_pattern = r'[ґєїі]'  # українські букви
    rus_pattern = r'[эъыё]'  # російські букви
    
    if re.search(ukr_pattern, text.lower()):
        return "uk"
    elif re.search(rus_pattern, text.lower()):
        return "ru"
    elif re.search(r'[a-z]', text.lower()):
        return "en"
    return "unknown"

# ===== ФУНКЦІЯ ДЛЯ ЗАПИТУ ДО GEMINI =====
async def ask_gemini(user_message, user_id, username, avatar_info="", user_lang="uk"):
    """Питаємо в Gemini шо воно думає (БЕЗКОШТОВНО!)"""
    
    # Визначаємо тип користувача
    user_type_info = ""
    if user_id in user_types:
        user_type_info = f"КОРИСТУВАЧ - {user_types[user_id]}. "
    
    # Перевіряємо чи користувач під захистом
    protection_info = ""
    if username in protected_users or f"@{username}" in protected_users:
        protection_info = "ЦЕЙ КОРИСТУВАЧ ПІД ЗАХИСТОМ ВЛАДА! ЗАХИЩАЙ ЙОГО! "
    
    # Додаємо інформацію про мову
    lang_info = f"Мова спілкування: {user_lang}. Відповідай ТІЄЮ Ж МОВОЮ, якою написано повідомлення."
    
    # Формуємо повний промт
    full_prompt = f"{SYSTEM_PROMPT}\n\nКОНТЕКСТ: {user_type_info}{protection_info}Аватарка: {avatar_info}\n{lang_info}\n\nКористувач {username} пише: {user_message}"
    
    # Gemini API запит
    url = f"{GEMINI_API_URL}?key={GEMINI_API_KEY}"
    
    payload = {
        "contents": [
            {
                "parts": [
                    {
                        "text": full_prompt
                    }
                ]
            }
        ],
        "generationConfig": {
            "temperature": 0.9,
            "maxOutputTokens": 1000,
            "topP": 0.95,
            "topK": 40
        },
        "safetySettings": [
            {
                "category": "HARM_CATEGORY_HARASSMENT",
                "threshold": "BLOCK_NONE"
            },
            {
                "category": "HARM_CATEGORY_HATE_SPEECH",
                "threshold": "BLOCK_NONE"
            },
            {
                "category": "HARM_CATEGORY_SEXUALLY_EXPLICIT",
                "threshold": "BLOCK_NONE"
            },
            {
                "category": "HARM_CATEGORY_DANGEROUS_CONTENT",
                "threshold": "BLOCK_NONE"
            }
        ]
    }
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, headers={"Content-Type": "application/json"}, json=payload) as response:
                if response.status == 200:
                    data = await response.json()
                    if 'candidates' in data and len(data['candidates']) > 0:
                        if 'content' in data['candidates'][0] and 'parts' in data['candidates'][0]['content']:
                            return data['candidates'][0]['content']['parts'][0]['text']
                        else:
                            return "Не вийшло, блядь! Gemini щось не то вернув!"
                    else:
                        return "Gemini мовчить, сука!"
                else:
                    error_text = await response.text()
                    logger.error(f"Gemini error: {response.status} - {error_text}")
                    
                    if "quota" in error_text.lower() or "rate" in error_text.lower():
                        return "Ліміти Gemini вичерпались, єбанат! Зачекай трохи або створи новий ключ!"
                    else:
                        return f"Помилка Gemini: {response.status}, блядь!"
    except Exception as e:
        logger.error(f"Exception: {e}")
        return f"Слоник захворів, сука! Помилка: {str(e)}"

# ===== АНАЛІЗ АВАТАРКИ ЧЕРЕЗ GEMINI VISION =====
async def analyze_avatar_gemini(photo_url):
    """Дивимось шо в користувача на аватарці через Gemini Vision (БЕЗКОШТОВНО!)"""
    
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GEMINI_API_KEY}"
    
    payload = {
        "contents": [
            {
                "parts": [
                    {
                        "text": "Опиши що на фото одним-двома словами українською мовою: це качок, дрищ, квадробер, анімешник, дівчина, пара, машина, тварина, природа, політик, військовий, чи просто заглушка? Відповідай ТІЛЬКИ типом, без зайвих слів."
                    },
                    {
                        "inline_data": {
                            "mime_type": "image/jpeg",
                            "data": await get_image_base64(photo_url)
                        }
                    }
                ]
            }
        ],
        "safetySettings": [
            {
                "category": "HARM_CATEGORY_HARASSMENT",
                "threshold": "BLOCK_NONE"
            },
            {
                "category": "HARM_CATEGORY_HATE_SPEECH",
                "threshold": "BLOCK_NONE"
            }
        ]
    }
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, headers={"Content-Type": "application/json"}, json=payload) as response:
                if response.status == 200:
                    data = await response.json()
                    if 'candidates' in data and len(data['candidates']) > 0:
                        if 'content' in data['candidates'][0] and 'parts' in data['candidates'][0]['content']:
                            return data['candidates'][0]['content']['parts'][0]['text']
                return "невідомо"
    except:
        return "невідомо"

async def get_image_base64(photo_url):
    """Отримуємо зображення і конвертуємо в base64"""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(photo_url) as response:
                if response.status == 200:
                    image_data = await response.read()
                    import base64
                    return base64.b64encode(image_data).decode('utf-8')
    except:
        return ""

# ===== ОБРОБНИК КОМАНДИ /start =====
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Коли користувач натискає /start"""
    user = update.effective_user
    user_lang = detect_language(user.language_code or "uk")
    
    greeting = "**Привіт! Я Бабка із слоника, блядь!** 😉\n\n"
    if user_lang == "ru":
        greeting = "**Привет! Я Бабка из слоника, блядь!** 😉\n\n"
    elif user_lang == "en":
        greeting = "**Hello! I'm Grandma with an elephant, fuck!** 😉\n\n"
    
    await update.message.reply_text(
        greeting +
        "Я вмію все, шо захочеш, друже! Математика, фізика, хімія, "
        "і захист Влада (@kexxynd)!\n\n"
        "Працюю на **GEMINI - БЕЗКОШТОВНО!** 🎉\n\n"
        "Просто пиши шо треба! А якщо Влад попросить захистити когось - я захищу!\n\n"
        "Команди:\n"
        "/start - запуск бота\n"
        "/help - допомога\n"
        "/info - інфа про бота",
        parse_mode='Markdown'
    )

# ===== ОБРОБНИК КОМАНДИ /help =====
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показуємо допомогу"""
    user = update.effective_user
    user_lang = detect_language(user.language_code or "uk")
    
    help_text = "**Допомога від Бабки із слоника:**\n\n"
    if user_lang == "ru":
        help_text = "**Помощь от Бабки из слоника:**\n\n"
    elif user_lang == "en":
        help_text = "**Help from Grandma with an elephant:**\n\n"
    
    await update.message.reply_text(
        help_text +
        "📝 **Текст** - просто пиши шо хочеш, я відповім\n"
        "📸 **Фото** - кинь фото, я проаналізую (Gemini Vision)\n"
        "🔢 **Математика** - напиши рівняння, розв'яжу\n\n"
        "**Спеціальні команди для Влада:**\n"
        "• 'захисти @юзернейм' - я візьму юзера під захист\n"
        "• 'поржи з @юзернейм' - я почну ржати з юзера\n\n"
        "**Важливо:** Якщо образиш Влада (@kexxynd) або його друзів - отримаєш по повній! 👊\n\n"
        "🤖 **Працює на GEMINI - БЕЗКОШТОВНО!**",
        parse_mode='Markdown'
    )

# ===== ОБРОБНИК КОМАНДИ /info =====
async def info_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Інфа про бота"""
    user = update.effective_user
    user_lang = detect_language(user.language_code or "uk")
    
    info_text = "**Інформація про бота:**\n\n"
    if user_lang == "ru":
        info_text = "**Информация о боте:**\n\n"
    elif user_lang == "en":
        info_text = "**Bot information:**\n\n"
    
    await update.message.reply_text(
        info_text +
        "🤖 **Ім'я:** Бабка із слоника\n"
        "👑 **Власник:** @kexxynd (Влад)\n"
        "🧠 **Мозок:** Google Gemini 1.5 Flash\n"
        "💰 **Ціна:** АБСОЛЮТНО БЕЗКОШТОВНО! 🎉\n"
        "👥 **Друзі Влада:** Під захистом\n"
        "📅 **Версія:** 69:420\n"
        "🔥 **Статус:** Найкращий друг\n"
        "🐘 **Слоник:** Завжди готовий\n\n"
        "**Функції:**\n"
        "• Відповіді на будь-які питання\n"
        "• Аналіз фото (Gemini Vision)\n"
        "• Захист друзів Влада\n"
        "• Гноблення ворогів\n"
        "• Підтримка діалогу 😉",
        parse_mode='Markdown'
    )

# ===== ОБРОБНИК ПОВІДОМЛЕНЬ =====
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Головний обробник всього що пишуть"""
    user = update.effective_user
    user_id = user.id
    username = user.username or user.first_name or "Невідомий"
    message_text = update.message.text
    
    # Визначаємо мову
    user_lang = detect_language(message_text)
    
    # Зберігаємо айді Влада при першому повідомленні
    global VLAK_ID
    if username == "kexxynd" or user.username == "kexxynd":
        VLAK_ID = user_id
    
    # Перевіряємо чи це Влад
    is_vlad = (user_id == VLAK_ID) or (username == "kexxynd") or (user.username == "kexxynd")
    
    # Перевіряємо спеціальні команди Влада
    if is_vlad:
        # Команда захисту
        if "захисти @" in message_text.lower() or "защити @" in message_text.lower():
            match = re.search(r'@(\w+)', message_text)
            if match:
                target_user = "@" + match.group(1)
                protected_users.add(target_user)
                
                response = f"Поняв, Влад! 😉 {target_user} тепер під моїм захистом, сука! "
                response += "Хто його чіпатиме - отримає від Бабки із слоника! 👊"
                if user_lang == "ru":
                    response = f"Понял, Влад! 😉 {target_user} теперь под моей защитой, сука! "
                    response += "Кто его тронет - получит от Бабки из слоника! 👊"
                elif user_lang == "en":
                    response = f"Got it, Vlad! 😉 {target_user} is now under my protection, bitch! "
                    response += "Anyone who touches them will get from Grandma with an elephant! 👊"
                
                await update.message.reply_text(response)
                return
        
        # Команда поржати
        if "поржи з @" in message_text.lower() or "поржи с @" in message_text.lower():
            match = re.search(r'@(\w+)', message_text)
            if match:
                target_user = "@" + match.group(1)
                
                response = f"ХАХАХА, {target_user}! 😂 Влад сказав поржати з тебе! "
                response += f"Ну шо, підарас, розказуй шо ти там наробив? 😉"
                if user_lang == "ru":
                    response = f"ХАХАХА, {target_user}! 😂 Влад сказал посмеяться с тебя! "
                    response += f"Ну что, пидорас, рассказывай что ты там натворил? 😉"
                elif user_lang == "en":
                    response = f"HAHAHA, {target_user}! 😂 Vlad said to laugh at you! "
                    response += f"So, fucker, tell us what did you do? 😉"
                
                await update.message.reply_text(response)
                return
    
    # Аналізуємо аватарку для нових користувачів
    if user_id not in user_types:
        photos = await context.bot.get_user_profile_photos(user_id, limit=1)
        avatar_info = "аватарки нема"
        
        if photos.total_count > 0:
            file = await context.bot.get_file(photos.photos[0][-1].file_id)
            file_url = file.file_path
            
            # Аналізуємо через Gemini Vision
            await update.message.reply_text("Аналізую твою аватарку, чекай... 🤔")
            avatar_type = await analyze_avatar_gemini(file_url)
            user_types[user_id] = avatar_type
            avatar_info = avatar_type
        else:
            user_types[user_id] = "без аватарки"
        
        # Вітання з аналізом
        greeting = f"Привіт, {username}! Я Бабка із слоника! "
        if avatar_info != "аватарки нема":
            greeting += f"Бачу ти {avatar_info}, підарас! 😉 "
        else:
            greeting += f"Аватарки нема, сором'язливий довбень! 😂 "
        
        await update.message.reply_text(greeting)
    
    # Визначаємо чи треба агресивно відповідати
    aggressive_mode = is_vlad and ("захисти" in message_text.lower() or "поржи" in message_text.lower())
    
    # Додаємо контекст
    context_info = ""
    if user_id in user_types:
        context_info = f"Користувач визначений як: {user_types[user_id]}. "
    
    # Формуємо повідомлення для AI
    response = await ask_gemini(message_text, user_id, username, avatar_info, user_lang)
    
    # Відправляємо
    await update.message.reply_text(response)

# ===== ОБРОБНИК ФОТО =====
async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Коли кидають фотку"""
    user = update.effective_user
    username = user.username or user.first_name or "Невідомий"
    user_lang = detect_language("uk")  # За замовчуванням
    
    # Отримуємо фото
    photo = update.message.photo[-1]
    file = await context.bot.get_file(photo.file_id)
    file_url = file.file_path
    
    # Аналізуємо
    await update.message.reply_text("Аналізую твою фотку, чекай... 🤔")
    analysis = await analyze_avatar_gemini(file_url)
    
    # Зберігаємо тип
    user_types[user.id] = analysis
    
    response = f"Оце так, {username}! На фото: {analysis}, блядь! 😂 "
    if "квадробер" in analysis.lower():
        response += "ГАВ ГАВ! Іди на вулицю, пес!"
    elif "дрищ" in analysis.lower():
        response += "Їсти треба більше, довбень!"
    elif "качок" in analysis.lower():
        response += "Поважаю, сука! Покачай мене! 💪"
    else:
        response += "Ну ок, підарас, буває! 😉"
    
    await update.message.reply_text(response)

# ===== ОБРОБНИК ГОЛОСОВИХ =====
async def handle_voice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Голосові поки не вміємо"""
    await update.message.reply_text("Голосові поки не вмію, єбанат! Gemini їх не їсть! Пиши текстом!")

# ===== ГОЛОВНА ФУНКЦІЯ =====
def main():
    """Запускаємо бота"""
    # Перевіряємо наявність токенів
    if not TELEGRAM_BOT_TOKEN:
        logger.error("Немає TELEGRAM_BOT_TOKEN!")
        print("ПОМИЛКА: Немає токена Telegram!")
        return
    
    if not GEMINI_API_KEY:
        logger.error("Немає GEMINI_API_KEY!")
        print("ПОМИЛКА: Немає ключа Gemini! Отримай безкоштовно на https://aistudio.google.com")
        return
    
    # Створюємо додаток
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    
    # Додаємо обробники команд
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("info", info_command))
    
    # Додаємо обробники повідомлень
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    application.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    application.add_handler(MessageHandler(filters.VOICE, handle_voice))
    
    # Запускаємо
    logger.info("Бот Бабка із слоника (GEMINI) запустився, блядь!")
    print("✅ БОТ ЗАПУЩЕНО! Працює на GEMINI - БЕЗКОШТОВНО!")
    application.run_polling()

if __name__ == "__main__":
    main()
