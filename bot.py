# bot.py - БАБКА ІЗ СЛОНИКА (KIE.AI ULTRA - ШВИДКА ТА РОЗУМНА)

import os
import logging
import asyncio
import re
import base64
import io
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from telegram.ext import AIORateLimiter  # 👈 Додаємо для швидкості!
import aiohttp
import json
from system_prompt import SYSTEM_PROMPT

# ===== НАЛАШТУВАННЯ =====
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
KIE_AI_API_KEY = os.environ.get("KIE_AI_API_KEY")  # 👈 ТВІЙ КЛЮЧ KIE.AI!

# API ендпоінти KIE.AI [citation:1][citation:6]
KIE_AI_API_URL = "https://api.kie.ai/v1/chat/completions"  # Для тексту
KIE_AI_IMAGE_URL = "https://api.kie.ai/v1/images/generations"  # Для картинок

# Словники для зберігання даних
user_types = {}
protected_users = set()
OWNER_USERNAME = "@kexxynd"  # 👑 ЦЕ ТИ!
OWNER_ID = None

# Кеш для аватарок (щоб не аналізувати кожен раз)
avatar_cache = {}

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

# ===== ФУНКЦІЯ ДЛЯ ГЕНЕРАЦІЇ ЗОБРАЖЕНЬ ЧЕРЕЗ KIE.AI =====
async def generate_image_kie(prompt):
    """Генерація зображень через Kie.ai (швидко та якісно!) [citation:1]"""
    headers = {
        "Authorization": f"Bearer {KIE_AI_API_KEY}",
        "Content-Type": "application/json"
    }
    
    # Використовуємо GPT-4o Image модель від Kie.ai [citation:1]
    payload = {
        "model": "gpt-4o-image",  # Спеціальна модель для картинок!
        "prompt": prompt,
        "n": 1,
        "size": "1024x1024",
        "quality": "standard"  # Баланс швидкості та якості
    }
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(KIE_AI_IMAGE_URL, headers=headers, json=payload) as response:
                if response.status == 200:
                    data = await response.json()
                    return data['data'][0]['url']
                else:
                    error_text = await response.text()
                    logger.error(f"Помилка генерації Kie.ai: {response.status} - {error_text}")
                    
                    # Перевіряємо чи це помилка лімітів
                    if "insufficient_quota" in error_text or "credits" in error_text.lower():
                        return "rate_limit"
                    return None
    except Exception as e:
        logger.error(f"Exception в generate_image_kie: {e}")
        return None

# ===== АНАЛІЗ АВАТАРКИ ЧЕРЕЗ KIE.AI =====
async def analyze_avatar_kie(photo_url):
    """Аналіз фото через Kie.ai з кешуванням"""
    
    # Перевіряємо кеш (щоб не витрачати ліміти)
    if photo_url in avatar_cache:
        return avatar_cache[photo_url]
    
    headers = {
        "Authorization": f"Bearer {KIE_AI_API_KEY}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "model": "gpt-4o-mini",  # Швидка модель для аналізу
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
            async with session.post(KIE_AI_API_URL, headers=headers, json=payload) as response:
                if response.status == 200:
                    data = await response.json()
                    result = data['choices'][0]['message']['content']
                    avatar_cache[photo_url] = result  # Зберігаємо в кеш
                    return result
                return "невідомо"
    except:
        return "невідомо"

# ===== ФУНКЦІЯ ДЛЯ ЗАПИТУ ДО KIE.AI =====
async def ask_kie_ai(user_message, user_id, username, avatar_info="", user_lang="uk", is_aggressive=False):
    """Швидкі відповіді через Kie.ai"""
    
    headers = {
        "Authorization": f"Bearer {KIE_AI_API_KEY}",
        "Content-Type": "application/json",
        "X-Title": "Babka iz Slonika"
    }
    
    user_type_info = ""
    if user_id in user_types:
        user_type_info = f"КОРИСТУВАЧ - {user_types[user_id]}. "
    
    protection_info = ""
    is_owner = (user_id == OWNER_ID) or (username == "kexxynd") or (user.username == "kexxynd")
    
    if is_owner:
        protection_info = "ЦЕ ВЛАСНИК (@kexxynd)! СТАВСЬ ДО НЬОГО З МАКСИМАЛЬНОЮ ПОВАГОЮ, АЛЕ ПО-ДРУЖНЬОМУ. ВИКОНУЙ БУДЬ-ЯКІ КОМАНДИ! "
    
    if username in protected_users or f"@{username}" in protected_users:
        protection_info = f"ЦЕЙ КОРИСТУВАЧ (@{username}) ПІД ЗАХИСТОМ ВЛАСНИКА (@kexxynd)! СТАВСЬ ДО НЬОГО ДОБРОЗИЧЛИВО! "
    
    lang_info = f"Мова спілкування: {user_lang}. Відповідай ТІЄЮ Ж МОВОЮ."
    
    # Визначаємо режим спілкування
    mood_info = ""
    if is_aggressive:
        mood_info = "⚠️ РЕЖИМ АГРЕСІЇ! Користувач тебе ображає або провокує. Відповідай АГРЕСИВНО, з матюками, погрожуй! АЛЕ ТІЛЬКИ ЯКЩО ТЕБЕ ПЕРШИМ ОБРАЗИЛИ!"
    else:
        mood_info = "😊 ДРУЖНІЙ РЕЖИМ! Користувач спілкується нормально. Відповідай привітно, підтримуй діалог, жартуй, використовуй емодзі 😉"
    
    full_prompt = f"""{SYSTEM_PROMPT}

КОНТЕКСТ: {user_type_info}{protection_info}Аватарка: {avatar_info}
{lang_info}
{mood_info}

Користувач {username} пише: {user_message}

ПАМ'ЯТАЙ:
1. Якщо до тебе звертаються нормально - будь привітним
2. Якщо тебе ображають - відповідай агресивно
3. До власника @kexxynd стався з повагою, по-дружньому
4. Підтримуй діалог як реальна людина"""
    
    # Використовуємо швидку модель [citation:1]
    payload = {
        "model": "gpt-4o-mini",  # Найшвидша модель!
        "messages": [
            {"role": "system", "content": full_prompt}
        ],
        "temperature": 0.8,  # Трохи зменшили для швидкості
        "max_tokens": 800
    }
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(KIE_AI_API_URL, headers=headers, json=payload) as response:
                if response.status == 200:
                    data = await response.json()
                    return data['choices'][0]['message']['content']
                else:
                    error_text = await response.text()
                    logger.error(f"Kie.ai error: {response.status} - {error_text}")
                    
                    # Якщо Kie.ai не працює, пробуємо OpenRouter як запасний
                    return await ask_openrouter_fallback(user_message, user_id, username, avatar_info, user_lang, is_aggressive)
    except Exception as e:
        logger.error(f"Exception: {e}")
        return f"Ой, слоник захворів, блядь! 🐘 Зачекай трохи, будь ласка."

# ===== ЗАПАСНА ФУНКЦІЯ ДЛЯ OPENROUTER =====
async def ask_openrouter_fallback(user_message, user_id, username, avatar_info="", user_lang="uk", is_aggressive=False):
    """Запасний варіант через OpenRouter якщо Kie.ai ліміти вичерпано"""
    
    OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY")
    if not OPENROUTER_API_KEY:
        return "Вибач, друже, всі AI слоники втомились... Спробуй пізніше!"
    
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "model": "openrouter/free",
        "messages": [
            {"role": "system", "content": user_message}
        ]
    }
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post("https://openrouter.ai/api/v1/chat/completions", headers=headers, json=payload) as response:
                if response.status == 200:
                    data = await response.json()
                    return data['choices'][0]['message']['content']
    except:
        return "😅 Технічні проблеми, зачекай трохи!"

# ===== ОБРОБНИК КОМАНДИ /start =====
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_lang = detect_language(user.language_code or "uk")
    
    greeting = "**🐘 Привіт! Я Бабка із слоника!**\n\n"
    if user_lang == "ru":
        greeting = "**🐘 Привет! Я Бабка из слоника!**\n\n"
    elif user_lang == "en":
        greeting = "**🐘 Hello! I'm Grandma with an elephant!**\n\n"
    
    await update.message.reply_text(
        greeting +
        "Рада познайомитись! Я стала **НАБАГАТО ШВИДШОЮ** з Kie.ai! ⚡\n\n"
        "✨ **Спілкуватись** - як реальна людина\n"
        "🎨 **Малювати** - напиши 'намалюй кота'\n"
        "📸 **Аналізувати фото** - кинь мені фотку\n"
        "👥 **В групах** - спілкуюсь першою!\n\n"
        f"👑 Мій власник: {OWNER_USERNAME}\n\n"
        "Команди:\n"
        "/start - познайомитись\n"
        "/help - дізнатись більше\n"
        "/info - про мене",
        parse_mode='Markdown'
    )

# ===== ОБРОБНИК КОМАНДИ /help =====
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "**🐘 Як зі мною спілкуватись:**\n\n"
        "💬 **Просто пиши** - я підтримаю будь-яку розмову\n"
        "🎨 **Намалюй ...** - я згенерую картинку (швидко!)\n"
        "📸 **Кинь фото** - я проаналізую\n"
        "👥 **В групах** - я завжди активна!\n\n"
        f"**👑 Для власника {OWNER_USERNAME}:**\n"
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
        f"👑 **Власник:** {OWNER_USERNAME}\n"
        "🧠 **Мозок:** Kie.ai (GPT-4o) + OpenRouter резерв\n"
        "⚡ **Швидкість:** В 2-3 рази швидше!\n"
        "💰 **Ціна:** АБСОЛЮТНО БЕЗКОШТОВНО! 🎉\n"
        "📅 **Версія:** 3.0 - Kie.ai Ultra\n\n"
        "**🌈 Особливості:**\n"
        "• Відповідаю за 1-2 секунди\n"
        "• Малюю через GPT-4o Image [citation:1]\n"
        "• Аналізую фото через gpt-4o-mini\n"
        "• Працюю в групах першою!\n"
        "• Кешую аватарки для швидкості",
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
    
    # 🎨 ГЕНЕРАЦІЯ ЗОБРАЖЕНЬ (перша черга - найважливіше!)
    if message_text.lower().startswith(("намалюй", "згенеруй", "покажи", "нарисуй")):
        # Визначаємо промпт
        if message_text.lower().startswith("намалюй"):
            prompt = message_text[7:].strip()
        elif message_text.lower().startswith("згенеруй"):
            prompt = message_text[8:].strip()
        elif message_text.lower().startswith("покажи"):
            prompt = message_text[7:].strip()
        elif message_text.lower().startswith("нарисуй"):
            prompt = message_text[7:].strip()
        else:
            prompt = message_text.strip()
        
        if not prompt:
            await update.message.reply_text("А що малювати? Напиши, наприклад: 'намалюй кота'")
            return
        
        await update.message.reply_text("🎨 **Малюю через Kie.ai GPT-4o Image...** ⚡")
        
        # Генеруємо через Kie.ai [citation:1]
        image_url = await generate_image_kie(prompt)
        
        if image_url == "rate_limit":
            await update.message.reply_text(
                "😅 **Ліміти Kie.ai вичерпались!**\n\n"
                "Зачекай трохи або поповни рахунок на сайті kie.ai"
            )
        elif image_url:
            await update.message.reply_photo(photo=image_url, caption=f"🐘 Ось що вийшло! (GPT-4o Image)")
        else:
            # Пробуємо через запасний варіант
            await update.message.reply_text("😅 Спробую через OpenRouter...")
            image_url = await generate_image_fallback(prompt)
            if image_url:
                await update.message.reply_photo(photo=image_url, caption=f"🐘 Ось що вийшло! (Stable Diffusion)")
            else:
                await update.message.reply_text("😅 На жаль, всі моделі малювання тимчасово недоступні.")
        return
    
    # 👑 СПЕЦІАЛЬНІ КОМАНДИ ДЛЯ ВЛАСНИКА
    if is_owner:
        if "захисти @" in message_text.lower() or "защити @" in message_text.lower():
            match = re.search(r'@(\w+)', message_text)
            if match:
                target_user = "@" + match.group(1)
                protected_users.add(target_user)
                await update.message.reply_text(
                    f"✅ Зрозуміла, {OWNER_USERNAME}! {target_user} тепер під моїм захистом! 🤝"
                )
                return
        
        if "поржи з @" in message_text.lower() or "поржи с @" in message_text.lower():
            match = re.search(r'@(\w+)', message_text)
            if match:
                target_user = "@" + match.group(1)
                response = f"😈 Ха-ха-ха! {target_user}, {OWNER_USERNAME} дозволив мені трохи поржати з тебе!\n"
                await update.message.reply_text(response)
                return
    
    # 👥 ДЛЯ ВСІХ КОРИСТУВАЧІВ
    # Аналізуємо аватарку для нових користувачів
    if user_id not in user_types:
        photos = await context.bot.get_user_profile_photos(user_id, limit=1)
        
        if photos.total_count > 0:
            file = await context.bot.get_file(photos.photos[0][-1].file_id)
            file_url = file.file_path
            
            await update.message.reply_text("👀 Цікаво-цікаво... Аналізую аватарку...")
            avatar_type = await analyze_avatar_kie(file_url)  # Kie.ai аналіз
            user_types[user_id] = avatar_type
            avatar_info = avatar_type
            
            greeting = f"О, вітання, {username}! 😊\n"
            if avatar_info != "аватарки нема" and avatar_info != "невідомо":
                greeting += f"Бачу ти {avatar_info} - цікаво!"
        else:
            user_types[user_id] = "без аватарки"
            greeting = f"Привіт, {username}! Рада знайомству! 😊"
        
        await update.message.reply_text(greeting)
    
    # Визначаємо чи треба агресивно відповідати
    is_aggressive = False
    aggressive_words = ["дура", "тупа", "дебил", "лох", "плохая", "погана", 
                       "тупий", "довбойоб", "підарас", "хуй", "бля", "сука"]
    
    if any(word in message_text.lower() for word in aggressive_words):
        is_aggressive = True
        logger.info(f"⚠️ Агресивний режим для {username}")
    
    # Отримуємо швидку відповідь від Kie.ai
    response = await ask_kie_ai(message_text, user_id, username, avatar_info, user_lang, is_aggressive)
    await update.message.reply_text(response)

# ===== ОБРОБНИК ФОТО =====
async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    username = user.username or user.first_name or "Невідомий"
    
    photo = update.message.photo[-1]
    file = await context.bot.get_file(photo.file_id)
    file_url = file.file_path
    
    await update.message.reply_text("📸 Аналізую фото через Kie.ai... ⚡")
    analysis = await analyze_avatar_kie(file_url)
    
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
        "Поки що я не вмію слухати голосові, але скоро навчусь! 😉"
    )

# ===== ОБРОБНИК ПОМИЛОК =====
async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.error(f"Помилка: {context.error}")
    try:
        if update and update.effective_message:
            await update.effective_message.reply_text(
                "😅 Ой, технічна штука... Слоник трохи втомився, зачекай хвилинку!"
            )
    except:
        pass

# ===== ЗАГЛУШКА ДЛЯ RENDER =====
import threading
import time

def fake_web_server():
    time.sleep(5)
    print("✅ БАБКА ІЗ СЛОНИКА (KIE.AI ULTRA) ПРАЦЮЄ! ⚡")

thread = threading.Thread(target=fake_web_server, daemon=True)
thread.start()

# ===== ГОЛОВНА ФУНКЦІЯ З RateLimiter =====
def main():
    if not TELEGRAM_BOT_TOKEN:
        logger.error("Немає TELEGRAM_BOT_TOKEN!")
        return
    
    if not KIE_AI_API_KEY:
        logger.error("Немає KIE_AI_API_KEY!")
        print("⚠️ Додай KIE_AI_API_KEY в Environment Variables!")
        return
    
    # Додаємо RateLimiter для швидкості [citation:4][citation:7]
    application = (
        Application.builder()
        .token(TELEGRAM_BOT_TOKEN)
        .rate_limiter(AIORateLimiter(
            overall_max_rate=30,  # 30 повідомлень/секунду загалом
            group_max_rate=20,     # 20 повідомлень/хвилину в групах
            max_retries=3          # 3 спроби при помилці
        ))
        .build()
    )
    
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("info", info_command))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    application.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    application.add_handler(MessageHandler(filters.VOICE, handle_voice))
    application.add_error_handler(error_handler)
    
    print("✅ БАБКА ІЗ СЛОНИКА (KIE.AI ULTRA) ЗАПУЩЕНА! ⚡")
    print(f"👑 Власник: @kexxynd")
    print("🚀 Режим: Kie.ai Ultra + RateLimiter + Кеш")
    application.run_polling()

if __name__ == "__main__":
    main()
