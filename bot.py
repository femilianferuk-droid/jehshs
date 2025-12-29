#!/usr/bin/env python3
"""
Telegram Bot для продажи аккаунтов с промокодами и админ-панелью
Исправленная версия с рабочей админ-панелью
"""

import logging
import sqlite3
import os
import json
import datetime
import asyncio
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters
from telegram.constants import ParseMode

# ============================================
# КОНФИГУРАЦИЯ
# ============================================
TOKEN = "8244265951:AAESPS6P-Yekbls_CkwvD4vpOts0lL9MxuA"
ADMIN_ID = 7973988177  # ID администратора
DATABASE_FILE = "accounts_bot.db"

# Прайс-лист (точно как в ТЗ)
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

# Реквизиты для оплаты (замените на свои)
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
        self.conn = None
        self.init_db()
    
    def init_db(self):
        """Инициализация базы данных"""
        try:
            self.conn = sqlite3.connect(DATABASE_FILE, check_same_thread=False)
            cursor = self.conn.cursor()
            
            # Таблица пользователей
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    user_id INTEGER PRIMARY KEY,
                    username TEXT,
                    balance REAL DEFAULT 0,
                    reg_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Таблица покупок
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
            
            # Таблица промокодов
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS promocodes (
                    code TEXT PRIMARY KEY,
                    amount REAL,
                    activations_left INTEGER,
                    expiry_date TEXT,
                    is_active INTEGER DEFAULT 1
                )
            ''')
            
            # Таблица использованных промокодов
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS used_promocodes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    code TEXT,
                    date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users (user_id),
                    FOREIGN KEY (code) REFERENCES promocodes (code)
                )
            ''')
            
            # Таблица для отслеживания состояния пользователей
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
            
        except Exception as e:
            logger.error(f"Ошибка инициализации БД: {e}")
    
    def add_user(self, user_id: int, username: str):
        """Добавление нового пользователя"""
        try:
            cursor = self.conn.cursor()
            cursor.execute(
                "INSERT OR IGNORE INTO users (user_id, username) VALUES (?, ?)",
                (user_id, username)
            )
            self.conn.commit()
        except Exception as e:
            logger.error(f"Ошибка добавления пользователя: {e}")
    
    def get_user(self, user_id: int) -> Optional[Tuple]:
        """Получение информации о пользователе"""
        try:
            cursor = self.conn.cursor()
            cursor.execute(
                "SELECT user_id, username, balance, reg_date FROM users WHERE user_id = ?",
                (user_id,)
            )
            return cursor.fetchone()
        except Exception as e:
            logger.error(f"Ошибка получения пользователя: {e}")
            return None
    
    def update_balance(self, user_id: int, amount: float):
        """Обновление баланса пользователя"""
        try:
            cursor = self.conn.cursor()
            cursor.execute(
                "UPDATE users SET balance = balance + ? WHERE user_id = ?",
                (amount, user_id)
            )
            self.conn.commit()
        except Exception as e:
            logger.error(f"Ошибка обновления баланса: {e}")
    
    def get_balance(self, user_id: int) -> float:
        """Получение баланса пользователя"""
        try:
            cursor = self.conn.cursor()
            cursor.execute(
                "SELECT balance FROM users WHERE user_id = ?",
                (user_id,)
            )
            result = cursor.fetchone()
            return result[0] if result else 0.0
        except Exception as e:
            logger.error(f"Ошибка получения баланса: {e}")
            return 0.0
    
    def add_purchase(self, user_id: int, country: str, amount: float) -> int:
        """Добавление покупки"""
        try:
            cursor = self.conn.cursor()
            cursor.execute(
                """INSERT INTO purchases (user_id, country, amount, status) 
                   VALUES (?, ?, ?, 'pending')""",
                (user_id, country, amount)
            )
            self.conn.commit()
            return cursor.lastrowid
        except Exception as e:
            logger.error(f"Ошибка добавления покупки: {e}")
            return -1
    
    def update_purchase_screenshot(self, purchase_id: int, screenshot: str):
        """Обновление скриншота оплаты"""
        try:
            cursor = self.conn.cursor()
            cursor.execute(
                "UPDATE purchases SET payment_screenshot = ? WHERE id = ?",
                (screenshot, purchase_id)
            )
            self.conn.commit()
        except Exception as e:
            logger.error(f"Ошибка обновления скриншота: {e}")
    
    def update_purchase_status(self, purchase_id: int, status: str, notes: str = None):
        """Обновление статуса покупки"""
        try:
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
        except Exception as e:
            logger.error(f"Ошибка обновления статуса покупки: {e}")
    
    def update_purchase_data(self, purchase_id: int, phone_number: str = None, code: str = None):
        """Обновление данных покупки (номер и код)"""
        try:
            cursor = self.conn.cursor()
            if phone_number and code:
                cursor.execute(
                    "UPDATE purchases SET phone_number = ?, code = ? WHERE id = ?",
                    (phone_number, code, purchase_id)
                )
            elif phone_number:
                cursor.execute(
                    "UPDATE purchases SET phone_number = ? WHERE id = ?",
                    (phone_number, purchase_id)
                )
            elif code:
                cursor.execute(
                    "UPDATE purchases SET code = ? WHERE id = ?",
                    (code, purchase_id)
                )
            self.conn.commit()
        except Exception as e:
            logger.error(f"Ошибка обновления данных покупки: {e}")
    
    def get_purchase(self, purchase_id: int) -> Optional[Tuple]:
        """Получение информации о покупке"""
        try:
            cursor = self.conn.cursor()
            cursor.execute(
                "SELECT * FROM purchases WHERE id = ?",
                (purchase_id,)
            )
            return cursor.fetchone()
        except Exception as e:
            logger.error(f"Ошибка получения покупки: {e}")
            return None
    
    def get_user_purchases(self, user_id: int, limit: int = 5) -> List[Tuple]:
        """Получение последних покупок пользователя"""
        try:
            cursor = self.conn.cursor()
            cursor.execute(
                """SELECT id, country, amount, status, date 
                   FROM purchases WHERE user_id = ? 
                   ORDER BY date DESC LIMIT ?""",
                (user_id, limit)
            )
            return cursor.fetchall()
        except Exception as e:
            logger.error(f"Ошибка получения покупок пользователя: {e}")
            return []
    
    def get_pending_purchases(self) -> List[Tuple]:
        """Получение покупок, ожидающих проверки"""
        try:
            cursor = self.conn.cursor()
            cursor.execute(
                """SELECT p.*, u.username 
                   FROM purchases p 
                   JOIN users u ON p.user_id = u.user_id 
                   WHERE p.status = 'pending' 
                   ORDER BY p.date DESC"""
            )
            return cursor.fetchall()
        except Exception as e:
            logger.error(f"Ошибка получения ожидающих покупок: {e}")
            return []
    
    def add_promocode(self, code: str, amount: float, activations_left: int, expiry_date: str = None):
        """Добавление промокода"""
        try:
            cursor = self.conn.cursor()
            cursor.execute(
                """INSERT INTO promocodes (code, amount, activations_left, expiry_date, is_active) 
                   VALUES (?, ?, ?, ?, 1)""",
                (code, amount, activations_left, expiry_date)
            )
            self.conn.commit()
            return True
        except Exception as e:
            logger.error(f"Ошибка добавления промокода: {e}")
            return False
    
    def get_promocode(self, code: str) -> Optional[Tuple]:
        """Получение информации о промокоде"""
        try:
            cursor = self.conn.cursor()
            cursor.execute(
                "SELECT * FROM promocodes WHERE code = ? AND is_active = 1",
                (code,)
            )
            return cursor.fetchone()
        except Exception as e:
            logger.error(f"Ошибка получения промокода: {e}")
            return None
    
    def get_all_promocodes(self) -> List[Tuple]:
        """Получение всех промокодов"""
        try:
            cursor = self.conn.cursor()
            cursor.execute(
                "SELECT * FROM promocodes ORDER BY code"
            )
            return cursor.fetchall()
        except Exception as e:
            logger.error(f"Ошибка получения всех промокодов: {e}")
            return []
    
    def deactivate_promocode(self, code: str):
        """Деактивация промокода"""
        try:
            cursor = self.conn.cursor()
            cursor.execute(
                "UPDATE promocodes SET is_active = 0 WHERE code = ?",
                (code,)
            )
            self.conn.commit()
        except Exception as e:
            logger.error(f"Ошибка деактивации промокода: {e}")
    
    def use_promocode(self, user_id: int, code: str):
        """Использование промокода"""
        try:
            cursor = self.conn.cursor()
            
            # Проверяем, использовал ли уже пользователь этот промокод
            cursor.execute(
                "SELECT id FROM used_promocodes WHERE user_id = ? AND code = ?",
                (user_id, code)
            )
            if cursor.fetchone():
                return False, "Вы уже использовали этот промокод"
            
            # Получаем информацию о промокоде
            promocode = self.get_promocode(code)
            if not promocode:
                return False, "Промокод не найден"
            
            code_data = promocode
            amount = code_data[1]
            activations_left = code_data[2]
            expiry_date = code_data[3]
            
            # Проверяем срок действия
            if expiry_date and expiry_date != "нет":
                try:
                    expiry = datetime.datetime.strptime(expiry_date, "%d.%m.%Y")
                    if datetime.datetime.now() > expiry:
                        return False, "Промокод истек"
                except:
                    pass
            
            # Проверяем количество активаций
            if activations_left > 0:
                # Уменьшаем количество активаций
                cursor.execute(
                    "UPDATE promocodes SET activations_left = activations_left - 1 WHERE code = ?",
                    (code,)
                )
                if activations_left - 1 <= 0:
                    cursor.execute(
                        "UPDATE promocodes SET is_active = 0 WHERE code = ?",
                        (code,)
                    )
            
            # Добавляем запись об использовании
            cursor.execute(
                "INSERT INTO used_promocodes (user_id, code) VALUES (?, ?)",
                (user_id, code)
            )
            
            # Пополняем баланс
            self.update_balance(user_id, amount)
            
            self.conn.commit()
            return True, f"Промокод активирован! Баланс пополнен на {amount}₽"
            
        except Exception as e:
            logger.error(f"Ошибка использования промокода: {e}")
            return False, "Ошибка при активации промокода"
    
    def set_user_state(self, user_id: int, state: str, data: str = None):
        """Установка состояния пользователя"""
        try:
            cursor = self.conn.cursor()
            cursor.execute(
                """INSERT OR REPLACE INTO user_states (user_id, state, data) 
                   VALUES (?, ?, ?)""",
                (user_id, state, data)
            )
            self.conn.commit()
        except Exception as e:
            logger.error(f"Ошибка установки состояния пользователя: {e}")
    
    def get_user_state(self, user_id: int) -> Optional[Tuple]:
        """Получение состояния пользователя"""
        try:
            cursor = self.conn.cursor()
            cursor.execute(
                "SELECT state, data FROM user_states WHERE user_id = ?",
                (user_id,)
            )
            return cursor.fetchone()
        except Exception as e:
            logger.error(f"Ошибка получения состояния пользователя: {e}")
            return None
    
    def clear_user_state(self, user_id: int):
        """Очистка состояния пользователя"""
        try:
            cursor = self.conn.cursor()
            cursor.execute(
                "DELETE FROM user_states WHERE user_id = ?",
                (user_id,)
            )
            self.conn.commit()
        except Exception as e:
            logger.error(f"Ошибка очистки состояния пользователя: {e}")
    
    def get_all_users(self) -> List[Tuple]:
        """Получение всех пользователей"""
        try:
            cursor = self.conn.cursor()
            cursor.execute(
                "SELECT user_id, username, balance, reg_date FROM users ORDER BY reg_date DESC"
            )
            return cursor.fetchall()
        except Exception as e:
            logger.error(f"Ошибка получения всех пользователей: {e}")
            return []
    
    def get_statistics(self) -> Dict:
        """Получение статистики"""
        try:
            cursor = self.conn.cursor()
            
            # Общее количество пользователей
            cursor.execute("SELECT COUNT(*) FROM users")
            total_users = cursor.fetchone()[0]
            
            # Общее количество покупок
            cursor.execute("SELECT COUNT(*) FROM purchases")
            total_purchases = cursor.fetchone()[0]
            
            # Общая выручка
            cursor.execute("SELECT SUM(amount) FROM purchases WHERE status = 'completed' OR status = 'approved'")
            total_revenue = cursor.fetchone()[0] or 0
            
            return {
                "total_users": total_users,
                "total_purchases": total_purchases,
                "total_revenue": total_revenue
            }
        except Exception as e:
            logger.error(f"Ошибка получения статистики: {e}")
            return {"total_users": 0, "total_purchases": 0, "total_revenue": 0}
    
    def update_price(self, country: str, new_price: float):
        """Обновление цены для страны"""
        try:
            # Находим страну в прайс-листе
            for item in PRICES:
                if item["country"] == country:
                    item["price"] = new_price
                    return True
            return False
        except Exception as e:
            logger.error(f"Ошибка обновления цены: {e}")
            return False

# ============================================
# ИНИЦИАЛИЗАЦИЯ БАЗЫ ДАННЫХ
# ============================================
db = Database()

# ============================================
# КЛАВИАТУРЫ
# ============================================
def get_main_keyboard():
    """Основная клавиатура пользователя"""
    return ReplyKeyboardMarkup([
        [KeyboardButton("🛒 Купить аккаунт")],
        [KeyboardButton("👤 Профиль"), KeyboardButton("🆘 Поддержка")]
    ], resize_keyboard=True)

def get_countries_keyboard():
    """Клавиатура выбора страны"""
    keyboard = []
    for i in range(0, len(PRICES), 2):
        row = []
        for j in range(2):
            if i + j < len(PRICES):
                item = PRICES[i + j]
                text = f"{item['emoji']} {item['country']} - {item['price']}₽"
                row.append(InlineKeyboardButton(text, callback_data=f"country_{i+j}"))
        keyboard.append(row)
    
    # Добавляем кнопку назад
    keyboard.append([InlineKeyboardButton("« Назад", callback_data="back_to_main")])
    
    return InlineKeyboardMarkup(keyboard)

def get_payment_keyboard(purchase_id: int):
    """Клавиатура после выбора страны"""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ Я оплатил(а)", callback_data=f"paid_{purchase_id}")],
        [InlineKeyboardButton("« Назад", callback_data="back_to_countries")]
    ])

def get_approved_purchase_keyboard(purchase_id: int):
    """Клавиатура после подтверждения оплаты"""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📱 Получить номер", callback_data=f"get_number_{purchase_id}")],
        [InlineKeyboardButton("🔢 Получить код", callback_data=f"get_code_{purchase_id}")]
    ])

def get_admin_keyboard():
    """Клавиатура админ-панели"""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📊 Статистика", callback_data="admin_stats")],
        [InlineKeyboardButton("📢 Рассылка", callback_data="admin_broadcast")],
        [InlineKeyboardButton("💰 Управление ценами", callback_data="admin_prices")],
        [InlineKeyboardButton("🧾 Проверить чеки", callback_data="admin_checks")],
        [InlineKeyboardButton("🎫 Управление промокодами", callback_data="admin_promocodes")],
        [InlineKeyboardButton("« Выйти из админ-панели", callback_data="admin_exit")]
    ])

def get_admin_promocodes_keyboard():
    """Клавиатура управления промокодами"""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("➕ Создать промокод", callback_data="promo_create")],
        [InlineKeyboardButton("📋 Список промокодов", callback_data="promo_list")],
        [InlineKeyboardButton("🗑️ Удалить промокод", callback_data="promo_delete")],
        [InlineKeyboardButton("« Назад в админ-панель", callback_data="back_to_admin")]
    ])

def get_check_purchase_keyboard(purchase_id: int):
    """Клавиатура для проверки чека"""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Одобрить", callback_data=f"check_approve_{purchase_id}"),
            InlineKeyboardButton("❌ Отклонить", callback_data=f"check_reject_{purchase_id}")
        ],
        [InlineKeyboardButton("« Назад к чекам", callback_data="admin_checks")]
    ])

def get_back_to_admin_keyboard():
    """Кнопка назад в админ-панель"""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("« Назад в админ-панель", callback_data="back_to_admin")]
    ])

# ============================================
# ОБРАБОТЧИКИ СООБЩЕНИЙ
# ============================================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /start"""
    user = update.effective_user
    db.add_user(user.id, user.username)
    
    await update.message.reply_text(
        f"👋 Привет, {user.first_name}!\n\n"
        "Добро пожаловать в бота для покупки аккаунтов!",
        reply_markup=get_main_keyboard()
    )

async def admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /admin"""
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
            "По всем вопросам обращайтесь к поддержке: https://t.me/starfizovoi",
            reply_markup=get_main_keyboard()
        )
    
    else:
        # Проверяем состояние пользователя
        state_data = db.get_user_state(user_id)
        if state_data:
            state, data = state_data
            
            if state == "waiting_promocode":
                # Активация промокода
                success, message = db.use_promocode(user_id, text)
                db.clear_user_state(user_id)
                
                if success:
                    await update.message.reply_text(
                        f"✅ {message}\n\n"
                        f"Текущий баланс: {db.get_balance(user_id)}₽",
                        reply_markup=get_main_keyboard()
                    )
                else:
                    await update.message.reply_text(
                        f"❌ {message}",
                        reply_markup=get_main_keyboard()
                    )
            
            elif state == "waiting_screenshot":
                # Сохранение скриншота
                purchase_id = int(data)
                
                if update.message.photo:
                    # Получаем самое большое фото
                    photo = update.message.photo[-1]
                    file_id = photo.file_id
                    
                    # Сохраняем скриншот
                    db.update_purchase_screenshot(purchase_id, file_id)
                    db.update_purchase_status(purchase_id, "checking")
                    db.clear_user_state(user_id)
                    
                    # Отправляем админу
                    purchase = db.get_purchase(purchase_id)
                    if purchase:
                        user = db.get_user(purchase[1])
                        caption = (
                            f"🆕 Новый чек на проверку!\n\n"
                            f"ID заказа: #{purchase_id}\n"
                            f"Пользователь: @{user[1] if user else 'N/A'} (ID: {user[0] if user else 'N/A'})\n"
                            f"Страна: {purchase[2]}\n"
                            f"Сумма: {purchase[3]}₽\n"
                            f"Дата: {purchase[6]}"
                        )
                        
                        try:
                            await context.bot.send_photo(
                                chat_id=ADMIN_ID,
                                photo=file_id,
                                caption=caption,
                                parse_mode=ParseMode.MARKDOWN,
                                reply_markup=get_check_purchase_keyboard(purchase_id)
                            )
                        except Exception as e:
                            logger.error(f"Ошибка отправки фото админу: {e}")
                            # Если не удалось отправить фото, отправляем текстовое сообщение
                            await context.bot.send_message(
                                chat_id=ADMIN_ID,
                                text=caption + "\n\n(Скриншот приложен, но не удалось отправить)",
                                parse_mode=ParseMode.MARKDOWN,
                                reply_markup=get_check_purchase_keyboard(purchase_id)
                            )
                    
                    await update.message.reply_text(
                        "✅ Чек отправлен на проверку администратору.\n"
                        "Статус: ⏳ Чек на проверке у администратора.",
                        reply_markup=get_main_keyboard()
                    )
                else:
                    await update.message.reply_text(
                        "Пожалуйста, отправьте скриншот оплаты (фото)."
                    )
            
            elif state.startswith("admin_"):
                # Обработка действий админа
                await handle_admin_state(update, context, state, data, text)
        
        else:
            await update.message.reply_text(
                "Используйте кнопки меню для навигации.",
                reply_markup=get_main_keyboard()
            )

async def handle_admin_state(update: Update, context: ContextTypes.DEFAULT_TYPE, state: str, data: str, text: str):
    """Обработка состояний админа"""
    user_id = update.effective_user.id
    
    if state == "admin_broadcast":
        if text.lower() == "отмена":
            db.clear_user_state(user_id)
            await update.message.reply_text(
                "Рассылка отменена.",
                reply_markup=get_admin_keyboard()
            )
            return
        
        # Сохраняем текст рассылки
        db.set_user_state(user_id, "admin_broadcast_confirm", text)
        
        await update.message.reply_text(
            f"📢 Подтвердите рассылку:\n\n{text}\n\n"
            f"Отправить всем пользователям?",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("✅ Отправить", callback_data="broadcast_confirm")],
                [InlineKeyboardButton("❌ Отмена", callback_data="broadcast_cancel")]
            ])
        )
    
    elif state == "admin_broadcast_confirm":
        db.clear_user_state(user_id)
        await update.message.reply_text(
            "Рассылка завершена.",
            reply_markup=get_admin_keyboard()
        )
    
    elif state == "admin_prices_select":
        # Выбор страны для изменения цены
        country_idx = int(data)
        new_price = None
        
        try:
            new_price = float(text)
        except:
            await update.message.reply_text(
                "Пожалуйста, введите корректную цену (число)."
            )
            return
        
        # Обновляем цену
        country = PRICES[country_idx]["country"]
        if db.update_price(country, new_price):
            db.clear_user_state(user_id)
            await update.message.reply_text(
                f"✅ Цена для {country} обновлена: {new_price}₽",
                reply_markup=get_admin_keyboard()
            )
        else:
            await update.message.reply_text(
                f"❌ Ошибка обновления цены для {country}",
                reply_markup=get_admin_keyboard()
            )
    
    elif state == "admin_promo_create_code":
        # Создание промокода: шаг 1 - код
        db.set_user_state(user_id, "admin_promo_create_amount", text)
        await update.message.reply_text(
            "Введите номинал (сумма пополнения в рублях):"
        )
    
    elif state == "admin_promo_create_amount":
        # Создание промокода: шаг 2 - сумма
        try:
            amount = float(text)
            db.set_user_state(user_id, f"admin_promo_create_activations_{amount}", data)
        except:
            await update.message.reply_text(
                "Пожалуйста, введите корректную сумму (число)."
            )
            return
        
        await update.message.reply_text(
            "Введите количество активаций (или 0 для бесконечного):"
        )
    
    elif state.startswith("admin_promo_create_activations_"):
        # Создание промокода: шаг 3 - активации
        parts = state.split("_")
        amount = float(parts[-1])
        code = data
        
        try:
            activations = int(text)
            db.set_user_state(user_id, f"admin_promo_create_expiry_{code}_{amount}_{activations}", "")
        except:
            await update.message.reply_text(
                "Пожалуйста, введите корректное количество активаций (число)."
            )
            return
        
        await update.message.reply_text(
            "Введите дату окончания в формате ДД.ММ.ГГГГ (или 'нет'):"
        )
    
    elif state.startswith("admin_promo_create_expiry_"):
        # Создание промокода: шаг 4 - дата окончания
        parts = state.split("_")
        code = parts[4]
        amount = float(parts[5])
        activations = int(parts[6])
        expiry_date = text if text.lower() != "нет" else None
        
        if expiry_date:
            try:
                # Проверяем формат даты
                datetime.datetime.strptime(expiry_date, "%d.%m.%Y")
            except:
                await update.message.reply_text(
                    "Неверный формат даты. Используйте ДД.ММ.ГГГГ или 'нет'."
                )
                return
        
        # Создаем промокод
        if db.add_promocode(code, amount, activations, expiry_date):
            db.clear_user_state(user_id)
            
            expiry_text = expiry_date if expiry_date else "бессрочно"
            await update.message.reply_text(
                f"✅ Промокод создан!\n\n"
                f"Код: {code}\n"
                f"Сумма: {amount}₽\n"
                f"Активаций: {activations if activations > 0 else '∞'}\n"
                f"Действует до: {expiry_text}",
                reply_markup=get_admin_keyboard()
            )
        else:
            await update.message.reply_text(
                "❌ Ошибка при создании промокода (возможно, код уже существует).",
                reply_markup=get_admin_keyboard()
            )
    
    elif state == "admin_promo_delete":
        # Удаление промокода
        if db.get_promocode(text):
            db.deactivate_promocode(text)
            db.clear_user_state(user_id)
            await update.message.reply_text(
                f"✅ Промокод {text} деактивирован.",
                reply_markup=get_admin_keyboard()
            )
        else:
            await update.message.reply_text(
                f"❌ Промокод {text} не найден."
            )
    
    elif state.startswith("admin_reject_"):
        # Отклонение чека с причиной
        purchase_id = int(state.split("_")[2])
        reason = text
        
        # Обновляем статус покупки
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
            except:
                pass
        
        await update.message.reply_text(
            f"✅ Заказ #{purchase_id} отклонен.",
            reply_markup=get_admin_keyboard()
        )

async def show_profile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать профиль пользователя"""
    user_id = update.effective_user.id
    user = db.get_user(user_id)
    
    if not user:
        await update.message.reply_text("Пользователь не найден.")
        return
    
    # Получаем последние покупки
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
                "completed": "✅",
                "rejected": "❌"
            }.get(purchase[3], "❓")
            
            profile_text += (
                f"• {purchase[1]} - {purchase[2]}₽ - "
                f"{purchase[4].split()[0]} - {status_emoji}\n"
            )
    else:
        profile_text += "Покупок еще нет\n"
    
    # Создаем клавиатуру для промокода
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

# ============================================
# ОБРАБОТЧИКИ CALLBACK-ЗАПРОСОВ
# ============================================
async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик callback-запросов"""
    query = update.callback_query
    user_id = query.from_user.id
    data = query.data
    
    await query.answer()
    
    # Обработка основных действий
    if data == "back_to_main":
        if query.message:
            await query.edit_message_text(
                "Главное меню:",
                reply_markup=get_main_keyboard()
            )
    
    elif data == "back_to_countries":
        if query.message:
            await query.edit_message_text(
                "Выберите страну:",
                reply_markup=get_countries_keyboard()
            )
    
    elif data == "back_to_admin":
        if user_id == ADMIN_ID and query.message:
            await query.edit_message_text(
                "🔐 Админ-панель:",
                reply_markup=get_admin_keyboard()
            )
        else:
            if query.message:
                await query.edit_message_text("У вас нет доступа к админ-панели.")
    
    elif data == "admin_checks":
        if user_id == ADMIN_ID:
            await show_admin_checks(query)
    
    elif data.startswith("country_"):
        await handle_country_selection(query, data)
    
    elif data.startswith("paid_"):
        await handle_payment_confirmation(query, data)
    
    elif data.startswith("get_number_"):
        await handle_get_number(query, data)
    
    elif data.startswith("get_code_"):
        await handle_get_code(query, data)
    
    elif data == "activate_promocode":
        await activate_promocode(query)
    
    # Админ-панель
    elif data == "admin_stats":
        await show_admin_stats(query)
    
    elif data == "admin_broadcast":
        await start_admin_broadcast(query)
    
    elif data == "admin_prices":
        await show_admin_prices(query)
    
    elif data == "admin_checks":
        await show_admin_checks(query)
    
    elif data == "admin_promocodes":
        await show_admin_promocodes(query)
    
    elif data == "admin_exit":
        if query.message:
            await query.edit_message_text(
                "Вы вышли из админ-панели.",
                reply_markup=get_main_keyboard()
            )
    
    elif data.startswith("check_approve_"):
        await approve_purchase(query, data)
    
    elif data.startswith("check_reject_"):
        await reject_purchase(query, data)
    
    # Управление промокодами
    elif data == "promo_create":
        await start_promo_creation(query)
    
    elif data == "promo_list":
        await show_promo_list(query)
    
    elif data == "promo_delete":
        await start_promo_deletion(query)
    
    # Рассылка
    elif data == "broadcast_confirm":
        await confirm_broadcast(query)
    
    elif data == "broadcast_cancel":
        if query.message:
            await query.edit_message_text(
                "Рассылка отменена.",
                reply_markup=get_admin_keyboard()
            )
    
    # Выбор страны для изменения цены
    elif data.startswith("price_"):
        await select_country_for_price(query, data)

async def handle_country_selection(query, data):
    """Обработка выбора страны"""
    try:
        country_idx = int(data.split("_")[1])
        country_data = PRICES[country_idx]
        
        # Создаем запись о покупке
        purchase_id = db.add_purchase(
            query.from_user.id,
            country_data["country"],
            country_data["price"]
        )
        
        if purchase_id > 0:
            payment_text = (
                f"*Страна:* {country_data['emoji']} {country_data['country']} ({country_data['code']})\n"
                f"*Сумма к оплате:* {country_data['price']}₽\n\n"
                f"*Оплата:*\n"
                f"🔸 **Карта:** `{PAYMENT_CARD}`\n"
                f"🔸 **Криптобот:** `{CRYPTO_BOT_LINK}`\n\n"
                f"После оплаты нажмите «✅ Я оплатил(а)» и отправьте скриншот чека."
            )
            
            if query.message:
                await query.edit_message_text(
                    payment_text,
                    parse_mode=ParseMode.MARKDOWN,
                    reply_markup=get_payment_keyboard(purchase_id)
                )
        else:
            if query.message:
                await query.edit_message_text(
                    "❌ Ошибка при создании заказа. Попробуйте еще раз.",
                    reply_markup=get_countries_keyboard()
                )
    except Exception as e:
        logger.error(f"Ошибка в handle_country_selection: {e}")
        if query.message:
            await query.message.reply_text("Произошла ошибка. Попробуйте еще раз.")

async def handle_payment_confirmation(query, data):
    """Обработка подтверждения оплаты"""
    try:
        purchase_id = int(data.split("_")[1])
        
        # Устанавливаем состояние ожидания скриншота
        db.set_user_state(query.from_user.id, "waiting_screenshot", str(purchase_id))
        
        if query.message:
            await query.edit_message_text(
                "📎 Пожалуйста, отправьте скриншот чека об оплате.",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("« Назад", callback_data="back_to_countries")]
                ])
            )
    except Exception as e:
        logger.error(f"Ошибка в handle_payment_confirmation: {e}")

async def handle_get_number(query, data):
    """Запрос номера телефона"""
    try:
        purchase_id = int(data.split("_")[2])
        purchase = db.get_purchase(purchase_id)
        
        if purchase and purchase[3] in ["approved", "completed"]:
            # Отправляем запрос админу
            user = db.get_user(purchase[1])
            message = (
                f"[USER] @{user[1] if user and user[1] else 'N/A'} "
                f"запрашивает номер для заказа #{purchase_id} "
                f"({purchase[2]}, {purchase[3]}₽)"
            )
            
            try:
                await query.bot.send_message(
                    chat_id=ADMIN_ID,
                    text=message,
                    reply_to_message_id=None
                )
                
                if query.message:
                    await query.edit_message_text(
                        "✅ Запрос на получение номера отправлен администратору.",
                        reply_markup=get_approved_purchase_keyboard(purchase_id)
                    )
            except Exception as e:
                logger.error(f"Ошибка отправки запроса админу: {e}")
                if query.message:
                    await query.edit_message_text(
                        "❌ Ошибка при отправке запроса.",
                        reply_markup=get_approved_purchase_keyboard(purchase_id)
                    )
        else:
            await query.answer("Заказ еще не подтвержден или не найден.", show_alert=True)
    except Exception as e:
        logger.error(f"Ошибка в handle_get_number: {e}")

async def handle_get_code(query, data):
    """Запрос кода"""
    try:
        purchase_id = int(data.split("_")[2])
        purchase = db.get_purchase(purchase_id)
        
        if purchase and purchase[3] in ["approved", "completed"]:
            # Отправляем запрос админу
            user = db.get_user(purchase[1])
            message = (
                f"[USER] @{user[1] if user and user[1] else 'N/A'} "
                f"запрашивает код для заказа #{purchase_id}"
            )
            
            try:
                await query.bot.send_message(
                    chat_id=ADMIN_ID,
                    text=message,
                    reply_to_message_id=None
                )
                
                if query.message:
                    await query.edit_message_text(
                        "✅ Запрос на получение кода отправлен администратору.",
                        reply_markup=get_approved_purchase_keyboard(purchase_id)
                    )
            except Exception as e:
                logger.error(f"Ошибка отправки запроса админу: {e}")
                if query.message:
                    await query.edit_message_text(
                        "❌ Ошибка при отправке запроса.",
                        reply_markup=get_approved_purchase_keyboard(purchase_id)
                    )
        else:
            await query.answer("Заказ еще не подтвержден или не найден.", show_alert=True)
    except Exception as e:
        logger.error(f"Ошибка в handle_get_code: {e}")

async def activate_promocode(query):
    """Активация промокода"""
    try:
        db.set_user_state(query.from_user.id, "waiting_promocode", "")
        
        if query.message:
            await query.edit_message_text(
                "Введите промокод:",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("« Назад", callback_data="back_to_main")]
                ])
            )
    except Exception as e:
        logger.error(f"Ошибка в activate_promocode: {e}")

# ============================================
# АДМИН-ПАНЕЛЬ
# ============================================
async def show_admin_stats(query):
    """Показать статистику"""
    try:
        stats = db.get_statistics()
        
        stats_text = (
            f"📊 *Статистика*\n\n"
            f"*Всего пользователей:* {stats['total_users']}\n"
            f"*Всего покупок:* {stats['total_purchases']}\n"
            f"*Общая выручка:* {stats['total_revenue']}₽"
        )
        
        if query.message:
            await query.edit_message_text(
                stats_text,
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=get_back_to_admin_keyboard()
            )
    except Exception as e:
        logger.error(f"Ошибка в show_admin_stats: {e}")

async def start_admin_broadcast(query):
    """Начать рассылку"""
    try:
        db.set_user_state(query.from_user.id, "admin_broadcast", "")
        
        if query.message:
            await query.edit_message_text(
                "Введите текст для рассылки (можно с разметкой Markdown):\n\n"
                "Для отмены введите 'отмена'.",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("« Отмена", callback_data="back_to_admin")]
                ])
            )
    except Exception as e:
        logger.error(f"Ошибка в start_admin_broadcast: {e}")

async def confirm_broadcast(query):
    """Подтверждение и отправка рассылки"""
    try:
        state_data = db.get_user_state(query.from_user.id)
        if not state_data or not state_data[1]:
            if query.message:
                await query.edit_message_text(
                    "Ошибка: текст рассылки не найден.",
                    reply_markup=get_admin_keyboard()
                )
            return
        
        broadcast_text = state_data[1]
        users = db.get_all_users()
        
        if query.message:
            await query.edit_message_text(
                "📢 Рассылка начата...",
                reply_markup=None
            )
        
        success_count = 0
        fail_count = 0
        
        for user in users:
            try:
                await query.bot.send_message(
                    chat_id=user[0],
                    text=broadcast_text,
                    parse_mode=ParseMode.MARKDOWN
                )
                success_count += 1
                await asyncio.sleep(0.05)  # Чтобы не превысить лимиты Telegram
            except Exception as e:
                logger.error(f"Ошибка отправки пользователю {user[0]}: {e}")
                fail_count += 1
        
        db.clear_user_state(query.from_user.id)
        
        if query.message:
            await query.edit_message_text(
                f"✅ Рассылка завершена!\n\n"
                f"Успешно: {success_count}\n"
                f"Не удалось: {fail_count}",
                reply_markup=get_admin_keyboard()
            )
    except Exception as e:
        logger.error(f"Ошибка в confirm_broadcast: {e}")

async def show_admin_prices(query):
    """Показать управление ценами"""
    try:
        keyboard = []
        for i, item in enumerate(PRICES):
            keyboard.append([
                InlineKeyboardButton(
                    f"{item['emoji']} {item['country']} - {item['price']}₽",
                    callback_data=f"price_{i}"
                )
            ])
        
        keyboard.append([InlineKeyboardButton("« Назад", callback_data="back_to_admin")])
        
        if query.message:
            await query.edit_message_text(
                "💰 Управление ценами:\n\nВыберите страну для изменения цены:",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
    except Exception as e:
        logger.error(f"Ошибка в show_admin_prices: {e}")

async def select_country_for_price(query, data):
    """Выбор страны для изменения цены"""
    try:
        country_idx = int(data.split("_")[1])
        country_data = PRICES[country_idx]
        
        db.set_user_state(query.from_user.id, "admin_prices_select", str(country_idx))
        
        if query.message:
            await query.edit_message_text(
                f"Введите новую цену для {country_data['emoji']} {country_data['country']}:\n\n"
                f"Текущая цена: {country_data['price']}₽",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("« Отмена", callback_data="back_to_admin")]
                ])
            )
    except Exception as e:
        logger.error(f"Ошибка в select_country_for_price: {e}")

async def show_admin_checks(query):
    """Показать чеки на проверку"""
    try:
        purchases = db.get_pending_purchases()
        
        if not purchases:
            if query.message:
                await query.edit_message_text(
                    "Нет чеков, ожидающих проверки.",
                    reply_markup=get_back_to_admin_keyboard()
                )
            return
        
        # Показываем первый чек в списке
        purchase = purchases[0]
        
        text = (
            f"🧾 *Чек на проверку #{purchase[0]}*\n\n"
            f"*Пользователь:* @{purchase[8] if purchase[8] else 'N/A'} (ID: {purchase[1]})\n"
            f"*Страна:* {purchase[2]}\n"
            f"*Сумма:* {purchase[3]}₽\n"
            f"*Дата:* {purchase[6]}\n\n"
            f"Всего чеков в очереди: {len(purchases)}"
        )
        
        # Проверяем, есть ли скриншот
        if purchase[5]:
            try:
                if query.message:
                    await query.bot.send_photo(
                        chat_id=query.from_user.id,
                        photo=purchase[5],
                        caption=text,
                        parse_mode=ParseMode.MARKDOWN,
                        reply_markup=get_check_purchase_keyboard(purchase[0])
                    )
                    await query.delete_message()
            except Exception as e:
                logger.error(f"Ошибка отправки фото: {e}")
                if query.message:
                    await query.edit_message_text(
                        text + "\n\n(Скриншот приложен, но не удалось отправить)",
                        parse_mode=ParseMode.MARKDOWN,
                        reply_markup=get_check_purchase_keyboard(purchase[0])
                    )
        else:
            if query.message:
                await query.edit_message_text(
                    text,
                    parse_mode=ParseMode.MARKDOWN,
                    reply_markup=get_check_purchase_keyboard(purchase[0])
                )
    except Exception as e:
        logger.error(f"Ошибка в show_admin_checks: {e}")

async def approve_purchase(query, data):
    """Одобрить покупку"""
    try:
        purchase_id = int(data.split("_")[2])
        
        # Обновляем статус покупки
        db.update_purchase_status(purchase_id, "approved")
        
        # Отправляем уведомление пользователю
        purchase = db.get_purchase(purchase_id)
        if purchase:
            try:
                await query.bot.send_message(
                    chat_id=purchase[1],
                    text=f"✅ Оплата подтверждена!\n\nЗаказ #{purchase_id} ({purchase[2]}) одобрен.",
                    reply_markup=get_approved_purchase_keyboard(purchase_id)
                )
            except Exception as e:
                logger.error(f"Ошибка отправки уведомления пользователю: {e}")
        
        if query.message:
            await query.edit_message_text(
                f"✅ Заказ #{purchase_id} одобрен.",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("➡️ Следующий чек", callback_data="admin_checks")],
                    [InlineKeyboardButton("« Назад в админ-панель", callback_data="back_to_admin")]
                ])
            )
    except Exception as e:
        logger.error(f"Ошибка в approve_purchase: {e}")

async def reject_purchase(query, data):
    """Отклонить покупку"""
    try:
        purchase_id = int(data.split("_")[2])
        
        # Запрашиваем причину
        db.set_user_state(query.from_user.id, f"admin_reject_{purchase_id}", "")
        
        if query.message:
            await query.edit_message_text(
                f"Введите причину отклонения для заказа #{purchase_id}:",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("« Отмена", callback_data="admin_checks")]
                ])
            )
    except Exception as e:
        logger.error(f"Ошибка в reject_purchase: {e}")

async def show_admin_promocodes(query):
    """Показать управление промокодами"""
    try:
        if query.message:
            await query.edit_message_text(
                "🎫 Управление промокодами:",
                reply_markup=get_admin_promocodes_keyboard()
            )
    except Exception as e:
        logger.error(f"Ошибка в show_admin_promocodes: {e}")

async def start_promo_creation(query):
    """Начать создание промокода"""
    try:
        db.set_user_state(query.from_user.id, "admin_promo_create_code", "")
        
        if query.message:
            await query.edit_message_text(
                "Введите код промокода (латиница, цифры, например: WELCOME50):",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("« Отмена", callback_data="back_to_admin")]
                ])
            )
    except Exception as e:
        logger.error(f"Ошибка в start_promo_creation: {e}")

async def show_promo_list(query):
    """Показать список промокодов"""
    try:
        promocodes = db.get_all_promocodes()
        
        if not promocodes:
            text = "Нет созданных промокодов."
        else:
            text = "📋 Список промокодов:\n\n"
            for promo in promocodes:
                status = "✅ Активен" if promo[4] else "❌ Неактивен"
                expiry = promo[3] if promo[3] else "бессрочно"
                activations = f"{promo[2]}" if promo[2] > 0 else "∞"
                
                text += (
                    f"*{promo[0]}* - {promo[1]}₽\n"
                    f"Активаций: {activations}\n"
                    f"Действует до: {expiry}\n"
                    f"Статус: {status}\n\n"
                )
        
        if query.message:
            await query.edit_message_text(
                text,
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=get_back_to_admin_keyboard()
            )
    except Exception as e:
        logger.error(f"Ошибка в show_promo_list: {e}")

async def start_promo_deletion(query):
    """Начать удаление промокода"""
    try:
        db.set_user_state(query.from_user.id, "admin_promo_delete", "")
        
        if query.message:
            await query.edit_message_text(
                "Введите код промокода для удаления:",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("« Отмена", callback_data="back_to_admin")]
                ])
            )
    except Exception as e:
        logger.error(f"Ошибка в start_promo_deletion: {e}")

# ============================================
# ОБРАБОТКА ОТВЕТОВ АДМИНА
# ============================================
async def handle_admin_reply(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка ответов админа на запросы"""
    try:
        if update.message.reply_to_message:
            reply_text = update.message.reply_to_message.text
            user_id = update.effective_user.id
            
            if user_id == ADMIN_ID:
                # Проверяем, является ли это ответом на запрос номера или кода
                if "[USER]" in reply_text:
                    # Извлекаем ID пользователя из текста
                    import re
                    match = re.search(r'заказа #(\d+)', reply_text)
                    if match:
                        purchase_id = int(match.group(1))
                        
                        # Получаем информацию о покупке
                        purchase = db.get_purchase(purchase_id)
                        if purchase:
                            # Отправляем данные пользователю
                            response_text = update.message.text
                            
                            if "номер" in reply_text.lower():
                                # Это ответ на запрос номера
                                db.update_purchase_data(purchase_id, phone_number=response_text)
                                await update.message.reply_text(f"✅ Номер отправлен пользователю.")
                                
                                # Отправляем пользователю
                                try:
                                    await context.bot.send_message(
                                        chat_id=purchase[1],
                                        text=f"📱 Номер для заказа #{purchase_id}:\n\n`{response_text}`",
                                        parse_mode=ParseMode.MARKDOWN
                                    )
                                except Exception as e:
                                    logger.error(f"Ошибка отправки номера пользователю: {e}")
                            
                            elif "код" in reply_text.lower():
                                # Это ответ на запрос кода
                                db.update_purchase_data(purchase_id, code=response_text)
                                await update.message.reply_text(f"✅ Код отправлен пользователю.")
                                
                                # Отправляем пользователю
                                try:
                                    await context.bot.send_message(
                                        chat_id=purchase[1],
                                        text=f"🔢 Код для заказа #{purchase_id}:\n\n`{response_text}`",
                                        parse_mode=ParseMode.MARKDOWN
                                    )
                                except Exception as e:
                                    logger.error(f"Ошибка отправки кода пользователю: {e}")
    except Exception as e:
        logger.error(f"Ошибка в handle_admin_reply: {e}")

# ============================================
# ГЛАВНАЯ ФУНКЦИЯ
# ============================================
def main():
    """Запуск бота"""
    # Создаем приложение
    application = Application.builder().token(TOKEN).build()
    
    # Обработчики команд
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("admin", admin_command))
    
    # Обработчик callback-запросов
    application.add_handler(CallbackQueryHandler(handle_callback))
    
    # Обработчик ответов админа
    application.add_handler(MessageHandler(filters.TEXT & filters.REPLY, handle_admin_reply))
    
    # Обработчик текстовых сообщений
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    # Обработчик фото (скриншоты оплаты)
    application.add_handler(MessageHandler(filters.PHOTO, handle_message))
    
    # Запуск бота
    print("Бот запущен...")
    print(f"ID администратора: {ADMIN_ID}")
    print("Для доступа к админ-панели отправьте команду /admin")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
