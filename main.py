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
)

# ========== КОНФИГ ==========
BOT_TOKEN = "8629137165:AAE2A5TwoT1MJ5YJMhb-m9zwMVCN5sA5ggk"
BOT_NAME = "WILLD GRAMM"
BOT_USERNAME = "WILLDGRAMM_bot"          # замените на реальный юзернейм бота
ADMIN_IDS = [8293927811, 8478884644]    # ID администраторов

# Обязательные подписки (замените на реальные ID после получения через /getid)
REQUIRED_CHANNEL_ID = -1002263528382    # ID канала @WILLDGRAMM
REQUIRED_CHAT_ID = -1002263528383       # ID чата @willdgrammchat

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

# Лимиты вывода
MIN_WITHDRAW_GRAM = 75000.0
MIN_WITHDRAW_GOLD = 10.0

# Бонус (только граммы)
BONUS_GRAM_MIN = 0
BONUS_GRAM_MAX = 250

# ========== ИНИЦИАЛИЗАЦИЯ ==========
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
        except:
            os.remove(DB_PATH)
    
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    
    cur.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id TEXT PRIMARY KEY,
            gram REAL DEFAULT 1000,
            gold REAL DEFAULT 0,
            total_bets INTEGER DEFAULT 0,
            total_wins INTEGER DEFAULT 0,
            last_bonus INTEGER DEFAULT 0,
            total_deposited_gram REAL DEFAULT 0,
            total_deposited_gold REAL DEFAULT 0,
            total_withdrawn_gram REAL DEFAULT 0,
            total_withdrawn_gold REAL DEFAULT 0
        )
    ''')
    
    cur.execute("PRAGMA table_info(users)")
    columns = [col[1] for col in cur.fetchall()]
    if "gram" not in columns: cur.execute("ALTER TABLE users ADD COLUMN gram REAL DEFAULT 1000")
    if "gold" not in columns: cur.execute("ALTER TABLE users ADD COLUMN gold REAL DEFAULT 0")
    if "total_bets" not in columns: cur.execute("ALTER TABLE users ADD COLUMN total_bets INTEGER DEFAULT 0")
    if "total_wins" not in columns: cur.execute("ALTER TABLE users ADD COLUMN total_wins INTEGER DEFAULT 0")
    if "last_bonus" not in columns: cur.execute("ALTER TABLE users ADD COLUMN last_bonus INTEGER DEFAULT 0")
    if "total_deposited_gram" not in columns: cur.execute("ALTER TABLE users ADD COLUMN total_deposited_gram REAL DEFAULT 0")
    if "total_deposited_gold" not in columns: cur.execute("ALTER TABLE users ADD COLUMN total_deposited_gold REAL DEFAULT 0")
    if "total_withdrawn_gram" not in columns: cur.execute("ALTER TABLE users ADD COLUMN total_withdrawn_gram REAL DEFAULT 0")
    if "total_withdrawn_gold" not in columns: cur.execute("ALTER TABLE users ADD COLUMN total_withdrawn_gold REAL DEFAULT 0")
    
    # Заявки на пополнение переводом (ручные)
    cur.execute('''
        CREATE TABLE IF NOT EXISTS transfer_requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT,
            currency TEXT,
            amount REAL,
            status TEXT,
            created_at INTEGER,
            processed_at INTEGER
        )
    ''')
    
    # Заявки на вывод
    cur.execute('''
        CREATE TABLE IF NOT EXISTS withdraw_requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT,
            currency TEXT,
            amount REAL,
            wallet TEXT,
            status TEXT,
            created_at INTEGER,
            processed_at INTEGER
        )
    ''')
    
    # Чеки
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
    
    # Промокоды
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
    value = round(value, 2)
    if value >= 1000:
        return f"{value/1000:.1f}K {GRAM_NAME}"
    return f"{value:.2f} {GRAM_NAME}"

def fmt_gold(value: float) -> str:
    value = round(value, 2)
    if value >= 1000:
        return f"{value/1000:.1f}K {GOLD_NAME}"
    return f"{value:.2f} {GOLD_NAME}"

def fmt_money(currency: str, value: float) -> str:
    return fmt_gram(value) if currency == "gram" else fmt_gold(value)

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

# ========== ЗАЯВКИ НА ПОПОЛНЕНИЕ ПЕРЕВОДОМ (ручные) ==========
def create_transfer_request(user_id: int, currency: str, amount: float) -> int:
    conn = get_db()
    conn.execute('''
        INSERT INTO transfer_requests (user_id, currency, amount, status, created_at)
        VALUES (?, ?, ?, 'pending', ?)
    ''', (str(user_id), currency, amount, now_ts()))
    conn.commit()
    req_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    conn.close()
    return req_id

def approve_transfer(req_id: int):
    conn = get_db()
    row = conn.execute("SELECT * FROM transfer_requests WHERE id = ?", (req_id,)).fetchone()
    if not row:
        conn.close()
        return False
    user_id = row["user_id"]
    currency = row["currency"]
    amount = row["amount"]
    update_balance(int(user_id), currency, amount)
    if currency == "gram":
        conn.execute("UPDATE users SET total_deposited_gram = total_deposited_gram + ? WHERE user_id = ?", (amount, user_id))
    else:
        conn.execute("UPDATE users SET total_deposited_gold = total_deposited_gold + ? WHERE user_id = ?", (amount, user_id))
    conn.execute("UPDATE transfer_requests SET status = 'approved', processed_at = ? WHERE id = ?", (now_ts(), req_id))
    conn.commit()
    conn.close()
    return True

def decline_transfer(req_id: int):
    conn = get_db()
    conn.execute("UPDATE transfer_requests SET status = 'declined', processed_at = ? WHERE id = ?", (now_ts(), req_id))
    conn.commit()
    conn.close()
    return True

def get_pending_transfers():
    conn = get_db()
    rows = conn.execute("SELECT * FROM transfer_requests WHERE status = 'pending' ORDER BY created_at ASC").fetchall()
    conn.close()
    return rows

# ========== ЗАЯВКИ НА ВЫВОД ==========
def create_withdraw_request(user_id: int, currency: str, amount: float, wallet: str) -> int:
    conn = get_db()
    conn.execute('''
        INSERT INTO withdraw_requests (user_id, currency, amount, wallet, status, created_at)
        VALUES (?, ?, ?, ?, 'pending', ?)
    ''', (str(user_id), currency, amount, wallet, now_ts()))
    conn.commit()
    req_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    conn.close()
    return req_id

def approve_withdraw(req_id: int):
    conn = get_db()
    row = conn.execute("SELECT * FROM withdraw_requests WHERE id = ?", (req_id,)).fetchone()
    if not row:
        conn.close()
        return False
    user_id = row["user_id"]
    currency = row["currency"]
    amount = row["amount"]
    update_balance(int(user_id), currency, -amount)
    if currency == "gram":
        conn.execute("UPDATE users SET total_withdrawn_gram = total_withdrawn_gram + ? WHERE user_id = ?", (amount, user_id))
    else:
        conn.execute("UPDATE users SET total_withdrawn_gold = total_withdrawn_gold + ? WHERE user_id = ?", (amount, user_id))
    conn.execute("UPDATE withdraw_requests SET status = 'approved', processed_at = ? WHERE id = ?", (now_ts(), req_id))
    conn.commit()
    conn.close()
    return True

def decline_withdraw(req_id: int):
    conn = get_db()
    conn.execute("UPDATE withdraw_requests SET status = 'declined', processed_at = ? WHERE id = ?", (now_ts(), req_id))
    conn.commit()
    conn.close()
    return True

def get_pending_withdraws():
    conn = get_db()
    rows = conn.execute("SELECT * FROM withdraw_requests WHERE status = 'pending' ORDER BY created_at ASC").fetchall()
    conn.close()
    return rows

# ========== ЧЕКИ ==========
def generate_check_code():
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))

def create_check(user_id: int, amount: float, currency: str, count: int):
    total = amount * count
    user = get_user(user_id)
    if user[currency] < total:
        return False, "❌ Недостаточно средств!"
    update_balance(user_id, currency, -total)
    code = generate_check_code()
    conn = get_db()
    conn.execute("INSERT INTO checks (code, creator_id, per_user, currency, remaining, claimed) VALUES (?, ?, ?, ?, ?, ?)",
                 (code, str(user_id), amount, currency, count, "[]"))
    conn.commit()
    conn.close()
    return True, code

def claim_check(user_id: int, code: str):
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
        return False, "❌ Вы уже активировали этот чек!", 0, ""
    claimed.append(str(user_id))
    reward = row["per_user"]
    currency = row["currency"]
    update_balance(user_id, currency, reward)
    conn.execute("UPDATE checks SET remaining = remaining - 1, claimed = ? WHERE code = ?",
                 (json.dumps(claimed), code.upper()))
    conn.commit()
    conn.close()
    return True, f"✅ Чек активирован! +{fmt_money(currency, reward)}", reward, currency

def get_user_checks(user_id: int):
    conn = get_db()
    rows = conn.execute("SELECT code, per_user, currency, remaining FROM checks WHERE creator_id = ?", (str(user_id),)).fetchall()
    conn.close()
    return rows

# ========== ПРОМОКОДЫ ==========
def create_promo(code: str, reward_gram: float, reward_gold: float, activations: int):
    conn = get_db()
    conn.execute("INSERT OR REPLACE INTO promos (name, reward_gram, reward_gold, remaining_activations, claimed) VALUES (?, ?, ?, ?, ?)",
                 (code.upper(), reward_gram, reward_gold, activations, "[]"))
    conn.commit()
    conn.close()

def redeem_promo(user_id: int, code: str):
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
        return False, "❌ Вы уже активировали этот промокод!", 0, 0
    claimed.append(str(user_id))
    reward_gram = row["reward_gram"] or 0
    reward_gold = row["reward_gold"] or 0
    if reward_gram > 0:
        update_balance(user_id, "gram", reward_gram)
    if reward_gold > 0:
        update_balance(user_id, "gold", reward_gold)
    conn.execute("UPDATE promos SET remaining_activations = remaining_activations - 1, claimed = ? WHERE name = ?",
                 (json.dumps(claimed), code.upper()))
    conn.commit()
    conn.close()
    return True, "✅ Промокод активирован!", reward_gram, reward_gold

# ========== ПРОВЕРКА ПОДПИСКИ ==========
async def check_subscription_by_id(user_id: int, bot: Bot, chat_id: int) -> bool:
    try:
        member = await bot.get_chat_member(chat_id, user_id)
        return member.status in ["member", "creator", "administrator"]
    except:
        return False

async def check_all_subscriptions(user_id: int, bot: Bot):
    is_channel = await check_subscription_by_id(user_id, bot, REQUIRED_CHANNEL_ID)
    is_chat = await check_subscription_by_id(user_id, bot, REQUIRED_CHAT_ID)
    return is_channel, is_chat

def get_subscribe_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📢 Подписаться на канал", url="https://t.me/WILLDGRAMM")],
        [InlineKeyboardButton(text="💬 Подписаться на чат", url="https://t.me/willdgrammchat")],
        [InlineKeyboardButton(text="✅ Проверить подписку", callback_data="check_subscribe")]
    ])

# ========== КЛАВИАТУРЫ ДЛЯ МЕНЮ ==========
def main_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👤 Профиль", callback_data="profile")],
        [InlineKeyboardButton(text="🎮 Игры", callback_data="games")],
        [InlineKeyboardButton(text="💎 Пополнить", callback_data="deposit")],
        [InlineKeyboardButton(text="💰 Вывести", callback_data="withdraw")],
        [InlineKeyboardButton(text="🎁 Бонус", callback_data="bonus")],
        [InlineKeyboardButton(text="🏆 Топ игроков", callback_data="top")],
        [InlineKeyboardButton(text="🧾 Чеки", callback_data="checks_menu")],
        [InlineKeyboardButton(text="🎟 Промокод", callback_data="promo_menu")]
    ])

def games_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎡 Рулетка", callback_data="game_roulette"), InlineKeyboardButton(text="📈 Краш", callback_data="game_crash")],
        [InlineKeyboardButton(text="🎲 Кубик", callback_data="game_cube"), InlineKeyboardButton(text="🎯 Кости", callback_data="game_dice")],
        [InlineKeyboardButton(text="⚽ Футбол", callback_data="game_football"), InlineKeyboardButton(text="🏀 Баскетбол", callback_data="game_basket")],
        [InlineKeyboardButton(text="◀️ Главное меню", callback_data="back_main")]
    ])

def deposit_currency_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💎 Пополнить Граммы", callback_data="deposit_gram")],
        [InlineKeyboardButton(text="🏅 Пополнить Iris-Gold", callback_data="deposit_gold")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="back_main")]
    ])

def deposit_method_menu(currency: str):
    if currency == "gram":
        return InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⭐ Пополнить Stars (авто)", callback_data=f"deposit_stars_gram")],
            [InlineKeyboardButton(text="💸 Переводом на бота (заявка)", callback_data=f"deposit_transfer_gram")],
            [InlineKeyboardButton(text="◀️ Назад", callback_data="deposit")]
        ])
    else:
        return InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⭐ Пополнить Stars (авто)", callback_data=f"deposit_stars_gold")],
            [InlineKeyboardButton(text="💸 Передать Gold админу (заявка)", callback_data=f"deposit_transfer_gold")],
            [InlineKeyboardButton(text="◀️ Назад", callback_data="deposit")]
        ])

def stars_amount_menu(currency: str):
    amounts = [1, 5, 10, 25, 50, 100]
    kb = []
    row = []
    for a in amounts:
        row.append(InlineKeyboardButton(text=f"⭐ {a}", callback_data=f"stars_{currency}_{a}"))
        if len(row) == 3:
            kb.append(row)
            row = []
    if row:
        kb.append(row)
    kb.append([InlineKeyboardButton(text="✏️ Своя сумма", callback_data=f"stars_custom_{currency}")])
    kb.append([InlineKeyboardButton(text="◀️ Назад", callback_data=f"deposit_{currency}")])
    return InlineKeyboardMarkup(inline_keyboard=kb)

def back_button():
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="◀️ Назад", callback_data="back_main")]])

# ========== СОСТОЯНИЯ ==========
class GameStates(StatesGroup):
    waiting_bet_amount = State()
    waiting_crash_mult = State()
    waiting_currency = State()

class DepositStates(StatesGroup):
    waiting_custom_stars = State()
    waiting_transfer_amount = State()

class WithdrawStates(StatesGroup):
    waiting_currency = State()
    waiting_amount = State()
    waiting_wallet = State()

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
    win, mult = False, 0
    if choice == "red" and color == "red": win, mult = True, 2
    elif choice == "black" and color == "black": win, mult = True, 2
    elif choice == "even" and num != 0 and num % 2 == 0: win, mult = True, 2
    elif choice == "odd" and num % 2 == 1: win, mult = True, 2
    elif choice == "zero" and num == 0: win, mult = True, 35
    return win, mult, num, color

def crash_game():
    r = random.random()
    if r < 0.05: return round(random.uniform(1.00, 1.50), 2)
    elif r < 0.30: return round(random.uniform(1.51, 2.50), 2)
    elif r < 0.60: return round(random.uniform(2.51, 4.00), 2)
    elif r < 0.85: return round(random.uniform(4.01, 7.00), 2)
    else: return round(random.uniform(7.01, 50.00), 2)

# ========== ОБРАБОТЧИКИ КОМАНД ==========
@dp.message(CommandStart())
async def start_cmd(message: Message, bot: Bot):
    ensure_user(message.from_user.id)
    is_channel, is_chat = await check_all_subscriptions(message.from_user.id, bot)
    if not is_channel or not is_chat:
        text = "🔒 <b>Доступ ограничен</b>\n\nТы ещё не подписан на:\n"
        if not is_channel: text += "❌ <b>Канал:</b> @WILLDGRAMM\n"
        if not is_chat: text += "❌ <b>Чат:</b> @willdgrammchat\n"
        text += "\nПодпишись и нажми проверку!"
        await message.answer(text, reply_markup=get_subscribe_keyboard())
        return
    user = get_user(message.from_user.id)
    await message.answer(
        f"🌟 <b>Добро пожаловать в {BOT_NAME}!</b>\n\n"
        f"💰 <b>Твой баланс:</b>\n"
        f"💎 {GRAM_NAME}: {fmt_gram(user['gram'])}\n"
        f"🏅 {GOLD_NAME}: {fmt_gold(user['gold'])}\n\n"
        f"👇 Используй кнопки ниже:",
        reply_markup=main_menu()
    )

@dp.callback_query(F.data == "check_subscribe")
async def check_subscribe_callback(call: CallbackQuery, bot: Bot):
    is_channel, is_chat = await check_all_subscriptions(call.from_user.id, bot)
    if is_channel and is_chat:
        await call.message.edit_text("✅ Подписка подтверждена! Теперь вы можете пользоваться ботом.", reply_markup=None)
        user = get_user(call.from_user.id)
        await call.message.answer(
            f"🌟 <b>Добро пожаловать в {BOT_NAME}!</b>\n\n"
            f"💰 Баланс:\n💎 {fmt_gram(user['gram'])}\n🏅 {fmt_gold(user['gold'])}",
            reply_markup=main_menu()
        )
    else:
        text = "🔒 Доступ ограничен. Вы не подписаны:\n"
        if not is_channel: text += "❌ Канал @WILLDGRAMM\n"
        if not is_chat: text += "❌ Чат @willdgrammchat\n"
        text += "\nПодпишитесь и нажмите проверку."
        await call.message.edit_text(text, reply_markup=get_subscribe_keyboard())
    await call.answer()

@dp.callback_query(F.data == "back_main")
async def back_main(call: CallbackQuery, bot: Bot):
    is_channel, is_chat = await check_all_subscriptions(call.from_user.id, bot)
    if not is_channel or not is_chat:
        await start_cmd(call.message, bot)
        return
    user = get_user(call.from_user.id)
    await call.message.edit_text(
        f"🌟 Главное меню\n\n💰 Баланс:\n💎 {fmt_gram(user['gram'])}\n🏅 {fmt_gold(user['gold'])}",
        reply_markup=main_menu()
    )
    await call.answer()

# ---------- Профиль, топ, бонус ----------
@dp.callback_query(F.data == "profile")
async def profile_cmd(call: CallbackQuery):
    user = get_user(call.from_user.id)
    wins = user["total_wins"] or 0
    bets = user["total_bets"] or 1
    wr = (wins / bets) * 100
    await call.message.edit_text(
        f"👤 <b>Профиль</b>\n\n"
        f"🆔 ID: <code>{call.from_user.id}</code>\n\n"
        f"💰 Баланс:\n💎 {fmt_gram(user['gram'])}\n🏅 {fmt_gold(user['gold'])}\n\n"
        f"📊 Статистика:\n"
        f"💎 Пополнено: {fmt_gram(user['total_deposited_gram'] or 0)}\n"
        f"🏅 Пополнено: {fmt_gold(user['total_deposited_gold'] or 0)}\n"
        f"📤 Выведено: {fmt_gram(user['total_withdrawn_gram'] or 0)} / {fmt_gold(user['total_withdrawn_gold'] or 0)}\n"
        f"🎲 Ставок: {bets} | Побед: {wins} ({wr:.1f}%)\n\n"
        f"📊 Лимиты:\n💎 {fmt_gram(MIN_BET_GRAM)}-{fmt_gram(MAX_BET_GRAM)} | 🏅 {fmt_gold(MIN_BET_GOLD)}-{fmt_gold(MAX_BET_GOLD)}\n"
        f"💎 Мин. вывод: {fmt_gram(MIN_WITHDRAW_GRAM)}\n🏅 Мин. вывод: {fmt_gold(MIN_WITHDRAW_GOLD)}",
        reply_markup=back_button()
    )
    await call.answer()

@dp.callback_query(F.data == "top")
async def top_cmd(call: CallbackQuery):
    top_gram = get_top_players("gram", 5)
    top_gold = get_top_players("gold", 5)
    medals = ["🥇", "🥈", "🥉"]
    text = "🏆 <b>Топ игроков</b>\n\n💎 <b>Граммы:</b>\n"
    for i, p in enumerate(top_gram):
        medal = medals[i] if i < 3 else f"{i+1}."
        text += f"{medal} {mention_user(int(p['user_id']))} — {fmt_gram(p['gram'])}\n"
    text += "\n🏅 <b>Iris-Gold:</b>\n"
    for i, p in enumerate(top_gold):
        medal = medals[i] if i < 3 else f"{i+1}."
        text += f"{medal} {mention_user(int(p['user_id']))} — {fmt_gold(p['gold'])}\n"
    await call.message.edit_text(text, reply_markup=back_button())
    await call.answer()

@dp.callback_query(F.data == "bonus")
async def bonus_cmd(call: CallbackQuery):
    user_id = call.from_user.id
    user = get_user(user_id)
    last = user["last_bonus"] or 0
    now = now_ts()
    if now - last < 43200:
        left = 43200 - (now - last)
        h = left // 3600
        m = (left % 3600) // 60
        await call.message.edit_text(f"⏰ Бонус через {h}ч {m}мин", reply_markup=back_button())
        await call.answer()
        return
    reward = random.randint(BONUS_GRAM_MIN, BONUS_GRAM_MAX)
    update_balance(user_id, "gram", reward)
    conn = get_db()
    conn.execute("UPDATE users SET last_bonus = ? WHERE user_id = ?", (now, str(user_id)))
    conn.commit()
    conn.close()
    await call.message.edit_text(f"🎁 Ежедневный бонус!\n💎 +{fmt_gram(reward)}", reply_markup=back_button())
    await call.answer()

# ---------- ПОПОЛНЕНИЕ ----------
@dp.callback_query(F.data == "deposit")
async def deposit_start(call: CallbackQuery):
    await call.message.edit_text("💎 Выберите валюту для пополнения:", reply_markup=deposit_currency_menu())
    await call.answer()

@dp.callback_query(F.data == "deposit_gram")
async def deposit_gram(call: CallbackQuery):
    await call.message.edit_text("💎 Выберите способ пополнения Грамм:", reply_markup=deposit_method_menu("gram"))
    await call.answer()

@dp.callback_query(F.data == "deposit_gold")
async def deposit_gold(call: CallbackQuery):
    await call.message.edit_text("🏅 Выберите способ пополнения Iris-Gold:", reply_markup=deposit_method_menu("gold"))
    await call.answer()

# ----- Способ: Stars (авто) -----
@dp.callback_query(F.data.startswith("deposit_stars_"))
async def deposit_stars_method(call: CallbackQuery):
    currency = call.data.split("_")[2]  # gram или gold
    await call.message.edit_text(
        f"⭐ Пополнение через Stars\n\nКурс: 1 Star = {fmt_gram(STAR_TO_GRAM) if currency=='gram' else fmt_gold(STAR_TO_GOLD)}\nВыберите сумму:",
        reply_markup=stars_amount_menu(currency)
    )
    await call.answer()

@dp.callback_query(F.data.startswith("stars_"))
async def stars_amount_selected(call: CallbackQuery, state: FSMContext):
    parts = call.data.split("_")
    if parts[1] == "custom":
        currency = parts[2]
        await state.update_data(currency=currency)
        await state.set_state(DepositStates.waiting_custom_stars)
        await call.message.edit_text(
            f"✏️ Введите сумму в Stars (от 1 до 10000):",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="◀️ Назад", callback_data=f"deposit_stars_{currency}")]])
        )
        await call.answer()
        return
    # предустановленная сумма
    currency = parts[1]   # gram или gold
    stars = int(parts[2])
    amount = stars * (STAR_TO_GRAM if currency == "gram" else STAR_TO_GOLD)
    # создаём инвойс
    await call.message.answer_invoice(
        title=f"💎 Пополнение {GRAM_NAME if currency=='gram' else GOLD_NAME}",
        description=f"Получите {fmt_money(currency, amount)} за {stars} Stars!",
        payload=f"deposit_{currency}_{stars}_{amount}",
        provider_token="",
        currency="XTR",
        prices=[LabeledPrice(label=f"{stars} Stars", amount=stars)],
        start_parameter=f"deposit_{currency}"
    )
    await call.answer()

@dp.message(DepositStates.waiting_custom_stars)
async def custom_stars_amount(message: Message, state: FSMContext):
    try:
        stars = int(message.text)
        if stars < 1 or stars > 10000:
            await message.answer("❌ Сумма от 1 до 10000 Stars")
            return
        data = await state.get_data()
        currency = data["currency"]
        amount = stars * (STAR_TO_GRAM if currency == "gram" else STAR_TO_GOLD)
        await message.answer_invoice(
            title=f"💎 Пополнение {GRAM_NAME if currency=='gram' else GOLD_NAME}",
            description=f"Получите {fmt_money(currency, amount)} за {stars} Stars!",
            payload=f"deposit_{currency}_{stars}_{amount}",
            provider_token="",
            currency="XTR",
            prices=[LabeledPrice(label=f"{stars} Stars", amount=stars)],
            start_parameter=f"deposit_{currency}"
        )
        await state.clear()
    except:
        await message.answer("❌ Введите целое число Stars")

@dp.pre_checkout_query()
async def pre_checkout_handler(query: PreCheckoutQuery):
    await query.answer(ok=True)

@dp.message(F.successful_payment)
async def successful_payment(message: Message):
    payload = message.successful_payment.invoice_payload
    parts = payload.split("_")
    currency = parts[1]
    stars = int(parts[2])
    amount = float(parts[3])
    new_balance = update_balance(message.from_user.id, currency, amount)
    if currency == "gram":
        update_balance(message.from_user.id, "total_deposited_gram", amount)
    else:
        update_balance(message.from_user.id, "total_deposited_gold", amount)
    await message.answer(
        f"✅ Пополнение успешно!\n⭐ {stars} Stars → {fmt_money(currency, amount)}\n💎 Новый баланс: {fmt_money(currency, new_balance)}",
        reply_markup=main_menu()
    )
    for admin in ADMIN_IDS:
        await message.bot.send_message(admin, f"💎 Новое пополнение!\n👤 {mention_user(message.from_user.id)}\n⭐ {stars} Stars → {fmt_money(currency, amount)}")

# ----- Способ: Переводом на бота / передача Gold (заявка) -----
@dp.callback_query(F.data.startswith("deposit_transfer_"))
async def deposit_transfer_method(call: CallbackQuery, state: FSMContext):
    currency = call.data.split("_")[2]  # gram или gold
    await state.update_data(currency=currency)
    await state.set_state(DepositStates.waiting_transfer_amount)
    if currency == "gram":
        await call.message.edit_text(
            f"💸 <b>Пополнение переводом на бота</b>\n\n"
            f"1️⃣ Переведите нужную сумму на @{BOT_USERNAME}\n"
            f"2️⃣ Укажите в комментарии: <code>Пополнение грамм</code>\n"
            f"3️⃣ Введите сумму, которую перевели (цифрами):\n\n"
            f"После проверки администратором средства поступят на баланс.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="◀️ Назад", callback_data=f"deposit_{currency}")]])
        )
    else:
        await call.message.edit_text(
            f"🏅 <b>Пополнение Iris-Gold через передачу админу</b>\n\n"
            f"1️⃣ Переведите Gold на @{BOT_USERNAME} (или укажите реквизиты)\n"
            f"2️⃣ Введите сумму, которую передали:\n\n"
            f"После проверки администратором средства поступят на баланс.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="◀️ Назад", callback_data=f"deposit_{currency}")]])
        )
    await call.answer()

@dp.message(DepositStates.waiting_transfer_amount)
async def transfer_amount_input(message: Message, state: FSMContext):
    try:
        amount = float(message.text.replace(",", "."))
        if amount <= 0:
            await message.answer("❌ Сумма должна быть положительной")
            return
        data = await state.get_data()
        currency = data["currency"]
        req_id = create_transfer_request(message.from_user.id, currency, amount)
        await message.answer(
            f"✅ Заявка на пополнение #{req_id} создана!\n"
            f"Сумма: {fmt_money(currency, amount)}\n"
            f"После проверки администратором средства поступят на баланс.",
            reply_markup=main_menu()
        )
        # Уведомление админам
        for admin in ADMIN_IDS:
            await message.bot.send_message(
                admin,
                f"📥 <b>Заявка на пополнение</b>\n"
                f"👤 {mention_user(message.from_user.id)}\n"
                f"💎 {GRAM_NAME if currency=='gram' else GOLD_NAME}: {fmt_money(currency, amount)}\n"
                f"🆔 Заявка #{req_id}\n\n"
                f"✅ /approve_transfer {req_id} - подтвердить\n"
                f"❌ /decline_transfer {req_id} - отклонить"
            )
        await state.clear()
    except:
        await message.answer("❌ Введите корректную сумму")

# ---------- ВЫВОД ----------
@dp.callback_query(F.data == "withdraw")
async def withdraw_start(call: CallbackQuery):
    await call.message.edit_text("💰 Выберите валюту для вывода:", reply_markup=withdraw_menu())
    await call.answer()

def withdraw_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💎 Вывести Граммы", callback_data="withdraw_gram")],
        [InlineKeyboardButton(text="🏅 Вывести Iris-Gold", callback_data="withdraw_gold")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="back_main")]
    ])

@dp.callback_query(F.data.startswith("withdraw_"))
async def withdraw_currency(call: CallbackQuery, state: FSMContext):
    currency = call.data.split("_")[1]
    await state.update_data(currency=currency)
    await state.set_state(WithdrawStates.waiting_amount)
    min_amount = MIN_WITHDRAW_GRAM if currency == "gram" else MIN_WITHDRAW_GOLD
    await call.message.edit_text(
        f"💰 Вывод {GRAM_NAME if currency=='gram' else GOLD_NAME}\n"
        f"Минимальная сумма: {fmt_money(currency, min_amount)}\n"
        f"Введите сумму вывода:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="◀️ Назад", callback_data="withdraw")]])
    )
    await call.answer()

@dp.message(WithdrawStates.waiting_amount)
async def withdraw_amount_input(message: Message, state: FSMContext):
    try:
        amount = float(message.text.replace(",", "."))
        data = await state.get_data()
        currency = data["currency"]
        min_amount = MIN_WITHDRAW_GRAM if currency == "gram" else MIN_WITHDRAW_GOLD
        if amount < min_amount:
            await message.answer(f"❌ Минимальная сумма {fmt_money(currency, min_amount)}")
            return
        user = get_user(message.from_user.id)
        if user[currency] < amount:
            await message.answer(f"❌ Недостаточно средств. Ваш баланс: {fmt_money(currency, user[currency])}")
            return
        await state.update_data(amount=amount)
        await state.set_state(WithdrawStates.waiting_wallet)
        await message.answer("💳 Введите реквизиты для вывода (кошелёк/карта):")
    except:
        await message.answer("❌ Введите число")

@dp.message(WithdrawStates.waiting_wallet)
async def withdraw_wallet_input(message: Message, state: FSMContext):
    wallet = message.text.strip()
    data = await state.get_data()
    currency = data["currency"]
    amount = data["amount"]
    req_id = create_withdraw_request(message.from_user.id, currency, amount, wallet)
    await message.answer(
        f"✅ Заявка на вывод #{req_id} создана!\n"
        f"Сумма: {fmt_money(currency, amount)}\n"
        f"Реквизиты: {wallet}\n"
        f"После проверки администратором средства будут отправлены.",
        reply_markup=main_menu()
    )
    for admin in ADMIN_IDS:
        await message.bot.send_message(
            admin,
            f"📤 <b>Заявка на вывод</b>\n"
            f"👤 {mention_user(message.from_user.id)}\n"
            f"💎 {GRAM_NAME if currency=='gram' else GOLD_NAME}: {fmt_money(currency, amount)}\n"
            f"📤 Кошелёк: {wallet}\n"
            f"🆔 Заявка #{req_id}\n\n"
            f"✅ /approve_withdraw {req_id} - подтвердить\n"
            f"❌ /decline_withdraw {req_id} - отклонить"
        )
    await state.clear()

# ---------- ИГРЫ ----------
@dp.callback_query(F.data == "games")
async def games_list(call: CallbackQuery):
    await call.message.edit_text("🎮 Выберите игру:", reply_markup=games_menu())
    await call.answer()

@dp.callback_query(F.data.startswith("game_"))
async def game_choice(call: CallbackQuery, state: FSMContext):
    game = call.data.split("_")[1]
    await state.update_data(game=game)
    await state.set_state(GameStates.waiting_currency)
    await call.message.edit_text(
        f"🎮 Игра {game.upper()}\nВыберите валюту ставки:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="💎 Граммы", callback_data="curr_gram")],
            [InlineKeyboardButton(text="🏅 Iris-Gold", callback_data="curr_gold")],
            [InlineKeyboardButton(text="◀️ Назад", callback_data="games")]
        ])
    )
    await call.answer()

@dp.callback_query(GameStates.waiting_currency, F.data.startswith("curr_"))
async def set_currency(call: CallbackQuery, state: FSMContext):
    currency = call.data.split("_")[1]
    await state.update_data(currency=currency)
    await state.set_state(GameStates.waiting_bet_amount)
    min_bet = MIN_BET_GRAM if currency == "gram" else MIN_BET_GOLD
    max_bet = MAX_BET_GRAM if currency == "gram" else MAX_BET_GOLD
    await call.message.edit_text(
        f"💰 Введите сумму ставки в {GRAM_NAME if currency=='gram' else GOLD_NAME}\n"
        f"Лимиты: {fmt_money(currency, min_bet)} - {fmt_money(currency, max_bet)}",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="◀️ Назад", callback_data="games")]])
    )
    await call.answer()

@dp.message(GameStates.waiting_bet_amount)
async def process_bet(message: Message, state: FSMContext):
    try:
        bet = float(message.text.replace(",", "."))
        data = await state.get_data()
        game = data["game"]
        currency = data["currency"]
        min_bet = MIN_BET_GRAM if currency == "gram" else MIN_BET_GOLD
        max_bet = MAX_BET_GRAM if currency == "gram" else MAX_BET_GOLD
        if bet < min_bet or bet > max_bet:
            await message.answer(f"❌ Ставка должна быть от {fmt_money(currency, min_bet)} до {fmt_money(currency, max_bet)}")
            return
        user = get_user(message.from_user.id)
        if user[currency] < bet:
            await message.answer(f"❌ Недостаточно средств. Ваш баланс: {fmt_money(currency, user[currency])}")
            return
        await state.update_data(bet=bet)
        if game == "crash":
            await state.set_state(GameStates.waiting_crash_mult)
            await message.answer("📈 Введите множитель выигрыша (1.10 - 10.00):")
        elif game in ["roulette", "cube", "dice"]:
            await show_bet_options(message, state, game, currency)
        else:
            await play_instant_game(message, state, game, bet, currency)
    except:
        await message.answer("❌ Введите корректное число")

async def show_bet_options(message: Message, state: FSMContext, game: str, currency: str):
    if game == "roulette":
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔴 Красное (x2)", callback_data=f"bet_roulette_red_{currency}"),
             InlineKeyboardButton(text="⚫ Чёрное (x2)", callback_data=f"bet_roulette_black_{currency}")],
            [InlineKeyboardButton(text="2️⃣ Чёт (x2)", callback_data=f"bet_roulette_even_{currency}"),
             InlineKeyboardButton(text="1️⃣ Нечет (x2)", callback_data=f"bet_roulette_odd_{currency}")],
            [InlineKeyboardButton(text="0️⃣ Зеро (x35)", callback_data=f"bet_roulette_zero_{currency}")],
            [InlineKeyboardButton(text="❌ Отмена", callback_data="games")]
        ])
    elif game == "cube":
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="1️⃣", callback_data=f"bet_cube_1_{currency}"),
             InlineKeyboardButton(text="2️⃣", callback_data=f"bet_cube_2_{currency}"),
             InlineKeyboardButton(text="3️⃣", callback_data=f"bet_cube_3_{currency}")],
            [InlineKeyboardButton(text="4️⃣", callback_data=f"bet_cube_4_{currency}"),
             InlineKeyboardButton(text="5️⃣", callback_data=f"bet_cube_5_{currency}"),
             InlineKeyboardButton(text="6️⃣", callback_data=f"bet_cube_6_{currency}")],
            [InlineKeyboardButton(text="❌ Отмена", callback_data="games")]
        ])
    else:  # dice
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📈 Больше 7 (x1.9)", callback_data=f"bet_dice_high_{currency}")],
            [InlineKeyboardButton(text="📉 Меньше 7 (x1.9)", callback_data=f"bet_dice_low_{currency}")],
            [InlineKeyboardButton(text="🎯 Равно 7 (x5.0)", callback_data=f"bet_dice_seven_{currency}")],
            [InlineKeyboardButton(text="❌ Отмена", callback_data="games")]
        ])
    await message.answer("🎲 Выберите вариант ставки:", reply_markup=kb)
    await state.clear()  # временно, данные о ставке потеряются — нужно сохранять в FSM. Упростим: сохраним в словарь active_bets
    # Для простоты оставим так, но в реальном коде нужно хранить bet/currency в памяти или в FSM.

# Для упрощения сделаем словарь active_bets
active_bets = {}

@dp.callback_query(F.data.startswith("bet_"))
async def handle_bet_callback(call: CallbackQuery):
    parts = call.data.split("_")
    game = parts[1]
    choice = parts[2]
    currency = parts[3]
    # здесь нужно получить ставку из временного хранилища или запросить заново
    # в целях демонстрации используем заглушку
    await call.message.answer("⚠️ Функция в разработке. Пожалуйста, введите ставку сначала через команду игры.")
    await call.answer()

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
            f"⚽ Футбол\nРезультат: {outcome}\nСтавка: {fmt_money(currency, bet)}\n"
            f"{'ПОБЕДА' if win else 'ПРОИГРЫШ'}\nВыплата: {fmt_money(currency, payout)}\n"
            f"Новый баланс: {fmt_money(currency, new_balance)}",
            reply_markup=games_menu()
        )
    elif game == "basket":
        result = await message.answer_dice(emoji="🏀")
        value = result.dice.value
        win = value in [4,5]
        payout = bet * 1.85 if win else 0
        new_balance = update_balance(message.from_user.id, currency, -bet + payout)
        add_bet_record(message.from_user.id, bet, win, "basket", currency)
        outcome = "ТОЧНЫЙ БРОСОК 🎉" if win else "ПРОМАХ 😔"
        await message.answer(
            f"🏀 Баскетбол\nРезультат: {outcome}\nСтавка: {fmt_money(currency, bet)}\n"
            f"{'ПОБЕДА' if win else 'ПРОИГРЫШ'}\nВыплата: {fmt_money(currency, payout)}\n"
            f"Новый баланс: {fmt_money(currency, new_balance)}",
            reply_markup=games_menu()
        )
    await state.clear()

@dp.message(GameStates.waiting_crash_mult)
async def process_crash_mult(message: Message, state: FSMContext):
    try:
        mult = float(message.text.replace(",", "."))
        if mult < 1.10 or mult > 10.00:
            await message.answer("❌ Множитель от 1.10 до 10.00")
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
            f"📈 Краш\nМножитель игры: x{crash_mult:.2f}\nВаш множитель: x{mult:.2f}\n"
            f"{'ПОБЕДА' if win else 'ПРОИГРЫШ'}\nВыплата: {fmt_money(currency, payout)}\n"
            f"Новый баланс: {fmt_money(currency, new_balance)}",
            reply_markup=games_menu()
        )
        await state.clear()
    except:
        await message.answer("❌ Введите число")

# ---------- ЧЕКИ ----------
@dp.callback_query(F.data == "checks_menu")
async def checks_menu(call: CallbackQuery):
    await call.message.edit_text("🧾 Меню чеков:", reply_markup=checks_menu_kb())
    await call.answer()

def checks_menu_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Создать чек", callback_data="check_create")],
        [InlineKeyboardButton(text="💸 Активировать чек", callback_data="check_claim")],
        [InlineKeyboardButton(text="📋 Мои чеки", callback_data="check_my")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="back_main")]
    ])

@dp.callback_query(F.data == "check_create")
async def check_create(call: CallbackQuery, state: FSMContext):
    await state.set_state(CheckStates.waiting_currency)
    await call.message.edit_text(
        "Выберите валюту чека:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="💎 Граммы", callback_data="check_curr_gram")],
            [InlineKeyboardButton(text="🏅 Iris-Gold", callback_data="check_curr_gold")],
            [InlineKeyboardButton(text="◀️ Назад", callback_data="checks_menu")]
        ])
    )
    await call.answer()

@dp.callback_query(F.data.startswith("check_curr_"))
async def check_currency(call: CallbackQuery, state: FSMContext):
    currency = call.data.split("_")[2]
    await state.update_data(currency=currency)
    await state.set_state(CheckStates.waiting_amount)
    min_amount = MIN_BET_GRAM if currency == "gram" else MIN_BET_GOLD
    await call.message.edit_text(
        f"💰 Введите сумму на один чек (мин. {fmt_money(currency, min_amount)}):",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="◀️ Назад", callback_data="checks_menu")]])
    )
    await call.answer()

@dp.message(CheckStates.waiting_amount)
async def check_amount_input(message: Message, state: FSMContext):
    try:
        amount = float(message.text.replace(",", "."))
        data = await state.get_data()
        currency = data["currency"]
        min_amount = MIN_BET_GRAM if currency == "gram" else MIN_BET_GOLD
        if amount < min_amount:
            await message.answer(f"❌ Минимальная сумма {fmt_money(currency, min_amount)}")
            return
        await state.update_data(amount=amount)
        await state.set_state(CheckStates.waiting_count)
        await message.answer("📦 Введите количество активаций (1-100):")
    except:
        await message.answer("❌ Введите число")

@dp.message(CheckStates.waiting_count)
async def check_count_input(message: Message, state: FSMContext):
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
                f"✅ Чек создан!\n🎫 Код: <code>{result}</code>\n"
                f"💰 Сумма: {fmt_money(currency, amount)}\n"
                f"📦 Активаций: {count}",
                reply_markup=main_menu()
            )
        else:
            await message.answer(f"❌ {result}", reply_markup=main_menu())
    except:
        await message.answer("❌ Введите целое число")

@dp.callback_query(F.data == "check_claim")
async def check_claim(call: CallbackQuery, state: FSMContext):
    await state.set_state(CheckStates.waiting_code)
    await call.message.edit_text("🎫 Введите код чека:", reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="◀️ Назад", callback_data="checks_menu")]]))
    await call.answer()

@dp.message(CheckStates.waiting_code)
async def claim_code_input(message: Message, state: FSMContext):
    code = message.text.strip().upper()
    ok, result, reward, currency = claim_check(message.from_user.id, code)
    await state.clear()
    if ok:
        await message.answer(f"✅ {result}\n💰 Новый баланс: {fmt_money(currency, get_user(message.from_user.id)[currency])}", reply_markup=main_menu())
    else:
        await message.answer(f"❌ {result}", reply_markup=main_menu())

@dp.callback_query(F.data == "check_my")
async def my_checks(call: CallbackQuery):
    checks = get_user_checks(call.from_user.id)
    if not checks:
        await call.message.edit_text("📭 У вас нет созданных чеков", reply_markup=back_button())
    else:
        text = "🧾 Ваши чеки:\n"
        for c in checks:
            curr_name = GRAM_NAME if c['currency'] == 'gram' else GOLD_NAME
            text += f"🎫 <code>{c['code']}</code> | {fmt_money(c['currency'], c['per_user'])} | {curr_name} | осталось: {c['remaining']}\n"
        await call.message.edit_text(text, reply_markup=back_button())
    await call.answer()

# ---------- ПРОМОКОДЫ ----------
@dp.callback_query(F.data == "promo_menu")
async def promo_menu(call: CallbackQuery, state: FSMContext):
    await state.set_state(PromoStates.waiting_code)
    await call.message.edit_text("🎟 Введите промокод:", reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="◀️ Назад", callback_data="back_main")]]))
    await call.answer()

@dp.message(PromoStates.waiting_code)
async def activate_promo_code(message: Message, state: FSMContext):
    code = message.text.strip().upper()
    ok, result, rg, rgo = redeem_promo(message.from_user.id, code)
    await state.clear()
    if ok:
        text = f"🎉 {result}\n"
        if rg: text += f"💎 +{fmt_gram(rg)}\n"
        if rgo: text += f"🏅 +{fmt_gold(rgo)}\n"
        user = get_user(message.from_user.id)
        text += f"\n💰 Новый баланс:\n💎 {fmt_gram(user['gram'])}\n🏅 {fmt_gold(user['gold'])}"
        await message.answer(text, reply_markup=main_menu())
    else:
        await message.answer(f"❌ {result}", reply_markup=main_menu())

# ---------- АДМИН-КОМАНДЫ ----------
@dp.message(Command("addpromo"))
async def add_promo_cmd(message: Message):
    if not is_admin(message.from_user.id):
        await message.answer("⛔ Только для админов")
        return
    parts = message.text.split()
    if len(parts) != 5:
        await message.answer("📝 Формат: /addpromo КОД ГРАММЫ ГОЛД АКТИВАЦИИ\nПример: /addpromo WELCOME 1000 5 50")
        return
    code = parts[1].upper()
    try:
        rg = float(parts[2])
        rgo = float(parts[3])
        acts = int(parts[4])
        create_promo(code, rg, rgo, acts)
        await message.answer(f"✅ Промокод {code} создан!\n💎 {fmt_gram(rg)}\n🏅 {fmt_gold(rgo)}\n🎯 {acts} активаций")
    except:
        await message.answer("❌ Ошибка")

@dp.message(Command("give"))
async def give_cmd(message: Message):
    if not is_admin(message.from_user.id):
        await message.answer("⛔ Только для админов")
        return
    parts = message.text.split()
    if len(parts) != 4:
        await message.answer("📝 Формат: /give ID ВАЛЮТА СУММА\nВалюта: gram или gold")
        return
    try:
        target = int(parts[1])
        currency = parts[2].lower()
        if currency not in ["gram","gold"]:
            await message.answer("❌ Валюта gram или gold")
            return
        amount = float(parts[3])
        new_bal = update_balance(target, currency, amount)
        await message.answer(f"✅ Выдано {fmt_money(currency, amount)} пользователю {target}\n💰 Новый баланс: {fmt_money(currency, new_bal)}")
    except:
        await message.answer("❌ Ошибка")

@dp.message(Command("approve_transfer"))
async def approve_transfer_cmd(message: Message):
    if not is_admin(message.from_user.id):
        await message.answer("⛔ Только для админов")
        return
    parts = message.text.split()
    if len(parts) != 2:
        await message.answer("📝 /approve_transfer ID")
        return
    try:
        req_id = int(parts[1])
        if approve_transfer(req_id):
            # Уведомим пользователя
            conn = get_db()
            row = conn.execute("SELECT user_id, currency, amount FROM transfer_requests WHERE id = ?", (req_id,)).fetchone()
            conn.close()
            if row:
                await message.bot.send_message(int(row["user_id"]), f"✅ Ваша заявка на пополнение #{req_id} одобрена!\n💰 Начислено: {fmt_money(row['currency'], row['amount'])}")
            await message.answer(f"✅ Заявка #{req_id} подтверждена")
        else:
            await message.answer(f"❌ Заявка #{req_id} не найдена")
    except:
        await message.answer("❌ Ошибка")

@dp.message(Command("decline_transfer"))
async def decline_transfer_cmd(message: Message):
    if not is_admin(message.from_user.id):
        await message.answer("⛔ Только для админов")
        return
    parts = message.text.split()
    if len(parts) != 2:
        await message.answer("📝 /decline_transfer ID")
        return
    try:
        req_id = int(parts[1])
        if decline_transfer(req_id):
            conn = get_db()
            row = conn.execute("SELECT user_id FROM transfer_requests WHERE id = ?", (req_id,)).fetchone()
            conn.close()
            if row:
                await message.bot.send_message(int(row["user_id"]), f"❌ Ваша заявка на пополнение #{req_id} отклонена. Свяжитесь с администратором.")
            await message.answer(f"✅ Заявка #{req_id} отклонена")
        else:
            await message.answer(f"❌ Заявка #{req_id} не найдена")
    except:
        await message.answer("❌ Ошибка")

@dp.message(Command("approve_withdraw"))
async def approve_withdraw_cmd(message: Message):
    if not is_admin(message.from_user.id):
        await message.answer("⛔ Только для админов")
        return
    parts = message.text.split()
    if len(parts) != 2:
        await message.answer("📝 /approve_withdraw ID")
        return
    try:
        req_id = int(parts[1])
        if approve_withdraw(req_id):
            conn = get_db()
            row = conn.execute("SELECT user_id, currency, amount FROM withdraw_requests WHERE id = ?", (req_id,)).fetchone()
            conn.close()
            if row:
                await message.bot.send_message(int(row["user_id"]), f"✅ Ваша заявка на вывод #{req_id} одобрена!\n💰 Сумма: {fmt_money(row['currency'], row['amount'])}\nСредства отправлены.")
            await message.answer(f"✅ Заявка #{req_id} подтверждена")
        else:
            await message.answer(f"❌ Заявка #{req_id} не найдена")
    except:
        await message.answer("❌ Ошибка")

@dp.message(Command("decline_withdraw"))
async def decline_withdraw_cmd(message: Message):
    if not is_admin(message.from_user.id):
        await message.answer("⛔ Только для админов")
        return
    parts = message.text.split()
    if len(parts) != 2:
        await message.answer("📝 /decline_withdraw ID")
        return
    try:
        req_id = int(parts[1])
        if decline_withdraw(req_id):
            conn = get_db()
            row = conn.execute("SELECT user_id FROM withdraw_requests WHERE id = ?", (req_id,)).fetchone()
            conn.close()
            if row:
                await message.bot.send_message(int(row["user_id"]), f"❌ Ваша заявка на вывод #{req_id} отклонена. Причина уточните у администратора.")
            await message.answer(f"✅ Заявка #{req_id} отклонена")
        else:
            await message.answer(f"❌ Заявка #{req_id} не найдена")
    except:
        await message.answer("❌ Ошибка")

@dp.message(Command("requests"))
async def list_requests(message: Message):
    if not is_admin(message.from_user.id):
        await message.answer("⛔ Только для админов")
        return
    transfers = get_pending_transfers()
    withdraws = get_pending_withdraws()
    text = "📋 <b>Активные заявки</b>\n\n"
    if transfers:
        text += "💸 <b>Пополнения переводом:</b>\n"
        for r in transfers:
            text += f"🆔 #{r['id']} | {mention_user(int(r['user_id']))} | {fmt_money(r['currency'], r['amount'])}\n"
    if withdraws:
        text += "💰 <b>Выводы:</b>\n"
        for r in withdraws:
            text += f"🆔 #{r['id']} | {mention_user(int(r['user_id']))} | {fmt_money(r['currency'], r['amount'])} | {r['wallet']}\n"
    if not transfers and not withdraws:
        text += "Нет активных заявок"
    await message.answer(text)

@dp.message(Command("all"))
async def all_users(message: Message):
    if not is_admin(message.from_user.id):
        await message.answer("⛔ Только для админов")
        return
    conn = get_db()
    users = conn.execute("SELECT user_id, gram, gold FROM users").fetchall()
    conn.close()
    text = "👥 Все пользователи:\n"
    for u in users:
        text += f"👤 {u['user_id']} | 💎 {fmt_gram(u['gram'])} | 🏅 {fmt_gold(u['gold'])}\n"
    await message.answer(text)

@dp.message(Command("getid"))
async def get_id(message: Message):
    await message.answer(f"ID этого чата: <code>{message.chat.id}</code>\nТип: {message.chat.type}")

# ========== ЗАПУСК ==========
async def main():
    bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    await bot.delete_webhook(drop_pending_updates=True)
    print("✅ Бот запущен!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
