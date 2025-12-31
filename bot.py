import sqlite3
import logging
import random
import os
import asyncio
from datetime import datetime
from typing import Dict, Optional, Tuple, List

from telegram import (
    Update, 
    InlineKeyboardButton, 
    InlineKeyboardMarkup, 
    ReplyKeyboardMarkup,
    KeyboardButton
)
from telegram.ext import (
    Application, 
    CommandHandler, 
    MessageHandler, 
    CallbackQueryHandler,
    ContextTypes, 
    filters
)

# ====================== КОНФИГУРАЦИЯ ======================
BOT_TOKEN = "8244265951:AAFpmG4DRb640YLvURAhIySdpf6VVJgXX4g"
ADMIN_ID = 7973988177
SUPPORT_USERNAME = "@starfizovoi"

# Курсы валют
EXCHANGE_RATES = {
    "USDT": 76.0,
    "TON": 115.0
}

# ПРАЙС-ЛИСТ СТРАН
COUNTRIES = {
    "usa": {"name": "🇺🇸 США", "price_rub": 30, "code": "+1"},
    "canada": {"name": "🇨🇦 Канада", "price_rub": 35, "code": "+1"},
    "russia": {"name": "🇷🇺 Россия", "price_rub": 199, "code": "+7"},
    "kazakhstan": {"name": "🇰🇿 Казахстан", "price_rub": 175, "code": "+7"},
    "egypt": {"name": "🇪🇬 Египет", "price_rub": 50, "code": "+20"},
    "south_africa": {"name": "🇿🇦 ЮАР", "price_rub": 100, "code": "+27"},
    "greece": {"name": "🇬🇷 Греция", "price_rub": 175, "code": "+30"},
    "netherlands": {"name": "🇳🇱 Нидерланды", "price_rub": 275, "code": "+31"},
    "belgium": {"name": "🇧🇪 Бельгия", "price_rub": 1200, "code": "+32"},
    "france": {"name": "🇫🇷 Франция", "price_rub": 250, "code": "+33"},
    "spain": {"name": "🇪🇸 Испания", "price_rub": 250, "code": "+34"},
    "hungary": {"name": "🇭🇺 Венгрия", "price_rub": 250, "code": "+36"},
    "italy": {"name": "🇮🇹 Италия", "price_rub": 600, "code": "+39"},
    "romania": {"name": "🇷🇴 Румыния", "price_rub": 80, "code": "+40"},
    "switzerland": {"name": "🇨🇭 Швейцария", "price_rub": 2000, "code": "+41"},
    "austria": {"name": "🇦🇹 Австрия", "price_rub": 1000, "code": "+43"},
    "uk": {"name": "🇬🇧 Великобритания", "price_rub": 125, "code": "+44"},
    "denmark": {"name": "🇩🇰 Дания", "price_rub": 1150, "code": "+45"},
    "sweden": {"name": "🇸🇪 Швеция", "price_rub": 400, "code": "+46"},
    "norway": {"name": "🇳🇴 Норвегия", "price_rub": 1150, "code": "+47"},
    "poland": {"name": "🇵🇱 Польша", "price_rub": 275, "code": "+48"},
    "brazil": {"name": "🇧🇷 Бразилия", "price_rub": 125, "code": "+55"},
    "colombia": {"name": "🇨🇴 Колумбия", "price_rub": 75, "code": "+57"},
    "indonesia": {"name": "🇮🇩 Индонезия", "price_rub": 50, "code": "+62"},
    "vietnam": {"name": "🇻🇳 Вьетнам", "price_rub": 70, "code": "+84"},
    "china": {"name": "🇨🇳 Китай", "price_rub": 750, "code": "+86"},
    "turkey": {"name": "🇹🇷 Турция", "price_rub": 100, "code": "+90"},
    "india": {"name": "🇮🇳 Индия", "price_rub": 40, "code": "+91"},
    "pakistan": {"name": "🇵🇰 Пакистан", "price_rub": 70, "code": "+92"},
    "afghanistan": {"name": "🇦🇫 Афганистан", "price_rub": 75, "code": "+93"},
    "sri_lanka": {"name": "🇱🇰 Шри-Ланка", "price_rub": 100, "code": "+94"},
    "myanmar": {"name": "🇲🇲 Мьянма", "price_rub": 35, "code": "+95"},
    "iran": {"name": "🇮🇷 Иран", "price_rub": 175, "code": "+98"},
    "morocco": {"name": "🇲🇦 Марокко", "price_rub": 75, "code": "+212"},
    "ivory_coast": {"name": "🇨🇮 Кот-д'Ивуар", "price_rub": 750, "code": "+225"},
    "ghana": {"name": "🇬🇭 Гана", "price_rub": 550, "code": "+233"},
    "nigeria": {"name": "🇳🇬 Нигерия", "price_rub": 45, "code": "+234"},
    "kenya": {"name": "🇰🇪 Кения", "price_rub": 40, "code": "+254"},
    "moldova": {"name": "🇲🇩 Молдова", "price_rub": 175, "code": "+373"},
    "armenia": {"name": "🇦🇲 Армения", "price_rub": 400, "code": "+374"},
    "belarus": {"name": "🇧🇾 Беларусь", "price_rub": 170, "code": "+375"},
    "ukraine": {"name": "🇺🇦 Украина", "price_rub": 235, "code": "+380"}
}

# Карта для оплаты
CARD_NUMBER = "5599 0021 2767 5173"
CRYPTO_BOT_LINK = "http://t.me/send?start=IVKF2M5j40O5"

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ====================== БАЗА ДАННЫХ ======================
class Database:
    def __init__(self, db_name="bot_database.db"):
        self.db_name = db_name
        self.init_db()
    
    def get_connection(self):
        """Получение соединения с БД"""
        return sqlite3.connect(self.db_name)
    
    def init_db(self):
        """Инициализация базы данных"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # Таблица пользователей
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    user_id INTEGER PRIMARY KEY,
                    username TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Таблица заказов
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS orders (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    order_id TEXT UNIQUE,
                    user_id INTEGER,
                    country_code TEXT,
                    country_name TEXT,
                    phone_code TEXT,
                    price_rub INTEGER,
                    status TEXT DEFAULT 'pending',
                    payment_method TEXT,
                    payment_screenshot TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users (user_id)
                )
            ''')
            
            # Таблица выданных данных
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS issued_data (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    order_id TEXT,
                    data_type TEXT,
                    data_text TEXT,
                    issued_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (order_id) REFERENCES orders (order_id)
                )
            ''')
            
            conn.commit()
            logger.info("База данных инициализирована")
    
    def add_user(self, user_id: int, username: str):
        """Добавление пользователя в БД"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT OR IGNORE INTO users (user_id, username) VALUES (?, ?)",
                (user_id, username or '')
            )
            conn.commit()
    
    def create_order(self, order_id: str, user_id: int, country_code: str, country_name: str, phone_code: str, price_rub: int):
        """Создание нового заказа"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                '''INSERT INTO orders 
                (order_id, user_id, country_code, country_name, phone_code, price_rub, status) 
                VALUES (?, ?, ?, ?, ?, ?, ?)''',
                (order_id, user_id, country_code, country_name, phone_code, price_rub, 'pending')
            )
            conn.commit()
            return order_id
    
    def update_order_payment(self, order_id: str, payment_method: str, screenshot_path: str = None):
        """Обновление информации об оплате заказа"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                '''UPDATE orders 
                SET payment_method = ?, payment_screenshot = ?, status = 'waiting_approval'
                WHERE order_id = ?''',
                (payment_method, screenshot_path, order_id)
            )
            conn.commit()
            return cursor.rowcount > 0
    
    def update_order_status(self, order_id: str, status: str):
        """Обновление статуса заказа"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE orders SET status = ? WHERE order_id = ?",
                (status, order_id)
            )
            conn.commit()
            return cursor.rowcount > 0
    
    def get_order(self, order_id: str) -> Optional[Tuple]:
        """Получение информации о заказе"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM orders WHERE order_id = ?", (order_id,))
            return cursor.fetchone()
    
    def get_user_orders(self, user_id: int, limit: int = 10) -> list:
        """Получение истории заказов пользователя"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                '''SELECT order_id, country_name, price_rub, created_at, status 
                FROM orders 
                WHERE user_id = ? 
                ORDER BY created_at DESC 
                LIMIT ?''',
                (user_id, limit)
            )
            return cursor.fetchall()
    
    def get_completed_user_orders(self, user_id: int, limit: int = 10) -> list:
        """Получение истории успешных покупок пользователя"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                '''SELECT order_id, country_name, price_rub, created_at 
                FROM orders 
                WHERE user_id = ? AND status = 'completed'
                ORDER BY created_at DESC 
                LIMIT ?''',
                (user_id, limit)
            )
            return cursor.fetchall()
    
    def add_issued_data(self, order_id: str, data_type: str, data_text: str):
        """Добавление выданных данных"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO issued_data (order_id, data_type, data_text) VALUES (?, ?, ?)",
                (order_id, data_type, data_text)
            )
            conn.commit()
            return cursor.lastrowid
    
    def get_issued_data(self, order_id: str, data_type: str = None) -> list:
        """Получение выданных данных для заказа"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            if data_type:
                cursor.execute(
                    "SELECT data_text FROM issued_data WHERE order_id = ? AND data_type = ? ORDER BY issued_at DESC LIMIT 1",
                    (order_id, data_type)
                )
            else:
                cursor.execute(
                    "SELECT data_type, data_text FROM issued_data WHERE order_id = ? ORDER BY issued_at DESC",
                    (order_id,)
                )
            return cursor.fetchall()
    
    def check_order_ownership(self, order_id: str, user_id: int) -> bool:
        """Проверка принадлежности заказа пользователю"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT 1 FROM orders WHERE order_id = ? AND user_id = ?",
                (order_id, user_id)
            )
            return cursor.fetchone() is not None
    
    def get_order_by_id(self, order_id: str):
        """Получение заказа по ID"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM orders WHERE order_id = ?",
                (order_id,)
            )
            row = cursor.fetchone()
            if row:
                columns = [description[0] for description in cursor.description]
                return dict(zip(columns, row))
            return None

# Инициализация базы данных
db = Database()

# ====================== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ======================
def generate_order_id() -> str:
    """Генерация уникального ID заказа"""
    timestamp = datetime.now().strftime("%Y%m%d")
    random_part = random.randint(10000, 99999)
    return f"ORD-{random_part}"

def format_price(price_rub: int) -> str:
    """Форматирование цены в разных валютах"""
    usdt_price = price_rub / EXCHANGE_RATES["USDT"]
    ton_price = price_rub / EXCHANGE_RATES["TON"]
    return f"~{usdt_price:.3f} USDT / ~{ton_price:.3f} TON"

def create_main_keyboard():
    """Создание главной клавиатуры"""
    keyboard = [
        [KeyboardButton("🛒 Купить аккаунт"), KeyboardButton("👤 Профиль")],
        [KeyboardButton("🆘 Поддержка")]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def create_countries_keyboard(page: int = 0):
    """Создание клавиатуры с пагинацией стран"""
    countries_list = list(COUNTRIES.items())
    items_per_page = 6
    total_pages = (len(countries_list) + items_per_page - 1) // items_per_page
    
    start_idx = page * items_per_page
    end_idx = start_idx + items_per_page
    page_countries = countries_list[start_idx:end_idx]
    
    keyboard = []
    
    for code, info in page_countries:
        button_text = f"{info['name']} - {info['price_rub']}₽"
        button = InlineKeyboardButton(button_text, callback_data=f"country_{code}")
        keyboard.append([button])
    
    # Кнопки навигации
    navigation_buttons = []
    if page > 0:
        navigation_buttons.append(InlineKeyboardButton("⬅️ Назад", callback_data=f"page_{page-1}"))
    
    if navigation_buttons:
        keyboard.append(navigation_buttons)
    
    if page < total_pages - 1:
        keyboard.append([InlineKeyboardButton("Вперед ➡️", callback_data=f"page_{page+1}")])
    
    return InlineKeyboardMarkup(keyboard)

# ====================== ОСНОВНЫЕ ОБРАБОТЧИКИ ======================
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /start"""
    try:
        user = update.effective_user
        logger.info(f"Пользователь {user.id} (@{user.username}) запустил бота")
        
        db.add_user(user.id, user.username)
        
        welcome_text = (
            "🤖 Добро пожаловать в бота для покупки аккаунтов!\n\n"
            "💎 Доступные функции:\n"
            "• 🛒 Купить аккаунт - выбор страны и оплата\n"
            "• 👤 Профиль - ваши данные и история покупок\n"
            "• 🆘 Поддержка - связь с администратором\n\n"
            "Выберите действие в меню ниже:"
        )
        
        await update.message.reply_text(
            welcome_text,
            reply_markup=create_main_keyboard()
        )
    except Exception as e:
        logger.error(f"Ошибка в start_command: {e}")
        await update.message.reply_text("Произошла ошибка. Попробуйте еще раз.")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик текстовых сообщений"""
    try:
        # Пропускаем сообщения от админа
        if update.effective_user.id == ADMIN_ID:
            return
        
        text = update.message.text
        
        if text == "🛒 Купить аккаунт":
            await show_account_types(update, context)
        elif text == "👤 Профиль":
            await show_profile(update, context)
        elif text == "🆘 Поддержка":
            await show_support(update, context)
        else:
            # Проверяем, не ждем ли мы скриншот
            if 'waiting_screenshot_for' in context.user_data:
                await update.message.reply_text("Пожалуйста, отправьте скриншот (фото или документ).")
            else:
                await update.message.reply_text(
                    "Используйте меню ниже:",
                    reply_markup=create_main_keyboard()
                )
    except Exception as e:
        logger.error(f"Ошибка в handle_message: {e}")
        await update.message.reply_text("Произошла ошибка. Попробуйте еще раз.")

async def show_support(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать информацию о поддержке"""
    support_text = f"🆘 По всем вопросам обращайтесь: {SUPPORT_USERNAME}"
    await update.message.reply_text(support_text)

async def show_profile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать профиль пользователя"""
    try:
        user = update.effective_user
        orders = db.get_completed_user_orders(user.id)
        
        profile_text = f"👤 Ваш профиль:\n"
        profile_text += f"├ ID: `{user.id}`\n"
        profile_text += f"├ Юзернейм: @{user.username if user.username else 'Отсутствует'}\n"
        profile_text += f"└ История покупок:\n"
        
        if orders:
            for order in orders:
                order_id, country_name, price_rub, created_at = order
                try:
                    date_str = datetime.strptime(created_at, "%Y-%m-%d %H:%M:%S").strftime("%Y-%m-%d")
                except:
                    date_str = created_at[:10]
                
                order_short_id = order_id.split('-')[1] if len(order_id.split('-')) > 1 else order_id
                profile_text += f"   • {date_str} | {country_name} (#{order_short_id})\n"
        else:
            profile_text += "   Пока нет покупок\n"
        
        await update.message.reply_text(profile_text, parse_mode='Markdown')
    except Exception as e:
        logger.error(f"Ошибка в show_profile: {e}")
        await update.message.reply_text("Ошибка при загрузке профиля.")

async def show_account_types(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать типы аккаунтов"""
    keyboard = [[
        InlineKeyboardButton("📱 ФИЗ аккаунты", callback_data="type_fiz")
    ]]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    if update.message:
        await update.message.reply_text(
            "Выберите тип аккаунта:",
            reply_markup=reply_markup
        )
    else:
        await update.callback_query.message.reply_text(
            "Выберите тип аккаунта:",
            reply_markup=reply_markup
        )

async def handle_country_page(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка пагинации стран"""
    query = update.callback_query
    await query.answer()
    
    try:
        page = int(query.data.split("_")[1])
        reply_markup = create_countries_keyboard(page)
        await query.message.edit_text(
            "Выберите страну:",
            reply_markup=reply_markup
        )
    except Exception as e:
        logger.error(f"Ошибка в handle_country_page: {e}")
        await query.message.edit_text("Произошла ошибка. Попробуйте еще раз.")

async def show_countries(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать список стран для выбора"""
    query = update.callback_query
    await query.answer()
    
    try:
        reply_markup = create_countries_keyboard(0)
        await query.message.edit_text(
            "Выберите страну:",
            reply_markup=reply_markup
        )
    except Exception as e:
        logger.error(f"Ошибка в show_countries: {e}")
        await query.message.edit_text("Произошла ошибка. Попробуйте еще раз.")

async def show_order_details(update: Update, context: ContextTypes.DEFAULT_TYPE, country_code: str):
    """Показать детали заказа"""
    query = update.callback_query
    await query.answer()
    
    try:
        if country_code not in COUNTRIES:
            await query.message.edit_text("Ошибка: страна не найдена.")
            return
        
        country_info = COUNTRIES[country_code]
        order_id = generate_order_id()
        
        # Сохраняем order_id в контексте
        context.user_data['current_order'] = {
            'order_id': order_id,
            'country_code': country_code,
            'country_name': country_info['name'],
            'phone_code': country_info['code'],
            'price_rub': country_info['price_rub']
        }
        
        # Создаем заказ в БД
        db.create_order(
            order_id, 
            query.from_user.id, 
            country_code, 
            country_info['name'],
            country_info['code'],
            country_info['price_rub']
        )
        
        price_info = format_price(country_info['price_rub'])
        
        order_text = (
            f"🛒 Детали заказа:\n"
            f"├ Страна: {country_info['name']}\n"
            f"├ Код страны: {country_info['code']}\n"
            f"├ Цена: {country_info['price_rub']}₽\n"
            f"├ Цена в USDT/TON: {price_info}\n"
            f"└ Номер заказа: `{order_id}`\n\n"
            "Выберите способ оплаты:"
        )
        
        keyboard = [[
            InlineKeyboardButton("💳 Карта", callback_data="pay_card"),
            InlineKeyboardButton("🤖 Криптобот", callback_data="pay_crypto")
        ]]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.message.edit_text(order_text, reply_markup=reply_markup, parse_mode='Markdown')
        
    except Exception as e:
        logger.error(f"Ошибка в show_order_details: {e}")
        await query.message.edit_text("Произошла ошибка при создании заказа.")

async def show_payment_card(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать реквизиты карты для оплаты"""
    query = update.callback_query
    await query.answer()
    
    try:
        order_info = context.user_data.get('current_order', {})
        order_id = order_info.get('order_id', 'N/A')
        price_rub = order_info.get('price_rub', 0)
        
        payment_text = (
            f"💳 Оплата на карту:\n\n"
            f"Номер: `{CARD_NUMBER}`\n"
            f"Сумма к оплате: *{price_rub}₽* (точно!)\n"
            f"Комментарий к переводу: `{order_id}`\n\n"
            f"⚠️ Обязательно укажите комментарий, иначе платеж не будет зачислен!\n\n"
            f"После оплаты нажмите кнопку ниже:"
        )
        
        keyboard = [[
            InlineKeyboardButton("✅ Я оплатил(а)", callback_data=f"paid_{order_id}")
        ]]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.message.edit_text(payment_text, reply_markup=reply_markup, parse_mode='Markdown')
        
        # Сохраняем метод оплаты
        context.user_data['payment_method'] = 'card'
        
    except Exception as e:
        logger.error(f"Ошибка в show_payment_card: {e}")
        await query.message.edit_text("Произошла ошибка.")

async def show_payment_crypto(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать реквизиты для крипто-оплаты"""
    query = update.callback_query
    await query.answer()
    
    try:
        order_info = context.user_data.get('current_order', {})
        order_id = order_info.get('order_id', 'N/A')
        price_rub = order_info.get('price_rub', 0)
        price_info = format_price(price_rub)
        
        payment_text = (
            f"🤖 Оплата через криптобота:\n\n"
            f"Перейдите по ссылке для оплаты: {CRYPTO_BOT_LINK}\n"
            f"Сумма: *{price_rub}₽* ({price_info})\n"
            f"Укажите номер заказа: `{order_id}`\n\n"
            f"⚠️ Обязательно укажите номер заказа, иначе платеж не будет зачислен!\n\n"
            f"После оплаты нажмите кнопку ниже:"
        )
        
        keyboard = [[
            InlineKeyboardButton("✅ Я оплатил(а)", callback_data=f"paid_{order_id}")
        ]]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.message.edit_text(payment_text, reply_markup=reply_markup, parse_mode='Markdown')
        
        # Сохраняем метод оплаты
        context.user_data['payment_method'] = 'crypto'
        
    except Exception as e:
        logger.error(f"Ошибка в show_payment_crypto: {e}")
        await query.message.edit_text("Произошла ошибка.")

async def request_screenshot(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Запрос скриншота об оплате"""
    query = update.callback_query
    await query.answer()
    
    try:
        callback_data = query.data
        order_id = callback_data.replace("paid_", "")
        
        # Сохраняем order_id в контексте
        context.user_data['waiting_screenshot_for'] = order_id
        
        await query.message.edit_text(
            "📎 Пожалуйста, отправьте скриншот чека об оплате (фото или документ).\n\n"
            "⚠️ Убедитесь, что на скриншоте видно:\n"
            "• Сумма оплаты\n"
            "• Номер заказа (комментарий)\n"
            "• Дата и время оплаты"
        )
    except Exception as e:
        logger.error(f"Ошибка в request_screenshot: {e}")
        await query.message.edit_text("Произошла ошибка.")

async def handle_screenshot(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка скриншота об оплате"""
    try:
        user = update.effective_user
        order_id = context.user_data.get('waiting_screenshot_for')
        
        if not order_id:
            await update.message.reply_text("Пожалуйста, начните процесс покупки сначала.")
            return
        
        # Получаем информацию о заказе
        order_info = db.get_order(order_id)
        if not order_info:
            await update.message.reply_text("Ошибка: заказ не найден.")
            context.user_data.pop('waiting_screenshot_for', None)
            return
        
        # Получаем файл
        file = None
        file_ext = "jpg"
        
        if update.message.photo:
            file = await update.message.photo[-1].get_file()
            file_ext = "jpg"
        elif update.message.document:
            file = await update.message.document.get_file()
            file_ext = update.message.document.file_name.split('.')[-1] if update.message.document.file_name and '.' in update.message.document.file_name else "bin"
        else:
            await update.message.reply_text("Пожалуйста, отправьте фото или документ.")
            return
        
        # Сохраняем информацию о файле
        os.makedirs("screenshots", exist_ok=True)
        file_path = f"screenshots/{order_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.{file_ext}"
        await file.download_to_drive(file_path)
        
        # Обновляем заказ в БД
        payment_method = context.user_data.get('payment_method', 'unknown')
        db.update_order_payment(order_id, payment_method, file_path)
        
        # Получаем информацию о стране
        country_name = order_info[4]  # country_name находится в индексе 4
        price_rub = order_info[6]     # price_rub находится в индексе 6
        
        # Отправляем уведомление админу
        admin_text = (
            f"🔔 Новый заказ на проверку!\n"
            f"├ Покупатель: @{user.username if user.username else 'без username'} (ID: {user.id})\n"
            f"├ Заказ: #{order_id}\n"
            f"├ Страна: {country_name}\n"
            f"└ Сумма: {price_rub}₽"
        )
        
        keyboard = [[
            InlineKeyboardButton("✅ Одобрить", callback_data=f"approve_{order_id}_{user.id}"),
            InlineKeyboardButton("❌ Отклонить", callback_data=f"reject_{order_id}_{user.id}")
        ]]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        # Отправляем сообщение админу с скриншотом
        try:
            with open(file_path, 'rb') as photo:
                await context.bot.send_photo(
                    chat_id=ADMIN_ID,
                    photo=photo,
                    caption=admin_text,
                    reply_markup=reply_markup
                )
        except Exception as e:
            logger.error(f"Ошибка отправки фото админу: {e}")
            # Если не получилось отправить фото, отправляем только текст
            await context.bot.send_message(
                chat_id=ADMIN_ID,
                text=admin_text + f"\n\n📎 Скриншот сохранен: {file_path}",
                reply_markup=reply_markup
            )
        
        await update.message.reply_text(
            "✅ Скриншот получен и отправлен на проверку администратору. "
            "Ожидайте подтверждения оплаты."
        )
        
        # Очищаем контекст
        context.user_data.pop('waiting_screenshot_for', None)
        context.user_data.pop('current_order', None)
        context.user_data.pop('payment_method', None)
        
    except Exception as e:
        logger.error(f"Ошибка в handle_screenshot: {e}")
        await update.message.reply_text("Произошла ошибка при обработке скриншота.")

async def handle_admin_approval(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка одобрения заказа админом"""
    query = update.callback_query
    await query.answer()
    
    try:
        callback_data = query.data
        _, order_id, user_id = callback_data.split("_")
        user_id = int(user_id)
        
        # Обновляем статус заказа
        db.update_order_status(order_id, "completed")
        
        # Отправляем уведомление пользователю
        keyboard = [[
            InlineKeyboardButton("📞 Получить номер", callback_data=f"get_num_{order_id}"),
            InlineKeyboardButton("🔑 Получить код", callback_data=f"get_code_{order_id}")
        ]]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        try:
            await context.bot.send_message(
                chat_id=user_id,
                text=f"✅ Ваш платеж по заказу #{order_id} подтвержден! Аккаунт готов к выдаче.",
                reply_markup=reply_markup
            )
            await query.message.edit_text(f"✅ Заказ #{order_id} одобрен. Пользователь уведомлен.")
        except Exception as e:
            logger.error(f"Ошибка отправки сообщения пользователю: {e}")
            await query.message.edit_text(f"✅ Заказ #{order_id} одобрен, но не удалось уведомить пользователя.")
            
    except Exception as e:
        logger.error(f"Ошибка в handle_admin_approval: {e}")
        await query.message.edit_text("Произошла ошибка при одобрении заказа.")

async def handle_admin_rejection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка отклонения заказа админом"""
    query = update.callback_query
    await query.answer()
    
    try:
        callback_data = query.data
        _, order_id, user_id = callback_data.split("_")
        user_id = int(user_id)
        
        # Обновляем статус заказа
        db.update_order_status(order_id, "rejected")
        
        # Отправляем уведомление пользователю
        try:
            await context.bot.send_message(
                chat_id=user_id,
                text=f"❌ Ваш платеж по заказу #{order_id} отклонен администратором. "
                     f"Свяжитесь с {SUPPORT_USERNAME} для выяснения причин."
            )
            await query.message.edit_text(f"❌ Заказ #{order_id} отклонен. Пользователь уведомлен.")
        except Exception as e:
            logger.error(f"Ошибка отправки сообщения пользователю: {e}")
            await query.message.edit_text(f"❌ Заказ #{order_id} отклонен, но не удалось уведомить пользователя.")
            
    except Exception as e:
        logger.error(f"Ошибка в handle_admin_rejection: {e}")
        await query.message.edit_text("Произошла ошибка при отклонении заказа.")

async def handle_data_request(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка запроса данных пользователем"""
    query = update.callback_query
    await query.answer()
    
    try:
        callback_data = query.data
        data_type = "phone" if "get_num" in callback_data else "code"
        order_id = callback_data.split("_")[-1]
        
        # Проверяем принадлежность заказа
        if not db.check_order_ownership(order_id, query.from_user.id):
            await query.answer("❌ Этот заказ не принадлежит вам!")
            return
        
        user = query.from_user
        
        # Проверяем статус заказа
        order = db.get_order_by_id(order_id)
        if not order or order['status'] != 'completed':
            await query.answer("❌ Заказ не подтвержден или не существует!")
            return
        
        # Проверяем, не были ли уже выданы данные
        issued_data = db.get_issued_data(order_id, data_type)
        if issued_data:
            # Данные уже выданы - отправляем их
            data_text = issued_data[0][0]
            await query.message.edit_text(
                f"📱 Данные для заказа #{order_id}:\n\n"
                f"{'📞 Номер телефона' if data_type == 'phone' else '🔑 Код'}: `{data_text}`\n\n"
                f"⚠️ Сохраните эти данные в надежном месте!",
                parse_mode='Markdown'
            )
            return
        
        # Отправляем запрос админу
        admin_text = (
            f"📲 Запрос на получение данных!\n"
            f"├ Покупатель: @{user.username if user.username else 'без username'}\n"
            f"├ Заказ: #{order_id}\n"
            f"├ Страна: {order['country_name']}\n"
            f"└ Запрошено: {'номер телефона' if data_type == 'phone' else 'код'}"
        )
        
        keyboard = [[
            InlineKeyboardButton("💬 Ответить", callback_data=f"admin_reply_{order_id}_{data_type}")
        ]]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await context.bot.send_message(
            chat_id=ADMIN_ID,
            text=admin_text,
            reply_markup=reply_markup
        )
        
        await query.message.edit_text(
            "📨 Запрос отправлен администратору. Ожидайте..."
        )
        
    except Exception as e:
        logger.error(f"Ошибка в handle_data_request: {e}")
        await query.answer("Произошла ошибка. Попробуйте еще раз.")

async def handle_admin_reply_request(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка запроса админа на ответ"""
    query = update.callback_query
    await query.answer()
    
    try:
        callback_data = query.data
        _, order_id, data_type = callback_data.split("_")
        
        # Просим админа ввести данные
        await query.message.edit_text(
            f"📝 Введите {'номер телефона' if data_type == 'phone' else 'код'} для заказа #{order_id}:"
        )
        
        # Сохраняем контекст для ответа
        context.user_data[f'awaiting_admin_reply_for_{order_id}_{data_type}'] = True
        context.user_data[f'current_admin_reply_order'] = order_id
        context.user_data[f'current_admin_reply_type'] = data_type
        
    except Exception as e:
        logger.error(f"Ошибка в handle_admin_reply_request: {e}")
        await query.message.edit_text("Произошла ошибка.")

async def handle_admin_text_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка текстовых сообщений от админа (для ответа на запросы данных)"""
    user = update.effective_user
    
    if user.id != ADMIN_ID:
        return
    
    text = update.message.text.strip()
    
    # Проверяем, не ждем ли мы ответ на запрос данных
    if 'awaiting_admin_reply_for_' in str(context.user_data.keys()):
        for key in list(context.user_data.keys()):
            if key.startswith('awaiting_admin_reply_for_'):
                order_id = context.user_data.get('current_admin_reply_order')
                data_type = context.user_data.get('current_admin_reply_type')
                
                if order_id and data_type:
                    # Находим user_id из БД
                    order = db.get_order_by_id(order_id)
                    if order:
                        user_id = order['user_id']
                        
                        # Отправляем данные пользователю
                        try:
                            await context.bot.send_message(
                                chat_id=user_id,
                                text=f"📱 Данные для заказа #{order_id}:\n\n"
                                     f"{'📞 Номер телефона' if data_type == 'phone' else '🔑 Код'}: `{text}`\n\n"
                                     f"⚠️ Сохраните эти данные в надежном месте!",
                                parse_mode='Markdown'
                            )
                            
                            # Сохраняем в БД
                            db.add_issued_data(order_id, data_type, text)
                            
                            await update.message.reply_text(
                                f"✅ Данные отправлены пользователю для заказа #{order_id}"
                            )
                            
                            # Очищаем контекст
                            context.user_data.pop(key, None)
                            context.user_data.pop('current_admin_reply_order', None)
                            context.user_data.pop('current_admin_reply_type', None)
                            return
                            
                        except Exception as e:
                            logger.error(f"Ошибка отправки данных пользователю: {e}")
                            await update.message.reply_text(
                                f"❌ Ошибка отправки данных: {e}"
                            )
                            return
    
    # Если это не ответ на запрос, игнорируем
    return

async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик callback запросов"""
    query = update.callback_query
    data = query.data
    
    try:
        if data == "type_fiz":
            await show_countries(update, context)
        elif data.startswith("page_"):
            await handle_country_page(update, context)
        elif data.startswith("country_"):
            country_code = data.replace("country_", "")
            await show_order_details(update, context, country_code)
        elif data == "pay_card":
            await show_payment_card(update, context)
        elif data == "pay_crypto":
            await show_payment_crypto(update, context)
        elif data.startswith("paid_"):
            await request_screenshot(update, context)
        elif data.startswith("approve_"):
            await handle_admin_approval(update, context)
        elif data.startswith("reject_"):
            await handle_admin_rejection(update, context)
        elif data.startswith("get_num_") or data.startswith("get_code_"):
            await handle_data_request(update, context)
        elif data.startswith("admin_reply_"):
            await handle_admin_reply_request(update, context)
        else:
            await query.answer("Неизвестная команда")
    except Exception as e:
        logger.error(f"Ошибка в callback_handler: {e}")
        try:
            await query.answer("Произошла ошибка. Пожалуйста, попробуйте снова.")
        except:
            pass

# ====================== ОСНОВНАЯ ФУНКЦИЯ ======================
def main():
    """Основная функция запуска бота"""
    # Создаем папку для скриншотов
    os.makedirs("screenshots", exist_ok=True)
    
    # Создаем приложение
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Регистрируем обработчики в правильном порядке
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CallbackQueryHandler(callback_handler))
    
    # Обработчик текстовых сообщений от админа (только для ответов на запросы)
    application.add_handler(MessageHandler(
        filters.TEXT & filters.User(ADMIN_ID), 
        handle_admin_text_message
    ))
    
    # Обработчик медиафайлов (скриншотов)
    application.add_handler(MessageHandler(
        filters.PHOTO | filters.Document.ALL,
        handle_screenshot
    ))
    
    # Общий обработчик текстовых сообщений для обычных пользователей
    application.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND,
        handle_message
    ))
    
    # Запуск бота
    print("=" * 50)
    print("🤖 БОТ ЗАПУЩЕН!")
    print("=" * 50)
    print(f"👑 Администратор: {ADMIN_ID}")
    print(f"💬 Поддержка: {SUPPORT_USERNAME}")
    print(f"🌍 Доступно стран: {len(COUNTRIES)}")
    print("=" * 50)
    print("📊 Статистика цен:")
    min_country = min(COUNTRIES.items(), key=lambda x: x[1]['price_rub'])
    max_country = max(COUNTRIES.items(), key=lambda x: x[1]['price_rub'])
    print(f"💰 Самая дешевая: {min_country[1]['name']} - {min_country[1]['price_rub']}₽")
    print(f"💎 Самая дорогая: {max_country[1]['name']} - {max_country[1]['price_rub']}₽")
    print("=" * 50)
    print("✅ Бот готов к работе!")
    print("✅ Команда /start должна работать")
    print("✅ Главное меню доступно")
    print("✅ База данных создана")
    print("=" * 50)
    
    try:
        application.run_polling(allowed_updates=Update.ALL_TYPES, drop_pending_updates=True)
    except Exception as e:
        logger.error(f"Ошибка запуска бота: {e}")
        print(f"❌ Ошибка запуска: {e}")

if __name__ == "__main__":
    main()
