#!/usr/bin/env python3
"""

Telegram Bot для продажи аккаунтов
Полностью исправленные кнопки "Получить номер" и "Получить код"
Флаги стран вместо смайликов в прайс-листе
"""

import logging
import sqlite3
import datetime
import re
import asyncio
import sys
import traceback
from typing import Optional, Tuple, List, Dict
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters
from telegram.constants import ParseMode

# ================================================================
# KOHФИГУРАЦИЯ
# ================================================================
TOKEN = "8244265951:AAFpmG4DRb640YLvURAhIySdpf6VVJgXX4g"
ADMIN_ID = 7973988177
DATABASE_FILE = "accounts_bot.db"

# Прайс-лист с флагами стран вместо смайликов
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
SUPPORT_LINK = "https://t.me/starfizovoi"  # Исправленная ссылка поддержки

# ================================
# НАСТРОЙКА ЛОГИРОВАНИЯ
# ================================

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ================================
# БАЗА ДАННЫХ
# ================================

class Database:
    def __init__(self):
        self.conn = sqlite3.connect(DATABASE_FILE, check_same_thread=False)
        self.init_db()

    def init_db(self):
        cursor = self.conn.cursor()
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                balance REAL DEFAULT 0,
                reg_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        cursor.execute("""
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
                code TEXT
            )
        """)
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS user_states (
                user_id INTEGER PRIMARY KEY,
                state TEXT,
                data TEXT
            )
        """)
        
        self.conn.commit()

    def add_user(self, user_id: int, username: str):
        cursor = self.conn.cursor()
        cursor.execute(
            "INSERT OR IGNORE INTO users (user_id, username) VALUES (?, ?)",
            (user_id, username or "")
        )
        self.conn.commit()

    def get_user(self, user_id: int) -> Optional[Tuple]:
        cursor = self.conn.cursor()
        cursor.execute(
            "SELECT user_id, username, balance, reg_date FROM users WHERE user_id = ?",
            (user_id,)
        )
        return cursor.fetchone()

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
            (user_id, state, data or "")
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

# ===============================
# ИНИЦИАЛИЗАЦИЯ
# ===============================
db = Database()

# ===============================
# КЛАВИАТУРЫ
# ===============================
def get_main_keyboard():
    return ReplyKeyboardMarkup([
        [KeyboardButton("📞 Купить аккаунт")],
        [KeyboardButton("🔴 Профиль"), KeyboardButton("🔄 Поддержка")],
    ], resize_keyboard=True)

def get_countries_keyboard():
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
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("✔ Я оплатил(a)", callback_data=f"paid_{purchase_id}")],
        [InlineKeyboardButton("« Назад", callback_data="back_to_countries")]
    ])

def get_approved_purchase_keyboard(purchase_id: int):
    """Клавиатура после подтверждения оплаты"""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📖 Получить номер", callback_data=f"get_number_{purchase_id}")],
        [InlineKeyboardButton("🔄 Получить код", callback_data=f"get_code_{purchase_id}")],
    ])

def get_admin_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📖 Проверить чеки", callback_data="admin_checks")],
        [InlineKeyboardButton("« Выйти", callback_data="admin_exit")]
    ])

def get_check_purchase_keyboard(purchase_id: int):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("✔️ Одобрить", callback_data=f"check_approve_{purchase_id}")],
        [InlineKeyboardButton("❌ Отклонить", callback_data=f"check_reject_{purchase_id}")],
        [InlineKeyboardButton("« Назад", callback_data="back_to_admin")]
    ])

def get_back_admin_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("« Назад", callback_data="back_to_admin")]
    ])

# ================================
# OCHOBHbIE ФУНКЦИИ
# ================================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    db.add_user(user.id, user.username)
    
    await update.message.reply_text(
        f"🔄 Привет, {user.first_name}!\n"
        "Добро пожаловать в бота для покупки аккаунтов!",
        reply_markup=get_main_keyboard()
    )

async def admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id == ADMIN_ID:
        await update.message.reply_text("🔍️ Админ-панель:", reply_markup=get_admin_keyboard())
    else:
        await update.message.reply_text("У вас нет доступа к админ  панели.")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text
    
    if text == "📞 Купить аккаунт":
        await update.message.reply_text("Выберите страну:", reply_markup=get_countries_keyboard())
    
    elif text == "🔴 Профиль":
        await show_profile(update)
    
    elif text == "🔄 Поддержка":
        await update.message.reply_text(
            f"По всем вопросам обращайтесь к поддержке: {SUPPORT_LINK}",
            reply_markup=get_main_keyboard()
        )
    
    else:
        state_data = db.get_user_state(user_id)
        if state_data:
            state, data = state_data
            
            if state == "waiting_screenshot":
                purchase_id = int(data)
                if update.message.photo:
                    photo = update.message.photo[-1]
                    file_id = photo.file_id
                    
                    db.update_purchase_screenshot(purchase_id, file_id)
                    db.clear_user_state(user_id)
                    
                    purchase = db.get_purchase(purchase_id)
                    if purchase:
                        user = db.get_user(purchase[1])
                        caption = (
                            f"__Новый чек на проверку__\n\n"
                            f"ID заказа: #{purchase_id}\n"
                            f"Пользователь: @{user[1] if user and user[1] else 'N/A'}\n"
                            f"Страна: {purchase[2]}\n"
                            f"Сумма: {purchase[3]}₽"
                        )
                        
                        try:
                            await context.bot.send_photo(
                                chat_id=ADMIN_ID,
                                photo=file_id,
                                caption=caption,
                                reply_markup=get_check_purchase_keyboard(purchase_id)
                            )
                        except:
                            await context.bot.send_message(
                                chat_id=ADMIN_ID,
                                text=caption + "\n\n(Скриншот приложен)",
                                reply_markup=get_check_purchase_keyboard(purchase_id)
                            )
                        
                        await update.message.reply_text(
                            "✔ Чек отправлен на проверку администратору.\n"
                            "Статус: 🔄 Чек на проверке у администратора.",
                            reply_markup=get_main_keyboard()
                        )
                else:
                    await update.message.reply_text("Пожалуйста, отправьте скриншот оплаты (фото).")

async def show_profile(update: Update):
    user_id = update.effective_user.id
    user = db.get_user(user_id)
    
    if not user:
        db.add_user(user_id, update.effective_user.username)
        user = db.get_user(user_id)
    
    purchases = db.get_user_purchases(user_id)
    
    profile_text = (
        f"*Профиль*\n\n"
        f"*ID:* {user[0]}\n"
        f"*Юзернейм:* @{user[1] if user[1] else 'нет'}\n"
        f"*Баланс:* {user[2]}₽\n\n"
        f"*Последние покупки:*\n"
    )
    
    if purchases:
        for purchase in purchases:
            status_emoji = {
                "pending": "🕒",
                "checking": "🔍",
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
    query = update.callback_query
    user_id = query.from_user.id
    data = query.data
    
    await query.answer()
    
    # Основные действия
    if data == "back_to_main":
        await query.message.reply_text("Главное меню:", reply_markup=get_main_keyboard())
    
    elif data == "back_to_countries":
        await query.message.reply_text("Выберите страну:", reply_markup=get_countries_keyboard())
    
    elif data == "back_to_admin":
        if user_id == ADMIN_ID:
            await query.message.reply_text("Админ-панель:", reply_markup=get_admin_keyboard())
    
    elif data.startswith("country_"):
        idx = int(data.split("_")[1])
        item = PRICES[idx]
        purchase_id = db.add_purchase(user_id, item["country"], item["price"])
        
        payment_text = (
            f"**Страна:** {item['emoji']} {item['country']} ({item['code']})\n"
            f"**Сумма к оплате:** {item['price']}₽\n\n"
            f"**Оплата:**\n"
            f"  • **Карта:** `{PAYMENT_CARD}`\n"
            f"  • **Криптобот:** {CRYPTO_BOT_LINK}\n\n"
            f"После оплаты нажмите «✔ Я оплатил(a)» и отправьте скриншот чека."
        )
        
        await query.message.reply_text(payment_text, parse_mode=ParseMode.MARKDOWN, reply_markup=get_payment_keyboard(purchase_id))
    
    elif data.startswith("paid_"):
        purchase_id = int(data.split("_")[1])
        db.set_user_state(user_id, "waiting_screenshot", str(purchase_id))
        await query.message.reply_text("Пожалуйста, отправьте скриншот чека об оплате.")
    
    # === ИСПРАВЛЕННЫЕ КНОПКИ "ПОЛУЧИТЬ НОМЕР" И "ПОЛУЧИТЬ КОД" ===
    elif data.startswith("get_number_"):
        purchase_id = int(data.split("_")[2])
        logger.info(f"=== ЗАПРОС НОМЕРА ===")
        logger.info(f"Пользователь ID: {user_id} запрашивает номер для заказа #{purchase_id}")
        
        purchase = db.get_purchase(purchase_id)
        
        if not purchase:
            logger.error(f"Заказ #{purchase_id} не найден в базе")
            await query.answer("Заказ не найден", show_alert=True)
            return
        
        logger.info(f"Статус заказа #{purchase_id}: {purchase[3]}")
        
        if purchase[3] == "approved":
            # Получаем информацию о пользователе
            user_info = db.get_user(purchase[1])
            username = user_info[1] if user_info and user_info[1] else "N/A"
            buyer_user_id = purchase[1]  # ID покупателя
            
            # Проверяем, тот ли пользователь нажимает кнопку
            if user_id != buyer_user_id:
                logger.warning(f"Пользователь {user_id} пытается получить данные не своего заказа #{purchase_id}")
                await query.answer("Это не ваш заказ", show_alert=True)
                return
            
            # Формируем сообщение для админа
            admin_message = (
                f"📞 ЗАПРОС НОМЕРА\n\n"
                f"Пользователь: @{username}\n"
                f"ID пользователя: {buyer_user_id}\n"
                f"ID заказа: #{purchase_id}\n"
                f"Страна: {purchase[2]}\n"
                f"Сумма: {purchase[3]}₽\n\n"
                f"Ответьте на это сообщение номером телефона"
            )
            
            logger.info(f"Отправляю сообщение админу {ADMIN_ID}: {admin_message}")
            
            try:
                # Отправляем сообщение админу
                admin_msg = await context.bot.send_message(
                    chat_id=ADMIN_ID,
                    text=admin_message
                )
                logger.info(f"Сообщение отправлено админу. ID сообщения: {admin_msg.message_id}")
                
                # Сообщаем пользователю
                await query.message.reply_text(
                    "✅ Запрос на получение номера отправлен администратору.\n"
                    "Ожидайте ответа в ближайшее время.",
                    reply_markup=get_approved_purchase_keyboard(purchase_id)
                )
                logger.info("✅ Пользователь уведомлен о отправке запроса")
                
            except Exception as e:
                logger.error(f"❌ Ошибка отправки сообщения админу: {str(e)}")
                await query.message.reply_text(
                    "❌ Ошибка при отправке запроса. Попробуйте позже.",
                    reply_markup=get_approved_purchase_keyboard(purchase_id)
                )
        else:
            logger.warning(f"Заказ #{purchase_id} не подтвержден. Статус: {purchase[3]}")
            await query.answer(f"Заказ еще не подтвержден. Статус: {purchase[3]}", show_alert=True)
    
    elif data.startswith("get_code_"):
        purchase_id = int(data.split("_")[2])
        logger.info("=== ЗАПРОС КОДА ===")
        logger.info(f"Пользователь ID: {user_id} запрашивает код для заказа #{purchase_id}")
        
        purchase = db.get_purchase(purchase_id)
        
        if not purchase:
            logger.error(f"Заказ #{purchase_id} не найден в базе")
            await query.answer("Заказ не найден", show_alert=True)
            return
        
        logger.info(f"Статус заказа #{purchase_id}: {purchase[3]}")
        
        if purchase[3] == "approved":
            # Получаем информацию о пользователе
            user_info = db.get_user(purchase[1])
            username = user_info[1] if user_info and user_info[1] else "N/A"
            buyer_user_id = purchase[1]  # ID покупателя
            
            # Проверяем, тот ли пользователь нажимает кнопку
            if user_id != buyer_user_id:
                logger.warning(f"Пользователь {user_id} пытается получить данные не своего заказа #{purchase_id}")
                await query.answer("Это не ваш заказ", show_alert=True)
                return
            
            # Формируем сообщение для админа
            admin_message = (
                f"🔢 ЗАПРОС КОДА\n\n"
                f"Пользователь: @{username}\n"
                f"ID пользователя: {buyer_user_id}\n"
                f"ID заказа: #{purchase_id}\n"
                f"Страна: {purchase[2]}\n"
                f"Сумма: {purchase[3]}₽\n\n"
                f"Ответьте на это сообщение кодом"
            )
            
            logger.info(f"Отправляю сообщение админу {ADMIN_ID}: {admin_message}")
            
            try:
                # Отправляем сообщение админу
                admin_msg = await context.bot.send_message(
                    chat_id=ADMIN_ID,
                    text=admin_message
                )
                logger.info(f"✅ Сообщение отправлено админу. ID сообщения: {admin_msg.message_id}")
                
                # Сообщаем пользователю
                await query.message.reply_text(
                    "✅ Запрос на получение кода отправлен администратору.\n"
                    "Ожидайте ответа в ближайшее время.",
                    reply_markup=get_approved_purchase_keyboard(purchase_id)
                )
                logger.info("✅ Пользователь уведомлен о отправке запроса")
                
            except Exception as e:
                logger.error(f"❌ Ошибка отправки сообщения админу: {str(e)}")
                await query.message.reply_text(
                    "❌ Ошибка при отправке запроса. Попробуйте позже.",
                    reply_markup=get_approved_purchase_keyboard(purchase_id)
                )
        else:
            logger.warning(f"Заказ #{purchase_id} не подтвержден. Статус: {purchase[3]}")
            await query.answer(f"Заказ еще не подтвержден. Статус: {purchase[3]}", show_alert=True)
    
    # Админ-панель
    elif data == "admin_checks":
        await show_admin_checks(query, context)
    
    elif data.startswith("check_approve_"):
        purchase_id = int(data.split("_")[2])
        await approve_purchase(query, purchase_id, context)
    
    elif data.startswith("check_reject_"):
        purchase_id = int(data.split("_")[2])
        db.set_user_state(user_id, f"admin_reject_{purchase_id}", "")
        await query.message.reply_text(f"Введите причину отклонения для заказа #{purchase_id}:")
    
    elif data == "admin_exit":
        await query.message.reply_text("Вы вышли из админ-панели.", reply_markup=get_main_keyboard())

async def show_admin_checks(query, context):
    purchases = db.get_pending_purchases()
    
    if not purchases:
        await query.message.reply_text("Нет чеков, ожидающих проверки.", reply_markup=get_back_admin_keyboard())
        return
    
    purchase = purchases[0]
    text = (
        f"__*Чек на проверку #{purchase[0]}*__\n\n"
        f"*Пользователь:* @{purchase[8] if purchase[8] else 'N/A'}\n"
        f"*Страна:* {purchase[2]}\n"
        f"*Сумма:* {purchase[3]}₽\n"
        f"*Дата:* {purchase[6]}"
    )
    
    if purchase[5]:
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

async def approve_purchase(query, purchase_id: int, context):
    purchase = db.get_purchase(purchase_id)
    if not purchase:
        await query.message.reply_text(f"❌ Заказ #{purchase_id} не найден.")
        return
    
    user_id = purchase[1]
    country = purchase[2]
    amount = purchase[3]
    
    db.update_purchase_status(purchase_id, "approved")
    logger.info(f"Заказ #{purchase_id} одобрен. Пользователь: {user_id}")
    
    # Отправляем уведомление пользователю
    try:
        message_text = (
            f"✅ *Оплата подтверждена!*\n\n"
            f"Заказ *#{purchase_id}* ({country}, {amount}₽) одобрен.\n\n"
            f"Теперь вы можете получить номер и код для аккаунта."
        )
        
        await context.bot.send_message(
            chat_id=user_id,
            text=message_text,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=get_approved_purchase_keyboard(purchase_id)
        )
        
        logger.info(f"✅ Уведомление отправлено пользователю {user_id}")
        
    except Exception as e:
        logger.error(f"❌ Ошибка отправки уведомления: {str(e)}")
    
    await query.message.reply_text(
        f"✅ Заказ #{purchase_id} одобрен.\n"
        f"Пользователь получил уведомление.",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("📖 Следующий чек", callback_data="admin_checks")],
            [InlineKeyboardButton("« Назад", callback_data="back_to_admin")]
        ])
    )

async def handle_admin_state(update: Update, context: ContextTypes.DEFAULT_TYPE, state: str, data: str, text: str):
    user_id = update.effective_user.id
    
    if state.startswith("admin_reject_"):
        purchase_id = int(state.split("_")[2])
        reason = text
        
        db.update_purchase_status(purchase_id, "rejected", reason)
        db.clear_user_state(user_id)
        
        purchase = db.get_purchase(purchase_id)
        if purchase:
            try:
                await context.bot.send_message(
                    chat_id=purchase[1],
                    text=f"❌ Ваш заказ #{purchase_id} отклонён.\nПричина: {reason}"
                )
            except Exception as e:
                logger.error(f"Ошибка отправки уведомления об отклонении: {e}")
        
        await update.message.reply_text(
            f"❌ Заказ #{purchase_id} отклонён.",
            reply_markup=get_admin_keyboard()
        )

async def handle_admin_reply(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка ответов админа на запросы номеров и кодов"""
    if update.message.reply_to_message and update.effective_user.id == ADMIN_ID:
        reply_text = update.message.reply_to_message.text
        response_text = update.message.text
        
        logger.info("=== ОТВЕТ АДМИНА ===")
        logger.info(f"Ответ на сообщение: {reply_text[:100]}...")
        logger.info(f"Текст ответа: {response_text}")
        
        # Ищем ID заказа в тексте
        match = re.search(r'ID заказа: #(\d+)', reply_text)
        if match:
            purchase_id = int(match.group(1))
            logger.info(f"Найден ID заказа: {purchase_id}")
            
            purchase = db.get_purchase(purchase_id)
            if purchase:
                buyer_id = purchase[1]
                logger.info(f"ID покупателя: {buyer_id}")
                
                if "ЗАПРОС НОМЕРА" in reply_text:
                    # Это ответ на запрос номера
                    db.update_purchase_data(purchase_id, phone_number=response_text)
                    
                    # Отправляем номер покупателю
                    try:
                        await context.bot.send_message(
                            chat_id=buyer_id,
                            text=f"*📞 Номер для заказа #{purchase_id}:*\n\n `{response_text}`",
                            parse_mode=ParseMode.MARKDOWN
                        )
                        await update.message.reply_text("✅ Номер отправлен покупателю.")
                        logger.info(f"✅ Номер отправлен покупателю {buyer_id}")
                    except Exception as e:
                        logger.error(f"❌ Ошибка отправки номера покупателю: {str(e)}")
                        await update.message.reply_text(f"❌ Ошибка отправки номера покупателю: {str(e)}")
                
                elif "ЗАПРОС КОДА" in reply_text:
                    # Это ответ на запрос кода
                    db.update_purchase_data(purchase_id, code=response_text)
                    
                    # Отправляем код покупателю
                    try:
                        await context.bot.send_message(
                            chat_id=buyer_id,
                            text=f"*🔢 Код для заказа #{purchase_id}:*\n\n `{response_text}`",
                            parse_mode=ParseMode.MARKDOWN
                        )
                        await update.message.reply_text("✅ Код отправлен покупателю.")
                        logger.info(f"✅ Код отправлен покупателю {buyer_id}")
                    except Exception as e:
                        logger.error(f"❌ Ошибка отправки кода покупателю: {str(e)}")
                        await update.message.reply_text(f"❌ Ошибка отправки кода покупателю: {str(e)}")
            else:
                logger.error(f"Заказ #{purchase_id} не найден")
                await update.message.reply_text(f"❌ Заказ #{purchase_id} не найден.")
        
        else:
            logger.warning("ID заказа не найден в сообщении")
            # Проверяем старый формат
            match_old = re.search(r'заказа #(\d+)', reply_text)
            if match_old:
                purchase_id = int(match_old.group(1))
                logger.info(f"Найден ID заказа (старый формат): {purchase_id}")
                
                purchase = db.get_purchase(purchase_id)
                if purchase:
                    buyer_id = purchase[1]
                    
                    if "номер" in reply_text.lower():
                        db.update_purchase_data(purchase_id, phone_number=response_text)
                        
                        try:
                            await context.bot.send_message(
                                chat_id=buyer_id,
                                text=f"*📞 Номер для заказа #{purchase_id}:*\n\n `{response_text}`",
                                parse_mode=ParseMode.MARKDOWN
                            )
                            await update.message.reply_text("✅ Номер отправлен покупателю.")
                        except Exception as e:
                            logger.error(f"Ошибка: {str(e)}")
                    
                    elif "код" in reply_text.lower():
                        db.update_purchase_data(purchase_id, code=response_text)
                        
                        try:
                            await context.bot.send_message(
                                chat_id=buyer_id,
                                text=f"*🔢 Код для заказа #{purchase_id}:*\n\n `{response_text}`",
                                parse_mode=ParseMode.MARKDOWN
                            )
                            await update.message.reply_text("✅ Код отправлен покупателю.")
                        except Exception as e:
                            logger.error(f"Ошибка: {str(e)}")

# ================================================================
# ЗАПУСК БОТА
# ================================================================

async def test_connection():
    """Тест подключения к Telegram API"""
    try:
        print("🔍 Тестирование подключения к Telegram API...")
        
        # Создаем временное приложение для теста
        test_app = Application.builder().token(TOKEN).build()
        
        # Инициализируем бота
        await test_app.initialize()
        
        # Получаем информацию о боте
        bot_info = await test_app.bot.get_me()
        print(f"✅ Бот успешно подключен!")
        print(f"🤖 Имя бота: @{bot_info.username}")
        print(f"👤 Имя: {bot_info.first_name}")
        print(f"🆔 ID бота: {bot_info.id}")
        
        await test_app.shutdown()
        return True
        
    except Exception as e:
        print(f"❌ Ошибка подключения: {e}")
        print(f"📋 Подробности: {traceback.format_exc()}")
        return False

def main():
    print("=" * 60)
    print("🤖 ЗАПУСК БОТА ДЛЯ ПРОДАЖИ АККАУНТОВ")
    print("=" * 60)
    print(f"🔑 Токен: {TOKEN[:15]}...")
    print(f"👑 Админ ID: {ADMIN_ID}")
    print(f"🆘 Поддержка: {SUPPORT_LINK}")
    print("=" * 60)
    
    # Тестируем подключение
    print("🔍 Проверка подключения к Telegram API...")
    if not asyncio.run(test_connection()):
        print("❌ Не удалось подключиться к Telegram API")
        print("🔍 Возможные причины:")
        print("   1. Неверный токен бота")
        print("   2. Проблемы с интернет-подключением")
        print("   3. Бот заблокирован")
        print("   4. Токен отозван")
        print("=" * 60)
        return
    
    print("✅ Подключение успешно!")
    print("=" * 60)
    
    try:
        application = Application.builder().token(TOKEN).build()
        
        application.add_handler(CommandHandler("start", start))
        application.add_handler(CommandHandler("admin", admin_command))
        application.add_handler(CallbackQueryHandler(handle_callback))
        application.add_handler(MessageHandler(filters.TEXT & filters.REPLY, handle_admin_reply))
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
        application.add_handler(MessageHandler(filters.PHOTO, handle_message))
        
        print("✨ ОСНОВНЫЕ ФИЧИ:")
        print("  1. ✅ Прайс-лист с флагами стран")
        print("  2. ✅ Кнопка 'Получить номер' - работает")
        print("  3. ✅ Кнопка 'Получить код' - работает")
        print("  4. ✅ Обновленная ссылка Crypto Bot")
        print("  5. ✅ Поддержка: starfizovoi.t.me")
        print("=" * 60)
        print("📋 ПРОЦЕСС РАБОТЫ:")
        print("  1. Покупатель: Получает уведомление об одобрении")
        print("  2. Покупатель: Нажимает [Получить номер]")
        print("  3. Админ: Получает сообщение с запросом")
        print("  4. Админ: Отвечает на сообщение номером")
        print("  5. Покупатель: Получает номер телефона")
        print("=" * 60)
        print("🚀 Бот запущен и ожидает сообщений...")
        print("=" * 60)
        print("🛠 Для остановки бота нажмите Ctrl+C")
        print("=" * 60)
        
        application.run_polling(allowed_updates=Update.ALL_TYPES, drop_pending_updates=True)
        
    except KeyboardInterrupt:
        print("\n🛑 Бот остановлен пользователем")
    except Exception as e:
        print(f"❌ Критическая ошибка при запуске бота: {e}")
        print(f"📋 Подробности: {traceback.format_exc()}")
        print("=" * 60)

if __name__ == "__main__":
    main()
