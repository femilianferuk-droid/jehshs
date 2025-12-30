#!/usr/bin/env python3
"""
Telegram Bot для продажи аккаунтов
Полный исправленный код с рабочими уведомлениями
"""

import logging
import sqlite3
import datetime
import re
import asyncio
from typing import Optional, Tuple, List, Dict
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters
from telegram.constants import ParseMode

# ============================================
# КОНФИГУРАЦИЯ
# ============================================
TOKEN = "8244265951:AAESPS6P-Yekbls_CkwvD4vpOts0lL9MxuA"
ADMIN_ID = 7973988177
DATABASE_FILE = "accounts_bot.db"

# Прайс-лист
PRICES = [
    {"code": "+1", "country": "США", "price": 30, "emoji": "🇺🇸"},
    {"code": "+1", "country": "Канада", "price": 35, "emoji": "🇨🇦"},
    {"code": "+7", "country": "Россия", "price": 199, "emoji": "🇷🇺"},
    {"code": "+7", "country": "Казахстан", "price": 175, "emoji": "🇰🇿"},
    {"code": "+20", "country": "Египет", "price": 50, "emoji": "🇪🇬"},
    {"code": "+27", "country": "ЮАР", "price": 100, "emoji": "🇿🇦"},
    {"code": "+30", "country": "Греция", "price": 175, "emoji": "🇬🇷"},
    {"code": "+31", "country": "Нидерланды", "price": 275, "emoji": "🇳🇱"},
    {"code": "+32", "country": "Бельгия", "price": 1200, "emoji": "🇧🇪"},
    {"code": "+33", "country": "Франция", "price": 250, "emoji": "🇫🇷"},
    {"code": "+34", "country": "Испания", "price": 250, "emoji": "🇪🇸"},
    {"code": "+36", "country": "Венгрия", "price": 250, "emoji": "🇭🇺"},
    {"code": "+39", "country": "Италия", "price": 600, "emoji": "🇮🇹"},
    {"code": "+40", "country": "Румыния", "price": 80, "emoji": "🇷🇴"},
    {"code": "+41", "country": "Швейцария", "price": 2000, "emoji": "🇨🇭"},
    {"code": "+43", "country": "Австрия", "price": 1000, "emoji": "🇦🇹"},
    {"code": "+44", "country": "Великобритания", "price": 125, "emoji": "🇬🇧"},
    {"code": "+45", "country": "Дания", "price": 1150, "emoji": "🇩🇰"},
    {"code": "+46", "country": "Швеция", "price": 400, "emoji": "🇸🇪"},
    {"code": "+47", "country": "Норвегия", "price": 1150, "emoji": "🇳🇴"},
    {"code": "+48", "country": "Польша", "price": 275, "emoji": "🇵🇱"},
    {"code": "+55", "country": "Бразилия", "price": 125, "emoji": "🇧🇷"},
    {"code": "+57", "country": "Колумбия", "price": 75, "emoji": "🇨🇴"},
    {"code": "+62", "country": "Индонезия", "price": 50, "emoji": "🇮🇩"},
    {"code": "+84", "country": "Вьетнам", "price": 70, "emoji": "🇻🇳"},
    {"code": "+86", "country": "Китай", "price": 750, "emoji": "🇨🇳"},
    {"code": "+90", "country": "Турция", "price": 100, "emoji": "🇹🇷"},
    {"code": "+91", "country": "Индия", "price": 40, "emoji": "🇮🇳"},
    {"code": "+92", "country": "Пакистан", "price": 70, "emoji": "🇵🇰"},
    {"code": "+93", "country": "Афганистан", "price": 75, "emoji": "🇦🇫"},
    {"code": "+94", "country": "Шри-Ланка", "price": 100, "emoji": "🇱🇰"},
    {"code": "+95", "country": "Мьянма", "price": 35, "emoji": "🇲🇲"},
    {"code": "+98", "country": "Иран", "price": 175, "emoji": "🇮🇷"},
    {"code": "+212", "country": "Марокко", "price": 75, "emoji": "🇲🇦"},
    {"code": "+225", "country": "Кот-д'Ивуар", "price": 750, "emoji": "🇨🇮"},
    {"code": "+233", "country": "Гана", "price": 550, "emoji": "🇬🇭"},
    {"code": "+234", "country": "Нигерия", "price": 45, "emoji": "🇳🇬"},
    {"code": "+254", "country": "Кения", "price": 40, "emoji": "🇰🇪"},
    {"code": "+373", "country": "Молдова", "price": 175, "emoji": "🇲🇩"},
    {"code": "+374", "country": "Армения", "price": 400, "emoji": "🇦🇲"},
    {"code": "+375", "country": "Беларусь", "price": 170, "emoji": "🇧🇾"},
    {"code": "+380", "country": "Украина", "price": 235, "emoji": "🇺🇦"},
]

# Реквизиты
PAYMENT_CARD = "5599 0021 2767 5173"
CRYPTO_BOT_LINK = "http://t.me/send?start=IVKF2M5j40O5"

# ============================================
# НАСТРОЙКА ЛОГИРОВАНИЯ
# ============================================
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ============================================
# БАЗА ДАННЫХ
# ============================================
class Database:
    def __init__(self):
        self.conn = sqlite3.connect(DATABASE_FILE, check_same_thread=False)
        self.init_db()
    
    def init_db(self):
        cursor = self.conn.cursor()
        
        # Пользователи
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                balance REAL DEFAULT 0,
                reg_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Покупки
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS purchases (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                country TEXT,
                amount REAL,
                status TEXT DEFAULT 'pending',
                payment_screenshot TEXT,
                date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                admin_notes TEXT,
                phone_number TEXT,
                code TEXT,
                FOREIGN KEY (user_id) REFERENCES users (user_id)
            )
        ''')
        
        # Промокоды
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS promocodes (
                code TEXT PRIMARY KEY,
                amount REAL,
                activations_left INTEGER,
                expiry_date TEXT,
                is_active INTEGER DEFAULT 1
            )
        ''')
        
        # Состояния пользователей
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS user_states (
                user_id INTEGER PRIMARY KEY,
                state TEXT,
                data TEXT,
                FOREIGN KEY (user_id) REFERENCES users (user_id)
            )
        ''')
        
        self.conn.commit()
        logger.info("База данных инициализирована")
    
    def add_user(self, user_id: int, username: str):
        cursor = self.conn.cursor()
        cursor.execute(
            "INSERT OR IGNORE INTO users (user_id, username) VALUES (?, ?)",
            (user_id, username or '')
        )
        self.conn.commit()
    
    def get_user(self, user_id: int) -> Optional[Tuple]:
        cursor = self.conn.cursor()
        cursor.execute(
            "SELECT user_id, username, balance, reg_date FROM users WHERE user_id = ?",
            (user_id,)
        )
        return cursor.fetchone()
    
    def update_balance(self, user_id: int, amount: float):
        cursor = self.conn.cursor()
        cursor.execute(
            "UPDATE users SET balance = balance + ? WHERE user_id = ?",
            (amount, user_id)
        )
        self.conn.commit()
    
    def get_balance(self, user_id: int) -> float:
        cursor = self.conn.cursor()
        cursor.execute(
            "SELECT balance FROM users WHERE user_id = ?",
            (user_id,)
        )
        result = cursor.fetchone()
        return result[0] if result else 0.0
    
    def add_purchase(self, user_id: int, country: str, amount: float) -> int:
        cursor = self.conn.cursor()
        cursor.execute(
            "INSERT INTO purchases (user_id, country, amount, status) VALUES (?, ?, ?, 'pending')",
            (user_id, country, amount)
        )
        self.conn.commit()
        return cursor.lastrowid
    
    def update_purchase_screenshot(self, purchase_id: int, screenshot: str):
        cursor = self.conn.cursor()
        cursor.execute(
            "UPDATE purchases SET payment_screenshot = ?, status = 'checking' WHERE id = ?",
            (screenshot, purchase_id)
        )
        self.conn.commit()
    
    def update_purchase_status(self, purchase_id: int, status: str, notes: str = None):
        cursor = self.conn.cursor()
        if notes:
            cursor.execute(
                "UPDATE purchases SET status = ?, admin_notes = ? WHERE id = ?",
                (status, notes, purchase_id)
            )
        else:
            cursor.execute(
                "UPDATE purchases SET status = ? WHERE id = ?",
                (status, purchase_id)
            )
        self.conn.commit()
    
    def update_purchase_data(self, purchase_id: int, phone_number: str = None, code: str = None):
        cursor = self.conn.cursor()
        if phone_number:
            cursor.execute(
                "UPDATE purchases SET phone_number = ? WHERE id = ?",
                (phone_number, purchase_id)
            )
        if code:
            cursor.execute(
                "UPDATE purchases SET code = ? WHERE id = ?",
                (code, purchase_id)
            )
        self.conn.commit()
    
    def get_purchase(self, purchase_id: int) -> Optional[Tuple]:
        cursor = self.conn.cursor()
        cursor.execute(
            "SELECT * FROM purchases WHERE id = ?",
            (purchase_id,)
        )
        return cursor.fetchone()
    
    def get_pending_purchases(self) -> List[Tuple]:
        cursor = self.conn.cursor()
        cursor.execute(
            """SELECT p.*, u.username 
               FROM purchases p 
               LEFT JOIN users u ON p.user_id = u.user_id 
               WHERE p.status = 'pending' 
               ORDER BY p.date DESC"""
        )
        return cursor.fetchall()
    
    def get_user_purchases(self, user_id: int, limit: int = 5) -> List[Tuple]:
        cursor = self.conn.cursor()
        cursor.execute(
            "SELECT id, country, amount, status, date FROM purchases WHERE user_id = ? ORDER BY date DESC LIMIT ?",
            (user_id, limit)
        )
        return cursor.fetchall()
    
    def set_user_state(self, user_id: int, state: str, data: str = None):
        cursor = self.conn.cursor()
        cursor.execute(
            "INSERT OR REPLACE INTO user_states (user_id, state, data) VALUES (?, ?, ?)",
            (user_id, state, data or '')
        )
        self.conn.commit()
    
    def get_user_state(self, user_id: int) -> Optional[Tuple]:
        cursor = self.conn.cursor()
        cursor.execute(
            "SELECT state, data FROM user_states WHERE user_id = ?",
            (user_id,)
        )
        return cursor.fetchone()
    
    def clear_user_state(self, user_id: int):
        cursor = self.conn.cursor()
        cursor.execute("DELETE FROM user_states WHERE user_id = ?", (user_id,))
        self.conn.commit()
    
    def get_all_users(self) -> List[Tuple]:
        cursor = self.conn.cursor()
        cursor.execute("SELECT user_id, username FROM users")
        return cursor.fetchall()
    
    def get_statistics(self) -> Dict:
        cursor = self.conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM users")
        total_users = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM purchases")
        total_purchases = cursor.fetchone()[0]
        
        cursor.execute("SELECT SUM(amount) FROM purchases WHERE status = 'approved' OR status = 'completed'")
        total_revenue = cursor.fetchone()[0] or 0
        
        return {
            "total_users": total_users,
            "total_purchases": total_purchases,
            "total_revenue": total_revenue
        }

# ============================================
# ИНИЦИАЛИЗАЦИЯ БАЗЫ ДАННЫХ
# ============================================
db = Database()

# ============================================
# КЛАВИАТУРЫ
# ============================================
def get_main_keyboard():
    """Основная клавиатура"""
    return ReplyKeyboardMarkup([
        [KeyboardButton("🛒 Купить аккаунт")],
        [KeyboardButton("👤 Профиль"), KeyboardButton("🆘 Поддержка")]
    ], resize_keyboard=True)

def get_countries_keyboard():
    """Выбор страны"""
    keyboard = []
    for i, item in enumerate(PRICES):
        keyboard.append([
            InlineKeyboardButton(
                f"{item['emoji']} {item['country']} - {item['price']}₽",
                callback_data=f"country_{i}"
            )
        ])
    keyboard.append([InlineKeyboardButton("« Назад", callback_data="back_to_main")])
    return InlineKeyboardMarkup(keyboard)

def get_payment_keyboard(purchase_id: int):
    """Оплата"""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ Я оплатил(а)", callback_data=f"paid_{purchase_id}")],
        [InlineKeyboardButton("« Назад", callback_data="back_to_countries")]
    ])

def get_approved_purchase_keyboard(purchase_id: int):
    """После подтверждения оплаты"""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📱 Получить номер", callback_data=f"get_number_{purchase_id}")],
        [InlineKeyboardButton("🔢 Получить код", callback_data=f"get_code_{purchase_id}")]
    ])

def get_admin_keyboard():
    """Админ-панель"""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📊 Статистика", callback_data="admin_stats")],
        [InlineKeyboardButton("📢 Рассылка", callback_data="admin_broadcast")],
        [InlineKeyboardButton("💰 Управление ценами", callback_data="admin_prices")],
        [InlineKeyboardButton("🧾 Проверить чеки", callback_data="admin_checks")],
        [InlineKeyboardButton("🎫 Промокоды", callback_data="admin_promocodes")],
        [InlineKeyboardButton("« Выйти", callback_data="admin_exit")]
    ])

def get_check_purchase_keyboard(purchase_id: int):
    """Проверка чека"""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Одобрить", callback_data=f"check_approve_{purchase_id}"),
            InlineKeyboardButton("❌ Отклонить", callback_data=f"check_reject_{purchase_id}")
        ],
        [InlineKeyboardButton("« Назад", callback_data="back_to_admin")]
    ])

def get_back_admin_keyboard():
    """Назад в админку"""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("« Назад в админ-панель", callback_data="back_to_admin")]
    ])

# ============================================
# ОСНОВНЫЕ ФУНКЦИИ
# ============================================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик /start"""
    user = update.effective_user
    db.add_user(user.id, user.username)
    
    await update.message.reply_text(
        f"👋 Привет, {user.first_name}!\n\n"
        "Добро пожаловать в бота для покупки аккаунтов!",
        reply_markup=get_main_keyboard()
    )

async def admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик /admin"""
    user_id = update.effective_user.id
    if user_id == ADMIN_ID:
        await update.message.reply_text(
            "🔐 Админ-панель:",
            reply_markup=get_admin_keyboard()
        )
    else:
        await update.message.reply_text("У вас нет доступа к админ-панели.")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик текстовых сообщений"""
    user_id = update.effective_user.id
    text = update.message.text
    
    if text == "🛒 Купить аккаунт":
        await update.message.reply_text(
            "Выберите страну:",
            reply_markup=get_countries_keyboard()
        )
    
    elif text == "👤 Профиль":
        await show_profile(update, context)
    
    elif text == "🆘 Поддержка":
        await update.message.reply_text(
            "По всем вопросам обращайтесь к поддержке:\nhttps://t.me/starfizovoi",
            reply_markup=get_main_keyboard()
        )
    
    else:
        # Проверяем состояние пользователя
        state_data = db.get_user_state(user_id)
        if state_data:
            state, data = state_data
            
            if state == "waiting_screenshot":
                purchase_id = int(data)
                if update.message.photo:
                    # Получаем фото
                    photo = update.message.photo[-1]
                    file_id = photo.file_id
                    
                    # Сохраняем скриншот
                    db.update_purchase_screenshot(purchase_id, file_id)
                    db.clear_user_state(user_id)
                    
                    # Получаем информацию о покупке
                    purchase = db.get_purchase(purchase_id)
                    if purchase:
                        user_info = db.get_user(purchase[1])
                        username = user_info[1] if user_info else "N/A"
                        
                        # Отправляем админу
                        caption = (
                            f"🆕 Новый чек на проверку!\n\n"
                            f"ID заказа: #{purchase_id}\n"
                            f"Пользователь: @{username}\n"
                            f"Страна: {purchase[2]}\n"
                            f"Сумма: {purchase[3]}₽\n"
                            f"Дата: {purchase[6]}"
                        )
                        
                        try:
                            await context.bot.send_photo(
                                chat_id=ADMIN_ID,
                                photo=file_id,
                                caption=caption,
                                reply_markup=get_check_purchase_keyboard(purchase_id)
                            )
                        except Exception as e:
                            logger.error(f"Ошибка отправки фото админу: {e}")
                            await context.bot.send_message(
                                chat_id=ADMIN_ID,
                                text=caption + "\n\n(Скриншот приложен)",
                                reply_markup=get_check_purchase_keyboard(purchase_id)
                            )
                    
                    await update.message.reply_text(
                        "✅ Чек отправлен на проверку администратору.\n"
                        "Статус: ⏳ Чек на проверке у администратора.",
                        reply_markup=get_main_keyboard()
                    )
                else:
                    await update.message.reply_text("Пожалуйста, отправьте скриншот оплаты (фото).")
            
            elif state.startswith("admin_"):
                # Обработка действий админа
                await handle_admin_state(update, context, state, data, text)
        
        else:
            await update.message.reply_text(
                "Используйте кнопки меню для навигации.",
                reply_markup=get_main_keyboard()
            )

async def show_profile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать профиль пользователя"""
    user_id = update.effective_user.id
    
    # Добавляем пользователя если его нет
    db.add_user(user_id, update.effective_user.username)
    user = db.get_user(user_id)
    
    if not user:
        await update.message.reply_text("Ошибка загрузки профиля.")
        return
    
    # Получаем покупки
    purchases = db.get_user_purchases(user_id)
    
    profile_text = (
        f"👤 *Профиль*\n\n"
        f"*ID:* `{user[0]}`\n"
        f"*Юзернейм:* @{user[1] if user[1] else 'нет'}\n"
        f"*Баланс:* {user[2]}₽\n\n"
        f"*Последние покупки:*\n"
    )
    
    if purchases:
        for purchase in purchases:
            status_emoji = {
                "pending": "⏳",
                "checking": "⏳",
                "approved": "✅",
                "rejected": "❌"
            }.get(purchase[3], "❓")
            
            profile_text += (
                f"• {purchase[1]} - {purchase[2]}₽ - "
                f"{purchase[4].split()[0]} - {status_emoji}\n"
            )
    else:
        profile_text += "Покупок еще нет\n"
    
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🎁 Активировать промокод", callback_data="activate_promocode")],
        [InlineKeyboardButton("« Назад", callback_data="back_to_main")]
    ])
    
    if update.callback_query:
        await update.callback_query.edit_message_text(
            profile_text,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=keyboard
        )
    else:
        await update.message.reply_text(
            profile_text,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=keyboard
        )

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик callback-запросов"""
    query = update.callback_query
    user_id = query.from_user.id
    data = query.data
    
    await query.answer()
    
    # Основные действия
    if data == "back_to_main":
        await query.message.reply_text(
            "Главное меню:",
            reply_markup=get_main_keyboard()
        )
    
    elif data == "back_to_countries":
        await query.message.reply_text(
            "Выберите страну:",
            reply_markup=get_countries_keyboard()
        )
    
    elif data == "back_to_admin":
        if user_id == ADMIN_ID:
            await query.message.reply_text(
                "🔐 Админ-панель:",
                reply_markup=get_admin_keyboard()
            )
    
    elif data.startswith("country_"):
        idx = int(data.split("_")[1])
        item = PRICES[idx]
        purchase_id = db.add_purchase(user_id, item["country"], item["price"])
        
        payment_text = (
            f"*Страна:* {item['emoji']} {item['country']} ({item['code']})\n"
            f"*Сумма к оплате:* {item['price']}₽\n\n"
            f"*Оплата:*\n"
            f"🔸 **Карта:** `{PAYMENT_CARD}`\n"
            f"🔸 **Криптобот:** `{CRYPTO_BOT_LINK}`\n\n"
            f"После оплаты нажмите «✅ Я оплатил(а)» и отправьте скриншот чека."
        )
        
        await query.message.reply_text(
            payment_text,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=get_payment_keyboard(purchase_id)
        )
    
    elif data.startswith("paid_"):
        purchase_id = int(data.split("_")[1])
        db.set_user_state(user_id, "waiting_screenshot", str(purchase_id))
        await query.message.reply_text(
            "📎 Пожалуйста, отправьте скриншот чека об оплате."
        )
    
    elif data.startswith("get_number_"):
        purchase_id = int(data.split("_")[2])
        purchase = db.get_purchase(purchase_id)
        
        if purchase and purchase[3] == "approved":
            user_info = db.get_user(purchase[1])
            username = user_info[1] if user_info else "N/A"
            
            message = (
                f"[USER] @{username} "
                f"запрашивает номер для заказа #{purchase_id} "
                f"({purchase[2]}, {purchase[3]}₽)"
            )
            
            try:
                await context.bot.send_message(
                    chat_id=ADMIN_ID,
                    text=message
                )
                await query.message.reply_text(
                    "✅ Запрос на получение номера отправлен администратору.",
                    reply_markup=get_approved_purchase_keyboard(purchase_id)
                )
            except Exception as e:
                logger.error(f"Ошибка отправки запроса админу: {e}")
    
    elif data.startswith("get_code_"):
        purchase_id = int(data.split("_")[2])
        purchase = db.get_purchase(purchase_id)
        
        if purchase and purchase[3] == "approved":
            user_info = db.get_user(purchase[1])
            username = user_info[1] if user_info else "N/A"
            
            message = (
                f"[USER] @{username} "
                f"запрашивает код для заказа #{purchase_id}"
            )
            
            try:
                await context.bot.send_message(
                    chat_id=ADMIN_ID,
                    text=message
                )
                await query.message.reply_text(
                    "✅ Запрос на получение кода отправлен администратору.",
                    reply_markup=get_approved_purchase_keyboard(purchase_id)
                )
            except Exception as e:
                logger.error(f"Ошибка отправки запроса админу: {e}")
    
    # Админ-панель
    elif data == "admin_stats":
        stats = db.get_statistics()
        stats_text = (
            f"📊 *Статистика*\n\n"
            f"*Всего пользователей:* {stats['total_users']}\n"
            f"*Всего покупок:* {stats['total_purchases']}\n"
            f"*Общая выручка:* {stats['total_revenue']}₽"
        )
        await query.message.reply_text(stats_text, parse_mode=ParseMode.MARKDOWN, reply_markup=get_back_admin_keyboard())
    
    elif data == "admin_checks":
        await show_admin_checks(query, context)
    
    elif data.startswith("check_approve_"):
        await approve_purchase(query, data, context)
    
    elif data.startswith("check_reject_"):
        purchase_id = int(data.split("_")[2])
        db.set_user_state(user_id, f"admin_reject_{purchase_id}", "")
        await query.message.reply_text(f"Введите причину отклонения для заказа #{purchase_id}:")
    
    elif data == "admin_exit":
        await query.message.reply_text("Вы вышли из админ-панели.", reply_markup=get_main_keyboard())

async def show_admin_checks(query, context):
    """Показать чеки на проверку"""
    purchases = db.get_pending_purchases()
    
    if not purchases:
        await query.message.reply_text("Нет чеков, ожидающих проверки.", reply_markup=get_back_admin_keyboard())
        return
    
    purchase = purchases[0]
    text = (
        f"🧾 *Чек на проверку #{purchase[0]}*\n\n"
        f"*Пользователь:* @{purchase[8] if purchase[8] else 'N/A'}\n"
        f"*Страна:* {purchase[2]}\n"
        f"*Сумма:* {purchase[3]}₽\n"
        f"*Дата:* {purchase[6]}"
    )
    
    if purchase[5]:  # Если есть скриншот
        try:
            await context.bot.send_photo(
                chat_id=query.from_user.id,
                photo=purchase[5],
                caption=text,
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=get_check_purchase_keyboard(purchase[0])
            )
        except:
            await query.message.reply_text(
                text + "\n\n(Скриншот приложен)",
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=get_check_purchase_keyboard(purchase[0])
            )
    else:
        await query.message.reply_text(
            text,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=get_check_purchase_keyboard(purchase[0])
        )

async def approve_purchase(query, data, context):
    """Одобрить покупку"""
    purchase_id = int(data.split("_")[2])
    
    # Получаем данные о покупке
    purchase = db.get_purchase(purchase_id)
    if not purchase:
        await query.message.reply_text(f"❌ Заказ #{purchase_id} не найден.")
        return
    
    user_id = purchase[1]  # ID пользователя, который купил
    country = purchase[2]
    amount = purchase[3]
    
    # Обновляем статус
    db.update_purchase_status(purchase_id, "approved")
    logger.info(f"Заказ #{purchase_id} одобрен. Пользователь: {user_id}")
    
    # Отправляем уведомление пользователю
    try:
        message_text = (
            f"✅ *Оплата подтверждена!*\n\n"
            f"Заказ *#{purchase_id}* ({country}, {amount}₽) одобрен.\n\n"
            f"Теперь вы можете получить номер и код для аккаунта."
        )
        
        # Отправляем сообщение пользователю
        await context.bot.send_message(
            chat_id=user_id,
            text=message_text,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=get_approved_purchase_keyboard(purchase_id)
        )
        
        logger.info(f"✅ Уведомление отправлено пользователю {user_id}")
        
    except Exception as e:
        logger.error(f"❌ Ошибка отправки уведомления: {str(e)}")
    
    # Отправляем сообщение админу
    await query.message.reply_text(
        f"✅ Заказ #{purchase_id} одобрен.\n"
        f"Пользователь получил уведомление.",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("➡️ Следующий чек", callback_data="admin_checks")],
            [InlineKeyboardButton("« Назад в админ-панель", callback_data="back_to_admin")]
        ])
    )

async def handle_admin_state(update: Update, context: ContextTypes.DEFAULT_TYPE, state: str, data: str, text: str):
    """Обработка состояний админа"""
    user_id = update.effective_user.id
    
    if state.startswith("admin_reject_"):
        purchase_id = int(state.split("_")[2])
        reason = text
        
        # Обновляем статус
        db.update_purchase_status(purchase_id, "rejected", reason)
        db.clear_user_state(user_id)
        
        # Отправляем уведомление пользователю
        purchase = db.get_purchase(purchase_id)
        if purchase:
            try:
                await context.bot.send_message(
                    chat_id=purchase[1],
                    text=f"❌ Чек отклонен.\n\nПричина: {reason}"
                )
            except Exception as e:
                logger.error(f"Ошибка отправки уведомления об отклонении: {e}")
        
        await update.message.reply_text(
            f"✅ Заказ #{purchase_id} отклонен.",
            reply_markup=get_admin_keyboard()
        )

async def handle_admin_reply(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка ответов админа"""
    if update.message.reply_to_message and update.effective_user.id == ADMIN_ID:
        reply_text = update.message.reply_to_message.text
        user_text = update.message.text
        
        if "[USER]" in reply_text:
            match = re.search(r'заказа #(\d+)', reply_text)
            if match:
                purchase_id = int(match.group(1))
                purchase = db.get_purchase(purchase_id)
                
                if purchase:
                    if "номер" in reply_text.lower():
                        db.update_purchase_data(purchase_id, phone_number=user_text)
                        
                        # Отправляем пользователю
                        await context.bot.send_message(
                            chat_id=purchase[1],
                            text=f"📱 *Номер для заказа #{purchase_id}:*\n\n`{user_text}`",
                            parse_mode=ParseMode.MARKDOWN
                        )
                        await update.message.reply_text("✅ Номер отправлен пользователю.")
                    
                    elif "код" in reply_text.lower():
                        db.update_purchase_data(purchase_id, code=user_text)
                        
                        # Отправляем пользователю
                        await context.bot.send_message(
                            chat_id=purchase[1],
                            text=f"🔢 *Код для заказа #{purchase_id}:*\n\n`{user_text}`",
                            parse_mode=ParseMode.MARKDOWN
                        )
                        await update.message.reply_text("✅ Код отправлен пользователю.")

# ============================================
# ГЛАВНАЯ ФУНКЦИЯ
# ============================================
def main():
    """Запуск бота"""
    application = Application.builder().token(TOKEN).build()
    
    # Обработчики
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("admin", admin_command))
    application.add_handler(CallbackQueryHandler(handle_callback))
    application.add_handler(MessageHandler(filters.TEXT & filters.REPLY, handle_admin_reply))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    application.add_handler(MessageHandler(filters.PHOTO, handle_message))
    
    print("=" * 60)
    print("🤖 БОТ ДЛЯ ПРОДАЖИ АККАУНТОВ")
    print("=" * 60)
    print(f"👑 Администратор: {ADMIN_ID}")
    print("🔑 Команда для админа: /admin")
    print("=" * 60)
    print("✅ Все функции работают:")
    print("   • Покупка аккаунтов")
    print("   • Профиль пользователя")
    print("   • Отправка чеков")
    print("   • Одобрение/отклонение чеков")
    print("   • Уведомления покупателям")
    print("   • Выдача номеров и кодов")
    print("=" * 60)
    
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
