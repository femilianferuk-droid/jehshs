import asyncio
import logging
import json
import sqlite3
import os
import requests
from datetime import datetime, date
from typing import Dict, List, Optional
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes
from telegram.constants import ParseMode

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Конфигурация
BOT_TOKEN = "8244265951:AAESPS6P-Yekbls_CkwvD4vpOts0lL9MxuA"
ADMIN_CHAT_ID = 7973988177
SUPPORT_LINK = "https://starfizovoi.t.me"
MINI_APP_URL = "https://nezeex-store.vercel.app/"
SITE_API_URL = "https://nezeex-store.vercel.app/api"

# База данных
DB_NAME = "nezeex_bot.db"

# Прайс-лист стран (должен быть синхронизирован с сайтом)
COUNTRIES = {
    '+1': {'name': 'США', 'price': 30, 'key': 'usa', 'flag': '🇺🇸'},
    '+1ca': {'name': 'Канада', 'price': 35, 'key': 'canada', 'flag': '🇨🇦'},
    '+7': {'name': 'Россия', 'price': 199, 'key': 'russia', 'flag': '🇷🇺'},
    '+7kz': {'name': 'Казахстан', 'price': 175, 'key': 'kazakhstan', 'flag': '🇰🇿'},
    '+20': {'name': 'Египет', 'price': 50, 'key': 'egypt', 'flag': '🇪🇬'},
    '+27': {'name': 'ЮАР', 'price': 100, 'key': 'south-africa', 'flag': '🇿🇦'},
    '+30': {'name': 'Греция', 'price': 175, 'key': 'greece', 'flag': '🇬🇷'},
    '+31': {'name': 'Нидерланды', 'price': 275, 'key': 'netherlands', 'flag': '🇳🇱'},
    '+32': {'name': 'Бельгия', 'price': 1200, 'key': 'belgium', 'flag': '🇧🇪'},
    '+33': {'name': 'Франция', 'price': 250, 'key': 'france', 'flag': '🇫🇷'},
    '+34': {'name': 'Испания', 'price': 250, 'key': 'spain', 'flag': '🇪🇸'},
    '+36': {'name': 'Венгрия', 'price': 250, 'key': 'hungary', 'flag': '🇭🇺'},
    '+39': {'name': 'Италия', 'price': 600, 'key': 'italy', 'flag': '🇮🇹'},
    '+40': {'name': 'Румыния', 'price': 80, 'key': 'romania', 'flag': '🇷🇴'},
    '+41': {'name': 'Швейцария', 'price': 2000, 'key': 'switzerland', 'flag': '🇨🇭'},
    '+43': {'name': 'Австрия', 'price': 1000, 'key': 'austria', 'flag': '🇦🇹'},
    '+44': {'name': 'Великобритания', 'price': 125, 'key': 'uk', 'flag': '🇬🇧'},
    '+45': {'name': 'Дания', 'price': 1150, 'key': 'denmark', 'flag': '🇩🇰'},
    '+46': {'name': 'Швеция', 'price': 400, 'key': 'sweden', 'flag': '🇸🇪'},
    '+47': {'name': 'Норвегия', 'price': 1150, 'key': 'norway', 'flag': '🇳🇴'},
    '+48': {'name': 'Польша', 'price': 275, 'key': 'poland', 'flag': '🇵🇱'},
    '+49': {'name': 'Германия', 'price': 300, 'key': 'germany', 'flag': '🇩🇪'},
    '+51': {'name': 'Перу', 'price': 150, 'key': 'peru', 'flag': '🇵🇪'},
    '+52': {'name': 'Мексика', 'price': 120, 'key': 'mexico', 'flag': '🇲🇽'},
    '+53': {'name': 'Куба', 'price': 180, 'key': 'cuba', 'flag': '🇨🇺'},
    '+54': {'name': 'Аргентина', 'price': 130, 'key': 'argentina', 'flag': '🇦🇷'},
    '+55': {'name': 'Бразилия', 'price': 125, 'key': 'brazil', 'flag': '🇧🇷'},
    '+56': {'name': 'Чили', 'price': 140, 'key': 'chile', 'flag': '🇨🇱'},
    '+57': {'name': 'Колумбия', 'price': 75, 'key': 'colombia', 'flag': '🇨🇴'},
    '+58': {'name': 'Венесуэла', 'price': 90, 'key': 'venezuela', 'flag': '🇻🇪'},
    '+60': {'name': 'Малайзия', 'price': 95, 'key': 'malaysia', 'flag': '🇲🇾'},
    '+61': {'name': 'Австралия', 'price': 110, 'key': 'australia', 'flag': '🇦🇺'},
    '+62': {'name': 'Индонезия', 'price': 50, 'key': 'indonesia', 'flag': '🇮🇩'},
    '+63': {'name': 'Филиппины', 'price': 65, 'key': 'philippines', 'flag': '🇵🇭'},
    '+64': {'name': 'Новая Зеландия', 'price': 115, 'key': 'new-zealand', 'flag': '🇳🇿'},
    '+66': {'name': 'Таиланд', 'price': 70, 'key': 'thailand', 'flag': '🇹🇭'},
    '+81': {'name': 'Япония', 'price': 500, 'key': 'japan', 'flag': '🇯🇵'},
    '+82': {'name': 'Южная Корея', 'price': 450, 'key': 'south-korea', 'flag': '🇰🇷'},
    '+84': {'name': 'Вьетнам', 'price': 70, 'key': 'vietnam', 'flag': '🇻🇳'},
    '+86': {'name': 'Китай', 'price': 750, 'key': 'china', 'flag': '🇨🇳'},
    '+90': {'name': 'Турция', 'price': 100, 'key': 'turkey', 'flag': '🇹🇷'},
    '+91': {'name': 'Индия', 'price': 40, 'key': 'india', 'flag': '🇮🇳'},
    '+92': {'name': 'Пакистан', 'price': 70, 'key': 'pakistan', 'flag': '🇵🇰'},
    '+93': {'name': 'Афганистан', 'price': 75, 'key': 'afghanistan', 'flag': '🇦🇫'},
    '+94': {'name': 'Шри-Ланка', 'price': 100, 'key': 'sri-lanka', 'flag': '🇱🇰'},
    '+95': {'name': 'Мьянма', 'price': 35, 'key': 'myanmar', 'flag': '🇲🇲'},
    '+98': {'name': 'Иран', 'price': 175, 'key': 'iran', 'flag': '🇮🇷'},
    '+212': {'name': 'Марокко', 'price': 75, 'key': 'morocco', 'flag': '🇲🇦'},
    '+213': {'name': 'Алжир', 'price': 85, 'key': 'algeria', 'flag': '🇩🇿'},
    '+216': {'name': 'Тунис', 'price': 90, 'key': 'tunisia', 'flag': '🇹🇳'},
    '+218': {'name': 'Ливия', 'price': 95, 'key': 'libya', 'flag': '🇱🇾'},
    '+225': {'name': 'Кот-д\'Ивуар', 'price': 750, 'key': 'ivory-coast', 'flag': '🇨🇮'},
    '+233': {'name': 'Гана', 'price': 550, 'key': 'ghana', 'flag': '🇬🇭'},
    '+234': {'name': 'Нигерия', 'price': 45, 'key': 'nigeria', 'flag': '🇳🇬'},
    '+251': {'name': 'Эфиопия', 'price': 60, 'key': 'ethiopia', 'flag': '🇪🇹'},
    '+254': {'name': 'Кения', 'price': 40, 'key': 'kenya', 'flag': '🇰🇪'},
    '+255': {'name': 'Танзания', 'price': 55, 'key': 'tanzania', 'flag': '🇹🇿'},
    '+249': {'name': 'Судан', 'price': 65, 'key': 'sudan', 'flag': '🇸🇩'},
    '+373': {'name': 'Молдова', 'price': 175, 'key': 'moldova', 'flag': '🇲🇩'},
    '+374': {'name': 'Армения', 'price': 400, 'key': 'armenia', 'flag': '🇦🇲'},
    '+375': {'name': 'Беларусь', 'price': 170, 'key': 'belarus', 'flag': '🇧🇾'},
    '+380': {'name': 'Украина', 'price': 235, 'key': 'ukraine', 'flag': '🇺🇦'},
    '+972': {'name': 'Израиль', 'price': 180, 'key': 'israel', 'flag': '🇮🇱'},
    '+971': {'name': 'ОАЭ', 'price': 200, 'key': 'uae', 'flag': '🇦🇪'},
    '+966': {'name': 'Саудовская Аравия', 'price': 190, 'key': 'saudi-arabia', 'flag': '🇸🇦'},
    '+965': {'name': 'Кувейт', 'price': 210, 'key': 'kuwait', 'flag': '🇰🇼'},
    '+974': {'name': 'Катар', 'price': 220, 'key': 'qatar', 'flag': '🇶🇦'},
    '+968': {'name': 'Оман', 'price': 205, 'key': 'oman', 'flag': '🇴🇲'},
    '+995': {'name': 'Грузия', 'price': 160, 'key': 'georgia', 'flag': '🇬🇪'},
    '+998': {'name': 'Узбекистан', 'price': 155, 'key': 'uzbekistan', 'flag': '🇺🇿'},
    '+992': {'name': 'Таджикистан', 'price': 145, 'key': 'tajikistan', 'flag': '🇹🇯'},
    '+993': {'name': 'Туркменистан', 'price': 150, 'key': 'turkmenistan', 'flag': '🇹🇲'},
    '+994': {'name': 'Азербайджан', 'price': 165, 'key': 'azerbaijan', 'flag': '🇦🇿'}
}

# Функция для получения кода страны из полного кода
def extract_country_code(full_code: str) -> str:
    """Извлекает код страны из полного кода (последние цифры после +)"""
    if '+' not in full_code:
        return None
    
    # Разделяем код на части
    parts = full_code.split('+')
    if len(parts) < 2:
        return None
    
    # Получаем код страны (последняя часть после +)
    country_code_part = '+' + parts[-1]
    
    # Проверяем специальные коды
    if country_code_part in ['+1ca', '+7kz']:
        return country_code_part
    
    # Для остальных кодов берем только цифры после +
    code_without_plus = parts[-1]
    digits = ''.join(filter(str.isdigit, code_without_plus))
    
    if not digits:
        return None
    
    # Собираем код страны
    country_code = '+' + digits
    
    # Проверяем существование страны
    if country_code in COUNTRIES:
        return country_code
    
    # Пробуем найти код с дополнительными символами
    for code in COUNTRIES:
        if code.startswith(country_code):
            return code
    
    return None

# Инициализация базы данных
def init_database():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    
    # Таблица пользователей
    c.execute('''CREATE TABLE IF NOT EXISTS users
                 (user_id INTEGER PRIMARY KEY,
                  username TEXT,
                  first_name TEXT,
                  last_name TEXT,
                  join_date TIMESTAMP,
                  is_admin BOOLEAN DEFAULT FALSE)''')
    
    # Таблица заказов
    c.execute('''CREATE TABLE IF NOT EXISTS orders
                 (order_id INTEGER PRIMARY KEY AUTOINCREMENT,
                  user_id INTEGER,
                  code TEXT UNIQUE,
                  country_code TEXT,
                  country_name TEXT,
                  status TEXT DEFAULT 'pending',
                  price INTEGER,
                  payment_screenshot TEXT,
                  created_at TIMESTAMP,
                  approved_at TIMESTAMP,
                  admin_id INTEGER,
                  phone_number TEXT,
                  phone_code TEXT,
                  phone_requested BOOLEAN DEFAULT FALSE,
                  code_requested BOOLEAN DEFAULT FALSE,
                  phone_sent_at TIMESTAMP,
                  code_sent_at TIMESTAMP)''')
    
    # Таблица активных кодов (синхронизация с сайтом)
    c.execute('''CREATE TABLE IF NOT EXISTS active_codes
                 (code TEXT PRIMARY KEY,
                  country_key TEXT,
                  country_name TEXT,
                  country_code TEXT,
                  price INTEGER,
                  created_at TIMESTAMP,
                  used BOOLEAN DEFAULT FALSE,
                  used_at TIMESTAMP,
                  order_id INTEGER)''')
    
    # Таблица статистики
    c.execute('''CREATE TABLE IF NOT EXISTS stats
                 (date DATE PRIMARY KEY,
                  orders_count INTEGER DEFAULT 0,
                  revenue INTEGER DEFAULT 0)''')
    
    # Добавляем админа если нет
    c.execute("SELECT * FROM users WHERE user_id = ?", (ADMIN_CHAT_ID,))
    if not c.fetchone():
        c.execute("INSERT INTO users (user_id, username, first_name, join_date, is_admin) VALUES (?, ?, ?, ?, ?)",
                  (ADMIN_CHAT_ID, "admin", "Admin", datetime.now(), True))
    
    conn.commit()
    conn.close()

class NezeexBot:
    def __init__(self):
        self.application = Application.builder().token(BOT_TOKEN).build()
        self.setup_handlers()
        init_database()
        
    def setup_handlers(self):
        """Настройка обработчиков"""
        # Команды
        self.application.add_handler(CommandHandler("start", self.start_command))
        self.application.add_handler(CommandHandler("admin", self.admin_command))
        self.application.add_handler(CommandHandler("stats", self.stats_command))
        self.application.add_handler(CommandHandler("broadcast", self.broadcast_command))
        
        # Callback-запросы (кнопки)
        self.application.add_handler(CallbackQueryHandler(self.button_handler))
        
        # Обработка текстовых сообщений
        self.application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.message_handler))
        
        # Обработка фото (скриншоты оплаты)
        self.application.add_handler(MessageHandler(filters.PHOTO, self.photo_handler))
    
    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработка команды /start"""
        user = update.effective_user
        user_id = user.id
        
        # Добавляем пользователя в БД если его нет
        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()
        c.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
        if not c.fetchone():
            c.execute("INSERT INTO users (user_id, username, first_name, last_name, join_date) VALUES (?, ?, ?, ?, ?)",
                      (user_id, user.username, user.first_name, user.last_name, datetime.now()))
            conn.commit()
        
        conn.close()
        
        # Основное меню
        keyboard = [
            [InlineKeyboardButton("🛒 Получить аккаунт", callback_data="get_account")],
            [InlineKeyboardButton("💬 Поддержка", url=SUPPORT_LINK)],
            [InlineKeyboardButton("🌐 Mini App", web_app=WebAppInfo(url=MINI_APP_URL))]
        ]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        welcome_text = f"""👋 Привет, {user.first_name}!

Добро пожаловать в Nezeex Store! 🏪

Здесь вы можете купить Telegram аккаунты по самым низким ценам!

✨ **Преимущества:**
• Мгновенная доставка ⚡
• Гарантия качества 🛡️
• Поддержка 24/7 💬
• Безопасно 🔒

🎁 **Как получить аккаунт:**
1. Купите аккаунт в Mini App 🌐
2. Получите уникальный код (8 символов + код страны)
3. Нажмите "Получить аккаунт" в боте
4. Отправьте код и скриншот оплаты
5. Получите данные аккаунта

Выберите действие ниже:"""
        
        await update.message.reply_text(welcome_text, reply_markup=reply_markup, parse_mode=ParseMode.MARKDOWN)
    
    async def get_account_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработка кнопки 'Получить аккаунт'"""
        await update.callback_query.answer()
        
        # Сохраняем состояние ожидания кода
        context.user_data['awaiting_code'] = True
        
        await update.callback_query.message.reply_text(
            "🎫 **Введите уникальный код:**\n\n"
            "Пожалуйста, введите код, который вы получили после покупки в Mini App.\n"
            "Формат кода: 8 символов + код страны\n"
            "Пример: `ABCD1234+1` (для США)\n"
            "Пример: `EFGH5678+7` (для России)\n\n"
            "Введите ваш код:",
            parse_mode=ParseMode.MARKDOWN
        )
    
    async def process_code(self, update: Update, context: ContextTypes.DEFAULT_TYPE, code: str):
        """Обработка введенного кода"""
        user_id = update.effective_user.id
        
        # Очищаем код от пробелов и приводим к верхнему регистру
        code = code.strip().upper()
        
        # Проверяем минимальную длину
        if len(code) < 3:
            await update.message.reply_text(
                "❌ **Код слишком короткий!**\n\n"
                "Введите код еще раз:",
                parse_mode=ParseMode.MARKDOWN
            )
            return
        
        # Извлекаем код страны
        country_code = extract_country_code(code)
        
        if not country_code:
            await update.message.reply_text(
                "❌ **Не удалось определить код страны!**\n\n"
                "Проверьте формат кода. Пример правильного формата:\n"
                "• `ABCD1234+1` (для США)\n"
                "• `EFGH5678+7` (для России)\n"
                "• `IJKL9012+44` (для Великобритании)\n\n"
                "Введите код еще раз:",
                parse_mode=ParseMode.MARKDOWN
            )
            return
        
        # Получаем информацию о стране
        if country_code not in COUNTRIES:
            await update.message.reply_text(
                f"❌ **Код страны '{country_code}' не поддерживается!**\n\n"
                f"Введите код еще раз:",
                parse_mode=ParseMode.MARKDOWN
            )
            return
        
        country_info = COUNTRIES[country_code]
        
        # Проверяем код в базе данных
        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()
        
        # Проверяем, есть ли код в базе данных бота
        c.execute("SELECT * FROM active_codes WHERE code = ?", (code,))
        code_data = c.fetchone()
        
        if code_data:
            # Код найден в базе бота
            c.execute("SELECT * FROM orders WHERE code = ?", (code,))
            order_data = c.fetchone()
            
            if order_data:
                # Заказ уже существует
                await self.handle_existing_order(update, context, order_data, code, country_info)
            else:
                # Код существует, но заказа нет - запрашиваем скриншот
                await self.request_screenshot(update, context, code, country_info)
        else:
            # Код не найден в базе бота
            # Пробуем проверить через API сайта
            await self.check_code_via_api(update, context, code, country_info)
        
        conn.close()
    
    async def check_code_via_api(self, update: Update, context: ContextTypes.DEFAULT_TYPE, code: str, country_info: dict):
        """Проверка кода через API сайта"""
        try:
            # В реальном проекте здесь будет запрос к вашему API
            # Для демо создаем код в базе
            
            conn = sqlite3.connect(DB_NAME)
            c = conn.cursor()
            
            # Добавляем код в базу данных
            c.execute("""INSERT INTO active_codes 
                        (code, country_key, country_name, country_code, price, created_at)
                        VALUES (?, ?, ?, ?, ?, ?)""",
                      (code, country_info['key'], country_info['name'], 
                       country_info['price'], country_info['code'], datetime.now()))
            
            conn.commit()
            conn.close()
            
            # Показываем информацию о стране и цене
            country_text = f"""✅ **Код подтвержден!**

{country_info['flag']} **Страна:** {country_info['name']}
💰 **Цена:** {country_info['price']} руб.
📞 **Код страны:** {country_info['code']}
🎫 **Ваш код:** `{code}`

📸 **Теперь отправьте скриншот чека об оплате.**"""
            
            context.user_data['awaiting_screenshot'] = True
            context.user_data['current_code'] = code
            context.user_data['current_country'] = country_info
            
            await update.message.reply_text(country_text, parse_mode=ParseMode.MARKDOWN)
            
        except Exception as e:
            logger.error(f"Ошибка проверки кода: {e}")
            
            # Если код уже существует (UNIQUE constraint)
            if "UNIQUE constraint" in str(e):
                await self.request_screenshot(update, context, code, country_info)
            else:
                await update.message.reply_text(
                    f"❌ **Ошибка при проверке кода!**\n\n"
                    f"Пожалуйста, попробуйте еще раз или обратитесь в поддержку: {SUPPORT_LINK}",
                    parse_mode=ParseMode.MARKDOWN
                )
    
    async def request_screenshot(self, update: Update, context: ContextTypes.DEFAULT_TYPE, code: str, country_info: dict):
        """Запрос скриншота оплаты"""
        # Показываем информацию о стране и цене
        country_text = f"""✅ **Код подтвержден!**

{country_info['flag']} **Страна:** {country_info['name']}
💰 **Цена:** {country_info['price']} руб.
📞 **Код страны:** {country_info['code']}
🎫 **Ваш код:** `{code}`

📸 **Теперь отправьте скриншот чека об оплате.**"""
        
        context.user_data['awaiting_screenshot'] = True
        context.user_data['current_code'] = code
        context.user_data['current_country'] = country_info
        
        await update.message.reply_text(country_text, parse_mode=ParseMode.MARKDOWN)
    
    async def handle_existing_order(self, update: Update, context: ContextTypes.DEFAULT_TYPE, 
                                   order_data: tuple, code: str, country_info: dict):
        """Обработка существующего заказа"""
        order_id = order_data[0]
        status = order_data[5]
        
        if status == 'pending':
            await update.message.reply_text(
                f"⏳ **Заказ уже ожидает проверки!**\n\n"
                f"{country_info['flag']} **Страна:** {country_info['name']}\n"
                f"💰 **Цена:** {country_info['price']} руб.\n"
                f"🎫 **Код:** `{code}`\n\n"
                f"Ваш заказ уже был отправлен на проверку. "
                f"Пожалуйста, ожидайте подтверждения администратора.",
                parse_mode=ParseMode.MARKDOWN
            )
        elif status == 'approved':
            # Заказ одобрен, показываем кнопки для получения данных
            context.user_data['current_order_id'] = order_id
            
            keyboard = [
                [InlineKeyboardButton("📱 Получить номер", callback_data=f"get_phone_{order_id}")],
                [InlineKeyboardButton("🔑 Получить код", callback_data=f"get_code_{order_id}")]
            ]
            
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await update.message.reply_text(
                f"✅ **Заказ одобрен!**\n\n"
                f"{country_info['flag']} **Страна:** {country_info['name']}\n"
                f"💰 **Цена:** {country_info['price']} руб.\n"
                f"🎫 **Код:** `{code}`\n\n"
                f"Вы можете получить данные аккаунта:",
                reply_markup=reply_markup,
                parse_mode=ParseMode.MARKDOWN
            )
        elif status == 'rejected':
            await update.message.reply_text(
                f"❌ **Заказ отклонен!**\n\n"
                f"{country_info['flag']} **Страна:** {country_info['name']}\n"
                f"💰 **Цена:** {country_info['price']} руб.\n"
                f"🎫 **Код:** `{code}`\n\n"
                f"Ваш заказ был отклонен администратором. "
                f"Если вы считаете это ошибкой, обратитесь в поддержку: {SUPPORT_LINK}",
                parse_mode=ParseMode.MARKDOWN
            )
        elif status == 'delivered':
            await update.message.reply_text(
                f"✅ **Аккаунт уже выдан!**\n\n"
                f"{country_info['flag']} **Страна:** {country_info['name']}\n"
                f"💰 **Цена:** {country_info['price']} руб.\n"
                f"🎫 **Код:** `{code}`\n\n"
                f"Данные аккаунта уже были вам отправлены. "
                f"Если у вас возникли проблемы, обратитесь в поддержку: {SUPPORT_LINK}",
                parse_mode=ParseMode.MARKDOWN
            )
    
    async def process_screenshot(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработка скриншота оплаты"""
        user_id = update.effective_user.id
        code = context.user_data.get('current_code')
        country_info = context.user_data.get('current_country')
        
        if not code or not country_info:
            await update.message.reply_text("❌ Ошибка: данные не найдены. Начните заново.")
            return
        
        # Получаем файл скриншота
        photo = update.message.photo[-1]
        file_id = photo.file_id
        
        # Получаем информацию о файле
        file = await context.bot.get_file(file_id)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        file_path = f"screenshots/{user_id}_{timestamp}.jpg"
        
        # Создаем папку если нет
        os.makedirs('screenshots', exist_ok=True)
        
        # Сохраняем файл
        await file.download_to_drive(file_path)
        
        # Создаем заказ в базе данных
        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()
        
        try:
            c.execute("""INSERT INTO orders 
                        (user_id, code, country_code, country_name, status, price, payment_screenshot, created_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                      (user_id, code, country_info['code'], country_info['name'], 
                       'pending', country_info['price'], file_path, datetime.now()))
            
            order_id = c.lastrowid
            
            # Обновляем код как использованный
            c.execute("UPDATE active_codes SET used = TRUE, used_at = ?, order_id = ? WHERE code = ?",
                      (datetime.now(), order_id, code))
            
            conn.commit()
            
            # Отправляем уведомление админу
            await self.notify_admin_new_order(context, order_id, code, country_info, user_id)
            
            # Отправляем подтверждение пользователю
            await update.message.reply_text(
                f"✅ **Скриншот успешно отправлен!**\n\n"
                f"{country_info['flag']} **Страна:** {country_info['name']}\n"
                f"💰 **Цена:** {country_info['price']} руб.\n"
                f"🎫 **Код:** `{code}`\n\n"
                f"Ваш заказ отправлен на проверку администратору.\n"
                f"Ожидайте подтверждения в течение 1-15 минут.\n\n"
                f"Вы получите уведомление, когда заказ будет проверен.",
                parse_mode=ParseMode.MARKDOWN
            )
            
        except Exception as e:
            logger.error(f"Ошибка создания заказа: {e}")
            await update.message.reply_text(
                "❌ **Ошибка при создании заказа!**\n\n"
                "Пожалуйста, попробуйте еще раз или обратитесь в поддержку.",
                parse_mode=ParseMode.MARKDOWN
            )
        
        finally:
            conn.close()
        
        # Очищаем состояние
        context.user_data.pop('awaiting_screenshot', None)
        context.user_data.pop('current_code', None)
        context.user_data.pop('current_country', None)
    
    async def notify_admin_new_order(self, context: ContextTypes.DEFAULT_TYPE, order_id: int, 
                                    code: str, country_info: dict, user_id: int):
        """Уведомление администратора о новом заказе"""
        user = await context.bot.get_chat(user_id)
        user_info = f"{user.first_name} (@{user.username})" if user.username else user.first_name
        
        keyboard = [
            [
                InlineKeyboardButton("✅ Одобрить", callback_data=f"approve_{order_id}"),
                InlineKeyboardButton("❌ Отклонить", callback_data=f"reject_{order_id}")
            ],
            [InlineKeyboardButton("📱 Посмотреть скриншот", callback_data=f"view_screenshot_{order_id}")]
        ]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        admin_message = f"""🛒 **Новый заказ #{order_id}!**

{country_info['flag']} **Страна:** {country_info['name']}
💰 **Цена:** {country_info['price']} руб.
📞 **Код страны:** {country_info['code']}
🎫 **Код:** `{code}`
👤 **Пользователь:** {user_info} (ID: {user_id})
📅 **Время:** {datetime.now().strftime('%H:%M %d.%m.%Y')}

**Статус:** ⏳ Ожидает проверки"""
        
        try:
            await context.bot.send_message(
                chat_id=ADMIN_CHAT_ID,
                text=admin_message,
                reply_markup=reply_markup,
                parse_mode=ParseMode.MARKDOWN
            )
        except Exception as e:
            logger.error(f"Ошибка отправки админу: {e}")
    
    async def approve_order(self, update: Update, context: ContextTypes.DEFAULT_TYPE, order_id: int):
        """Одобрение заказа админом"""
        await update.callback_query.answer()
        
        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()
        
        try:
            # Обновляем статус заказа
            c.execute("UPDATE orders SET status = 'approved', approved_at = ?, admin_id = ? WHERE order_id = ?",
                      (datetime.now(), ADMIN_CHAT_ID, order_id))
            
            # Получаем информацию о заказе
            c.execute("SELECT user_id, code, country_name, price FROM orders WHERE order_id = ?", (order_id,))
            order_data = c.fetchone()
            
            user_id = order_data[0]
            code = order_data[1]
            country_name = order_data[2]
            price = order_data[3]
            
            conn.commit()
            
            # Обновляем сообщение админу
            await update.callback_query.edit_message_text(
                f"✅ **Заказ #{order_id} одобрен!**\n\n"
                f"📍 **Страна:** {country_name}\n"
                f"💰 **Цена:** {price} руб.\n"
                f"🎫 **Код:** `{code}`\n"
                f"👤 **ID пользователя:** {user_id}\n"
                f"📅 **Одобрено:** {datetime.now().strftime('%H:%M %d.%m.%Y')}\n\n"
                f"Теперь пользователь может получить данные аккаунта.",
                parse_mode=ParseMode.MARKDOWN
            )
            
            # Отправляем уведомление пользователю
            await self.notify_user_order_approved(context, user_id, order_id, code, country_name)
            
        except Exception as e:
            logger.error(f"Ошибка одобрения заказа: {e}")
            await update.callback_query.edit_message_text(
                f"❌ **Ошибка при одобрении заказа:**\n{e}"
            )
        
        finally:
            conn.close()
    
    async def notify_user_order_approved(self, context: ContextTypes.DEFAULT_TYPE, user_id: int, 
                                        order_id: int, code: str, country_name: str):
        """Уведомление пользователя об одобрении заказа"""
        try:
            keyboard = [
                [InlineKeyboardButton("📱 Получить номер", callback_data=f"get_phone_{order_id}")],
                [InlineKeyboardButton("🔑 Получить код", callback_data=f"get_code_{order_id}")]
            ]
            
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await context.bot.send_message(
                chat_id=user_id,
                text=f"✅ **Ваш заказ #{order_id} одобрен!**\n\n"
                     f"📍 **Страна:** {country_name}\n"
                     f"🎫 **Код:** `{code}`\n\n"
                     f"Теперь вы можете получить данные аккаунта:",
                reply_markup=reply_markup,
                parse_mode=ParseMode.MARKDOWN
            )
        except Exception as e:
            logger.error(f"Ошибка отправки пользователю: {e}")
            await context.bot.send_message(
                chat_id=ADMIN_CHAT_ID,
                text=f"⚠️ Не удалось отправить уведомление пользователю {user_id}\nОшибка: {str(e)}"
            )
    
    async def reject_order(self, update: Update, context: ContextTypes.DEFAULT_TYPE, order_id: int):
        """Отклонение заказа админом"""
        await update.callback_query.answer()
        
        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()
        
        try:
            # Обновляем статус заказа
            c.execute("UPDATE orders SET status = 'rejected', approved_at = ?, admin_id = ? WHERE order_id = ?",
                      (datetime.now(), ADMIN_CHAT_ID, order_id))
            
            # Получаем информацию о заказе
            c.execute("SELECT user_id, code, country_name FROM orders WHERE order_id = ?", (order_id,))
            order_data = c.fetchone()
            
            user_id = order_data[0]
            code = order_data[1]
            country_name = order_data[2]
            
            conn.commit()
            
            # Обновляем сообщение админу
            await update.callback_query.edit_message_text(
                f"❌ **Заказ #{order_id} отклонен!**\n\n"
                f"📍 **Страна:** {country_name}\n"
                f"🎫 **Код:** `{code}`\n"
                f"👤 **ID пользователя:** {user_id}\n"
                f"📅 **Отклонено:** {datetime.now().strftime('%H:%M %d.%m.%Y')}",
                parse_mode=ParseMode.MARKDOWN
            )
            
            # Отправляем уведомление пользователю
            await context.bot.send_message(
                chat_id=user_id,
                text=f"❌ **Ваш заказ #{order_id} отклонен!**\n\n"
                     f"📍 **Страна:** {country_name}\n"
                     f"🎫 **Код:** `{code}`\n\n"
                     f"Если вы считаете это ошибкой, обратитесь в поддержку: {SUPPORT_LINK}",
                parse_mode=ParseMode.MARKDOWN
            )
            
        except Exception as e:
            logger.error(f"Ошибка отклонения заказа: {e}")
            await update.callback_query.edit_message_text(
                f"❌ **Ошибка при отклонении заказа:**\n{e}"
            )
        
        finally:
            conn.close()
    
    async def get_phone_request(self, update: Update, context: ContextTypes.DEFAULT_TYPE, order_id: int):
        """Запрос номера телефона"""
        await update.callback_query.answer()
        
        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()
        
        try:
            # Проверяем статус заказа
            c.execute("SELECT user_id, status, phone_number, phone_requested, code, country_name FROM orders WHERE order_id = ?", (order_id,))
            order_data = c.fetchone()
            
            if not order_data:
                await update.callback_query.message.reply_text("❌ Заказ не найден!")
                return
            
            user_id = order_data[0]
            status = order_data[1]
            phone_number = order_data[2]
            phone_requested = order_data[3]
            code = order_data[4]
            country_name = order_data[5]
            
            if status != 'approved':
                await update.callback_query.message.reply_text("❌ Заказ еще не одобрен!")
                return
            
            if phone_number:
                # Номер уже выдан
                await update.callback_query.message.reply_text(
                    f"📱 **Номер телефона:**\n\n"
                    f"`{phone_number}`\n\n"
                    f"📍 **Страна:** {country_name}\n"
                    f"🎫 **Код:** `{code}`\n\n"
                    f"Сохраните его в надежном месте!",
                    parse_mode=ParseMode.MARKDOWN
                )
                return
            
            # Отправляем запрос админу
            if not phone_requested:
                c.execute("UPDATE orders SET phone_requested = TRUE WHERE order_id = ?", (order_id,))
                conn.commit()
                
                # Отправляем уведомление админу
                keyboard = [
                    [InlineKeyboardButton("📱 Выдать номер", callback_data=f"provide_phone_{order_id}")]
                ]
                
                reply_markup = InlineKeyboardMarkup(keyboard)
                
                await context.bot.send_message(
                    chat_id=ADMIN_CHAT_ID,
                    text=f"📱 **Запрос номера телефона**\n\n"
                         f"🛒 **Заказ #{order_id}**\n"
                         f"📍 **Страна:** {country_name}\n"
                         f"🎫 **Код:** `{code}`\n"
                         f"👤 **ID пользователя:** {user_id}\n"
                         f"📅 **Запрошено:** {datetime.now().strftime('%H:%M %d.%m.%Y')}\n\n"
                         f"Нажмите кнопку ниже, чтобы ввести номер телефона:",
                    reply_markup=reply_markup,
                    parse_mode=ParseMode.MARKDOWN
                )
            
            await update.callback_query.message.reply_text(
                "📱 **Запрос отправлен администратору!**\n\n"
                "Номер телефона будет отправлен вам в течение 1-5 минут.\n"
                "Ожидайте уведомления.",
                parse_mode=ParseMode.MARKDOWN
            )
            
        except Exception as e:
            logger.error(f"Ошибка запроса номера: {e}")
            await update.callback_query.message.reply_text(
                "❌ Ошибка при запросе номера. Попробуйте позже."
            )
        
        finally:
            conn.close()
    
    async def get_code_request(self, update: Update, context: ContextTypes.DEFAULT_TYPE, order_id: int):
        """Запрос кода аккаунта"""
        await update.callback_query.answer()
        
        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()
        
        try:
            # Проверяем статус заказа
            c.execute("SELECT user_id, status, phone_code, code_requested, code, country_name FROM orders WHERE order_id = ?", (order_id,))
            order_data = c.fetchone()
            
            if not order_data:
                await update.callback_query.message.reply_text("❌ Заказ не найден!")
                return
            
            user_id = order_data[0]
            status = order_data[1]
            phone_code = order_data[2]
            code_requested = order_data[3]
            code = order_data[4]
            country_name = order_data[5]
            
            if status != 'approved':
                await update.callback_query.message.reply_text("❌ Заказ еще не одобрен!")
                return
            
            if phone_code:
                # Код уже выдан
                await update.callback_query.message.reply_text(
                    f"🔑 **Код аккаунта:**\n\n"
                    f"`{phone_code}`\n\n"
                    f"📍 **Страна:** {country_name}\n"
                    f"🎫 **Код:** `{code}`\n\n"
                    f"Сохраните его в надежном месте!",
                    parse_mode=ParseMode.MARKDOWN
                )
                return
            
            # Отправляем запрос админу
            if not code_requested:
                c.execute("UPDATE orders SET code_requested = TRUE WHERE order_id = ?", (order_id,))
                conn.commit()
                
                # Отправляем уведомление админу
                keyboard = [
                    [InlineKeyboardButton("🔑 Выдать код", callback_data=f"provide_code_{order_id}")]
                ]
                
                reply_markup = InlineKeyboardMarkup(keyboard)
                
                await context.bot.send_message(
                    chat_id=ADMIN_CHAT_ID,
                    text=f"🔑 **Запрос кода аккаунта**\n\n"
                         f"🛒 **Заказ #{order_id}**\n"
                         f"📍 **Страна:** {country_name}\n"
                         f"🎫 **Код:** `{code}`\n"
                         f"👤 **ID пользователя:** {user_id}\n"
                         f"📅 **Запрошено:** {datetime.now().strftime('%H:%M %d.%m.%Y')}\n\n"
                         f"Нажмите кнопку ниже, чтобы ввести код аккаунта:",
                    reply_markup=reply_markup,
                    parse_mode=ParseMode.MARKDOWN
                )
            
            await update.callback_query.message.reply_text(
                "🔑 **Запрос отправлен администратору!**\n\n"
                "Код аккаунта будет отправлен вам в течение 1-5 минут.\n"
                "Ожидайте уведомления.",
                parse_mode=ParseMode.MARKDOWN
            )
            
        except Exception as e:
            logger.error(f"Ошибка запроса кода: {e}")
            await update.callback_query.message.reply_text(
                "❌ Ошибка при запросе кода. Попробуйте позже."
            )
        
        finally:
            conn.close()
    
    async def provide_phone_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE, order_id: int):
        """Обработчик выдачи номера телефона админом"""
        await update.callback_query.answer()
        
        # Сохраняем order_id для следующего сообщения
        context.user_data['providing_phone_for'] = order_id
        
        await update.callback_query.message.reply_text(
            f"📱 **Выдача номера для заказа #{order_id}**\n\n"
            f"Пожалуйста, введите номер телефона в формате:\n"
            f"`+XXXXXXXXXXX`\n\n"
            f"Пример: `+79123456789`",
            parse_mode=ParseMode.MARKDOWN
        )
    
    async def provide_code_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE, order_id: int):
        """Обработчик выдачи кода аккаунта админом"""
        await update.callback_query.answer()
        
        # Сохраняем order_id для следующего сообщения
        context.user_data['providing_code_for'] = order_id
        
        await update.callback_query.message.reply_text(
            f"🔑 **Выдача кода для заказа #{order_id}**\n\n"
            f"Пожалуйста, введите код аккаунта.\n"
            f"Это может быть пароль, код подтверждения и т.д.",
            parse_mode=ParseMode.MARKDOWN
        )
    
    async def process_admin_phone(self, update: Update, context: ContextTypes.DEFAULT_TYPE, phone_number: str):
        """Обработка номера телефона от админа"""
        order_id = context.user_data.get('providing_phone_for')
        
        if not order_id:
            await update.message.reply_text("❌ Не найден заказ для выдачи номера.")
            return
        
        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()
        
        try:
            # Обновляем номер в заказе
            c.execute("UPDATE orders SET phone_number = ?, phone_sent_at = ? WHERE order_id = ?",
                      (phone_number, datetime.now(), order_id))
            
            # Получаем информацию о заказе
            c.execute("SELECT user_id, code, country_name FROM orders WHERE order_id = ?", (order_id,))
            order_data = c.fetchone()
            
            user_id = order_data[0]
            code = order_data[1]
            country_name = order_data[2]
            
            conn.commit()
            
            # Отправляем подтверждение админу
            await update.message.reply_text(
                f"✅ **Номер телефона выдан!**\n\n"
                f"🛒 **Заказ #{order_id}**\n"
                f"📍 **Страна:** {country_name}\n"
                f"🎫 **Код:** `{code}`\n"
                f"📱 **Номер:** `{phone_number}`\n"
                f"👤 **ID пользователя:** {user_id}\n"
                f"📅 **Выдано:** {datetime.now().strftime('%H:%M %d.%m.%Y')}",
                parse_mode=ParseMode.MARKDOWN
            )
            
            # Отправляем номер пользователю
            try:
                await context.bot.send_message(
                    chat_id=user_id,
                    text=f"📱 **Номер телефона для заказа #{order_id}**\n\n"
                         f"📍 **Страна:** {country_name}\n"
                         f"🎫 **Код:** `{code}`\n"
                         f"📱 **Номер:** `{phone_number}`\n\n"
                         f"Сохраните его в надежном месте!",
                    parse_mode=ParseMode.MARKDOWN
                )
            except Exception as e:
                logger.error(f"Ошибка отправки номера пользователю: {e}")
                await update.message.reply_text(
                    f"⚠️ Не удалось отправить номер пользователю {user_id}\nОшибка: {str(e)}"
                )
            
        except Exception as e:
            logger.error(f"Ошибка выдачи номера: {e}")
            await update.message.reply_text(
                f"❌ Ошибка при выдаче номера: {e}"
            )
        
        finally:
            conn.close()
            context.user_data.pop('providing_phone_for', None)
    
    async def process_admin_code(self, update: Update, context: ContextTypes.DEFAULT_TYPE, account_code: str):
        """Обработка кода аккаунта от админа"""
        order_id = context.user_data.get('providing_code_for')
        
        if not order_id:
            await update.message.reply_text("❌ Не найден заказ для выдачи кода.")
            return
        
        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()
        
        try:
            # Обновляем код в заказе
            c.execute("UPDATE orders SET phone_code = ?, code_sent_at = ? WHERE order_id = ?",
                      (account_code, datetime.now(), order_id))
            
            # Получаем информацию о заказе
            c.execute("SELECT user_id, code, country_name FROM orders WHERE order_id = ?", (order_id,))
            order_data = c.fetchone()
            
            user_id = order_data[0]
            code = order_data[1]
            country_name = order_data[2]
            
            conn.commit()
            
            # Отправляем подтверждение админу
            await update.message.reply_text(
                f"✅ **Код аккаунта выдан!**\n\n"
                f"🛒 **Заказ #{order_id}**\n"
                f"📍 **Страна:** {country_name}\n"
                f"🎫 **Код:** `{code}`\n"
                f"🔑 **Код аккаунта:** `{account_code}`\n"
                f"👤 **ID пользователя:** {user_id}\n"
                f"📅 **Выдано:** {datetime.now().strftime('%H:%M %d.%m.%Y')}",
                parse_mode=ParseMode.MARKDOWN
            )
            
            # Отправляем код пользователю
            try:
                await context.bot.send_message(
                    chat_id=user_id,
                    text=f"🔑 **Код аккаунта для заказа #{order_id}**\n\n"
                         f"📍 **Страна:** {country_name}\n"
                         f"🎫 **Код:** `{code}`\n"
                         f"🔑 **Код аккаунта:** `{account_code}`\n\n"
                         f"Сохраните его в надежном месте!",
                    parse_mode=ParseMode.MARKDOWN
                )
            except Exception as e:
                logger.error(f"Ошибка отправки кода пользователю: {e}")
                await update.message.reply_text(
                    f"⚠️ Не удалось отправить код пользователю {user_id}\nОшибка: {str(e)}"
                )
            
        except Exception as e:
            logger.error(f"Ошибка выдачи кода: {e}")
            await update.message.reply_text(
                f"❌ Ошибка при выдаче кода: {e}"
            )
        
        finally:
            conn.close()
            context.user_data.pop('providing_code_for', None)
    
    async def admin_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда админ-панели"""
        user_id = update.effective_user.id
        
        if user_id != ADMIN_CHAT_ID:
            await update.message.reply_text("⛔ У вас нет доступа к админ-панели!")
            return
        
        keyboard = [
            [InlineKeyboardButton("📊 Статистика", callback_data="admin_stats")],
            [InlineKeyboardButton("📋 Проверка чеков", callback_data="admin_receipts")],
            [InlineKeyboardButton("📢 Рассылка", callback_data="admin_broadcast")],
            [InlineKeyboardButton("🎫 Выдача аккаунтов", callback_data="admin_deliver")],
            [InlineKeyboardButton("➕ Добавить код", callback_data="admin_add_code")]
        ]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            "👑 **Админ-панель Nezeex Store**\n\nВыберите действие:",
            reply_markup=reply_markup,
            parse_mode=ParseMode.MARKDOWN
        )
    
    async def stats_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда статистики"""
        user_id = update.effective_user.id
        
        if user_id != ADMIN_CHAT_ID:
            await update.message.reply_text("⛔ У вас нет доступа к статистике!")
            return
        
        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()
        
        try:
            # Общая статистика
            c.execute("SELECT COUNT(*) FROM users")
            total_users = c.fetchone()[0]
            
            c.execute("SELECT COUNT(*) FROM orders")
            total_orders = c.fetchone()[0]
            
            c.execute("SELECT COUNT(*) FROM orders WHERE status = 'pending'")
            pending_orders = c.fetchone()[0]
            
            c.execute("SELECT COUNT(*) FROM orders WHERE status = 'approved'")
            approved_orders = c.fetchone()[0]
            
            c.execute("SELECT SUM(price) FROM orders WHERE status = 'approved'")
            total_revenue = c.fetchone()[0] or 0
            
            # Статистика за сегодня
            today = date.today()
            c.execute("SELECT COUNT(*), SUM(price) FROM orders WHERE DATE(created_at) = ? AND status = 'approved'", (today,))
            today_stats = c.fetchone()
            today_orders = today_stats[0] or 0
            today_revenue = today_stats[1] or 0
            
            # Активные коды
            c.execute("SELECT COUNT(*) FROM active_codes WHERE used = FALSE")
            active_codes = c.fetchone()[0]
            
            # Топ стран по продажам
            c.execute("""
                SELECT country_name, COUNT(*) as count, SUM(price) as revenue 
                FROM orders 
                WHERE status = 'approved' 
                GROUP BY country_name 
                ORDER BY count DESC 
                LIMIT 5
            """)
            top_countries = c.fetchall()
            
            stats_text = f"""📊 **Статистика Nezeex Store**

👥 **Пользователи:**
• Всего пользователей: {total_users}

🛒 **Заказы:**
• Всего заказов: {total_orders}
• Ожидают проверки: {pending_orders}
• Одобрено: {approved_orders}
• За сегодня: {today_orders}

💰 **Финансы:**
• Общая выручка: {total_revenue} руб.
• Выручка за сегодня: {today_revenue} руб.

🎫 **Коды:**
• Активных кодов: {active_codes}

🏆 **Топ-5 стран:**
"""
            
            for i, (country, count, revenue) in enumerate(top_countries, 1):
                stats_text += f"{i}. {country}: {count} заказов ({revenue} руб.)\n"
            
            stats_text += f"\n📅 Дата: {today.strftime('%d.%m.%Y')}"
            
            await update.message.reply_text(stats_text, parse_mode=ParseMode.MARKDOWN)
            
        except Exception as e:
            logger.error(f"Ошибка получения статистики: {e}")
            await update.message.reply_text(
                f"❌ Ошибка при получении статистики:\n{e}"
            )
        
        finally:
            conn.close()
    
    async def broadcast_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда рассылки"""
        user_id = update.effective_user.id
        
        if user_id != ADMIN_CHAT_ID:
            await update.message.reply_text("⛔ У вас нет доступа к рассылке!")
            return
        
        if not context.args:
            await update.message.reply_text(
                "📢 **Использование рассылки:**\n"
                "`/broadcast Ваше сообщение`\n\n"
                "Или отправьте сообщение после команды.",
                parse_mode=ParseMode.MARKDOWN
            )
            return
        
        message = ' '.join(context.args)
        context.user_data['broadcast_message'] = message
        
        keyboard = [
            [InlineKeyboardButton("✅ Да, отправить", callback_data="broadcast_confirm")],
            [InlineKeyboardButton("❌ Отмена", callback_data="broadcast_cancel")]
        ]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            f"📢 **Предпросмотр рассылки:**\n\n{message}\n\n"
            f"Отправить это сообщение всем пользователям?",
            reply_markup=reply_markup,
            parse_mode=ParseMode.MARKDOWN
        )
    
    async def execute_broadcast(self, context: ContextTypes.DEFAULT_TYPE, message: str):
        """Выполнение рассылки"""
        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()
        
        try:
            c.execute("SELECT user_id FROM users")
            users = c.fetchall()
            
            total_users = len(users)
            successful = 0
            failed = 0
            
            await context.bot.send_message(
                chat_id=ADMIN_CHAT_ID,
                text=f"📢 **Начата рассылка...**\n\n"
                     f"Всего пользователей: {total_users}\n"
                     f"Сообщение: {message[:50]}..."
            )
            
            for user_id, in users:
                try:
                    await context.bot.send_message(
                        chat_id=user_id,
                        text=message,
                        parse_mode=ParseMode.MARKDOWN
                    )
                    successful += 1
                    
                    # Пауза, чтобы не превысить лимиты Telegram
                    if successful % 20 == 0:
                        await asyncio.sleep(1)
                        
                except Exception as e:
                    failed += 1
                    logger.error(f"Ошибка отправки пользователю {user_id}: {e}")
            
            await context.bot.send_message(
                chat_id=ADMIN_CHAT_ID,
                text=f"✅ **Рассылка завершена!**\n\n"
                     f"Всего пользователей: {total_users}\n"
                     f"Успешно: {successful}\n"
                     f"Не удалось: {failed}"
            )
            
        except Exception as e:
            logger.error(f"Ошибка рассылки: {e}")
            await context.bot.send_message(
                chat_id=ADMIN_CHAT_ID,
                text=f"❌ **Ошибка рассылки:**\n{e}"
            )
        
        finally:
            conn.close()
    
    async def button_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик нажатий на кнопки"""
        query = update.callback_query
        await query.answer()
        
        data = query.data
        
        try:
            if data == "get_account":
                await self.get_account_command(update, context)
            
            elif data.startswith("approve_"):
                order_id = int(data.split("_")[1])
                await self.approve_order(update, context, order_id)
            
            elif data.startswith("reject_"):
                order_id = int(data.split("_")[1])
                await self.reject_order(update, context, order_id)
            
            elif data.startswith("get_phone_"):
                order_id = int(data.split("_")[2])
                await self.get_phone_request(update, context, order_id)
            
            elif data.startswith("get_code_"):
                order_id = int(data.split("_")[2])
                await self.get_code_request(update, context, order_id)
            
            elif data.startswith("provide_phone_"):
                order_id = int(data.split("_")[2])
                await self.provide_phone_handler(update, context, order_id)
            
            elif data.startswith("provide_code_"):
                order_id = int(data.split("_")[2])
                await self.provide_code_handler(update, context, order_id)
            
            elif data == "admin_stats":
                await self.stats_command(update, context)
            
            elif data == "admin_receipts":
                await self.show_pending_orders(update, context)
            
            elif data == "admin_broadcast":
                await update.callback_query.message.reply_text(
                    "📢 **Рассылка:**\n\n"
                    "Используйте команду:\n"
                    "`/broadcast Ваше сообщение`",
                    parse_mode=ParseMode.MARKDOWN
                )
            
            elif data == "admin_deliver":
                await self.show_orders_for_delivery(update, context)
            
            elif data == "admin_add_code":
                await update.callback_query.message.reply_text(
                    "➕ **Добавление кода:**\n\n"
                    "Коды добавляются автоматически с сайта.\n"
                    "Для ручного добавления используйте SQL запрос к базе данных."
                )
            
            elif data == "broadcast_confirm":
                message = context.user_data.get('broadcast_message')
                if message:
                    await query.edit_message_text(
                        f"📢 **Рассылка начата...**\n\n"
                        f"Сообщение: {message[:100]}...",
                        parse_mode=ParseMode.MARKDOWN
                    )
                    await self.execute_broadcast(context, message)
                else:
                    await query.edit_message_text("❌ Сообщение для рассылки не найдено!")
            
            elif data == "broadcast_cancel":
                await query.edit_message_text("❌ Рассылка отменена.")
            
            elif data.startswith("view_screenshot_"):
                order_id = int(data.split("_")[2])
                await self.view_screenshot(update, context, order_id)
        
        except Exception as e:
            logger.error(f"Ошибка обработки кнопки {data}: {e}")
            await query.edit_message_text(f"❌ Ошибка: {str(e)}")
    
    async def show_pending_orders(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Показать заказы ожидающие проверки"""
        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()
        
        try:
            c.execute("""
                SELECT order_id, user_id, code, country_name, price, created_at 
                FROM orders 
                WHERE status = 'pending' 
                ORDER BY created_at DESC 
                LIMIT 20
            """)
            pending_orders = c.fetchall()
            
            if not pending_orders:
                await update.callback_query.message.reply_text(
                    "✅ **Нет заказов ожидающих проверки!**",
                    parse_mode=ParseMode.MARKDOWN
                )
                return
            
            orders_text = "📋 **Заказы ожидающие проверки:**\n\n"
            
            for order in pending_orders:
                order_id, user_id, code, country_name, price, created_at = order
                orders_text += f"🛒 **Заказ #{order_id}**\n"
                orders_text += f"📍 **Страна:** {country_name}\n"
                orders_text += f"💰 **Цена:** {price} руб.\n"
                orders_text += f"🎫 **Код:** `{code}`\n"
                orders_text += f"👤 **ID пользователя:** {user_id}\n"
                orders_text += f"📅 **Время:** {created_at}\n\n"
                
                # Добавляем кнопки для каждого заказа
                keyboard = [
                    [
                        InlineKeyboardButton(f"✅ #{order_id}", callback_data=f"approve_{order_id}"),
                        InlineKeyboardButton(f"❌ #{order_id}", callback_data=f"reject_{order_id}")
                    ]
                ]
                
                reply_markup = InlineKeyboardMarkup(keyboard)
                
                await update.callback_query.message.reply_text(
                    orders_text,
                    reply_markup=reply_markup,
                    parse_mode=ParseMode.MARKDOWN
                )
                
                orders_text = ""  # Сбрасываем текст для следующего сообщения
        
        except Exception as e:
            logger.error(f"Ошибка показа заказов: {e}")
            await update.callback_query.message.reply_text(
                f"❌ Ошибка при получении заказов:\n{e}"
            )
        
        finally:
            conn.close()
    
    async def show_orders_for_delivery(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Показать заказы для выдачи"""
        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()
        
        try:
            c.execute("""
                SELECT order_id, user_id, code, country_name, price, 
                       phone_number, phone_code, phone_requested, code_requested
                FROM orders 
                WHERE status = 'approved' 
                ORDER BY approved_at DESC 
                LIMIT 20
            """)
            approved_orders = c.fetchall()
            
            if not approved_orders:
                await update.callback_query.message.reply_text(
                    "✅ **Нет заказов для выдачи!**",
                    parse_mode=ParseMode.MARKDOWN
                )
                return
            
            for order in approved_orders:
                (order_id, user_id, code, country_name, price, 
                 phone_number, phone_code, phone_requested, code_requested) = order
                
                order_text = f"🛒 **Заказ #{order_id}**\n"
                order_text += f"📍 **Страна:** {country_name}\n"
                order_text += f"💰 **Цена:** {price} руб.\n"
                order_text += f"🎫 **Код:** `{code}`\n"
                order_text += f"👤 **ID пользователя:** {user_id}\n\n"
                
                if phone_number:
                    order_text += f"📱 **Номер:** `{phone_number}`\n"
                else:
                    order_text += "📱 **Номер:** ❌ Не выдан\n"
                
                if phone_code:
                    order_text += f"🔑 **Код:** `{phone_code}`\n"
                else:
                    order_text += "🔑 **Код:** ❌ Не выдан\n"
                
                if phone_requested and not phone_number:
                    order_text += "\n⚠️ **Ожидает номер!**\n"
                
                if code_requested and not phone_code:
                    order_text += "\n⚠️ **Ожидает код!**\n"
                
                # Создаем кнопки для управления выдачей
                buttons = []
                
                if not phone_number or not phone_code:
                    if not phone_number:
                        buttons.append(InlineKeyboardButton(f"📱 Выдать номер", callback_data=f"provide_phone_{order_id}"))
                    if not phone_code:
                        buttons.append(InlineKeyboardButton(f"🔑 Выдать код", callback_data=f"provide_code_{order_id}"))
                
                if buttons:
                    keyboard = [buttons]
                    reply_markup = InlineKeyboardMarkup(keyboard)
                else:
                    reply_markup = None
                
                await update.callback_query.message.reply_text(
                    order_text,
                    reply_markup=reply_markup,
                    parse_mode=ParseMode.MARKDOWN
                )
        
        except Exception as e:
            logger.error(f"Ошибка показа заказов для выдачи: {e}")
            await update.callback_query.message.reply_text(
                f"❌ Ошибка при получении заказов:\n{e}"
            )
        
        finally:
            conn.close()
    
    async def view_screenshot(self, update: Update, context: ContextTypes.DEFAULT_TYPE, order_id: int):
        """Просмотр скриншота оплаты"""
        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()
        
        try:
            c.execute("SELECT payment_screenshot FROM orders WHERE order_id = ?", (order_id,))
            screenshot_path = c.fetchone()[0]
            
            if not screenshot_path or not os.path.exists(screenshot_path):
                await update.callback_query.message.reply_text(
                    f"❌ Скриншот для заказа #{order_id} не найден!"
                )
                return
            
            # Отправляем скриншот
            with open(screenshot_path, 'rb') as photo:
                await update.callback_query.message.reply_photo(
                    photo=photo,
                    caption=f"📸 **Скриншот оплаты для заказа #{order_id}**"
                )
        
        except Exception as e:
            logger.error(f"Ошибка просмотра скриншота: {e}")
            await update.callback_query.message.reply_text(
                f"❌ Ошибка при просмотре скриншота:\n{e}"
            )
        
        finally:
            conn.close()
    
    async def message_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик текстовых сообщений"""
        message_text = update.message.text
        
        # Проверяем состояние ожидания кода
        if context.user_data.get('awaiting_code'):
            await self.process_code(update, context, message_text)
            context.user_data.pop('awaiting_code', None)
            return
        
        # Проверяем состояние ожидания номера от админа
        elif context.user_data.get('providing_phone_for'):
            await self.process_admin_phone(update, context, message_text)
            return
        
        # Проверяем состояние ожидания кода от админа
        elif context.user_data.get('providing_code_for'):
            await self.process_admin_code(update, context, message_text)
            return
        
        # Обычное сообщение
        else:
            await update.message.reply_text(
                "ℹ️ **Используйте меню бота:**\n\n"
                "• Нажмите '🛒 Получить аккаунт' для активации кода\n"
                "• Нажмите '💬 Поддержка' для связи с менеджером\n"
                "• Нажмите '🌐 Mini App' для перехода на сайт",
                parse_mode=ParseMode.MARKDOWN
            )
    
    async def photo_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик фотографий (скриншоты оплаты)"""
        # Проверяем состояние ожидания скриншота
        if context.user_data.get('awaiting_screenshot'):
            await self.process_screenshot(update, context)
            return
        
        # Если фото отправлено без контекста
        else:
            await update.message.reply_text(
                "📸 **Пожалуйста, сначала введите код:**\n\n"
                "1. Нажмите '🛒 Получить аккаунт'\n"
                "2. Введите ваш код\n"
                "3. Затем отправьте скриншот оплаты",
                parse_mode=ParseMode.MARKDOWN
            )
    
    def run(self):
        """Запуск бота"""
        self.application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    bot = NezeexBot()
    bot.run()
