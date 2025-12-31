import sqlite3
import logging
from datetime import datetime
from typing import Dict, Optional, Tuple
import json
import os

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

# Прайс-лист стран
COUNTRIES = {
    "usa": {"name": "🇺🇸 США", "price_rub": 30},
    "germany": {"name": "🇩🇪 Германия", "price_rub": 35},
    "france": {"name": "🇫🇷 Франция", "price_rub": 32},
    "uk": {"name": "🇬🇧 Великобритания", "price_rub": 38},
    "japan": {"name": "🇯🇵 Япония", "price_rub": 40},
    "canada": {"name": "🇨🇦 Канада", "price_rub": 33},
    "brazil": {"name": "🇧🇷 Бразилия", "price_rub": 28},
    "india": {"name": "🇮🇳 Индия", "price_rub": 25},
    "russia": {"name": "🇷🇺 Россия", "price_rub": 20},
    "china": {"name": "🇨🇳 Китай", "price_rub": 36},
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
    
    def init_db(self):
        """Инициализация базы данных"""
        with sqlite3.connect(self.db_name) as conn:
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
                    order_id TEXT PRIMARY KEY,
                    user_id INTEGER,
                    country_code TEXT,
                    country_name TEXT,
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
                    order_id TEXT,
                    data_type TEXT,  -- 'phone' или 'code'
                    data_text TEXT,
                    issued_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (order_id) REFERENCES orders (order_id)
                )
            ''')
            
            conn.commit()
    
    def add_user(self, user_id: int, username: str):
        """Добавление пользователя в БД"""
        with sqlite3.connect(self.db_name) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT OR IGNORE INTO users (user_id, username) VALUES (?, ?)",
                (user_id, username)
            )
            conn.commit()
    
    def create_order(self, order_id: str, user_id: int, country_code: str, country_name: str, price_rub: int):
        """Создание нового заказа"""
        with sqlite3.connect(self.db_name) as conn:
            cursor = conn.cursor()
            cursor.execute(
                '''INSERT INTO orders 
                (order_id, user_id, country_code, country_name, price_rub, status) 
                VALUES (?, ?, ?, ?, ?, ?)''',
                (order_id, user_id, country_code, country_name, price_rub, 'pending')
            )
            conn.commit()
    
    def update_order_payment(self, order_id: str, payment_method: str, screenshot_path: str = None):
        """Обновление информации об оплате заказа"""
        with sqlite3.connect(self.db_name) as conn:
            cursor = conn.cursor()
            cursor.execute(
                '''UPDATE orders 
                SET payment_method = ?, payment_screenshot = ?, status = 'waiting_approval'
                WHERE order_id = ?''',
                (payment_method, screenshot_path, order_id)
            )
            conn.commit()
    
    def update_order_status(self, order_id: str, status: str):
        """Обновление статуса заказа"""
        with sqlite3.connect(self.db_name) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE orders SET status = ? WHERE order_id = ?",
                (status, order_id)
            )
            conn.commit()
    
    def get_order(self, order_id: str) -> Optional[Tuple]:
        """Получение информации о заказе"""
        with sqlite3.connect(self.db_name) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM orders WHERE order_id = ?", (order_id,))
            return cursor.fetchone()
    
    def get_user_orders(self, user_id: int, limit: int = 5) -> list:
        """Получение истории заказов пользователя"""
        with sqlite3.connect(self.db_name) as conn:
            cursor = conn.cursor()
            cursor.execute(
                '''SELECT order_id, country_name, price_rub, created_at, status 
                FROM orders 
                WHERE user_id = ? AND status = 'completed'
                ORDER BY created_at DESC 
                LIMIT ?''',
                (user_id, limit)
            )
            return cursor.fetchall()
    
    def add_issued_data(self, order_id: str, data_type: str, data_text: str):
        """Добавление выданных данных"""
        with sqlite3.connect(self.db_name) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO issued_data (order_id, data_type, data_text) VALUES (?, ?, ?)",
                (order_id, data_type, data_text)
            )
            conn.commit()

# Инициализация базы данных
db = Database()

# ====================== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ======================
def generate_order_id() -> str:
    """Генерация уникального ID заказа"""
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    import random
    random_part = random.randint(1000, 9999)
    return f"ORD-{timestamp}-{random_part}"

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

# ====================== ОБРАБОТЧИКИ КОМАНД ======================
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /start"""
    user = update.effective_user
    db.add_user(user.id, user.username)
    
    welcome_text = (
        "🤖 Добро пожаловать в бота для покупки аккаунтов!\n\n"
        "Выберите действие в меню ниже:"
    )
    
    await update.message.reply_text(
        welcome_text,
        reply_markup=create_main_keyboard()
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик текстовых сообщений"""
    text = update.message.text
    
    if text == "🛒 Купить аккаунт":
        await show_account_types(update, context)
    elif text == "👤 Профиль":
        await show_profile(update, context)
    elif text == "🆘 Поддержка":
        await show_support(update, context)

async def show_support(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать информацию о поддержке"""
    support_text = f"🆘 По всем вопросам обращайтесь: {SUPPORT_USERNAME}"
    await update.message.reply_text(support_text)

async def show_profile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать профиль пользователя"""
    user = update.effective_user
    orders = db.get_user_orders(user.id)
    
    profile_text = f"👤 Ваш профиль:\n"
    profile_text += f"├ ID: `{user.id}`\n"
    profile_text += f"├ Юзернейм: @{user.username if user.username else 'Отсутствует'}\n"
    profile_text += f"└ История покупок:\n"
    
    if orders:
        for order in orders:
            order_id, country_name, price_rub, created_at, _ = order
            date_str = datetime.strptime(created_at, "%Y-%m-%d %H:%M:%S").strftime("%Y-%m-%d")
            profile_text += f"   • {date_str} | {country_name} ({price_rub}₽) - #{order_id.split('-')[1]}\n"
    else:
        profile_text += "   Пока нет покупок\n"
    
    await update.message.reply_text(profile_text, parse_mode='Markdown')

async def show_account_types(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать типы аккаунтов"""
    keyboard = [[
        InlineKeyboardButton("📱 ФИЗ аккаунты", callback_data="type_fiz")
    ]]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        "Выберите тип аккаунта:",
        reply_markup=reply_markup
    )

async def show_countries(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать список стран для выбора"""
    keyboard = []
    row = []
    
    for code, info in COUNTRIES.items():
        button = InlineKeyboardButton(
            f"{info['name']} - {info['price_rub']}₽",
            callback_data=f"country_{code}"
        )
        row.append(button)
        if len(row) == 2:
            keyboard.append(row)
            row = []
    
    if row:
        keyboard.append(row)
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.callback_query.message.edit_text(
        "Выберите страну:",
        reply_markup=reply_markup
    )

async def show_order_details(update: Update, context: ContextTypes.DEFAULT_TYPE, country_code: str):
    """Показать детали заказа"""
    query = update.callback_query
    await query.answer()
    
    country_info = COUNTRIES[country_code]
    order_id = generate_order_id()
    
    # Сохраняем order_id в контексте
    context.user_data['current_order'] = {
        'order_id': order_id,
        'country_code': country_code,
        'country_name': country_info['name'],
        'price_rub': country_info['price_rub']
    }
    
    # Создаем заказ в БД
    db.create_order(
        order_id, 
        query.from_user.id, 
        country_code, 
        country_info['name'], 
        country_info['price_rub']
    )
    
    price_info = format_price(country_info['price_rub'])
    
    order_text = (
        f"🛒 Детали заказа:\n"
        f"├ Страна: {country_info['name']}\n"
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

async def show_payment_card(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать реквизиты карты для оплаты"""
    query = update.callback_query
    await query.answer()
    
    order_info = context.user_data.get('current_order', {})
    order_id = order_info.get('order_id', 'N/A')
    price_rub = order_info.get('price_rub', 0)
    
    payment_text = (
        f"💳 Оплата на карту:\n\n"
        f"Номер: `{CARD_NUMBER}`\n"
        f"Сумма к оплате: *{price_rub}₽* (точно!)\n"
        f"Комментарий к переводу: `{order_id}`\n\n"
        f"После оплаты нажмите кнопку ниже:"
    )
    
    keyboard = [[
        InlineKeyboardButton("✅ Я оплатил(а)", callback_data=f"paid_{order_id}")
    ]]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.message.edit_text(payment_text, reply_markup=reply_markup, parse_mode='Markdown')
    
    # Сохраняем метод оплаты
    context.user_data['payment_method'] = 'card'

async def show_payment_crypto(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать реквизиты для крипто-оплаты"""
    query = update.callback_query
    await query.answer()
    
    order_info = context.user_data.get('current_order', {})
    order_id = order_info.get('order_id', 'N/A')
    price_rub = order_info.get('price_rub', 0)
    price_info = format_price(price_rub)
    
    payment_text = (
        f"🤖 Оплата через криптобота:\n\n"
        f"Перейдите по ссылке для оплаты: {CRYPTO_BOT_LINK}\n"
        f"Сумма: *{price_rub}₽* ({price_info})\n"
        f"Укажите номер заказа: `{order_id}`\n\n"
        f"После оплаты нажмите кнопку ниже:"
    )
    
    keyboard = [[
        InlineKeyboardButton("✅ Я оплатил(а)", callback_data=f"paid_{order_id}")
    ]]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.message.edit_text(payment_text, reply_markup=reply_markup, parse_mode='Markdown')
    
    # Сохраняем метод оплаты
    context.user_data['payment_method'] = 'crypto'

async def request_screenshot(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Запрос скриншота об оплате"""
    query = update.callback_query
    await query.answer()
    
    callback_data = query.data
    order_id = callback_data.replace("paid_", "")
    
    # Сохраняем order_id в контексте
    context.user_data['waiting_screenshot_for'] = order_id
    
    await query.message.edit_text(
        "📎 Пожалуйста, отправьте скриншот чека об оплате (фото или документ)."
    )

async def handle_screenshot(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка скриншота об оплате"""
    user = update.effective_user
    order_id = context.user_data.get('waiting_screenshot_for')
    
    if not order_id:
        await update.message.reply_text("Пожалуйста, начните процесс покупки сначала.")
        return
    
    # Получаем файл
    if update.message.photo:
        file = await update.message.photo[-1].get_file()
    elif update.message.document:
        file = await update.message.document.get_file()
    else:
        await update.message.reply_text("Пожалуйста, отправьте фото или документ.")
        return
    
    # Сохраняем информацию о файле
    file_path = f"screenshots/{order_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg"
    os.makedirs("screenshots", exist_ok=True)
    await file.download_to_drive(file_path)
    
    # Получаем информацию о заказе
    order_info = db.get_order(order_id)
    if not order_info:
        await update.message.reply_text("Ошибка: заказ не найден.")
        return
    
    # Обновляем заказ в БД
    payment_method = context.user_data.get('payment_method', 'unknown')
    db.update_order_payment(order_id, payment_method, file_path)
    
    # Отправляем уведомление админу
    order_details = f"Заказ: {order_info[1]}\nСтрана: {order_info[4]}\nЦена: {order_info[5]}₽"
    
    admin_text = (
        f"🔔 Новый заказ на проверку!\n"
        f"├ Покупатель: @{user.username if user.username else 'без username'} (ID: {user.id})\n"
        f"├ Заказ: #{order_id}\n"
        f"├ Страна: {order_info[4]}\n"
        f"└ Сумма: {order_info[5]}₽"
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

async def handle_admin_approval(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка одобрения заказа админом"""
    query = update.callback_query
    await query.answer()
    
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
    except Exception as e:
        logger.error(f"Ошибка отправки сообщения пользователю: {e}")
    
    # Обновляем сообщение админа
    await query.message.edit_text(
        f"✅ Заказ #{order_id} одобрен. Пользователь уведомлен."
    )

async def handle_admin_rejection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка отклонения заказа админом"""
    query = update.callback_query
    await query.answer()
    
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
    except Exception as e:
        logger.error(f"Ошибка отправки сообщения пользователю: {e}")
    
    # Обновляем сообщение админа
    await query.message.edit_text(
        f"❌ Заказ #{order_id} отклонен. Пользователь уведомлен."
    )

async def handle_data_request(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка запроса данных пользователем"""
    query = update.callback_query
    await query.answer()
    
    callback_data = query.data
    data_type = "phone" if "get_num" in callback_data else "code"
    order_id = callback_data.split("_")[-1]
    
    user = query.from_user
    
    # Отправляем запрос админу
    admin_text = (
        f"📲 Запрос на получение данных!\n"
        f"├ Покупатель: @{user.username if user.username else 'без username'}\n"
        f"├ Заказ: #{order_id}\n"
        f"└ Запрошено: {'номер телефона' if data_type == 'phone' else 'код'}"
    )
    
    # Сохраняем информацию для ответа
    context.user_data[f'admin_reply_to_{order_id}_{data_type}'] = user.id
    
    keyboard = [[
        InlineKeyboardButton("💬 Ответить", callback_data=f"reply_{order_id}_{data_type}")
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

async def handle_admin_reply(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка ответа админа на запрос данных"""
    query = update.callback_query
    await query.answer()
    
    callback_data = query.data
    _, order_id, data_type = callback_data.split("_")
    
    # Просим админа ввести данные
    await query.message.edit_text(
        f"📝 Введите {'номер телефона' if data_type == 'phone' else 'код'} для заказа #{order_id}:"
    )
    
    # Сохраняем контекст для ответа
    context.user_data[f'awaiting_admin_reply_for_{order_id}_{data_type}'] = True

async def handle_admin_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка сообщений от админа"""
    user = update.effective_user
    
    if user.id != ADMIN_ID:
        return
    
    text = update.message.text
    
    # Проверяем, не ждем ли мы ответ на запрос данных
    for key in list(context.user_data.keys()):
        if key.startswith('awaiting_admin_reply_for_'):
            _, order_id, data_type = key.replace('awaiting_admin_reply_for_', '').split('_')
            
            # Ищем user_id в другом ключе
            user_id_key = f'admin_reply_to_{order_id}_{data_type}'
            user_id = context.user_data.get(user_id_key)
            
            if user_id:
                # Отправляем данные пользователю
                try:
                    await context.bot.send_message(
                        chat_id=user_id,
                        text=f"📱 Данные для заказа #{order_id}:\n\n{text}"
                    )
                    
                    # Сохраняем в БД
                    db.add_issued_data(order_id, data_type, text)
                    
                    await update.message.reply_text(
                        f"✅ Данные отправлены пользователю для заказа #{order_id}"
                    )
                except Exception as e:
                    logger.error(f"Ошибка отправки данных пользователю: {e}")
                    await update.message.reply_text(
                        f"❌ Ошибка отправки данных: {e}"
                    )
                
                # Очищаем контекст
                context.user_data.pop(key, None)
                context.user_data.pop(user_id_key, None)
                
            return

async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик callback запросов"""
    query = update.callback_query
    data = query.data
    
    try:
        if data == "type_fiz":
            await show_countries(update, context)
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
        elif data.startswith("reply_"):
            await handle_admin_reply(update, context)
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
    
    # Регистрируем обработчики
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CallbackQueryHandler(callback_handler))
    
    # Обработчик сообщений от админа (должен быть перед общим обработчиком)
    application.add_handler(MessageHandler(
        filters.TEXT & filters.User(ADMIN_ID), 
        handle_admin_message
    ))
    
    # Обработчик скриншотов
    application.add_handler(MessageHandler(
        filters.PHOTO | filters.DOCUMENT,
        handle_screenshot
    ))
    
    # Общий обработчик текстовых сообщений
    application.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND,
        handle_message
    ))
    
    # Запуск бота
    print("Бот запущен...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
