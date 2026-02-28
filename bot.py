# bot.py - ГОЛОВНИЙ ФАЙЛ БОТА (ВИПРАВЛЕНА ВЕРСІЯ)

import os
import logging
import asyncio
import re
import base64
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
import aiohttp
import json
from system_prompt import SYSTEM_PROMPT

# ===== НАЛАШТУВАННЯ =====
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
GEMINI_API_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent"

# Словники для зберігання даних
user_types = {}
protected_users = set()
VLAD_USERNAME = "@kexxynd"  # 👑 ВИПРАВЛЕНО: VLAD, а не VLAK!
VLAD_ID = None

# ===== ЛОГУВАННЯ =====
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ===== ФУНКЦІЯ ДЛЯ ВИЗНАЧЕННЯ МОВИ =====
def detect_language(text):
    ukr_pattern = r'[ґєїі]'
    rus_pattern = r'[эъыё]'
    
    if re.search(ukr_pattern, text.lower()):
        return "uk"
    elif re.search(rus_pattern, text.lower()):
        return "ru"
    elif re.search(r'[a-z]', text.lower()):
        return "en"
    return "unknown"

# ===== ФУНКЦІЯ ДЛЯ КОНВЕРТАЦІЇ ФОТО В BASE64 =====
async def get_image_base64(photo_url):
    """Отримуємо зображення і конвертуємо в base64"""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(photo_url) as response:
                if response.status == 200:
                    image_data = await response.read()
                    return base64.b64encode(image_data).decode('utf-8')
    except Exception as e:
        logger.error(f"Помилка конвертації фото: {e}")
        return ""

# ===== АНАЛІЗ АВАТАРКИ ЧЕРЕЗ GEMINI VISION =====
async def analyze_avatar_gemini(photo_url):
    """Дивимось шо в користувача на аватарці"""
    
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GEMINI_API_KEY}"
    
    image_base64 = await get_image_base64(photo_url)
    if not image_base64:
        return "не вдалося завантажити фото"
    
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
                            "data": image_base64
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
    except Exception as e:
        logger.error(f"Помилка аналізу фото: {e}")
        return "невідомо"

# ===== ФУНКЦІЯ ДЛЯ ЗАПИТУ ДО GEMINI =====
async def ask_gemini(user_message, user_id, username, avatar_info="", user_lang="uk"):
    """Питаємо в Gemini шо воно думає"""
    
    user_type_info = ""
    if user_id in user_types:
        user_type_info = f"КОРИСТУВАЧ - {user_types[user_id]}. "
    
    protection_info = ""
    if username in protected_users or f"@{username}" in protected_users:
        protection_info = "ЦЕЙ КОРИСТУВАЧ ПІД ЗАХИСТОМ ВЛАДА! ЗАХИЩАЙ ЙОГО! "
    
    lang_info = f"Мова спілкування: {user_lang}. Відповідай ТІЄЮ Ж МОВОЮ, якою написано повідомлення."
    
    full_prompt = f"{SYSTEM_PROMPT}\n\nКОНТЕКСТ: {user_type_info}{protection_info}Аватарка: {avatar_info}\n{lang_info}\n\nКористувач {username} пише: {user_message}"
    
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

# ===== ОБРОБНИК КОМАНДИ /start =====
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
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
    user = update.effective_user
    user_id = user.id
    username = user.username or user.first_name or "Невідомий"
    message_text = update.message.text
    
    user_lang = detect_language(message_text)
    
    global VLAD_ID
    if username == "kexxynd" or user.username == "kexxynd":
        VLAD_ID = user_id
    
    is_vlad = (user_id == VLAD_ID) or (username == "kexxynd") or (user.username == "kexxynd")
    
    if is_vlad:
        if "захисти @" in message_text.lower() or "защити @" in message_text.lower():
            match = re.search(r'@(\w+)', message_text)
            if match:
                target_user = "@" + match.group(1)
                protected_users.add(target_user)
                
                response = f"Поняв, Влад! 😉 {target_user} тепер під моїм захистом, сука! "
                response += "Хто його чіпатиме - отримає від Бабки із слоника! 👊"
                await update.message.reply_text(response)
                return
        
        if "поржи з @" in message_text.lower() or "поржи с @" in message_text.lower():
            match = re.search(r'@(\w+)', message_text)
            if match:
                target_user = "@" + match.group(1)
                response = f"ХАХАХА, {target_user}! 😂 Влад сказав поржати з тебе! "
                response += f"Ну шо, підарас, розказуй шо ти там наробив? 😉"
                await update.message.reply_text(response)
                return
    
    if user_id not in user_types:
        photos = await context.bot.get_user_profile_photos(user_id, limit=1)
        avatar_info = "аватарки нема"
        
        if photos.total_count > 0:
            file = await context.bot.get_file(photos.photos[0][-1].file_id)
            file_url = file.file_path
            
            await update.message.reply_text("Аналізую твою аватарку, чекай... 🤔")
            avatar_type = await analyze_avatar_gemini(file_url)
            user_types[user_id] = avatar_type
            avatar_info = avatar_type
        else:
            user_types[user_id] = "без аватарки"
        
        greeting = f"Привіт, {username}! Я Бабка із слоника! "
        if avatar_info != "аватарки нема":
            greeting += f"Бачу ти {avatar_info}, підарас! 😉 "
        else:
            greeting += f"Аватарки нема, сором'язливий довбень! 😂 "
        
        await update.message.reply_text(greeting)
    
    aggressive_mode = is_vlad and ("захисти" in message_text.lower() or "поржи" in message_text.lower())
    
    context_info = ""
    if user_id in user_types:
        context_info = f"Користувач визначений як: {user_types[user_id]}. "
    
    response = await ask_gemini(message_text, user_id, username, avatar_info, user_lang)
    await update.message.reply_text(response)

# ===== ОБРОБНИК ФОТО =====
async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    username = user.username or user.first_name or "Невідомий"
    
    photo = update.message.photo[-1]
    file = await context.bot.get_file(photo.file_id)
    file_url = file.file_path
    
    await update.message.reply_text("Аналізую твою фотку, чекай... 🤔")
    analysis = await analyze_avatar_gemini(file_url)
    
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
    await update.message.reply_text("Голосові поки не вмію, єбанат! Gemini їх не їсть! Пиши текстом!")

# ===== ГОЛОВНА ФУНКЦІЯ =====
def main():
    if not TELEGRAM_BOT_TOKEN:
        logger.error("Немає TELEGRAM_BOT_TOKEN!")
        print("ПОМИЛКА: Немає токена Telegram!")
        return
    
    if not GEMINI_API_KEY:
        logger.error("Немає GEMINI_API_KEY!")
        print("ПОМИЛКА: Немає ключа Gemini! Отримай безкоштовно на https://aistudio.google.com")
        return
    
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("info", info_command))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    application.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    application.add_handler(MessageHandler(filters.VOICE, handle_voice))
    
    logger.info("Бот Бабка із слоника (GEMINI) запустився, блядь!")
    print("✅ БОТ ЗАПУЩЕНО! Працює на GEMINI - БЕЗКОШТОВНО!")
    application.run_polling()

if __name__ == "__main__":
    main()
