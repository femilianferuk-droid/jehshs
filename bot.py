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
    status: str = "pending"
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
    waiting_payment = State()

class AdminStates(StatesGroup):
    waiting_premium_date = State()
    waiting_premium_month = State()
    waiting_otleg_country = State()
    waiting_otleg_price = State()
    waiting_otleg_text = State()
    waiting_broadcast = State()
    waiting_price_type = State()
    waiting_price_value = State()
    waiting_fiz_price = State()
    waiting_fiz_value = State()

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
        
        # Получаем данные заказа
        cursor.execute("SELECT price, user_id, product_type FROM orders WHERE order_id = ?", (order_id,))
        row = cursor.fetchone()
        
        if row:
            price, user_id, product_type = row
            
            # Обновляем статус заказа
            cursor.execute("UPDATE orders SET status = ? WHERE order_id = ?", (status, order_id))
            
            # Если заказ подтвержден - обновляем статистику
            if status == "confirmed":
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
                "created_at": row[6]
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
                "created_at": row[6]
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
            status_emoji = "✅" if order["status"] == "confirmed" else "⏳" if order["status"] == "pending" else "❌"
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
    await callback.message.edit_text("👋 Главное меню")
    await callback.message.edit_reply_markup(reply_markup=None)
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
        f"После оплаты получите данные аккаунта у поддержки\n\n"
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
            f"После оплаты получите данные аккаунта у поддержки\n\n"
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
                f"После оплаты получите данные аккаунта у поддержки\n\n"
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
        f"Админ проверит оплату и одобрит заказ.\n\n"
        f"🆘 Получить аккаунт вы можете у поддержки: {SUPPORT_USERNAME}"
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
    
    await callback.message.edit_text(payment_text)
    await callback.message.edit_reply_markup(reply_markup=None)
    
    # Сохраняем информацию о заказе
    await state.update_data(
        order_id=order_id,
        product_type=product_type,
        price=price,
        description=description
    )
    
    await state.set_state(BuyStates.waiting_payment)
    await callback.answer()

# Обработка скриншотов оплаты
@dp.message(BuyStates.waiting_payment)
async def process_payment_screenshot(message: types.Message, state: FSMContext):
    if not message.photo:
        await message.answer("📎 Пожалуйста, отправьте скриншот оплаты в виде фото")
        return
    
    data = await state.get_data()
    order_id = data['order_id']
    product_type = data['product_type']
    price = data['price']
    description = data['description']
    user = message.from_user
    
    # Отправляем админу
    admin_text = (
        f"🛒 Новый заказ #{order_id}\n\n"
        f"👤 Пользователь: @{user.username if user.username else 'без username'} (ID: {user.id})\n"
        f"📦 Товар: {description}\n"
        f"💸 Сумма: {price}₽\n\n"
        f"Проверьте оплату и подтвердите заказ:"
    )
    
    try:
        # Отправляем фото и текст админу
        await bot.send_photo(
            chat_id=ADMIN_CHAT_ID,
            photo=message.photo[-1].file_id,
            caption=admin_text,
            reply_markup=get_payment_confirmation_keyboard(order_id)
        )
        
        await message.answer(
            "✅ Скриншот отправлен на проверку админу.\n"
            "Ожидайте подтверждения оплаты.\n\n"
            f"🆘 Получить аккаунт вы можете у поддержки: {SUPPORT_USERNAME}"
        )
        
    except Exception as e:
        logger.error(f"Ошибка отправки скриншота админу: {e}")
        await message.answer("❌ Произошла ошибка при отправке скриншота. Попробуйте еще раз.")
    
    await state.clear()

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
                         f"🆘 Получить аккаунт вы можете у поддержки: {SUPPORT_USERNAME}"
                )
            except:
                pass  # Пользователь может заблокировать бота
            
            await callback.message.edit_text(f"✅ Заказ #{order_id} подтвержден!")
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
            except:
                pass
            
            await callback.message.edit_text(f"❌ Заказ #{order_id} отклонен!")
            await callback.answer("❌ Заказ отклонен", show_alert=True)
            
    except Exception as e:
        logger.error(f"Ошибка подтверждения заказа: {e}")
        await callback.answer("❌ Произошла ошибка", show_alert=True)

# Админские обработчики
@dp.callback_query(lambda c: c.data == "admin_stats")
async def admin_stats(callback: types.CallbackQuery):
    if callback.from_user.id != ADMIN_CHAT_ID:
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return
    
    stats = db.get_stats()
    config = db.get_config()
    
    stats_text = (
        f"📊 Статистика магазина\n\n"
        f"🛒 Всего покупок: {stats.get('total_purchases', 0)}\n"
        f"🎫 Премиум аккаунтов: {stats.get('premium_purchases', 0)}\n"
        f"🌍 ФИЗ аккаунтов: {stats.get('fiz_purchases', 0)}\n"
        f"🎭 Аккаунтов с отлегой: {stats.get('otleg_purchases', 0)}\n"
        f"💰 Общая выручка: {stats.get('total_revenue', 0):.2f}₽\n\n"
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

@dp.callback_query(lambda c: c.data == "admin_premium_month")
async def admin_premium_month(callback: types.CallbackQuery, state: FSMContext):
    if callback.from_user.id != ADMIN_CHAT_ID:
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return
    
    config = db.get_config()
    await callback.message.edit_text(
        f"📆 Текущее количество месяцев: {config.premium_month}\n\n"
        f"Введите новое количество месяцев:"
    )
    await callback.message.edit_reply_markup(
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="❌ Отмена", callback_data="back_admin")]
            ]
        )
    )
    await state.set_state(AdminStates.waiting_premium_month)
    await callback.answer()

@dp.message(AdminStates.waiting_premium_month)
async def admin_save_premium_month(message: types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_CHAT_ID:
        await state.clear()
        return
    
    try:
        months = int(message.text.strip())
        if months <= 0:
            await message.answer("❌ Количество месяцев должно быть больше 0. Попробуйте еще раз:")
            return
        
        config = db.get_config()
        config.premium_month = months
        db.update_config(config)
        
        await message.answer(f"✅ Количество месяцев премиума изменено на {months}")
        await message.answer("⚙️ Админ панель:", reply_markup=get_admin_keyboard())
        
    except ValueError:
        await message.answer("❌ Неверный формат. Введите целое число:")
        return
    
    await state.clear()

@dp.callback_query(lambda c: c.data == "admin_add_otleg")
async def admin_add_otleg(callback: types.CallbackQuery, state: FSMContext):
    if callback.from_user.id != ADMIN_CHAT_ID:
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return
    
    await callback.message.edit_text(
        "🌍 Введите страну для новой отлеги:"
    )
    await callback.message.edit_reply_markup(
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="❌ Отмена", callback_data="back_admin")]
            ]
        )
    )
    await state.set_state(AdminStates.waiting_otleg_country)
    await callback.answer()

@dp.message(AdminStates.waiting_otleg_country)
async def admin_save_otleg_country(message: types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_CHAT_ID:
        await state.clear()
        return
    
    country = message.text.strip()
    await state.update_data(otleg_country=country)
    
    await message.answer(
        f"🌍 Страна: {country}\n\n"
        f"Введите цену для этой отлеги:"
    )
    await state.set_state(AdminStates.waiting_otleg_price)

@dp.message(AdminStates.waiting_otleg_price)
async def admin_save_otleg_price(message: types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_CHAT_ID:
        await state.clear()
        return
    
    try:
        price = float(message.text.replace(',', '.'))
        if price <= 0:
            await message.answer("❌ Цена должна быть больше 0. Попробуйте еще раз:")
            return
        
        data = await state.get_data()
        country = data.get('otleg_country', '')
        
        await state.update_data(otleg_price=price)
        
        await message.answer(
            f"🌍 Страна: {country}\n"
            f"💰 Цена: {price}₽\n\n"
            f"Введите описание отлеги:"
        )
        await state.set_state(AdminStates.waiting_otleg_text)
        
    except ValueError:
        await message.answer("❌ Неверный формат цены. Введите число (например: 199):")
        return

@dp.message(AdminStates.waiting_otleg_text)
async def admin_save_otleg_text(message: types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_CHAT_ID:
        await state.clear()
        return
    
    text = message.text.strip()
    data = await state.get_data()
    country = data.get('otleg_country', '')
    price = data.get('otleg_price', 0)
    
    config = db.get_config()
    config.otleg_accounts.append({
        "country": country,
        "price": price,
        "text": text
    })
    db.update_config(config)
    
    await message.answer(
        f"✅ Отлега добавлена!\n\n"
        f"🌍 Страна: {country}\n"
        f"💰 Цена: {price}₽\n"
        f"📝 Описание: {text}"
    )
    await message.answer("⚙️ Админ панель:", reply_markup=get_admin_keyboard())
    
    await state.clear()

@dp.callback_query(lambda c: c.data == "admin_remove_otleg")
async def admin_remove_otleg(callback: types.CallbackQuery):
    if callback.from_user.id != ADMIN_CHAT_ID:
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return
    
    config = db.get_config()
    
    if not config.otleg_accounts:
        await callback.message.edit_text(
            "😔 Нет аккаунтов с отлегой для удаления."
        )
        await callback.message.edit_reply_markup(
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[
                    [InlineKeyboardButton(text="◀️ Назад в админку", callback_data="back_admin")]
                ]
            )
        )
    else:
        await callback.message.edit_text(
            "❌ Выберите аккаунт для удаления:"
        )
        await callback.message.edit_reply_markup(
            reply_markup=get_remove_otleg_keyboard()
        )
    await callback.answer()

@dp.callback_query(lambda c: c.data.startswith("remove_otleg_"))
async def remove_otleg_account(callback: types.CallbackQuery):
    if callback.from_user.id != ADMIN_CHAT_ID:
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return
    
    try:
        index = int(callback.data.split("_")[2])
        config = db.get_config()
        
        if 0 <= index < len(config.otleg_accounts):
            removed = config.otleg_accounts.pop(index)
            db.update_config(config)
            
            await callback.answer(f"✅ Удалено: {removed.get('country', 'Неизвестно')}", show_alert=True)
            
            if not config.otleg_accounts:
                await callback.message.edit_text(
                    "✅ Все аккаунты с отлегой удалены."
                )
                await callback.message.edit_reply_markup(
                    reply_markup=InlineKeyboardMarkup(
                        inline_keyboard=[
                            [InlineKeyboardButton(text="◀️ Назад в админку", callback_data="back_admin")]
                        ]
                    )
                )
            else:
                await callback.message.edit_reply_markup(
                    reply_markup=get_remove_otleg_keyboard()
                )
        else:
            await callback.answer("❌ Аккаунт не найден", show_alert=True)
    except (IndexError, ValueError):
        await callback.answer("❌ Ошибка удаления", show_alert=True)

@dp.callback_query(lambda c: c.data == "admin_broadcast")
async def admin_broadcast(callback: types.CallbackQuery, state: FSMContext):
    if callback.from_user.id != ADMIN_CHAT_ID:
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return
    
    await callback.message.edit_text(
        "✉️ Введите сообщение для рассылки всем пользователям:"
    )
    await callback.message.edit_reply_markup(
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="❌ Отмена", callback_data="back_admin")]
            ]
        )
    )
    await state.set_state(AdminStates.waiting_broadcast)
    await callback.answer()

@dp.message(AdminStates.waiting_broadcast)
async def admin_send_broadcast(message: types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_CHAT_ID:
        await state.clear()
        return
    
    broadcast_text = message.text
    sent_count = 0
    failed_count = 0
    
    # В реальном проекте нужно получить всех пользователей из базы данных
    # Здесь упрощенная версия
    await message.answer("⏳ Начинаю рассылку...")
    
    # Пример: можно добавить получение пользователей из базы
    # users = get_all_users_from_db()
    # for user in users:
    #     try:
    #         await bot.send_message(user.user_id, broadcast_text)
    #         sent_count += 1
    #     except:
    #         failed_count += 1
    
    await message.answer(
        f"✅ Рассылка завершена!\n\n"
        f"Отправлено: {sent_count}\n"
        f"Не отправлено: {failed_count}"
    )
    await message.answer("⚙️ Админ панель:", reply_markup=get_admin_keyboard())
    
    await state.clear()

# Запуск бота
async def main():
    logger.info("Бот запускается...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
