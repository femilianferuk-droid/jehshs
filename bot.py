import logging
import asyncio
import json
import os
import sqlite3
from datetime import datetime
from typing import Dict, List, Optional
from dataclasses import dataclass, field, asdict

from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import (
    InlineKeyboardMarkup, InlineKeyboardButton,
    ReplyKeyboardMarkup, KeyboardButton
)
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Конфигурация
BOT_TOKEN = "8244265951:AAESPS6P-Yekbls_CkwvD4vpOts0lL9MxuA"
ADMIN_CHAT_ID = 7973988177
SUPPORT_USERNAME = "@starfizovoi"
PAYMENT_SBP = "+79818376180"
PAYMENT_CARD = "5599002127675173"

# База данных
DB_FILE = "accounts_bot.db"

# Модели данных
@dataclass
class UserProfile:
    user_id: int
    username: str = ""
    balance: float = 0.0
    purchases_count: int = 0
    total_spent: float = 0.0
    registration_date: str = ""
    first_name: str = ""
    
    def to_dict(self):
        return asdict(self)

@dataclass
class Order:
    order_id: int
    user_id: int
    product_type: str
    product_name: str
    price: float
    status: str = "pending"  # pending, confirmed, number_sent, code_sent, completed
    account_number: str = ""
    account_codes: List[str] = field(default_factory=list)
    created_at: str = ""

@dataclass
class BotConfig:
    premium_date: str = "15.01.2024"
    premium_month: int = 1
    premium_price: float = 39.99
    fiz_prices: Dict[str, float] = field(default_factory=lambda: {
        "usa": 30.0,
        "india": 15.0,
        "russia": 199.0,
        "kazakhstan": 199.0
    })
    otleg_accounts: List[Dict] = field(default_factory=list)

# Состояния FSM
class BuyStates(StatesGroup):
    choosing_account_type = State()
    waiting_payment_screenshot = State()
    waiting_for_account = State()  # Ожидание номера аккаунта от админа
    waiting_for_code = State()     # Ожидание кода от админа

class AdminStates(StatesGroup):
    waiting_premium_date = State()
    waiting_premium_month = State()
    waiting_otleg_country = State()
    waiting_otleg_price = State()
    waiting_otleg_text = State()
    waiting_broadcast = State()
    waiting_price_value = State()
    # Состояния для выдачи аккаунтов
    waiting_account_number = State()
    waiting_account_code = State()

# Класс базы данных
class Database:
    def __init__(self, db_file: str = DB_FILE):
        self.db_file = db_file
        self.init_db()
        
    def init_db(self):
        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()
        
        # Таблица пользователей
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                first_name TEXT,
                balance REAL DEFAULT 0.0,
                purchases_count INTEGER DEFAULT 0,
                total_spent REAL DEFAULT 0.0,
                registration_date TEXT
            )
        ''')
        
        # Таблица заказов
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS orders (
                order_id INTEGER PRIMARY KEY,
                user_id INTEGER,
                product_type TEXT,
                product_name TEXT,
                price REAL,
                status TEXT DEFAULT 'pending',
                account_number TEXT DEFAULT '',
                account_codes TEXT DEFAULT '[]',
                created_at TEXT,
                FOREIGN KEY (user_id) REFERENCES users (user_id)
            )
        ''')
        
        # Таблица статистики
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS stats (
                id INTEGER PRIMARY KEY,
                total_purchases INTEGER DEFAULT 0,
                premium_purchases INTEGER DEFAULT 0,
                fiz_purchases INTEGER DEFAULT 0,
                otleg_purchases INTEGER DEFAULT 0,
                total_revenue REAL DEFAULT 0.0
            )
        ''')
        
        # Таблица конфигурации
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS config (
                id INTEGER PRIMARY KEY,
                premium_date TEXT,
                premium_month INTEGER,
                premium_price REAL,
                fiz_prices TEXT,
                otleg_accounts TEXT
            )
        ''')
        
        # Инициализируем статистику если нет записей
        cursor.execute("SELECT COUNT(*) FROM stats")
        if cursor.fetchone()[0] == 0:
            cursor.execute('''
                INSERT INTO stats (id, total_purchases, premium_purchases, fiz_purchases, otleg_purchases, total_revenue)
                VALUES (1, 0, 0, 0, 0, 0.0)
            ''')
            
        # Инициализируем конфигурацию если нет записей
        cursor.execute("SELECT COUNT(*) FROM config")
        if cursor.fetchone()[0] == 0:
            default_config = BotConfig()
            cursor.execute('''
                INSERT INTO config (id, premium_date, premium_month, premium_price, fiz_prices, otleg_accounts)
                VALUES (1, ?, ?, ?, ?, ?)
            ''', (
                default_config.premium_date,
                default_config.premium_month,
                default_config.premium_price,
                json.dumps(default_config.fiz_prices),
                json.dumps(default_config.otleg_accounts)
            ))
        
        conn.commit()
        conn.close()
    
    def get_user(self, user_id: int) -> Optional[UserProfile]:
        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
        row = cursor.fetchone()
        conn.close()
        
        if row:
            return UserProfile(
                user_id=row[0],
                username=row[1] or "",
                first_name=row[2] or "",
                balance=row[3],
                purchases_count=row[4],
                total_spent=row[5],
                registration_date=row[6] or ""
            )
        return None
    
    def create_or_update_user(self, user: types.User):
        existing = self.get_user(user.id)
        if not existing:
            conn = sqlite3.connect(self.db_file)
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO users (user_id, username, first_name, registration_date)
                VALUES (?, ?, ?, ?)
            ''', (
                user.id,
                user.username,
                user.first_name,
                datetime.now().strftime("%d.%m.%Y %H:%M")
            ))
            conn.commit()
            conn.close()
    
    def create_order(self, order: Order) -> int:
        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO orders (order_id, user_id, product_type, product_name, price, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (
            order.order_id,
            order.user_id,
            order.product_type,
            order.product_name,
            order.price,
            datetime.now().strftime("%d.%m.%Y %H:%M")
        ))
        conn.commit()
        conn.close()
        return order.order_id
    
    def update_order_status(self, order_id: int, status: str):
        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()
        cursor.execute("UPDATE orders SET status = ? WHERE order_id = ?", (status, order_id))
        
        # Если заказ подтвержден - обновляем статистику
        if status == "confirmed":
            cursor.execute("SELECT price, user_id, product_type FROM orders WHERE order_id = ?", (order_id,))
            row = cursor.fetchone()
            
            if row:
                price, user_id, product_type = row
                
                cursor.execute('''
                    UPDATE stats 
                    SET total_purchases = total_purchases + 1,
                        total_revenue = total_revenue + ?
                ''', (price,))
                
                # Обновляем статистику по типам
                if product_type == "premium":
                    cursor.execute("UPDATE stats SET premium_purchases = premium_purchases + 1")
                elif "fiz" in product_type:
                    cursor.execute("UPDATE stats SET fiz_purchases = fiz_purchases + 1")
                elif "otleg" in product_type:
                    cursor.execute("UPDATE stats SET otleg_purchases = otleg_purchases + 1")
                
                # Добавляем покупку пользователю
                cursor.execute('''
                    UPDATE users 
                    SET purchases_count = purchases_count + 1,
                        total_spent = total_spent + ?
                    WHERE user_id = ?
                ''', (price, user_id))
        
        conn.commit()
        conn.close()
    
    def update_order_account_number(self, order_id: int, account_number: str):
        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()
        cursor.execute("UPDATE orders SET account_number = ?, status = 'number_sent' WHERE order_id = ?", 
                      (account_number, order_id))
        conn.commit()
        conn.close()
    
    def add_account_code(self, order_id: int, code: str):
        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()
        
        # Получаем текущие коды
        cursor.execute("SELECT account_codes FROM orders WHERE order_id = ?", (order_id,))
        row = cursor.fetchone()
        current_codes = json.loads(row[0]) if row and row[0] else []
        
        # Добавляем новый код
        current_codes.append(code)
        
        # Обновляем статус и коды
        cursor.execute("UPDATE orders SET account_codes = ?, status = 'code_sent' WHERE order_id = ?",
                      (json.dumps(current_codes), order_id))
        
        conn.commit()
        conn.close()
        return current_codes
    
    def get_order(self, order_id: int) -> Optional[Dict]:
        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM orders WHERE order_id = ?", (order_id,))
        row = cursor.fetchone()
        conn.close()
        
        if row:
            return {
                "order_id": row[0],
                "user_id": row[1],
                "product_type": row[2],
                "product_name": row[3],
                "price": row[4],
                "status": row[5],
                "account_number": row[6] or "",
                "account_codes": json.loads(row[7]) if row[7] else [],
                "created_at": row[8]
            }
        return None
    
    def get_config(self) -> BotConfig:
        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM config WHERE id = 1")
        row = cursor.fetchone()
        conn.close()
        
        if row:
            return BotConfig(
                premium_date=row[1],
                premium_month=row[2],
                premium_price=row[3],
                fiz_prices=json.loads(row[4]),
                otleg_accounts=json.loads(row[5])
            )
        return BotConfig()
    
    def update_config(self, config: BotConfig):
        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE config 
            SET premium_date = ?,
                premium_month = ?,
                premium_price = ?,
                fiz_prices = ?,
                otleg_accounts = ?
            WHERE id = 1
        ''', (
            config.premium_date,
            config.premium_month,
            config.premium_price,
            json.dumps(config.fiz_prices),
            json.dumps(config.otleg_accounts)
        ))
        conn.commit()
        conn.close()
    
    def get_stats(self) -> Dict:
        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM stats WHERE id = 1")
        row = cursor.fetchone()
        conn.close()
        
        if row:
            return {
                "total_purchases": row[1],
                "premium_purchases": row[2],
                "fiz_purchases": row[3],
                "otleg_purchases": row[4],
                "total_revenue": row[5]
            }
        return {}
    
    def get_user_orders(self, user_id: int) -> List[Dict]:
        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM orders WHERE user_id = ? ORDER BY created_at DESC", (user_id,))
        rows = cursor.fetchall()
        conn.close()
        
        orders = []
        for row in rows:
            orders.append({
                "order_id": row[0],
                "product_type": row[2],
                "product_name": row[3],
                "price": row[4],
                "status": row[5],
                "account_number": row[6] or "",
                "account_codes": json.loads(row[7]) if row[7] else [],
                "created_at": row[8]
            })
        return orders
    
    def get_pending_orders(self) -> List[Dict]:
        """Получить все заказы со статусом confirmed (ожидающие выдачи)"""
        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM orders WHERE status = 'confirmed' ORDER BY created_at ASC")
        rows = cursor.fetchall()
        conn.close()
        
        orders = []
        for row in rows:
            orders.append({
                "order_id": row[0],
                "user_id": row[1],
                "product_type": row[2],
                "product_name": row[3],
                "price": row[4],
                "status": row[5],
                "account_number": row[6] or "",
                "account_codes": json.loads(row[7]) if row[7] else [],
                "created_at": row[8]
            })
        return orders

# Инициализация бота и базы данных
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())
db = Database()

# Клавиатуры
def get_main_keyboard():
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🛒 Купить аккаунт")],
            [KeyboardButton(text="👤 Профиль"), KeyboardButton(text="🆘 Поддержка")]
        ],
        resize_keyboard=True
    )
    return keyboard

def get_account_types_keyboard():
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🎫 Аккаунт с премиум", callback_data="premium")],
            [InlineKeyboardButton(text="🌍 ФИЗ аккаунт", callback_data="fiz")],
            [InlineKeyboardButton(text="🎭 Аккаунт с отлегой", callback_data="otleg")],
            [InlineKeyboardButton(text="◀️ Назад", callback_data="back_main")]
        ]
    )
    return keyboard

def get_fiz_countries_keyboard():
    config = db.get_config()
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=f"🇺🇸 США - {config.fiz_prices['usa']}₽", callback_data="fiz_usa")],
            [InlineKeyboardButton(text=f"🇮🇳 Индия - {config.fiz_prices['india']}₽", callback_data="fiz_india")],
            [InlineKeyboardButton(text=f"🇷🇺 Россия - {config.fiz_prices['russia']}₽", callback_data="fiz_russia")],
            [InlineKeyboardButton(text=f"🇰🇿 Казахстан - {config.fiz_prices['kazakhstan']}₽", callback_data="fiz_kazakhstan")],
            [InlineKeyboardButton(text="◀️ Назад", callback_data="back_accounts")]
        ]
    )
    return keyboard

def get_otleg_keyboard():
    config = db.get_config()
    keyboard = InlineKeyboardMarkup(inline_keyboard=[])
    
    if config.otleg_accounts:
        for i, account in enumerate(config.otleg_accounts):
            keyboard.inline_keyboard.append([
                InlineKeyboardButton(
                    text=f"{account.get('country', 'Неизвестно')} - {account.get('price', 0)}₽",
                    callback_data=f"otleg_{i}"
                )
            ])
    else:
        keyboard.inline_keyboard.append([
            InlineKeyboardButton(text="😔 Нет доступных аккаунтов", callback_data="none")
        ])
    
    keyboard.inline_keyboard.append([
        InlineKeyboardButton(text="◀️ Назад", callback_data="back_accounts")
    ])
    
    return keyboard

def get_admin_keyboard():
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📊 Статистика", callback_data="admin_stats")],
            [InlineKeyboardButton(text="✉️ Рассылка", callback_data="admin_broadcast")],
            [InlineKeyboardButton(text="🎫 Изменить дату премиума", callback_data="admin_premium_date")],
            [InlineKeyboardButton(text="📅 Изменить месяц премиума", callback_data="admin_premium_month")],
            [InlineKeyboardButton(text="🌍 Добавить отлегу", callback_data="admin_add_otleg")],
            [InlineKeyboardButton(text="❌ Удалить отлегу", callback_data="admin_remove_otleg")],
            [InlineKeyboardButton(text="💰 Настройки цен", callback_data="admin_prices")],
            [InlineKeyboardButton(text="📦 Заказы к выдаче", callback_data="admin_pending_orders")],
            [InlineKeyboardButton(text="◀️ Назад", callback_data="back_main")]
        ]
    )
    return keyboard

def get_price_settings_keyboard():
    config = db.get_config()
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=f"🎫 Премиум: {config.premium_price}₽", callback_data="edit_premium_price")],
            [InlineKeyboardButton(text=f"🇺🇸 США: {config.fiz_prices['usa']}₽", callback_data="edit_fiz_usa")],
            [InlineKeyboardButton(text=f"🇮🇳 Индия: {config.fiz_prices['india']}₽", callback_data="edit_fiz_india")],
            [InlineKeyboardButton(text=f"🇷🇺 Россия: {config.fiz_prices['russia']}₽", callback_data="edit_fiz_russia")],
            [InlineKeyboardButton(text=f"🇰🇿 Казахстан: {config.fiz_prices['kazakhstan']}₽", callback_data="edit_fiz_kazakhstan")],
            [InlineKeyboardButton(text="◀️ Назад в админку", callback_data="back_admin")]
        ]
    )
    return keyboard

def get_remove_otleg_keyboard():
    config = db.get_config()
    keyboard = InlineKeyboardMarkup(inline_keyboard=[])
    
    if config.otleg_accounts:
        for i, account in enumerate(config.otleg_accounts):
            keyboard.inline_keyboard.append([
                InlineKeyboardButton(
                    text=f"❌ {account.get('country', 'Неизвестно')} - {account.get('price', 0)}₽",
                    callback_data=f"remove_otleg_{i}"
                )
            ])
    else:
        keyboard.inline_keyboard.append([
            InlineKeyboardButton(text="😔 Нет аккаунтов для удаления", callback_data="none")
        ])
    
    keyboard.inline_keyboard.append([
        InlineKeyboardButton(text="◀️ Назад в админку", callback_data="back_admin")
    ])
    
    return keyboard

def get_payment_confirmation_keyboard(order_id: int):
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="✅ Подтвердить оплату", callback_data=f"confirm_{order_id}")],
            [InlineKeyboardButton(text="❌ Отклонить оплату", callback_data=f"reject_{order_id}")]
        ]
    )
    return keyboard

def get_account_management_keyboard(order_id: int):
    """Клавиатура для управления выдачей аккаунта"""
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📱 Выдать номер", callback_data=f"give_number_{order_id}")],
            [InlineKeyboardButton(text="🔑 Выдать код", callback_data=f"give_code_{order_id}")],
            [InlineKeyboardButton(text="✅ Завершить выдачу", callback_data=f"complete_{order_id}")]
        ]
    )
    return keyboard

def get_user_order_keyboard(order_id: int):
    """Клавиатура для пользователя после подтверждения оплаты"""
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📱 Получить номер", callback_data=f"get_number_{order_id}")],
            [InlineKeyboardButton(text="🔑 Получить код", callback_data=f"get_code_{order_id}")]
        ]
    )
    return keyboard

# Обработчики команд
@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    db.create_or_update_user(message.from_user)
    
    welcome_text = (
        "👋 Добро пожаловать в магазин аккаунтов!\n\n"
        "🛍️ Здесь вы можете купить:\n"
        "• Аккаунты с премиум доступом\n"
        "• ФИЗ аккаунты разных стран\n"
        "• Аккаунты с отлегой\n\n"
        "💳 Удобная оплата по СБП или карте\n"
        "⚡ Моментальная доставка после подтверждения\n\n"
        "Выберите действие:"
    )
    
    await message.answer(
        welcome_text,
        reply_markup=get_main_keyboard()
    )

@dp.message(Command("admin"))
async def cmd_admin(message: types.Message):
    if message.from_user.id == ADMIN_CHAT_ID:
        await message.answer(
            "⚙️ Админ панель:",
            reply_markup=get_admin_keyboard()
        )
    else:
        await message.answer("⛔ У вас нет доступа к админ панели")

@dp.message(lambda message: message.text == "🛒 Купить аккаунт")
async def buy_account(message: types.Message, state: FSMContext):
    await message.answer(
        "📦 Выберите тип аккаунта:",
        reply_markup=get_account_types_keyboard()
    )
    await state.set_state(BuyStates.choosing_account_type)

@dp.message(lambda message: message.text == "👤 Профиль")
async def profile(message: types.Message):
    user = db.get_user(message.from_user.id)
    if not user:
        user = UserProfile(user_id=message.from_user.id)
        db.create_or_update_user(message.from_user)
        user = db.get_user(message.from_user.id)
    
    orders = db.get_user_orders(message.from_user.id)
    
    profile_text = (
        f"👤 Ваш профиль\n\n"
        f"🆔 ID: {message.from_user.id}\n"
        f"👤 Username: @{message.from_user.username if message.from_user.username else 'Не установлен'}\n"
        f"💰 Баланс: {user.balance:.2f}₽\n"
        f"🛒 Покупок: {user.purchases_count}\n"
        f"💸 Всего потрачено: {user.total_spent:.2f}₽\n"
        f"📅 Дата регистрации: {user.registration_date}\n\n"
        f"📋 Последние заказы:\n"
    )
    
    if orders:
        for order in orders[:3]:  # Показываем последние 3 заказа
            status_emoji = "✅" if order["status"] == "completed" else "⏳" if order["status"] in ["confirmed", "number_sent", "code_sent"] else "❌"
            profile_text += f"{status_emoji} #{order['order_id']}: {order['product_name']} - {order['price']}₽\n"
    else:
        profile_text += "📭 У вас пока нет заказов"
    
    await message.answer(profile_text)

@dp.message(lambda message: message.text == "🆘 Поддержка")
async def support(message: types.Message):
    await message.answer(
        f"🆘 Поддержка\n\n"
        f"По всем вопросам обращайтесь:\n"
        f"{SUPPORT_USERNAME}\n\n"
        f"⏰ Время работы: 24/7\n"
        f"⚡ Среднее время ответа: 5-15 минут"
    )

# Обработчики callback-запросов
@dp.callback_query(lambda c: c.data == "back_main")
async def back_main(callback: types.CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.answer("👋 Главное меню", reply_markup=get_main_keyboard())
    await callback.answer()

@dp.callback_query(lambda c: c.data == "back_accounts")
async def back_accounts(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.edit_text("📦 Выберите тип аккаунта:")
    await callback.message.edit_reply_markup(reply_markup=get_account_types_keyboard())
    await state.set_state(BuyStates.choosing_account_type)
    await callback.answer()

@dp.callback_query(lambda c: c.data == "back_admin")
async def back_admin(callback: types.CallbackQuery):
    if callback.from_user.id == ADMIN_CHAT_ID:
        await callback.message.edit_text("⚙️ Админ панель:")
        await callback.message.edit_reply_markup(reply_markup=get_admin_keyboard())
    await callback.answer()

@dp.callback_query(lambda c: c.data == "premium")
async def choose_premium(callback: types.CallbackQuery):
    config = db.get_config()
    description = (
        f"🎫 Аккаунт с премиум\n\n"
        f"✅ Премиум до: {config.premium_date}\n"
        f"📅 Срок: {config.premium_month} месяц(ев)\n"
        f"💰 Цена: {config.premium_price}₽\n\n"
        f"После оплаты админ выдаст вам номер и код аккаунта\n\n"
        f"Купить?"
    )
    
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="✅ Купить", callback_data="buy_premium")],
            [InlineKeyboardButton(text="◀️ Назад", callback_data="back_accounts")]
        ]
    )
    
    await callback.message.edit_text(description)
    await callback.message.edit_reply_markup(reply_markup=keyboard)
    await callback.answer()

@dp.callback_query(lambda c: c.data == "fiz")
async def choose_fiz(callback: types.CallbackQuery):
    await callback.message.edit_text("🌍 Выберите страну ФИЗ аккаунта:")
    await callback.message.edit_reply_markup(reply_markup=get_fiz_countries_keyboard())
    await callback.answer()

@dp.callback_query(lambda c: c.data.startswith("fiz_"))
async def choose_fiz_country(callback: types.CallbackQuery):
    config = db.get_config()
    country_map = {
        "fiz_usa": ("США", config.fiz_prices['usa']),
        "fiz_india": ("Индия", config.fiz_prices['india']),
        "fiz_russia": ("Россия", config.fiz_prices['russia']),
        "fiz_kazakhstan": ("Казахстан", config.fiz_prices['kazakhstan'])
    }
    
    if callback.data in country_map:
        country, price = country_map[callback.data]
        
        description = (
            f"🌍 ФИЗ аккаунт: {country}\n\n"
            f"• Страна: {country}\n"
            f"• Цена: {price}₽\n\n"
            f"После оплаты админ выдаст вам номер и код аккаунта\n\n"
            f"Купить?"
        )
        
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="✅ Купить", callback_data=f"buy_{callback.data}")],
                [InlineKeyboardButton(text="◀️ Назад", callback_data="fiz")]
            ]
        )
        
        await callback.message.edit_text(description)
        await callback.message.edit_reply_markup(reply_markup=keyboard)
    await callback.answer()

@dp.callback_query(lambda c: c.data == "otleg")
async def choose_otleg(callback: types.CallbackQuery):
    config = db.get_config()
    
    if not config.otleg_accounts:
        await callback.message.edit_text(
            "😔 Аккаунтов с отлегой пока нет в наличии.\n"
            "Попробуйте позже или выберите другой тип аккаунта."
        )
        await callback.message.edit_reply_markup(
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[
                    [InlineKeyboardButton(text="◀️ Назад", callback_data="back_accounts")]
                ]
            )
        )
    else:
        await callback.message.edit_text("🎭 Выберите аккаунт с отлегой:")
        await callback.message.edit_reply_markup(reply_markup=get_otleg_keyboard())
    await callback.answer()

@dp.callback_query(lambda c: c.data.startswith("otleg_"))
async def choose_otleg_account(callback: types.CallbackQuery):
    try:
        index = int(callback.data.split("_")[1])
        config = db.get_config()
        
        if 0 <= index < len(config.otleg_accounts):
            account = config.otleg_accounts[index]
            
            description = (
                f"🎭 Аккаунт с отлегой\n\n"
                f"• Страна: {account.get('country', 'Неизвестно')}\n"
                f"• Отлега: {account.get('text', 'Описание отсутствует')}\n"
                f"• Цена: {account.get('price', 0)}₽\n\n"
                f"После оплаты админ выдаст вам номер и код аккаунта\n\n"
                f"Купить?"
            )
            
            keyboard = InlineKeyboardMarkup(
                inline_keyboard=[
                    [InlineKeyboardButton(text="✅ Купить", callback_data=f"buy_otleg_{index}")],
                    [InlineKeyboardButton(text="◀️ Назад", callback_data="otleg")]
                ]
            )
            
            await callback.message.edit_text(description)
            await callback.message.edit_reply_markup(reply_markup=keyboard)
        else:
            await callback.answer("❌ Аккаунт не найден", show_alert=True)
    except (IndexError, ValueError):
        await callback.answer("❌ Ошибка выбора аккаунта", show_alert=True)
    await callback.answer()

@dp.callback_query(lambda c: c.data.startswith("buy_"))
async def process_purchase(callback: types.CallbackQuery, state: FSMContext):
    config = db.get_config()
    
    if callback.data == "buy_premium":
        product_type = "premium"
        price = config.premium_price
        description = f"Аккаунт с премиум ({config.premium_month} мес.)"
        
    elif callback.data in ["buy_fiz_usa", "buy_fiz_india", "buy_fiz_russia", "buy_fiz_kazakhstan"]:
        country = callback.data[8:]  # удаляем "buy_fiz_"
        price = config.fiz_prices.get(country, 0)
        product_type = f"fiz_{country}"
        country_names = {"usa": "США", "india": "Индия", "russia": "Россия", "kazakhstan": "Казахстан"}
        description = f"ФИЗ аккаунт ({country_names.get(country, country)})"
        
    elif callback.data.startswith("buy_otleg_"):
        try:
            index = int(callback.data[10:])  # удаляем "buy_otleg_"
            account = config.otleg_accounts[index]
            price = account.get('price', 0)
            product_type = f"otleg_{index}"
            description = f"Аккаунт с отлегой ({account.get('country', 'Неизвестно')})"
        except (IndexError, ValueError):
            await callback.answer("❌ Ошибка покупки", show_alert=True)
            return
    
    # Генерируем ID заказа
    order_id = int(datetime.now().timestamp())
    
    payment_text = (
        f"💰 Оплата заказа #{order_id}\n\n"
        f"📦 Товар: {description}\n"
        f"💸 Сумма: {price}₽\n\n"
        f"💳 Для оплаты отправьте {price}₽ на реквизиты:\n"
        f"📱 СБП: {PAYMENT_SBP} (банк: Юмани)\n"
        f"💳 Карта: {PAYMENT_CARD}\n\n"
        f"После оплаты отправьте скриншот чека в этот чат.\n"
        f"Админ проверит оплату и выдаст вам номер и код аккаунта.\n\n"
        f"🆘 По всем вопросам: {SUPPORT_USERNAME}"
    )
    
    # Создаем заказ в базе данных
    order = Order(
        order_id=order_id,
        user_id=callback.from_user.id,
        product_type=product_type,
        product_name=description,
        price=price
    )
    db.create_order(order)
    
    # Отправляем новое сообщение с инструкцией
    await callback.message.answer(payment_text)
    
    # Сохраняем информацию о заказе
    await state.update_data(
        order_id=order_id,
        product_type=product_type,
        price=price,
        description=description
    )
    
    # Устанавливаем состояние ожидания скриншота
    await state.set_state(BuyStates.waiting_payment_screenshot)
    await callback.answer("✅ Заказ создан! Отправьте скриншот оплаты")

# Обработка скриншотов оплаты
@dp.message(lambda message: message.photo, BuyStates.waiting_payment_screenshot)
async def process_payment_screenshot_photo(message: types.Message, state: FSMContext):
    """Обработка скриншота в виде фото"""
    await handle_payment_screenshot(message, state, message.photo[-1].file_id)

@dp.message(BuyStates.waiting_payment_screenshot)
async def process_payment_screenshot_any(message: types.Message, state: FSMContext):
    """Обработка любых сообщений в состоянии ожидания скриншота"""
    if message.document:
        # Если это документ (файл)
        await handle_payment_screenshot(message, state, message.document.file_id)
    elif message.text:
        # Если это текст, напоминаем отправить скриншот
        await message.answer("📎 Пожалуйста, отправьте скриншот оплаты в виде фото или документа")
    else:
        await message.answer("❌ Не удалось распознать скриншот. Отправьте фото или документ с изображением")

async def handle_payment_screenshot(message: types.Message, state: FSMContext, file_id: str):
    """Общая функция обработки скриншота"""
    try:
        data = await state.get_data()
        order_id = data.get('order_id')
        price = data.get('price', 0)
        description = data.get('description', 'Неизвестный товар')
        
        if not order_id:
            await message.answer("❌ Ошибка: данные заказа не найдены. Пожалуйста, создайте заказ заново.")
            await state.clear()
            return
        
        user = message.from_user
        
        # Отправляем админу
        admin_text = (
            f"🛒 Новый заказ #{order_id}\n\n"
            f"👤 Пользователь: @{user.username if user.username else 'без username'} (ID: {user.id})\n"
            f"📦 Товар: {description}\n"
            f"💸 Сумма: {price}₽\n\n"
            f"Проверьте оплату:"
        )
        
        # Отправляем фото/документ админу
        await bot.send_photo(
            chat_id=ADMIN_CHAT_ID,
            photo=file_id,
            caption=admin_text,
            reply_markup=get_payment_confirmation_keyboard(order_id)
        )
        
        await message.answer(
            "✅ Скриншот отправлен на проверку админу.\n"
            "Ожидайте подтверждения оплаты.\n\n"
            f"🆘 По всем вопросам: {SUPPORT_USERNAME}"
        )
        
        # Очищаем состояние
        await state.clear()
        
    except Exception as e:
        logger.error(f"Ошибка обработки скриншота: {e}")
        await message.answer("❌ Произошла ошибка при обработке скриншота. Попробуйте еще раз.")

# Обработка подтверждения/отклонения оплаты админом
@dp.callback_query(lambda c: c.data.startswith("confirm_") or c.data.startswith("reject_"))
async def handle_payment_confirmation(callback: types.CallbackQuery):
    if callback.from_user.id != ADMIN_CHAT_ID:
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return
    
    try:
        action, order_id = callback.data.split("_")
        order_id = int(order_id)
        
        order = db.get_order(order_id)
        if not order:
            await callback.answer("❌ Заказ не найден", show_alert=True)
            return
        
        if action == "confirm":
            db.update_order_status(order_id, "confirmed")
            # Уведомляем пользователя
            try:
                await bot.send_message(
                    chat_id=order['user_id'],
                    text=f"✅ Ваш заказ #{order_id} подтвержден!\n\n"
                         f"📦 Товар: {order['product_name']}\n"
                         f"💸 Сумма: {order['price']}₽\n\n"
                         f"🔄 Теперь вы можете получить номер и код аккаунта.",
                    reply_markup=get_user_order_keyboard(order_id)
                )
            except Exception as e:
                logger.error(f"Не удалось отправить уведомление пользователю: {e}")
            
            # Отправляем админу меню для выдачи аккаунта
            admin_followup_text = (
                f"✅ Заказ #{order_id} подтвержден!\n\n"
                f"👤 Пользователь: ID {order['user_id']}\n"
                f"📦 Товар: {order['product_name']}\n\n"
                f"Выберите действие для выдачи аккаунта:"
            )
            
            await bot.send_message(
                chat_id=ADMIN_CHAT_ID,
                text=admin_followup_text,
                reply_markup=get_account_management_keyboard(order_id)
            )
            
            await callback.answer("✅ Заказ подтвержден", show_alert=True)
            
        elif action == "reject":
            db.update_order_status(order_id, "rejected")
            # Уведомляем пользователя
            try:
                await bot.send_message(
                    chat_id=order['user_id'],
                    text=f"❌ Ваш заказ #{order_id} отклонен!\n\n"
                         f"Причина: оплата не подтверждена\n"
                         f"Если вы произвели оплату, свяжитесь с поддержкой: {SUPPORT_USERNAME}"
                )
            except Exception as e:
                logger.error(f"Не удалось отправить уведомление пользователю: {e}")
            
            # Редактируем сообщение админу
            await callback.message.edit_caption(
                caption=f"❌ Заказ #{order_id} отклонен!\n"
                       f"Пользователь уведомлен."
            )
            await callback.answer("❌ Заказ отклонен", show_alert=True)
            
    except Exception as e:
        logger.error(f"Ошибка подтверждения заказа: {e}")
        await callback.answer("❌ Произошла ошибка", show_alert=True)

# ====== ВЫДАЧА АККАУНТОВ ======

# 1. Пользователь запрашивает номер
@dp.callback_query(lambda c: c.data.startswith("get_number_"))
async def user_request_number(callback: types.CallbackQuery):
    try:
        order_id = int(callback.data.split("_")[2])
        order = db.get_order(order_id)
        
        if not order:
            await callback.answer("❌ Заказ не найден", show_alert=True)
            return
        
        # Проверяем, что пользователь запрашивает свой заказ
        if callback.from_user.id != order['user_id']:
            await callback.answer("⛔ Это не ваш заказ", show_alert=True)
            return
        
        if order['status'] != 'confirmed':
            await callback.answer("⛔ Заказ еще не подтвержден или уже обработан", show_alert=True)
            return
        
        # Уведомляем админа
        await bot.send_message(
            chat_id=ADMIN_CHAT_ID,
            text=f"📱 Запрос на выдачу номера аккаунта\n\n"
                 f"🔢 Заказ: #{order_id}\n"
                 f"👤 Пользователь: @{callback.from_user.username if callback.from_user.username else 'без username'} (ID: {callback.from_user.id})\n"
                 f"📦 Товар: {order['product_name']}\n\n"
                 f"Нажмите кнопку ниже для выдачи номера:",
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[
                    [InlineKeyboardButton(text="📱 Выдать номер", callback_data=f"give_number_{order_id}")]
                ]
            )
        )
        
        await callback.answer("✅ Запрос на номер отправлен админу")
        await callback.message.answer("✅ Запрос на номер аккаунта отправлен админу. Ожидайте...")
        
    except Exception as e:
        logger.error(f"Ошибка запроса номера: {e}")
        await callback.answer("❌ Произошла ошибка", show_alert=True)

# 2. Админ выдает номер
@dp.callback_query(lambda c: c.data.startswith("give_number_"))
async def admin_give_number(callback: types.CallbackQuery, state: FSMContext):
    if callback.from_user.id != ADMIN_CHAT_ID:
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return
    
    try:
        order_id = int(callback.data.split("_")[2])
        order = db.get_order(order_id)
        
        if not order:
            await callback.answer("❌ Заказ не найден", show_alert=True)
            return
        
        await state.update_data(order_id=order_id)
        await callback.message.answer(
            f"📱 Выдача номера для заказа #{order_id}\n\n"
            f"👤 Пользователь: ID {order['user_id']}\n"
            f"📦 Товар: {order['product_name']}\n\n"
            f"Введите номер аккаунта для выдачи:"
        )
        
        await state.set_state(AdminStates.waiting_account_number)
        await callback.answer()
        
    except Exception as e:
        logger.error(f"Ошибка выдачи номера: {e}")
        await callback.answer("❌ Произошла ошибка", show_alert=True)

@dp.message(AdminStates.waiting_account_number)
async def admin_save_account_number(message: types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_CHAT_ID:
        await state.clear()
        return
    
    data = await state.get_data()
    order_id = data.get('order_id')
    
    if not order_id:
        await message.answer("❌ Ошибка: данные заказа не найдены")
        await state.clear()
        return
    
    account_number = message.text.strip()
    
    if not account_number:
        await message.answer("❌ Номер аккаунта не может быть пустым. Попробуйте еще раз:")
        return
    
    # Сохраняем номер в базе
    db.update_order_account_number(order_id, account_number)
    
    # Отправляем номер пользователю
    order = db.get_order(order_id)
    if order:
        try:
            await bot.send_message(
                chat_id=order['user_id'],
                text=f"📱 Номер аккаунта для заказа #{order_id}\n\n"
                     f"🔢 Номер: {account_number}\n\n"
                     f"✅ Номер получен! Теперь вы можете запросить код аккаунта.",
                reply_markup=get_user_order_keyboard(order_id)
            )
        except Exception as e:
            logger.error(f"Не удалось отправить номер пользователю: {e}")
    
    await message.answer(
        f"✅ Номер аккаунта выдан для заказа #{order_id}\n\n"
        f"🔢 Номер: {account_number}\n\n"
        f"Пользователь уведомлен."
    )
    
    await state.clear()

# 3. Пользователь запрашивает код
@dp.callback_query(lambda c: c.data.startswith("get_code_"))
async def user_request_code(callback: types.CallbackQuery):
    try:
        order_id = int(callback.data.split("_")[2])
        order = db.get_order(order_id)
        
        if not order:
            await callback.answer("❌ Заказ не найден", show_alert=True)
            return
        
        # Проверяем, что пользователь запрашивает свой заказ
        if callback.from_user.id != order['user_id']:
            await callback.answer("⛔ Это не ваш заказ", show_alert=True)
            return
        
        if order['status'] not in ['number_sent', 'code_sent']:
            await callback.answer("⛔ Сначала получите номер аккаунта", show_alert=True)
            return
        
        # Уведомляем админа
        code_count = len(order['account_codes']) + 1
        
        await bot.send_message(
            chat_id=ADMIN_CHAT_ID,
            text=f"🔑 Запрос на выдачу кода аккаунта\n\n"
                 f"🔢 Заказ: #{order_id}\n"
                 f"👤 Пользователь: @{callback.from_user.username if callback.from_user.username else 'без username'} (ID: {callback.from_user.id})\n"
                 f"📦 Товар: {order['product_name']}\n"
                 f"📱 Номер: {order['account_number']}\n"
                 f"📊 Запрос кода №{code_count}\n\n"
                 f"Нажмите кнопку ниже для выдачи кода:",
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[
                    [InlineKeyboardButton(text="🔑 Выдать код", callback_data=f"give_code_{order_id}")]
                ]
            )
        )
        
        await callback.answer("✅ Запрос на код отправлен админу")
        await callback.message.answer("✅ Запрос на код аккаунта отправлен админу. Ожидайте...")
        
    except Exception as e:
        logger.error(f"Ошибка запроса кода: {e}")
        await callback.answer("❌ Произошла ошибка", show_alert=True)

# 4. Админ выдает код
@dp.callback_query(lambda c: c.data.startswith("give_code_"))
async def admin_give_code(callback: types.CallbackQuery, state: FSMContext):
    if callback.from_user.id != ADMIN_CHAT_ID:
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return
    
    try:
        order_id = int(callback.data.split("_")[2])
        order = db.get_order(order_id)
        
        if not order:
            await callback.answer("❌ Заказ не найден", show_alert=True)
            return
        
        await state.update_data(order_id=order_id)
        code_count = len(order['account_codes']) + 1
        
        await callback.message.answer(
            f"🔑 Выдача кода для заказа #{order_id}\n\n"
            f"👤 Пользователь: ID {order['user_id']}\n"
            f"📦 Товар: {order['product_name']}\n"
            f"📱 Номер: {order['account_number']}\n"
            f"📊 Будет выдан код №{code_count}\n\n"
            f"Введите код аккаунта для выдачи:"
        )
        
        await state.set_state(AdminStates.waiting_account_code)
        await callback.answer()
        
    except Exception as e:
        logger.error(f"Ошибка выдачи кода: {e}")
        await callback.answer("❌ Произошла ошибка", show_alert=True)

@dp.message(AdminStates.waiting_account_code)
async def admin_save_account_code(message: types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_CHAT_ID:
        await state.clear()
        return
    
    data = await state.get_data()
    order_id = data.get('order_id')
    
    if not order_id:
        await message.answer("❌ Ошибка: данные заказа не найдены")
        await state.clear()
        return
    
    account_code = message.text.strip()
    
    if not account_code:
        await message.answer("❌ Код аккаунта не может быть пустым. Попробуйте еще раз:")
        return
    
    # Сохраняем код в базе
    all_codes = db.add_account_code(order_id, account_code)
    code_count = len(all_codes)
    
    # Отправляем код пользователю
    order = db.get_order(order_id)
    if order:
        try:
            codes_text = "\n".join([f"{i+1}. {code}" for i, code in enumerate(all_codes)])
            
            await bot.send_message(
                chat_id=order['user_id'],
                text=f"🔑 Код аккаунта для заказа #{order_id}\n\n"
                     f"📱 Номер: {order['account_number']}\n"
                     f"🔢 Выдан код №{code_count}: {account_code}\n\n"
                     f"📋 Все полученные коды:\n{codes_text}\n\n"
                     f"✅ Код получен! Вы можете запрашивать новые коды при необходимости.",
                reply_markup=get_user_order_keyboard(order_id)
            )
        except Exception as e:
            logger.error(f"Не удалось отправить код пользователю: {e}")
    
    await message.answer(
        f"✅ Код аккаунта выдан для заказа #{order_id}\n\n"
        f"📱 Номер: {order['account_number'] if order else 'N/A'}\n"
        f"🔢 Код №{code_count}: {account_code}\n\n"
        f"Пользователь уведомлен."
    )
    
    await state.clear()

# 5. Завершение выдачи
@dp.callback_query(lambda c: c.data.startswith("complete_"))
async def admin_complete_order(callback: types.CallbackQuery):
    if callback.from_user.id != ADMIN_CHAT_ID:
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return
    
    try:
        order_id = int(callback.data.split("_")[1])
        db.update_order_status(order_id, "completed")
        
        order = db.get_order(order_id)
        if order:
            try:
                await bot.send_message(
                    chat_id=order['user_id'],
                    text=f"✅ Выдача аккаунта для заказа #{order_id} завершена!\n\n"
                         f"📦 Товар: {order['product_name']}\n"
                         f"📱 Номер: {order['account_number']}\n"
                         f"🔢 Кодов получено: {len(order['account_codes'])}\n\n"
                         f"Спасибо за покупку! 🎉"
                )
            except Exception as e:
                logger.error(f"Не удалось отправить уведомление пользователю: {e}")
        
        await callback.answer("✅ Выдача завершена", show_alert=True)
        await callback.message.answer(f"✅ Выдача аккаунта для заказа #{order_id} завершена!")
        
    except Exception as e:
        logger.error(f"Ошибка завершения выдачи: {e}")
        await callback.answer("❌ Произошла ошибка", show_alert=True)

# Админ: просмотр заказов к выдаче
@dp.callback_query(lambda c: c.data == "admin_pending_orders")
async def admin_pending_orders(callback: types.CallbackQuery):
    if callback.from_user.id != ADMIN_CHAT_ID:
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return
    
    orders = db.get_pending_orders()
    
    if not orders:
        await callback.message.edit_text(
            "📭 Нет заказов, ожидающих выдачи аккаунтов."
        )
        await callback.message.edit_reply_markup(
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[
                    [InlineKeyboardButton(text="◀️ Назад в админку", callback_data="back_admin")]
                ]
            )
        )
    else:
        text = "📦 Заказы, ожидающие выдачи аккаунтов:\n\n"
        
        for order in orders:
            text += (
                f"🔢 Заказ #{order['order_id']}\n"
                f"👤 Пользователь: ID {order['user_id']}\n"
                f"📦 Товар: {order['product_name']}\n"
                f"💰 Сумма: {order['price']}₽\n"
                f"📅 Создан: {order['created_at']}\n"
                f"⚡ Статус: {order['status']}\n"
                f"📱 Номер: {'Выдан' if order['account_number'] else 'Не выдан'}\n"
                f"🔑 Кодов: {len(order['account_codes'])}\n"
                f"---\n"
            )
        
        text += "\nДля выдачи аккаунта используйте кнопки в соответствующих уведомлениях."
        
        await callback.message.edit_text(text[:4000])  # Ограничение Telegram
        await callback.message.edit_reply_markup(
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[
                    [InlineKeyboardButton(text="◀️ Назад в админку", callback_data="back_admin")]
                ]
            )
        )
    
    await callback.answer()

# Админские обработчики (остальные функции)
@dp.callback_query(lambda c: c.data == "admin_stats")
async def admin_stats(callback: types.CallbackQuery):
    if callback.from_user.id != ADMIN_CHAT_ID:
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return
    
    stats = db.get_stats()
    config = db.get_config()
    
    # Получаем все заказы для дополнительной статистики
    all_orders = db.get_pending_orders()
    
    stats_text = (
        f"📊 Статистика магазина\n\n"
        f"🛒 Всего покупок: {stats.get('total_purchases', 0)}\n"
        f"🎫 Премиум аккаунтов: {stats.get('premium_purchases', 0)}\n"
        f"🌍 ФИЗ аккаунтов: {stats.get('fiz_purchases', 0)}\n"
        f"🎭 Аккаунтов с отлегой: {stats.get('otleg_purchases', 0)}\n"
        f"💰 Общая выручка: {stats.get('total_revenue', 0):.2f}₽\n\n"
        f"📦 Заказов к выдаче: {len(all_orders)}\n\n"
        f"⚙️ Текущие настройки:\n"
        f"• Дата премиума: {config.premium_date}\n"
        f"• Месяцев премиума: {config.premium_month}\n"
        f"• Цена премиума: {config.premium_price}₽"
    )
    
    await callback.message.edit_text(stats_text)
    await callback.message.edit_reply_markup(
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="◀️ Назад в админку", callback_data="back_admin")]
            ]
        )
    )
    await callback.answer()

# Остальные админские функции (изменение цен, даты и т.д.)
@dp.callback_query(lambda c: c.data == "admin_prices")
async def admin_prices(callback: types.CallbackQuery):
    if callback.from_user.id != ADMIN_CHAT_ID:
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return
    
    await callback.message.edit_text("💰 Настройка цен:")
    await callback.message.edit_reply_markup(reply_markup=get_price_settings_keyboard())
    await callback.answer()

@dp.callback_query(lambda c: c.data.startswith("edit_"))
async def admin_edit_price(callback: types.CallbackQuery, state: FSMContext):
    if callback.from_user.id != ADMIN_CHAT_ID:
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return
    
    config = db.get_config()
    edit_type = callback.data
    
    if edit_type == "edit_premium_price":
        await state.update_data(edit_type="premium_price")
        await callback.message.edit_text(
            f"🎫 Текущая цена премиума: {config.premium_price}₽\n\n"
            f"Введите новую цену (например: 49.99):"
        )
        await callback.message.edit_reply_markup(
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[
                    [InlineKeyboardButton(text="❌ Отмена", callback_data="admin_prices")]
                ]
            )
        )
        await state.set_state(AdminStates.waiting_price_value)
        
    elif edit_type.startswith("edit_fiz_"):
        country = edit_type[9:]  # удаляем "edit_fiz_"
        country_names = {"usa": "США", "india": "Индия", "russia": "Россия", "kazakhstan": "Казахстан"}
        country_name = country_names.get(country, country)
        
        await state.update_data(edit_type=f"fiz_{country}")
        await callback.message.edit_text(
            f"🌍 Текущая цена ФИЗ {country_name}: {config.fiz_prices.get(country, 0)}₽\n\n"
            f"Введите новую цену (например: 35):"
        )
        await callback.message.edit_reply_markup(
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[
                    [InlineKeyboardButton(text="❌ Отмена", callback_data="admin_prices")]
                ]
            )
        )
        await state.set_state(AdminStates.waiting_price_value)
    
    await callback.answer()

@dp.message(AdminStates.waiting_price_value)
async def admin_save_price(message: types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_CHAT_ID:
        await state.clear()
        return
    
    try:
        price = float(message.text.replace(',', '.'))
        if price <= 0:
            await message.answer("❌ Цена должна быть больше 0. Попробуйте еще раз:")
            return
        
        data = await state.get_data()
        edit_type = data.get('edit_type', '')
        
        config = db.get_config()
        
        if edit_type == "premium_price":
            config.premium_price = price
            await message.answer(f"✅ Цена премиума изменена на {price}₽")
            
        elif edit_type.startswith("fiz_"):
            country = edit_type[4:]  # удаляем "fiz_"
            if country in config.fiz_prices:
                config.fiz_prices[country] = price
                country_names = {"usa": "США", "india": "Индия", "russia": "Россия", "kazakhstan": "Казахстан"}
                country_name = country_names.get(country, country)
                await message.answer(f"✅ Цена ФИЗ {country_name} изменена на {price}₽")
        
        db.update_config(config)
        
        await message.answer("💰 Настройка цен:", reply_markup=get_price_settings_keyboard())
        
    except ValueError:
        await message.answer("❌ Неверный формат цены. Введите число (например: 39.99):")
        return
    
    await state.clear()

# Остальные админские функции (сокращены для краткости)
@dp.callback_query(lambda c: c.data == "admin_premium_date")
async def admin_premium_date(callback: types.CallbackQuery, state: FSMContext):
    if callback.from_user.id != ADMIN_CHAT_ID:
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return
    
    config = db.get_config()
    await callback.message.edit_text(
        f"📅 Текущая дата премиума: {config.premium_date}\n\n"
        f"Введите новую дату в формате ДД.ММ.ГГГГ:"
    )
    await callback.message.edit_reply_markup(
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="❌ Отмена", callback_data="back_admin")]
            ]
        )
    )
    await state.set_state(AdminStates.waiting_premium_date)
    await callback.answer()

@dp.message(AdminStates.waiting_premium_date)
async def admin_save_premium_date(message: types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_CHAT_ID:
        await state.clear()
        return
    
    new_date = message.text.strip()
    
    # Простая проверка формата даты
    if len(new_date) == 10 and new_date[2] == '.' and new_date[5] == '.':
        config = db.get_config()
        config.premium_date = new_date
        db.update_config(config)
        
        await message.answer(f"✅ Дата премиума изменена на {new_date}")
        await message.answer("⚙️ Админ панель:", reply_markup=get_admin_keyboard())
    else:
        await message.answer("❌ Неверный формат даты. Введите в формате ДД.ММ.ГГГГ:")
        return
    
    await state.clear()

# Остальные админские функции (аналогично)...

# Запуск бота
async def main():
    logger.info("Бот запускается...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
