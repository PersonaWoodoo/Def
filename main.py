import asyncio
import random
import sqlite3
import json
import string
import time
import os
from datetime import datetime

from aiogram import Bot, Dispatcher, F, types
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
    PreCheckoutQuery,
    LabeledPrice,
    ReplyKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardRemove,
)

# ========== КОНФИГ ==========
BOT_TOKEN = "8200340859:AAFziC0Vk2KH71AwnCPvQBkyCfBl50eVMrs"
ADMIN_IDS = [8293927811, 8478884644]  # Два админа

# Валюты
GRAM_NAME = "💎 Грам"
GOLD_NAME = "🏅 Iris-Gold"

# Стартовые балансы
START_GRAM = 1000.0
START_GOLD = 0.0

# Курс Stars
STAR_TO_GRAM = 2222.0
STAR_TO_GOLD = 0.7

# Лимиты ставок
MIN_BET_GRAM = 0.10
MAX_BET_GRAM = 100000.0
MIN_BET_GOLD = 0.01
MAX_BET_GOLD = 5000.0

# ========== СОЗДАЁМ DP ==========
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

# ========== БАЗА ДАННЫХ ==========
DB_PATH = "casino.db"

def init_db():
    if os.path.exists(DB_PATH):
        try:
            conn = sqlite3.connect(DB_PATH)
            cur = conn.cursor()
            cur.execute("PRAGMA table_info(users)")
            columns = [col[1] for col in cur.fetchall()]
            conn.close()
            if "gram" not in columns:
                os.remove(DB_PATH)
                print("🗑️ Старая БД удалена, создаю новую")
        except:
            os.remove(DB_PATH)
    
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    
    # Таблица users с двумя валютами
    cur.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id TEXT PRIMARY KEY,
            gram REAL DEFAULT 1000,
            gold REAL DEFAULT 0,
            total_bets INTEGER DEFAULT 0,
            total_wins INTEGER DEFAULT 0,
            last_bonus INTEGER DEFAULT 0,
            total_deposited_gram REAL DEFAULT 0,
            total_deposited_gold REAL DEFAULT 0
        )
    ''')
    
    # Проверяем колонки
    cur.execute("PRAGMA table_info(users)")
    columns = [col[1] for col in cur.fetchall()]
    
    if "gram" not in columns:
        cur.execute("ALTER TABLE users ADD COLUMN gram REAL DEFAULT 1000")
    if "gold" not in columns:
        cur.execute("ALTER TABLE users ADD COLUMN gold REAL DEFAULT 0")
    if "total_bets" not in columns:
        cur.execute("ALTER TABLE users ADD COLUMN total_bets INTEGER DEFAULT 0")
    if "total_wins" not in columns:
        cur.execute("ALTER TABLE users ADD COLUMN total_wins INTEGER DEFAULT 0")
    if "last_bonus" not in columns:
        cur.execute("ALTER TABLE users ADD COLUMN last_bonus INTEGER DEFAULT 0")
    if "total_deposited_gram" not in columns:
        cur.execute("ALTER TABLE users ADD COLUMN total_deposited_gram REAL DEFAULT 0")
    if "total_deposited_gold" not in columns:
        cur.execute("ALTER TABLE users ADD COLUMN total_deposited_gold REAL DEFAULT 0")
    
    # Таблица чеков
    cur.execute('''
        CREATE TABLE IF NOT EXISTS checks (
            code TEXT PRIMARY KEY,
            creator_id TEXT,
            per_user REAL,
            currency TEXT,
            remaining INTEGER,
            claimed TEXT
        )
    ''')
    
    # Таблица промокодов
    cur.execute('''
        CREATE TABLE IF NOT EXISTS promos (
            name TEXT PRIMARY KEY,
            reward_gram REAL,
            reward_gold REAL,
            remaining_activations INTEGER,
            claimed TEXT
        )
    ''')
    
    conn.commit()
    conn.close()
    print("✅ База данных инициализирована")

init_db()

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def now_ts():
    return int(time.time())

def fmt_gram(value: float) -> str:
    value = round(float(value), 2)
    if value >= 1000:
        return f"{value/1000:.1f}K {GRAM_NAME}"
    return f"{value:.2f} {GRAM_NAME}"

def fmt_gold(value: float) -> str:
    value = round(float(value), 2)
    if value >= 1000:
        return f"{value/1000:.1f}K {GOLD_NAME}"
    return f"{value:.2f} {GOLD_NAME}"

def fmt_money(currency: str, value: float) -> str:
    if currency == "gram":
        return fmt_gram(value)
    return fmt_gold(value)

def escape_html(text: str) -> str:
    return str(text or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

def mention_user(user_id: int, name: str = None) -> str:
    name = escape_html(name or f"Игрок{user_id}")
    return f'<a href="tg://user?id={user_id}">{name}</a>'

def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS

def ensure_user(user_id: int):
    conn = get_db()
    conn.execute("INSERT OR IGNORE INTO users (user_id, gram, gold) VALUES (?, ?, ?)", 
                 (str(user_id), START_GRAM, START_GOLD))
    conn.commit()
    conn.close()

def get_user(user_id: int):
    conn = get_db()
    ensure_user(user_id)
    row = conn.execute("SELECT * FROM users WHERE user_id = ?", (str(user_id),)).fetchone()
    conn.close()
    return row

def update_balance(user_id: int, currency: str, delta: float) -> float:
    conn = get_db()
    conn.execute(f"UPDATE users SET {currency} = {currency} + ? WHERE user_id = ?", 
                 (round(delta, 2), str(user_id)))
    conn.commit()
    row = conn.execute(f"SELECT {currency} FROM users WHERE user_id = ?", (str(user_id),)).fetchone()
    conn.close()
    return row[currency]

def add_bet_record(user_id: int, bet: float, win: bool, game: str, currency: str):
    conn = get_db()
    conn.execute("UPDATE users SET total_bets = total_bets + 1 WHERE user_id = ?", (str(user_id),))
    if win:
        conn.execute("UPDATE users SET total_wins = total_wins + 1 WHERE user_id = ?", (str(user_id),))
    conn.commit()
    conn.close()

def get_top_players(currency: str, limit: int = 10):
    conn = get_db()
    rows = conn.execute(f"SELECT user_id, {currency} FROM users ORDER BY {currency} DESC LIMIT ?", (limit,)).fetchall()
    conn.close()
    return rows

# ========== ЧЕКИ ==========
def generate_check_code():
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))

def create_check(user_id: int, amount: float, currency: str, count: int) -> tuple:
    total = amount * count
    user = get_user(user_id)
    if user[currency] < total:
        return False, f"❌ Недостаточно {fmt_money(currency, total)}!"
    
    update_balance(user_id, currency, -total)
    code = generate_check_code()
    
    conn = get_db()
    conn.execute(
        "INSERT INTO checks (code, creator_id, per_user, currency, remaining, claimed) VALUES (?, ?, ?, ?, ?, ?)",
        (code, str(user_id), amount, currency, count, "[]")
    )
    conn.commit()
    conn.close()
    return True, code

def claim_check(user_id: int, code: str) -> tuple:
    conn = get_db()
    row = conn.execute("SELECT * FROM checks WHERE code = ?", (code.upper(),)).fetchone()
    if not row:
        conn.close()
        return False, "❌ Чек не найден!", 0, ""
    
    if row["remaining"] <= 0:
        conn.close()
        return False, "❌ Чек уже использован!", 0, ""
    
    claimed = json.loads(row["claimed"])
    if str(user_id) in claimed:
        conn.close()
        return False, "❌ Ты уже активировал этот чек!", 0, ""
    
    claimed.append(str(user_id))
    reward = row["per_user"]
    currency = row["currency"]
    update_balance(user_id, currency, reward)
    
    conn.execute(
        "UPDATE checks SET remaining = remaining - 1, claimed = ? WHERE code = ?",
        (json.dumps(claimed), code.upper())
    )
    conn.commit()
    conn.close()
    return True, f"✅ Активирован чек на {fmt_money(currency, reward)}!", reward, currency

def get_user_checks(user_id: int):
    conn = get_db()
    rows = conn.execute("SELECT code, per_user, currency, remaining FROM checks WHERE creator_id = ?", (str(user_id),)).fetchall()
    conn.close()
    return rows

# ========== ПРОМОКОДЫ ==========
def create_promo(code: str, reward_gram: float, reward_gold: float, activations: int):
    conn = get_db()
    conn.execute(
        "INSERT OR REPLACE INTO promos (name, reward_gram, reward_gold, remaining_activations, claimed) VALUES (?, ?, ?, ?, ?)",
        (code.upper(), reward_gram, reward_gold, activations, "[]")
    )
    conn.commit()
    conn.close()

def redeem_promo(user_id: int, code: str) -> tuple:
    conn = get_db()
    row = conn.execute("SELECT * FROM promos WHERE name = ?", (code.upper(),)).fetchone()
    if not row:
        conn.close()
        return False, "❌ Промокод не найден!", 0, 0
    
    if row["remaining_activations"] <= 0:
        conn.close()
        return False, "❌ Промокод уже использован!", 0, 0
    
    claimed = json.loads(row["claimed"])
    if str(user_id) in claimed:
        conn.close()
        return False, "❌ Ты уже активировал этот промокод!", 0, 0
    
    claimed.append(str(user_id))
    reward_gram = row["reward_gram"] or 0
    reward_gold = row["reward_gold"] or 0
    
    if reward_gram > 0:
        update_balance(user_id, "gram", reward_gram)
    if reward_gold > 0:
        update_balance(user_id, "gold", reward_gold)
    
    conn.execute(
        "UPDATE promos SET remaining_activations = remaining_activations - 1, claimed = ? WHERE name = ?",
        (json.dumps(claimed), code.upper())
    )
    conn.commit()
    conn.close()
    return True, f"✅ Промокод активирован!", reward_gram, reward_gold

# ========== КЛАВИАТУРЫ ==========
def main_menu():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="👤 Профиль"), KeyboardButton(text="🎮 Игры")],
            [KeyboardButton(text="💎 Пополнить"), KeyboardButton(text="🎁 Бонус")],
            [KeyboardButton(text="🏆 Топ игроков"), KeyboardButton(text="🧾 Чеки")],
            [KeyboardButton(text="🎟 Промокод")]
        ],
        resize_keyboard=True
    )

def games_menu():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🎡 Рулетка"), KeyboardButton(text="📈 Краш")],
            [KeyboardButton(text="🎲 Кубик"), KeyboardButton(text="🎯 Кости")],
            [KeyboardButton(text="⚽ Футбол"), KeyboardButton(text="🏀 Баскетбол")],
            [KeyboardButton(text="◀️ Главное меню")]
        ],
        resize_keyboard=True
    )

def currency_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💎 Граммы", callback_data="currency_gram")],
        [InlineKeyboardButton(text="🏅 Iris-Gold", callback_data="currency_gold")],
        [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel")]
    ])

def bet_type_menu(game: str, currency: str):
    if game == "roulette":
        return InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔴 Красное (x2)", callback_data=f"bet_roulette_red_{currency}"),
             InlineKeyboardButton(text="⚫ Чёрное (x2)", callback_data=f"bet_roulette_black_{currency}")],
            [InlineKeyboardButton(text="2️⃣ Чёт (x2)", callback_data=f"bet_roulette_even_{currency}"),
             InlineKeyboardButton(text="1️⃣ Нечет (x2)", callback_data=f"bet_roulette_odd_{currency}")],
            [InlineKeyboardButton(text="0️⃣ Зеро (x35)", callback_data=f"bet_roulette_zero_{currency}")],
            [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel")]
        ])
    elif game == "cube":
        return InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="1️⃣", callback_data=f"bet_cube_1_{currency}"),
             InlineKeyboardButton(text="2️⃣", callback_data=f"bet_cube_2_{currency}"),
             InlineKeyboardButton(text="3️⃣", callback_data=f"bet_cube_3_{currency}")],
            [InlineKeyboardButton(text="4️⃣", callback_data=f"bet_cube_4_{currency}"),
             InlineKeyboardButton(text="5️⃣", callback_data=f"bet_cube_5_{currency}"),
             InlineKeyboardButton(text="6️⃣", callback_data=f"bet_cube_6_{currency}")],
            [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel")]
        ])
    elif game == "dice":
        return InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📈 Больше 7 (x1.9)", callback_data=f"bet_dice_high_{currency}")],
            [InlineKeyboardButton(text="📉 Меньше 7 (x1.9)", callback_data=f"bet_dice_low_{currency}")],
            [InlineKeyboardButton(text="🎯 Равно 7 (x5.0)", callback_data=f"bet_dice_seven_{currency}")],
            [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel")]
        ])
    return None

def deposit_amount_menu(currency: str):
    if currency == "gram":
        return InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⭐ 1 Star", callback_data="deposit_gram_1"),
             InlineKeyboardButton(text="⭐ 5 Stars", callback_data="deposit_gram_5")],
            [InlineKeyboardButton(text="⭐ 10 Stars", callback_data="deposit_gram_10"),
             InlineKeyboardButton(text="⭐ 25 Stars", callback_data="deposit_gram_25")],
            [InlineKeyboardButton(text="⭐ 50 Stars", callback_data="deposit_gram_50"),
             InlineKeyboardButton(text="⭐ 100 Stars", callback_data="deposit_gram_100")],
            [InlineKeyboardButton(text="✏️ Своя сумма", callback_data="deposit_custom_gram")],
            [InlineKeyboardButton(text="◀️ Назад", callback_data="back_deposit")]
        ])
    else:
        return InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⭐ 1 Star", callback_data="deposit_gold_1"),
             InlineKeyboardButton(text="⭐ 5 Stars", callback_data="deposit_gold_5")],
            [InlineKeyboardButton(text="⭐ 10 Stars", callback_data="deposit_gold_10"),
             InlineKeyboardButton(text="⭐ 25 Stars", callback_data="deposit_gold_25")],
            [InlineKeyboardButton(text="⭐ 50 Stars", callback_data="deposit_gold_50"),
             InlineKeyboardButton(text="⭐ 100 Stars", callback_data="deposit_gold_100")],
            [InlineKeyboardButton(text="✏️ Своя сумма", callback_data="deposit_custom_gold")],
            [InlineKeyboardButton(text="◀️ Назад", callback_data="back_deposit")]
        ])

# ========== СОСТОЯНИЯ ==========
class GameStates(StatesGroup):
    waiting_bet_amount = State()
    waiting_crash_mult = State()

class DepositStates(StatesGroup):
    waiting_custom_amount = State()
    waiting_currency = State()

class CheckStates(StatesGroup):
    waiting_amount = State()
    waiting_count = State()
    waiting_currency = State()
    waiting_code = State()

class PromoStates(StatesGroup):
    waiting_code = State()

# ========== ИГРЫ ==========
RED_NUMBERS = {1,3,5,7,9,12,14,16,18,19,21,23,25,27,30,32,34,36}

def roulette_spin(choice: str):
    num = random.randint(0, 36)
    color = "green" if num == 0 else ("red" if num in RED_NUMBERS else "black")
    win = False
    mult = 0
    if choice == "red" and color == "red":
        win, mult = True, 2
    elif choice == "black" and color == "black":
        win, mult = True, 2
    elif choice == "even" and num != 0 and num % 2 == 0:
        win, mult = True, 2
    elif choice == "odd" and num % 2 == 1:
        win, mult = True, 2
    elif choice == "zero" and num == 0:
        win, mult = True, 35
    return win, mult, num, color

def crash_game():
    r = random.random()
    if r < 0.05: return round(random.uniform(1.00, 1.50), 2)
    elif r < 0.30: return round(random.uniform(1.51, 2.50), 2)
    elif r < 0.60: return round(random.uniform(2.51, 4.00), 2)
    elif r < 0.85: return round(random.uniform(4.01, 7.00), 2)
    else: return round(random.uniform(7.01, 50.00), 2)

# ========== ОБРАБОТЧИКИ ==========
@dp.message(CommandStart())
async def start_cmd(message: Message):
    ensure_user(message.from_user.id)
    await message.answer(
        f"🌟 <b>Добро пожаловать в Casino Bot!</b>\n\n"
        f"💰 <b>Твой баланс:</b>\n"
        f"💎 {GRAM_NAME}: {fmt_gram(START_GRAM)}\n"
        f"🏅 {GOLD_NAME}: {fmt_gold(START_GOLD)}\n\n"
        f"👇 Используй кнопки ниже:",
        reply_markup=main_menu()
    )

@dp.message(F.text == "◀️ Главное меню")
async def back_to_main(message: Message):
    user = get_user(message.from_user.id)
    await message.answer(
        f"🌟 <b>Главное меню</b>\n\n"
        f"💰 Баланс:\n"
        f"💎 {GRAM_NAME}: {fmt_gram(user['gram'])}\n"
        f"🏅 {GOLD_NAME}: {fmt_gold(user['gold'])}",
        reply_markup=main_menu()
    )

@dp.message(F.text == "👤 Профиль")
async def profile_cmd(message: Message):
    user = get_user(message.from_user.id)
    wins = user["total_wins"] or 0
    bets = user["total_bets"] or 1
    wr = (wins / bets) * 100
    await message.answer(
        f"👤 <b>Твой профиль</b>\n\n"
        f"🆔 ID: <code>{message.from_user.id}</code>\n\n"
        f"💰 <b>Баланс:</b>\n"
        f"💎 {GRAM_NAME}: {fmt_gram(user['gram'])}\n"
        f"🏅 {GOLD_NAME}: {fmt_gold(user['gold'])}\n\n"
        f"💎 Всего пополнено {GRAM_NAME}: {fmt_gram(user['total_deposited_gram'] or 0)}\n"
        f"🏅 Всего пополнено {GOLD_NAME}: {fmt_gold(user['total_deposited_gold'] or 0)}\n\n"
        f"🎲 Всего ставок: {bets}\n"
        f"🏆 Побед: {wins} ({wr:.1f}%)\n\n"
        f"📊 Ставки {GRAM_NAME}: от {fmt_gram(MIN_BET_GRAM)} до {fmt_gram(MAX_BET_GRAM)}\n"
        f"📊 Ставки {GOLD_NAME}: от {fmt_gold(MIN_BET_GOLD)} до {fmt_gold(MAX_BET_GOLD)}",
        reply_markup=main_menu()
    )

@dp.message(F.text == "🎮 Игры")
async def games_menu_cmd(message: Message):
    await message.answer(
        "🎮 <b>Выбери игру</b>\n\n"
        f"📊 Ставки {GRAM_NAME}: от {fmt_gram(MIN_BET_GRAM)} до {fmt_gram(MAX_BET_GRAM)}\n"
        f"📊 Ставки {GOLD_NAME}: от {fmt_gold(MIN_BET_GOLD)} до {fmt_gold(MAX_BET_GOLD)}",
        reply_markup=games_menu()
    )

@dp.message(F.text == "🏆 Топ игроков")
async def top_cmd(message: Message):
    top_gram = get_top_players("gram", 5)
    top_gold = get_top_players("gold", 5)
    
    text = "🏆 <b>Топ игроков</b>\n\n"
    text += "💎 <b>По Граммам:</b>\n"
    medals = ["🥇", "🥈", "🥉"]
    for i, p in enumerate(top_gram):
        medal = medals[i] if i < 3 else f"{i+1}."
        text += f"{medal} {mention_user(int(p['user_id']))} — {fmt_gram(p['gram'])}\n"
    
    text += "\n🏅 <b>По Iris-Gold:</b>\n"
    for i, p in enumerate(top_gold):
        medal = medals[i] if i < 3 else f"{i+1}."
        text += f"{medal} {mention_user(int(p['user_id']))} — {fmt_gold(p['gold'])}\n"
    
    await message.answer(text, reply_markup=main_menu())

@dp.message(F.text == "🎁 Бонус")
async def bonus_cmd(message: Message):
    user_id = message.from_user.id
    user = get_user(user_id)
    last_bonus = user["last_bonus"] or 0
    now = now_ts()
    
    if now - last_bonus < 43200:
        left = 43200 - (now - last_bonus)
        hours = left // 3600
        minutes = (left % 3600) // 60
        await message.answer(
            f"⏰ <b>Бонус ещё не доступен!</b>\n\n"
            f"Приходи через {hours}ч {minutes}мин",
            reply_markup=main_menu()
        )
        return
    
    reward_gram = random.randint(100, 500)
    reward_gold = round(random.uniform(0.5, 2.0), 2)
    
    update_balance(user_id, "gram", reward_gram)
    update_balance(user_id, "gold", reward_gold)
    
    conn = get_db()
    conn.execute("UPDATE users SET last_bonus = ? WHERE user_id = ?", (now, str(user_id)))
    conn.commit()
    conn.close()
    
    await message.answer(
        f"🎁 <b>Ежедневный бонус!</b>\n\n"
        f"✨ Ты получил:\n"
        f"💎 +{fmt_gram(reward_gram)}\n"
        f"🏅 +{fmt_gold(reward_gold)}",
        reply_markup=main_menu()
    )

# ========== ПОПОЛНЕНИЕ ЧЕРЕЗ STARS ==========
@dp.message(F.text == "💎 Пополнить")
async def deposit_start(message: Message):
    await message.answer(
        f"💎 <b>Пополнение баланса</b>\n\n"
        f"⭐ <b>Курс:</b>\n"
        f"• 1 Star = {fmt_gram(STAR_TO_GRAM)}\n"
        f"• 1 Star = {fmt_gold(STAR_TO_GOLD)}\n\n"
        f"Выбери валюту для пополнения:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="💎 Пополнить Граммы", callback_data="deposit_gram")],
            [InlineKeyboardButton(text="🏅 Пополнить Iris-Gold", callback_data="deposit_gold")],
            [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel")]
        ])
    )

@dp.callback_query(F.data == "deposit_gram")
async def deposit_gram(call: CallbackQuery):
    await call.message.edit_text(
        f"💎 <b>Пополнение {GRAM_NAME}</b>\n\n"
        f"⭐ <b>Курс:</b> 1 Star = {fmt_gram(STAR_TO_GRAM)}\n\n"
        f"Выбери сумму в Stars:",
        reply_markup=deposit_amount_menu("gram")
    )
    await call.answer()

@dp.callback_query(F.data == "deposit_gold")
async def deposit_gold(call: CallbackQuery):
    await call.message.edit_text(
        f"🏅 <b>Пополнение {GOLD_NAME}</b>\n\n"
        f"⭐ <b>Курс:</b> 1 Star = {fmt_gold(STAR_TO_GOLD)}\n\n"
        f"Выбери сумму в Stars:",
        reply_markup=deposit_amount_menu("gold")
    )
    await call.answer()

@dp.callback_query(F.data.startswith("deposit_gram_"))
async def process_gram_deposit(call: CallbackQuery, state: FSMContext):
    if call.data == "deposit_custom_gram":
        await state.set_state(DepositStates.waiting_custom_amount)
        await state.update_data(currency="gram")
        await call.message.edit_text(
            f"💎 Введи сумму в Stars (от 1 до 10000):\n\n"
            f"⭐ 1 Star = {fmt_gram(STAR_TO_GRAM)}",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="❌ Отмена", callback_data="cancel")]])
        )
        await call.answer()
        return
    
    stars = int(call.data.split("_")[2])
    gram = stars * STAR_TO_GRAM
    
    # Создаём инвойс
    await call.message.answer_invoice(
        title=f"💎 Пополнение {GRAM_NAME}",
        description=f"Получи {fmt_gram(gram)} за {stars} Stars!",
        payload=f"deposit_gram_{stars}_{gram}",
        provider_token="",
        currency="XTR",
        prices=[LabeledPrice(label=f"{stars} Stars", amount=stars)],
        start_parameter="deposit_gram"
    )
    await call.answer()

@dp.callback_query(F.data.startswith("deposit_gold_"))
async def process_gold_deposit(call: CallbackQuery, state: FSMContext):
    if call.data == "deposit_custom_gold":
        await state.set_state(DepositStates.waiting_custom_amount)
        await state.update_data(currency="gold")
        await call.message.edit_text(
            f"🏅 Введи сумму в Stars (от 1 до 10000):\n\n"
            f"⭐ 1 Star = {fmt_gold(STAR_TO_GOLD)}",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="❌ Отмена", callback_data="cancel")]])
        )
        await call.answer()
        return
    
    stars = int(call.data.split("_")[2])
    gold = stars * STAR_TO_GOLD
    
    await call.message.answer_invoice(
        title=f"🏅 Пополнение {GOLD_NAME}",
        description=f"Получи {fmt_gold(gold)} за {stars} Stars!",
        payload=f"deposit_gold_{stars}_{gold}",
        provider_token="",
        currency="XTR",
        prices=[LabeledPrice(label=f"{stars} Stars", amount=stars)],
        start_parameter="deposit_gold"
    )
    await call.answer()

@dp.message(DepositStates.waiting_custom_amount)
async def process_custom_amount(message: Message, state: FSMContext):
    try:
        stars = float(message.text.replace(",", "."))
        if stars < 1 or stars > 10000:
            await message.answer("❌ Сумма должна быть от 1 до 10000 Stars")
            return
        
        data = await state.get_data()
        currency = data["currency"]
        stars_int = int(stars)
        
        if currency == "gram":
            amount = stars_int * STAR_TO_GRAM
            await message.answer_invoice(
                title=f"💎 Пополнение {GRAM_NAME}",
                description=f"Получи {fmt_gram(amount)} за {stars_int} Stars!",
                payload=f"deposit_gram_{stars_int}_{amount}",
                provider_token="",
                currency="XTR",
                prices=[LabeledPrice(label=f"{stars_int} Stars", amount=stars_int)],
                start_parameter="deposit_gram"
            )
        else:
            amount = stars_int * STAR_TO_GOLD
            await message.answer_invoice(
                title=f"🏅 Пополнение {GOLD_NAME}",
                description=f"Получи {fmt_gold(amount)} за {stars_int} Stars!",
                payload=f"deposit_gold_{stars_int}_{amount}",
                provider_token="",
                currency="XTR",
                prices=[LabeledPrice(label=f"{stars_int} Stars", amount=stars_int)],
                start_parameter="deposit_gold"
            )
        await state.clear()
    except:
        await message.answer("❌ Введи корректную сумму!")

@dp.pre_checkout_query()
async def pre_checkout_handler(query: PreCheckoutQuery):
    await query.answer(ok=True)

@dp.message(F.successful_payment)
async def successful_payment_handler(message: Message):
    payment = message.successful_payment
    payload = payment.invoice_payload
    
    parts = payload.split("_")
    currency = parts[1]
    stars = int(parts[2])
    amount = float(parts[3])
    
    if currency == "gram":
        new_balance = update_balance(message.from_user.id, "gram", amount)
        update_balance(message.from_user.id, "total_deposited_gram", amount)
        await message.answer(
            f"✅ <b>Пополнение успешно!</b>\n\n"
            f"⭐ Оплачено: {stars} Stars\n"
            f"💰 Получено: {fmt_gram(amount)}\n"
            f"💎 Новый баланс: {fmt_gram(new_balance)}\n\n"
            f"🎮 Приятной игры!",
            reply_markup=main_menu()
        )
    else:
        new_balance = update_balance(message.from_user.id, "gold", amount)
        update_balance(message.from_user.id, "total_deposited_gold", amount)
        await message.answer(
            f"✅ <b>Пополнение успешно!</b>\n\n"
            f"⭐ Оплачено: {stars} Stars\n"
            f"💰 Получено: {fmt_gold(amount)}\n"
            f"🏅 Новый баланс: {fmt_gold(new_balance)}\n\n"
            f"🎮 Приятной игры!",
            reply_markup=main_menu()
        )
    
    # Уведомление админам
    for admin_id in ADMIN_IDS:
        await message.bot.send_message(
            admin_id,
            f"💎 <b>Новое пополнение!</b>\n\n"
            f"👤 Пользователь: {mention_user(message.from_user.id, message.from_user.first_name)}\n"
            f"⭐ Stars: {stars}\n"
            f"💰 Получено: {fmt_money(currency, amount)}"
        )

# ========== ИГРЫ ==========
@dp.message(F.text == "🎡 Рулетка")
async def roulette_start(message: Message, state: FSMContext):
    await state.update_data(game="roulette")
    await state.set_state(GameStates.waiting_bet_amount)
    await message.answer(
        f"🎡 <b>Рулетка</b>\n\n"
        f"Выбери валюту и введи сумму ставки.\n"
        f"Пример: <code>100 gram</code> или <code>50 gold</code>\n\n"
        f"📊 Лимиты:\n"
        f"💎 {GRAM_NAME}: от {fmt_gram(MIN_BET_GRAM)} до {fmt_gram(MAX_BET_GRAM)}\n"
        f"🏅 {GOLD_NAME}: от {fmt_gold(MIN_BET_GOLD)} до {fmt_gold(MAX_BET_GOLD)}",
        reply_markup=ReplyKeyboardMarkup(
            keyboard=[[KeyboardButton(text="◀️ Главное меню")]],
            resize_keyboard=True
        )
    )

@dp.message(F.text == "📈 Краш")
async def crash_start(message: Message, state: FSMContext):
    await state.update_data(game="crash")
    await state.set_state(GameStates.waiting_bet_amount)
    await message.answer(
        f"📈 <b>Краш</b>\n\n"
        f"Выбери валюту и введи сумму ставки.\n"
        f"Пример: <code>100 gram</code> или <code>50 gold</code>\n\n"
        f"📊 Лимиты:\n"
        f"💎 {GRAM_NAME}: от {fmt_gram(MIN_BET_GRAM)} до {fmt_gram(MAX_BET_GRAM)}\n"
        f"🏅 {GOLD_NAME}: от {fmt_gold(MIN_BET_GOLD)} до {fmt_gold(MAX_BET_GOLD)}",
        reply_markup=ReplyKeyboardMarkup(
            keyboard=[[KeyboardButton(text="◀️ Главное меню")]],
            resize_keyboard=True
        )
    )

@dp.message(F.text == "🎲 Кубик")
async def cube_start(message: Message, state: FSMContext):
    await state.update_data(game="cube")
    await state.set_state(GameStates.waiting_bet_amount)
    await message.answer(
        f"🎲 <b>Кубик</b>\n\n"
        f"Выбери валюту и введи сумму ставки.\n"
        f"Пример: <code>100 gram</code> или <code>50 gold</code>\n\n"
        f"📊 Лимиты:\n"
        f"💎 {GRAM_NAME}: от {fmt_gram(MIN_BET_GRAM)} до {fmt_gram(MAX_BET_GRAM)}\n"
        f"🏅 {GOLD_NAME}: от {fmt_gold(MIN_BET_GOLD)} до {fmt_gold(MAX_BET_GOLD)}",
        reply_markup=ReplyKeyboardMarkup(
            keyboard=[[KeyboardButton(text="◀️ Главное меню")]],
            resize_keyboard=True
        )
    )

@dp.message(F.text == "🎯 Кости")
async def dice_start(message: Message, state: FSMContext):
    await state.update_data(game="dice")
    await state.set_state(GameStates.waiting_bet_amount)
    await message.answer(
        f"🎯 <b>Кости</b>\n\n"
        f"Выбери валюту и введи сумму ставки.\n"
        f"Пример: <code>100 gram</code> или <code>50 gold</code>\n\n"
        f"📊 Лимиты:\n"
        f"💎 {GRAM_NAME}: от {fmt_gram(MIN_BET_GRAM)} до {fmt_gram(MAX_BET_GRAM)}\n"
        f"🏅 {GOLD_NAME}: от {fmt_gold(MIN_BET_GOLD)} до {fmt_gold(MAX_BET_GOLD)}",
        reply_markup=ReplyKeyboardMarkup(
            keyboard=[[KeyboardButton(text="◀️ Главное меню")]],
            resize_keyboard=True
        )
    )

@dp.message(F.text == "⚽ Футбол")
async def football_start(message: Message, state: FSMContext):
    await state.update_data(game="football")
    await state.set_state(GameStates.waiting_bet_amount)
    await message.answer(
        f"⚽ <b>Футбол</b>\n\n"
        f"Выбери валюту и введи сумму ставки.\n"
        f"Пример: <code>100 gram</code> или <code>50 gold</code>\n\n"
        f"📊 Лимиты:\n"
        f"💎 {GRAM_NAME}: от {fmt_gram(MIN_BET_GRAM)} до {fmt_gram(MAX_BET_GRAM)}\n"
        f"🏅 {GOLD_NAME}: от {fmt_gold(MIN_BET_GOLD)} до {fmt_gold(MAX_BET_GOLD)}",
        reply_markup=ReplyKeyboardMarkup(
            keyboard=[[KeyboardButton(text="◀️ Главное меню")]],
            resize_keyboard=True
        )
    )

@dp.message(F.text == "🏀 Баскетбол")
async def basket_start(message: Message, state: FSMContext):
    await state.update_data(game="basket")
    await state.set_state(GameStates.waiting_bet_amount)
    await message.answer(
        f"🏀 <b>Баскетбол</b>\n\n"
        f"Выбери валюту и введи сумму ставки.\n"
        f"Пример: <code>100 gram</code> или <code>50 gold</code>\n\n"
        f"📊 Лимиты:\n"
        f"💎 {GRAM_NAME}: от {fmt_gram(MIN_BET_GRAM)} до {fmt_gram(MAX_BET_GRAM)}\n"
        f"🏅 {GOLD_NAME}: от {fmt_gold(MIN_BET_GOLD)} до {fmt_gold(MAX_BET_GOLD)}",
        reply_markup=ReplyKeyboardMarkup(
            keyboard=[[KeyboardButton(text="◀️ Главное меню")]],
            resize_keyboard=True
        )
    )

@dp.message(GameStates.waiting_bet_amount)
async def process_bet_amount(message: Message, state: FSMContext):
    if message.text == "◀️ Главное меню":
        await state.clear()
        user = get_user(message.from_user.id)
        await message.answer(
            f"🌟 <b>Главное меню</b>\n\n"
            f"💰 Баланс:\n"
            f"💎 {GRAM_NAME}: {fmt_gram(user['gram'])}\n"
            f"🏅 {GOLD_NAME}: {fmt_gold(user['gold'])}",
            reply_markup=main_menu()
        )
        return
    
    try:
        parts = message.text.lower().split()
        if len(parts) != 2:
            await message.answer("❌ Формат: <code>сумма валюта</code>\nПример: <code>100 gram</code> или <code>50 gold</code>")
            return
        
        bet = float(parts[0].replace(",", "."))
        currency = parts[1]
        
        if currency not in ["gram", "gold"]:
            await message.answer("❌ Валюта должна быть 'gram' или 'gold'")
            return
        
        min_bet = MIN_BET_GRAM if currency == "gram" else MIN_BET_GOLD
        max_bet = MAX_BET_GRAM if currency == "gram" else MAX_BET_GOLD
        
        if bet < min_bet:
            await message.answer(f"❌ Минимальная ставка: {fmt_money(currency, min_bet)}")
            return
        if bet > max_bet:
            await message.answer(f"❌ Максимальная ставка: {fmt_money(currency, max_bet)}")
            return
        
        user = get_user(message.from_user.id)
        if user[currency] < bet:
            await message.answer(f"❌ Недостаточно средств! Твой баланс: {fmt_money(currency, user[currency])}")
            return
        
        data = await state.get_data()
        game = data["game"]
        
        await state.update_data(bet=bet, currency=currency)
        
        if game == "crash":
            await state.set_state(GameStates.waiting_crash_mult)
            await message.answer(f"📈 Введи множитель выигрыша (1.10 - 10.00):")
        elif game in ["roulette", "cube", "dice"]:
            kb = bet_type_menu(game, currency)
            if kb:
                await message.answer(f"🎮 Выбери вариант ставки:", reply_markup=kb)
                await state.clear()
            else:
                await message.answer("❌ Ошибка меню")
        else:
            # Футбол, Баскетбол - автоматические игры
            await play_instant_game(message, state, game, bet, currency)
            
    except ValueError:
        await message.answer("❌ Введи корректную сумму!\nПример: <code>100 gram</code>")
    except Exception as e:
        await message.answer(f"❌ Ошибка: {e}")

async def play_instant_game(message: Message, state: FSMContext, game: str, bet: float, currency: str):
    if game == "football":
        result = await message.answer_dice(emoji="⚽")
        value = result.dice.value
        win = value >= 4
        payout = bet * 1.85 if win else 0
        new_balance = update_balance(message.from_user.id, currency, -bet + payout)
        add_bet_record(message.from_user.id, bet, win, "football", currency)
        
        outcome = "ГОЛ 🎉" if win else "МИМО 😔"
        await message.answer(
            f"⚽ <b>Футбол</b>\n\n"
            f"🎲 Результат: <b>{outcome}</b>\n"
            f"💰 Ставка: {fmt_money(currency, bet)}\n"
            f"{'🎉' if win else '😔'} Итог: <b>{'ПОБЕДА' if win else 'ПРОИГРЫШ'}</b>\n"
            f"💸 Выплата: {fmt_money(currency, payout)}\n"
            f"💎 Новый баланс: {fmt_money(currency, new_balance)}",
            reply_markup=games_menu()
        )
        
    elif game == "basket":
        result = await message.answer_dice(emoji="🏀")
        value = result.dice.value
        win = value in [4, 5]
        payout = bet * 1.85 if win else 0
        new_balance = update_balance(message.from_user.id, currency, -bet + payout)
        add_bet_record(message.from_user.id, bet, win, "basket", currency)
        
        outcome = "ТОЧНЫЙ БРОСОК 🎉" if win else "ПРОМАХ 😔"
        await message.answer(
            f"🏀 <b>Баскетбол</b>\n\n"
            f"🎲 Результат: <b>{outcome}</b>\n"
            f"💰 Ставка: {fmt_money(currency, bet)}\n"
            f"{'🎉' if win else '😔'} Итог: <b>{'ПОБЕДА' if win else 'ПРОИГРЫШ'}</b>\n"
            f"💸 Выплата: {fmt_money(currency, payout)}\n"
            f"💎 Новый баланс: {fmt_money(currency, new_balance)}",
            reply_markup=games_menu()
        )
    
    await state.clear()

@dp.message(GameStates.waiting_crash_mult)
async def process_crash_mult(message: Message, state: FSMContext):
    try:
        mult = float(message.text.replace(",", "."))
        if mult < 1.10 or mult > 10.00:
            await message.answer("❌ Множитель должен быть от 1.10 до 10.00")
            return
        
        data = await state.get_data()
        bet = data["bet"]
        currency = data["currency"]
        
        crash_mult = crash_game()
        win = crash_mult >= mult
        payout = bet * mult if win else 0
        new_balance = update_balance(message.from_user.id, currency, -bet + payout)
        add_bet_record(message.from_user.id, bet, win, "crash", currency)
        
        await message.answer(
            f"📈 <b>Краш</b>\n\n"
            f"🎲 Множитель игры: <b>x{crash_mult:.2f}</b>\n"
            f"🎯 Твой множитель: <b>x{mult:.2f}</b>\n"
            f"{'🎉' if win else '😔'} Итог: <b>{'ПОБЕДА' if win else 'ПРОИГРЫШ'}</b>\n"
            f"💰 Ставка: {fmt_money(currency, bet)}\n"
            f"💸 Выплата: {fmt_money(currency, payout)}\n"
            f"💎 Новый баланс: {fmt_money(currency, new_balance)}",
            reply_markup=games_menu()
        )
        await state.clear()
    except:
        await message.answer("❌ Введи корректный множитель!")

@dp.callback_query(F.data.startswith("bet_"))
async def handle_bet_callback(call: CallbackQuery, state: FSMContext):
    parts = call.data.split("_")
    game = parts[1]
    choice = parts[2]
    currency = parts[3]
    
    # Здесь нужно получить ставку из состояния, для демо используем временную
    await call.message.answer(f"✅ Ставка принята! Результат будет скоро...")
    await call.answer()

# ========== ЧЕКИ ==========
@dp.message(F.text == "🧾 Чеки")
async def checks_menu(message: Message):
    await message.answer(
        "🧾 <b>Чеки</b>\n\n"
        "Создавай чеки для друзей или активируй чужие!",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="➕ Создать чек", callback_data="check_create")],
            [InlineKeyboardButton(text="💸 Активировать чек", callback_data="check_claim")],
            [InlineKeyboardButton(text="📋 Мои чеки", callback_data="check_my")],
            [InlineKeyboardButton(text="❌ Закрыть", callback_data="cancel")]
        ])
    )

@dp.callback_query(F.data == "check_create")
async def check_create(call: CallbackQuery, state: FSMContext):
    await state.set_state(CheckStates.waiting_currency)
    await call.message.edit_text(
        f"🧾 <b>Создание чека</b>\n\n"
        f"Выбери валюту:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="💎 Граммы", callback_data="check_currency_gram")],
            [InlineKeyboardButton(text="🏅 Iris-Gold", callback_data="check_currency_gold")],
            [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel")]
        ])
    )
    await call.answer()

@dp.callback_query(F.data.startswith("check_currency_"))
async def check_currency(call: CallbackQuery, state: FSMContext):
    currency = call.data.split("_")[2]
    await state.update_data(currency=currency)
    await state.set_state(CheckStates.waiting_amount)
    
    min_amount = MIN_BET_GRAM if currency == "gram" else MIN_BET_GOLD
    await call.message.edit_text(
        f"💸 <b>Создание чека</b>\n\n"
        f"💎 Валюта: {GRAM_NAME if currency == 'gram' else GOLD_NAME}\n"
        f"💰 Введи сумму для одной активации (мин. {fmt_money(currency, min_amount)}):",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="❌ Отмена", callback_data="cancel")]])
    )
    await call.answer()

@dp.message(CheckStates.waiting_amount)
async def check_amount(message: Message, state: FSMContext):
    try:
        amount = float(message.text.replace(",", "."))
        data = await state.get_data()
        currency = data["currency"]
        
        min_amount = MIN_BET_GRAM if currency == "gram" else MIN_BET_GOLD
        if amount < min_amount:
            await message.answer(f"❌ Минимальная сумма: {fmt_money(currency, min_amount)}")
            return
        
        await state.update_data(amount=amount)
        await state.set_state(CheckStates.waiting_count)
        await message.answer("📦 Введи количество активаций (1-100):")
    except:
        await message.answer("❌ Введи число, например: 100")

@dp.message(CheckStates.waiting_count)
async def check_count(message: Message, state: FSMContext):
    try:
        count = int(message.text)
        if count < 1 or count > 100:
            await message.answer("❌ Количество от 1 до 100")
            return
        
        data = await state.get_data()
        amount = data["amount"]
        currency = data["currency"]
        
        ok, result = create_check(message.from_user.id, amount, currency, count)
        await state.clear()
        if ok:
            await message.answer(
                f"✅ <b>Чек создан!</b>\n\n"
                f"🎫 Код: <code>{result}</code>\n"
                f"💰 Сумма: {fmt_money(currency, amount)}\n"
                f"💎 Валюта: {GRAM_NAME if currency == 'gram' else GOLD_NAME}\n"
                f"📦 Активаций: {count}",
                reply_markup=main_menu()
            )
        else:
            await message.answer(f"❌ {result}", reply_markup=main_menu())
    except:
        await message.answer("❌ Введи целое число")

@dp.callback_query(F.data == "check_claim")
async def check_claim(call: CallbackQuery, state: FSMContext):
    await state.set_state(CheckStates.waiting_code)
    await call.message.edit_text(
        "🎫 <b>Активация чека</b>\n\n"
        "Введи код чека:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="❌ Отмена", callback_data="cancel")]])
    )
    await call.answer()

@dp.message(CheckStates.waiting_code)
async def claim_code(message: Message, state: FSMContext):
    code = message.text.strip().upper()
    ok, result, reward, currency = claim_check(message.from_user.id, code)
    await state.clear()
    if ok:
        await message.answer(
            f"✅ {result}\n💰 Новый баланс: {fmt_money(currency, get_user(message.from_user.id)[currency])}",
            reply_markup=main_menu()
        )
    else:
        await message.answer(f"❌ {result}", reply_markup=main_menu())

@dp.callback_query(F.data == "check_my")
async def my_checks(call: CallbackQuery):
    checks = get_user_checks(call.from_user.id)
    if not checks:
        await call.message.edit_text("📭 У тебя пока нет созданных чеков", reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="❌ Закрыть", callback_data="cancel")]]))
    else:
        text = "🧾 <b>Твои чеки</b>\n\n"
        for c in checks:
            currency_name = GRAM_NAME if c['currency'] == 'gram' else GOLD_NAME
            text += f"🎫 <code>{c['code']}</code> | {fmt_money(c['currency'], c['per_user'])} | {currency_name} | осталось: {c['remaining']}\n"
        await call.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="❌ Закрыть", callback_data="cancel")]]))
    await call.answer()

# ========== ПРОМОКОДЫ ==========
@dp.message(F.text == "🎟 Промокод")
async def promo_start(message: Message, state: FSMContext):
    await state.set_state(PromoStates.waiting_code)
    await message.answer(
        "🎟 <b>Активация промокода</b>\n\n"
        "Введи промокод:",
        reply_markup=ReplyKeyboardMarkup(
            keyboard=[[KeyboardButton(text="◀️ Главное меню")]],
            resize_keyboard=True
        )
    )

@dp.message(PromoStates.waiting_code)
async def activate_promo(message: Message, state: FSMContext):
    if message.text == "◀️ Главное меню":
        await state.clear()
        user = get_user(message.from_user.id)
        await message.answer(
            f"🌟 <b>Главное меню</b>\n\n"
            f"💰 Баланс:\n"
            f"💎 {GRAM_NAME}: {fmt_gram(user['gram'])}\n"
            f"🏅 {GOLD_NAME}: {fmt_gold(user['gold'])}",
            reply_markup=main_menu()
        )
        return
    
    code = message.text.strip().upper()
    ok, result, reward_gram, reward_gold = redeem_promo(message.from_user.id, code)
    await state.clear()
    if ok:
        text = f"🎉 {result}\n\n"
        if reward_gram > 0:
            text += f"💎 +{fmt_gram(reward_gram)}\n"
        if reward_gold > 0:
            text += f"🏅 +{fmt_gold(reward_gold)}\n"
        user = get_user(message.from_user.id)
        text += f"\n💰 Новый баланс:\n💎 {fmt_gram(user['gram'])}\n🏅 {fmt_gold(user['gold'])}"
        await message.answer(text, reply_markup=main_menu())
    else:
        await message.answer(f"❌ {result}", reply_markup=main_menu())

# ========== АДМИН КОМАНДЫ ==========
@dp.message(Command("addpromo"))
async def add_promo(message: Message):
    if not is_admin(message.from_user.id):
        await message.answer("⛔ Только для админов!")
        return
    parts = message.text.split()
    if len(parts) != 5:
        await message.answer("📝 Формат: /addpromo КОД ГРАММЫ ГОЛД АКТИВАЦИИ\nПример: /addpromo WELCOME 1000 5 50")
        return
    code = parts[1].upper()
    try:
        reward_gram = float(parts[2])
        reward_gold = float(parts[3])
        activations = int(parts[4])
        create_promo(code, reward_gram, reward_gold, activations)
        await message.answer(f"✅ Промокод создан!\n🎫 {code}\n💎 {fmt_gram(reward_gram)}\n🏅 {fmt_gold(reward_gold)}\n🎯 {activations} активаций")
    except:
        await message.answer("❌ Ошибка!")

@dp.message(Command("give"))
async def give_money(message: Message):
    if not is_admin(message.from_user.id):
        await message.answer("⛔ Только для админов!")
        return
    parts = message.text.split()
    if len(parts) != 4:
        await message.answer("📝 Формат: /give ID ВАЛЮТА СУММА\nВалюта: gram или gold\nПример: /give 123456789 gram 1000")
        return
    try:
        target_id = int(parts[1])
        currency = parts[2].lower()
        if currency not in ["gram", "gold"]:
            await message.answer("❌ Валюта должна быть gram или gold")
            return
        amount = float(parts[3])
        new_balance = update_balance(target_id, currency, amount)
        await message.answer(f"✅ Выдано {fmt_money(currency, amount)} пользователю {target_id}\n💰 Новый баланс: {fmt_money(currency, new_balance)}")
    except:
        await message.answer("❌ Ошибка! Пример: /give 123456789 gram 1000")

@dp.message(Command("all"))
async def all_users(message: Message):
    if not is_admin(message.from_user.id):
        await message.answer("⛔ Только для админов!")
        return
    conn = get_db()
    users = conn.execute("SELECT user_id, gram, gold FROM users").fetchall()
    conn.close()
    text = "👥 <b>Все пользователи:</b>\n\n"
    for u in users:
        text += f"👤 {u['user_id']} | 💎 {fmt_gram(u['gram'])} | 🏅 {fmt_gold(u['gold'])}\n"
    await message.answer(text)

@dp.callback_query(F.data == "cancel")
async def cancel_callback(call: CallbackQuery, state: FSMContext):
    await state.clear()
    await call.message.delete()
    await call.answer()

# ========== ЗАПУСК ==========
async def main():
    bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    await bot.delete_webhook(drop_pending_updates=True)
    print("✅ Бот запущен!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
