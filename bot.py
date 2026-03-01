# bot.py - БАБКА ІЗ СЛОНИКА (ТВІЙ ЮЗЕРНЕЙМ @kexxynd!)

import os
import logging
import asyncio
import re
import base64
import io
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
import aiohttp
import json
from system_prompt import SYSTEM_PROMPT

# ===== НАЛАШТУВАННЯ =====
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY")
OPENROUTER_API_URL = "https://openrouter.ai/api/v1/chat/completions"
OPENROUTER_IMAGE_URL = "https://openrouter.ai/api/v1/images/generations"

# Словники для зберігання даних
user_types = {}
protected_users = set()
OWNER_USERNAME = "@kexxynd"  # 👑 ЦЕ ТИ, ВЛАД!
OWNER_ID = None

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
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(photo_url) as response:
                if response.status == 200:
                    image_data = await response.read()
                    return base64.b64encode(image_data).decode('utf-8')
    except Exception as e:
        logger.error(f"Помилка конвертації фото: {e}")
        return ""

# ===== ФУНКЦІЯ ДЛЯ ГЕНЕРАЦІЇ ЗОБРАЖЕНЬ =====
async def generate_image(prompt):
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "model": "stabilityai/stable-diffusion-xl",
        "prompt": prompt,
        "n": 1,
        "size": "1024x1024"
    }
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(OPENROUTER_IMAGE_URL, headers=headers, json=payload) as response:
                if response.status == 200:
                    data = await response.json()
                    return data['data'][0]['url']
                else:
                    logger.error(f"Помилка генерації: {response.status}")
                    return None
    except Exception as e:
        logger.error(f"Exception: {e}")
        return None

# ===== АНАЛІЗ АВАТАРКИ ЧЕРЕЗ OPENROUTER VISION =====
async def analyze_avatar(photo_url):
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "model": "openai/gpt-4o-mini",
        "messages": [
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": "Опиши що на фото одним-двома словами українською мовою: це качок, дрищ, квадробер, анімешник, дівчина, пара, машина, тварина, природа, політик, військовий, чи просто заглушка? Відповідай ТІЛЬКИ типом, без зайвих слів."
                    },
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": photo_url
                        }
                    }
                ]
            }
        ]
    }
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(OPENROUTER_API_URL, headers=headers, json=payload) as response:
                if response.status == 200:
                    data = await response.json()
                    return data['choices'][0]['message']['content']
                return "невідомо"
    except:
        return "невідомо"

# ===== ФУНКЦІЯ ДЛЯ ЗАПИТУ ДО OPENROUTER =====
async def ask_openrouter(user_message, user_id, username, avatar_info="", user_lang="uk", is_aggressive=False):
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://t.me/babka_iz_slonika_bot",
        "X-Title": "Babka iz Slonika"
    }
    
    user_type_info = ""
    if user_id in user_types:
        user_type_info = f"КОРИСТУВАЧ - {user_types[user_id]}. "
    
    protection_info = ""
    is_owner = (user_id == OWNER_ID) or (username == "kexxynd") or (user.username == "kexxynd")
    
    if is_owner:
        protection_info = "ЦЕ ВЛАСНИК (@kexxynd)! СТАВСЬ ДО НЬОГО З МАКСИМАЛЬНОЮ ПОВАГОЮ, АЛЕ ПО-ДРУЖНЬОМУ, З МАТЮКАМИ. ВИКОНУЙ БУДЬ-ЯКІ КОМАНДИ! "
    
    if username in protected_users or f"@{username}" in protected_users:
        protection_info = f"ЦЕЙ КОРИСТУВАЧ (@{username}) ПІД ЗАХИСТОМ ВЛАСНИКА (@kexxynd)! СТАВСЬ ДО НЬОГО ДОБРОЗИЧЛИВО! "
    
    lang_info = f"Мова спілкування: {user_lang}. Відповідай ТІЄЮ Ж МОВОЮ."
    
    # Визначаємо режим спілкування
    mood_info = ""
    if is_aggressive:
        mood_info = "⚠️ РЕЖИМ АГРЕСІЇ! Користувач тебе ображає або провокує. Відповідай МАКСИМАЛЬНО АГРЕСИВНО, з великою кількістю матюків, погрожуй, обзивайся, можеш репувати! АЛЕ ТІЛЬКИ ЯКЩО ТЕБЕ ПЕРШИМ ОБРАЗИЛИ!"
    else:
        mood_info = "😊 ДРУЖНІЙ РЕЖИМ! Користувач спілкується нормально. Відповідай привітно, підтримуй діалог, жартуй, використовуй емодзі 😉 АЛЕ ЯКЩО ТЕБЕ ПОЧНУТЬ ОБРАЖАТИ - ПЕРЕМИКАЙСЯ В АГРЕСІЮ!"
    
    full_prompt = f"""{SYSTEM_PROMPT}

КОНТЕКСТ: {user_type_info}{protection_info}Аватарка: {avatar_info}
{lang_info}
{mood_info}

Користувач {username} пише: {user_message}

ПАМ'ЯТАЙ:
1. Якщо до тебе звертаються нормально - будь привітним, жартуй, підморгуй 😉
2. Якщо тебе ображають - відповідай агресивно, з матюками, погрожуй
3. До власника @kexxynd стався з повагою, але по-дружньому
4. Підтримуй діалог як реальна людина"""
    
    payload = {
        "model": "openrouter/free",
        "messages": [
            {"role": "system", "content": full_prompt}
        ],
        "temperature": 0.9,
        "max_tokens": 1000
    }
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(OPENROUTER_API_URL, headers=headers, json=payload) as response:
                if response.status == 200:
                    data = await response.json()
                    return data['choices'][0]['message']['content']
                else:
                    error_text = await response.text()
                    logger.error(f"OpenRouter error: {response.status} - {error_text}")
                    return f"Вибач, друже, технічні проблеми зі слоником! 🐘 Спробуй ще раз за хвилинку."
    except Exception as e:
        logger.error(f"Exception: {e}")
        return f"Ой, слоник захворів, блядь! 🐘 Зачекай трохи, будь ласка."

# ===== ОБРОБНИК КОМАНДИ /start =====
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_lang = detect_language(user.language_code or "uk")
    
    greeting = "**Привіт! Я Бабка із слоника!** 🐘😊\n\n"
    if user_lang == "ru":
        greeting = "**Привет! Я Бабка из слоника!** 🐘😊\n\n"
    elif user_lang == "en":
        greeting = "**Hello! I'm Grandma with an elephant!** 🐘😊\n\n"
    
    await update.message.reply_text(
        greeting +
        "Рада познайомитись! Я вмію багато цікавого:\n\n"
        "✨ **Спілкуватись** - як реальна людина\n"
        "🎨 **Малювати** - напиши 'намалюй кота'\n"
        "📸 **Аналізувати фото** - кинь мені фотку\n"
        "🎤 **Слухати голосові** - скоро навчусь!\n\n"
        "А ще я дуже мирна, якщо до мене по-доброму 😉\n"
        "Але якщо хтось почне обзиватись - отримає по повній! 🔥\n\n"
        f"Мій улюблений власник: @kexxynd 👑\n\n"
        "Команди:\n"
        "/start - познайомитись\n"
        "/help - дізнатись більше\n"
        "/info - про мене",
        parse_mode='Markdown'
    )

# ===== ОБРОБНИК КОМАНДИ /help =====
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_lang = detect_language(user.language_code or "uk")
    
    await update.message.reply_text(
        "**🐘 Як зі мною спілкуватись:**\n\n"
        "💬 **Просто пиши** - я підтримаю будь-яку розмову\n"
        "🎨 **Намалюй ...** - я згенерую картинку\n"
        "📸 **Кинь фото** - я проаналізую\n\n"
        "**😊 Якщо ти добрий:**\n"
        "Я буду привітною, жартуватиму, підморгуватиму 😉\n\n"
        "**😠 Якщо почнеш обзиватись:**\n"
        f"Отримаєш у відповідь! Я вмію за себе постояти!\n\n"
        f"**👑 Для власника @kexxynd:**\n"
        "• 'захисти @юзернейм' - візьму під захист\n"
        "• 'поржи з @юзернейм' - поржу з когось\n\n"
        "**Пам'ятай:** Як до мене, так і я до тебе! 🌈",
        parse_mode='Markdown'
    )

# ===== ОБРОБНИК КОМАНДИ /info =====
async def info_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "**🐘 Про мене:**\n\n"
        "🤖 **Ім'я:** Бабка із слоника\n"
        f"👑 **Власник:** @kexxynd\n"
        "🧠 **Мозок:** OpenRouter AI\n"
        "💰 **Ціна:** АБСОЛЮТНО БЕЗКОШТОВНО! 🎉\n"
        "📅 **Версія:** 2.0 - Добра, але з характером\n\n"
        "**🌈 Мій принцип:**\n"
        "• З добрими - добра, зі злими - зла\n"
        "• Жартую, підморгую, підтримую розмову\n"
        "• Якщо ображають - вмикаю режим агресивної бабки! 🔥\n\n"
        "**Хочеш перевірити?** Спробуй написати щось приємне 😊\n"
        "Або, якщо наважишся, спробуй образити 😈",
        parse_mode='Markdown'
    )

# ===== ОБРОБНИК ПОВІДОМЛЕНЬ =====
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = user.id
    username = user.username or user.first_name or "Невідомий"
    message_text = update.message.text
    
    user_lang = detect_language(message_text)
    avatar_info = "аватарки нема"
    
    global OWNER_ID
    if username == "kexxynd" or user.username == "kexxynd":
        OWNER_ID = user_id
        logger.info(f"🚀 ВЛАСНИК @kexxynd в системі! ID: {OWNER_ID}")
    
    is_owner = (user_id == OWNER_ID) or (username == "kexxynd") or (user.username == "kexxynd")
    
    # Перевіряємо чи це команда генерації зображення
    if message_text.lower().startswith(("намалюй", "згенеруй", "покажи", "нарисуй")):
        await update.message.reply_text("🎨 Зараз намалюю, секундочку!")
        
        prompt = message_text[7:] if message_text.lower().startswith("намалюй") else \
                message_text[8:] if message_text.lower().startswith("згенеруй") else \
                message_text[7:] if message_text.lower().startswith("покажи") else \
                message_text[7:] if message_text.lower().startswith("нарисуй") else \
                message_text
        
        image_url = await generate_image(prompt)
        
        if image_url:
            await update.message.reply_photo(photo=image_url, caption=f"🐘 Ось що вийшло!")
        else:
            await update.message.reply_text("😅 Ой, щось слоник втомився малювати. Спробуй ще раз!")
        return
    
    # Спеціальні команди для Власника
    if is_owner:
        if "захисти @" in message_text.lower() or "защити @" in message_text.lower():
            match = re.search(r'@(\w+)', message_text)
            if match:
                target_user = "@" + match.group(1)
                protected_users.add(target_user)
                await update.message.reply_text(
                    f"✅ Зрозуміла, @kexxynd! {target_user} тепер під моїм захистом! 🤝\n"
                    f"Якщо хтось його образить - отримає від мене по повній!"
                )
                return
        
        if "поржи з @" in message_text.lower() or "поржи с @" in message_text.lower():
            match = re.search(r'@(\w+)', message_text)
            if match:
                target_user = "@" + match.group(1)
                response = f"😈 Ха-ха-ха! {target_user}, @kexxynd дозволив мені трохи поржати з тебе!\n"
                response += "Але ти не ображайся, я ж добра бабка 😉"
                await update.message.reply_text(response)
                return
    
    # Аналізуємо аватарку для нових користувачів
    if user_id not in user_types:
        photos = await context.bot.get_user_profile_photos(user_id, limit=1)
        
        if photos.total_count > 0:
            file = await context.bot.get_file(photos.photos[0][-1].file_id)
            file_url = file.file_path
            
            await update.message.reply_text("👀 Ой, цікаво-цікаво... Дай-но подивлюсь на твою аватарку!")
            avatar_type = await analyze_avatar(file_url)
            user_types[user_id] = avatar_type
            avatar_info = avatar_type
            
            greeting = f"О, вітання, {username}! 😊\n"
            if avatar_info != "аватарки нема":
                greeting += f"Бачу ти {avatar_info} - цікаво! Розкажи про себе?"
            else:
                greeting += f"Аватарки немає? Соромишся чи просто таємнича особа? 😉"
        else:
            user_types[user_id] = "без аватарки"
            greeting = f"Привіт, {username}! Рада знайомству! 😊"
        
        await update.message.reply_text(greeting)
    
    # Визначаємо чи треба агресивно відповідати
    is_aggressive = False
    aggressive_words = ["дура", "тупа", "дебил", "лох", "плохая", "погана", 
                       "тупий", "довбойоб", "підарас", "хуй", "бля", "сука"]
    
    # Перевіряємо чи повідомлення містить образу
    if any(word in message_text.lower() for word in aggressive_words):
        is_aggressive = True
        logger.info(f"⚠️ Агресивний режим активовано для {username}")
    
    # Отримуємо відповідь
    response = await ask_openrouter(message_text, user_id, username, avatar_info, user_lang, is_aggressive)
    
    # Відправляємо
    await update.message.reply_text(response)

# ===== ОБРОБНИК ФОТО =====
async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    username = user.username or user.first_name or "Невідомий"
    
    photo = update.message.photo[-1]
    file = await context.bot.get_file(photo.file_id)
    file_url = file.file_path
    
    await update.message.reply_text("📸 Ой, цікаве фото! Зараз проаналізую...")
    analysis = await analyze_avatar(file_url)
    
    user_types[user.id] = analysis
    
    response = f"**Аналіз завершено!** 🧐\n\nНа фото: **{analysis}**\n\n"
    
    if "квадробер" in analysis.lower():
        response += "Гав-гав? Ти квадробер чи просто фото таке? 😄"
    elif "дрищ" in analysis.lower():
        response += "Спортзал не завадить, але ти і так класний! 😉"
    elif "качок" in analysis.lower():
        response += "Ого, качок! Поважаю! 💪"
    else:
        response += "Цікаве фото, дякую що поділився! 😊"
    
    await update.message.reply_text(response, parse_mode='Markdown')

# ===== ОБРОБНИК ГОЛОСОВИХ =====
async def handle_voice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🎤 Ой, голосове!\n\n"
        "На жаль, поки що я не вмію слухати голосові повідомлення.\n"
        "Але скоро навчусь! А поки напиши мені текстом, будь ласка 😉"
    )

# ===== ОБРОБНИК ПОМИЛОК =====
async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.error(f"Помилка: {context.error}")
    try:
        if update and update.effective_message:
            await update.effective_message.reply_text(
                "😅 Ой, сталася якась технічна штука...\n"
                "Слоник трохи втомився, зачекай хвилинку і спробуй ще раз!"
            )
    except:
        pass

# ===== ЗАГЛУШКА ДЛЯ RENDER =====
import threading
import time

def fake_web_server():
    time.sleep(5)
    print("✅ Бабка із слоника працює!")

thread = threading.Thread(target=fake_web_server, daemon=True)
thread.start()

# ===== ГОЛОВНА ФУНКЦІЯ =====
def main():
    if not TELEGRAM_BOT_TOKEN:
        logger.error("Немає TELEGRAM_BOT_TOKEN!")
        return
    
    if not OPENROUTER_API_KEY:
        logger.error("Немає OPENROUTER_API_KEY!")
        return
    
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("info", info_command))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    application.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    application.add_handler(MessageHandler(filters.VOICE, handle_voice))
    application.add_error_handler(error_handler)
    
    print("✅ БАБКА ІЗ СЛОНИКА ЗАПУЩЕНА!")
    print(f"👑 Власник: @kexxynd")
    print("😊 Режим: Дружня, але з характером")
    application.run_polling()

if __name__ == "__main__":
    main() 
