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
BOT_USERNAME = "WILLDGRAMM_bot"
MAIN_ADMIN_ID = 8293927811
ADMIN_IDS = [8293927811, 8478884644]

# Обязательные подписки (замените на реальные ID)
REQUIRED_CHANNEL_ID = -1002263528382
REQUIRED_CHAT_ID = -1002263528383

# Валюты
GRAM_NAME = "💎 Грам"
GOLD_NAME = "🏅 Iris-Gold"

# Стартовые балансы
START_GRAM = 500.0
START_GOLD = 0.0

# Курс Stars
STAR_TO_GRAM = 2222.0
STAR_TO_GOLD = 0.7

# Лимиты
MIN_BET_GRAM = 0.10
MAX_BET_GRAM = 100000.0
MIN_BET_GOLD = 0.01
MAX_BET_GOLD = 5000.0
MIN_WITHDRAW_GRAM = 75000.0
MIN_WITHDRAW_GOLD = 10.0

# Бонус
BONUS_GRAM_MIN = 0
BONUS_GRAM_MAX = 250

# ========== МНОЖИТЕЛИ ИГР ==========
FOOTBALL_MULTIPLIERS = {"gol": 1.4, "mimo": 1.6}
BASKET_MULTIPLIERS = {"tochniy": 1.4, "promah": 1.6}
CUBE_MULTIPLIERS = {"normal": 1.8, "three": 2.0}
ROULETTE_MULTIPLIERS = {"color": 1.8, "even_odd": 1.8, "zero": 25.0}
DICE_MULTIPLIER = 3.5

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
        except:
            os.remove(DB_PATH)
    
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    
    cur.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id TEXT PRIMARY KEY,
            gram REAL DEFAULT 500,
            gold REAL DEFAULT 0,
            username TEXT,
            first_name TEXT,
            last_name TEXT,
            total_bets INTEGER DEFAULT 0,
            total_wins INTEGER DEFAULT 0,
            last_bonus INTEGER DEFAULT 0,
            total_deposited_gram REAL DEFAULT 0,
            total_deposited_gold REAL DEFAULT 0,
            total_withdrawn_gram REAL DEFAULT 0,
            total_withdrawn_gold REAL DEFAULT 0,
            is_banned INTEGER DEFAULT 0,
            is_admin INTEGER DEFAULT 0,
            registered_at INTEGER DEFAULT 0,
            last_seen INTEGER DEFAULT 0
        )
    ''')
    
    cur.execute("PRAGMA table_info(users)")
    columns = [col[1] for col in cur.fetchall()]
    if "gram" not in columns: cur.execute("ALTER TABLE users ADD COLUMN gram REAL DEFAULT 500")
    if "gold" not in columns: cur.execute("ALTER TABLE users ADD COLUMN gold REAL DEFAULT 0")
    if "username" not in columns: cur.execute("ALTER TABLE users ADD COLUMN username TEXT")
    if "first_name" not in columns: cur.execute("ALTER TABLE users ADD COLUMN first_name TEXT")
    if "last_name" not in columns: cur.execute("ALTER TABLE users ADD COLUMN last_name TEXT")
    if "total_bets" not in columns: cur.execute("ALTER TABLE users ADD COLUMN total_bets INTEGER DEFAULT 0")
    if "total_wins" not in columns: cur.execute("ALTER TABLE users ADD COLUMN total_wins INTEGER DEFAULT 0")
    if "last_bonus" not in columns: cur.execute("ALTER TABLE users ADD COLUMN last_bonus INTEGER DEFAULT 0")
    if "total_deposited_gram" not in columns: cur.execute("ALTER TABLE users ADD COLUMN total_deposited_gram REAL DEFAULT 0")
    if "total_deposited_gold" not in columns: cur.execute("ALTER TABLE users ADD COLUMN total_deposited_gold REAL DEFAULT 0")
    if "total_withdrawn_gram" not in columns: cur.execute("ALTER TABLE users ADD COLUMN total_withdrawn_gram REAL DEFAULT 0")
    if "total_withdrawn_gold" not in columns: cur.execute("ALTER TABLE users ADD COLUMN total_withdrawn_gold REAL DEFAULT 0")
    if "is_banned" not in columns: cur.execute("ALTER TABLE users ADD COLUMN is_banned INTEGER DEFAULT 0")
    if "is_admin" not in columns: cur.execute("ALTER TABLE users ADD COLUMN is_admin INTEGER DEFAULT 0")
    if "registered_at" not in columns: cur.execute("ALTER TABLE users ADD COLUMN registered_at INTEGER DEFAULT 0")
    if "last_seen" not in columns: cur.execute("ALTER TABLE users ADD COLUMN last_seen INTEGER DEFAULT 0")
    
    # Делаем админов админами в БД
    for admin_id in ADMIN_IDS:
        cur.execute("UPDATE users SET is_admin = 1 WHERE user_id = ?", (str(admin_id),))
    
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
    
    cur.execute('''
        CREATE TABLE IF NOT EXISTS promos (
            name TEXT PRIMARY KEY,
            reward_gram REAL,
            reward_gold REAL,
            remaining_activations INTEGER,
            claimed TEXT
        )
    ''')
    
    cur.execute('''
        CREATE TABLE IF NOT EXISTS admin_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            admin_id TEXT,
            action TEXT,
            target_id TEXT,
            amount REAL,
            timestamp INTEGER
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
    if user_id in ADMIN_IDS:
        return True
    conn = get_db()
    row = conn.execute("SELECT is_admin FROM users WHERE user_id = ?", (str(user_id),)).fetchone()
    conn.close()
    return row and row["is_admin"] == 1

def is_banned(user_id: int) -> bool:
    conn = get_db()
    row = conn.execute("SELECT is_banned FROM users WHERE user_id = ?", (str(user_id),)).fetchone()
    conn.close()
    return row and row["is_banned"] == 1

def ensure_user(user_id: int, username: str = None, first_name: str = None, last_name: str = None):
    conn = get_db()
    conn.execute("""
        INSERT OR IGNORE INTO users (user_id, gram, gold, is_admin, registered_at, username, first_name, last_name) 
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (str(user_id), START_GRAM, START_GOLD, 1 if user_id in ADMIN_IDS else 0, now_ts(), username, first_name, last_name))
    conn.commit()
    conn.close()

def update_user_info(user_id: int, username: str = None, first_name: str = None, last_name: str = None):
    conn = get_db()
    if username:
        conn.execute("UPDATE users SET username = ?, last_seen = ? WHERE user_id = ?", (username, now_ts(), str(user_id)))
    if first_name:
        conn.execute("UPDATE users SET first_name = ?, last_seen = ? WHERE user_id = ?", (first_name, now_ts(), str(user_id)))
    if last_name:
        conn.execute("UPDATE users SET last_name = ?, last_seen = ? WHERE user_id = ?", (last_name, now_ts(), str(user_id)))
    conn.execute("UPDATE users SET last_seen = ? WHERE user_id = ?", (now_ts(), str(user_id)))
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

def set_admin(user_id: int, is_admin_val: bool):
    conn = get_db()
    conn.execute("UPDATE users SET is_admin = ? WHERE user_id = ?", (1 if is_admin_val else 0, str(user_id)))
    conn.commit()
    conn.close()
    if is_admin_val and int(user_id) not in ADMIN_IDS:
        ADMIN_IDS.append(int(user_id))

def set_ban(user_id: int, is_banned_val: bool):
    conn = get_db()
    conn.execute("UPDATE users SET is_banned = ? WHERE user_id = ?", (1 if is_banned_val else 0, str(user_id)))
    conn.commit()
    conn.close()

def add_admin_log(admin_id: int, action: str, target_id: int = None, amount: float = None):
    conn = get_db()
    conn.execute("INSERT INTO admin_logs (admin_id, action, target_id, amount, timestamp) VALUES (?, ?, ?, ?, ?)",
                 (str(admin_id), action, str(target_id) if target_id else None, amount, now_ts()))
    conn.commit()
    conn.close()

def add_bet_record(user_id: int, bet: float, win: bool, game: str, currency: str):
    conn = get_db()
    conn.execute("UPDATE users SET total_bets = total_bets + 1 WHERE user_id = ?", (str(user_id),))
    if win:
        conn.execute("UPDATE users SET total_wins = total_wins + 1 WHERE user_id = ?", (str(user_id),))
    conn.commit()
    conn.close()

def get_top_players(currency: str, limit: int = 10):
    conn = get_db()
    rows = conn.execute(f"SELECT user_id, {currency} FROM users WHERE is_banned = 0 ORDER BY {currency} DESC LIMIT ?", (limit,)).fetchall()
    conn.close()
    return rows

def get_all_users():
    conn = get_db()
    rows = conn.execute("SELECT user_id, gram, gold, is_admin, is_banned, username, first_name, registered_at FROM users ORDER BY user_id").fetchall()
    conn.close()
    return rows

def get_admin_logs(limit: int = 50):
    conn = get_db()
    rows = conn.execute("SELECT * FROM admin_logs ORDER BY timestamp DESC LIMIT ?", (limit,)).fetchall()
    conn.close()
    return rows

def get_bot_stats():
    conn = get_db()
    total_users = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    total_bets = conn.execute("SELECT SUM(total_bets) FROM users").fetchone()[0] or 0
    total_wins = conn.execute("SELECT SUM(total_wins) FROM users").fetchone()[0] or 0
    total_deposited_gram = conn.execute("SELECT SUM(total_deposited_gram) FROM users").fetchone()[0] or 0
    total_deposited_gold = conn.execute("SELECT SUM(total_deposited_gold) FROM users").fetchone()[0] or 0
    total_withdrawn_gram = conn.execute("SELECT SUM(total_withdrawn_gram) FROM users").fetchone()[0] or 0
    total_withdrawn_gold = conn.execute("SELECT SUM(total_withdrawn_gold) FROM users").fetchone()[0] or 0
    conn.close()
    return {
        "total_users": total_users,
        "total_bets": total_bets,
        "total_wins": total_wins,
        "total_deposited_gram": total_deposited_gram,
        "total_deposited_gold": total_deposited_gold,
        "total_withdrawn_gram": total_withdrawn_gram,
        "total_withdrawn_gold": total_withdrawn_gold,
    }

# ========== ЗАЯВКИ ==========
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

# ========== КЛАВИАТУРЫ ==========
def main_menu():
    kb = [
        [InlineKeyboardButton(text="👤 Профиль", callback_data="profile"), InlineKeyboardButton(text="🎮 Игры", callback_data="games")],
        [InlineKeyboardButton(text="💎 Пополнить", callback_data="deposit"), InlineKeyboardButton(text="💰 Вывести", callback_data="withdraw")],
        [InlineKeyboardButton(text="🎁 Бонус", callback_data="bonus"), InlineKeyboardButton(text="🏆 Топ", callback_data="top")],
        [InlineKeyboardButton(text="🧾 Чеки", callback_data="checks_menu"), InlineKeyboardButton(text="🎟 Промокод", callback_data="promo_menu")]
    ]
    if is_admin(MAIN_ADMIN_ID):
        kb.append([InlineKeyboardButton(text="⚙️ Админ-панель", callback_data="admin_panel")])
    return InlineKeyboardMarkup(inline_keyboard=kb)

def games_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎡 Рулетка", callback_data="game_roulette"), InlineKeyboardButton(text="📈 Краш", callback_data="game_crash")],
        [InlineKeyboardButton(text="🎲 Кубик", callback_data="game_cube"), InlineKeyboardButton(text="🎯 Кости", callback_data="game_dice")],
        [InlineKeyboardButton(text="⚽ Футбол", callback_data="game_football"), InlineKeyboardButton(text="🏀 Баскетбол", callback_data="game_basket")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="back_main")]
    ])

def admin_panel_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👥 Все пользователи", callback_data="admin_all_users")],
        [InlineKeyboardButton(text="💰 Выдать валюту", callback_data="admin_give")],
        [InlineKeyboardButton(text="🔫 Забрать валюту", callback_data="admin_take")],
        [InlineKeyboardButton(text="👑 Выдать админа", callback_data="admin_set_admin")],
        [InlineKeyboardButton(text="👑 Снять админа", callback_data="admin_remove_admin")],
        [InlineKeyboardButton(text="🔒 Заблокировать", callback_data="admin_ban")],
        [InlineKeyboardButton(text="🔓 Разблокировать", callback_data="admin_unban")],
        [InlineKeyboardButton(text="📥 Заявки на вывод", callback_data="admin_withdraw_requests")],
        [InlineKeyboardButton(text="💸 Заявки на пополнение", callback_data="admin_transfer_requests")],
        [InlineKeyboardButton(text="📊 Статистика бота", callback_data="admin_stats")],
        [InlineKeyboardButton(text="📜 Логи админов", callback_data="admin_logs")],
        [InlineKeyboardButton(text="📢 Рассылка", callback_data="admin_broadcast")],
        [InlineKeyboardButton(text="🎟 Создать промокод", callback_data="admin_create_promo")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="back_main")]
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
            [InlineKeyboardButton(text="⭐ Пополнить Stars (авто)", callback_data="deposit_stars_gram")],
            [InlineKeyboardButton(text="💸 Переводом на бота (заявка)", callback_data="deposit_transfer_gram")],
            [InlineKeyboardButton(text="◀️ Назад", callback_data="deposit")]
        ])
    else:
        return InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⭐ Пополнить Stars (авто)", callback_data="deposit_stars_gold")],
            [InlineKeyboardButton(text="💸 Передать Gold админу (заявка)", callback_data="deposit_transfer_gold")],
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

def withdraw_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💎 Вывести Граммы", callback_data="withdraw_gram")],
        [InlineKeyboardButton(text="🏅 Вывести Iris-Gold", callback_data="withdraw_gold")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="back_main")]
    ])

def checks_menu_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Создать чек", callback_data="check_create")],
        [InlineKeyboardButton(text="💸 Активировать чек", callback_data="check_claim")],
        [InlineKeyboardButton(text="📋 Мои чеки", callback_data="check_my")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="back_main")]
    ])

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

class AdminStates(StatesGroup):
    waiting_user_id = State()
    waiting_amount = State()
    waiting_currency = State()
    waiting_broadcast = State()
    waiting_promo_code = State()
    waiting_promo_reward_gram = State()
    waiting_promo_reward_gold = State()
    waiting_promo_activations = State()

# Хранилище активных игр
active_games = {}

# ========== ИГРЫ ==========
RED_NUMBERS = {1,3,5,7,9,12,14,16,18,19,21,23,25,27,30,32,34,36}

def roulette_spin(choice: str):
    num = random.randint(0, 36)
    color = "green" if num == 0 else ("red" if num in RED_NUMBERS else "black")
    win = False
    mult = 0
    if choice in ["red", "black"] and ((choice == "red" and color == "red") or (choice == "black" and color == "black")):
        win, mult = True, ROULETTE_MULTIPLIERS["color"]
    elif choice in ["even", "odd"] and num != 0 and ((choice == "even" and num % 2 == 0) or (choice == "odd" and num % 2 == 1)):
        win, mult = True, ROULETTE_MULTIPLIERS["even_odd"]
    elif choice == "zero" and num == 0:
        win, mult = True, ROULETTE_MULTIPLIERS["zero"]
    return win, mult, num, color

def crash_game():
    r = random.random()
    if r < 0.05: return round(random.uniform(1.00, 1.50), 2)
    elif r < 0.30: return round(random.uniform(1.51, 2.50), 2)
    elif r < 0.60: return round(random.uniform(2.51, 4.00), 2)
    elif r < 0.85: return round(random.uniform(4.01, 7.00), 2)
    else: return round(random.uniform(7.01, 50.00), 2)

# ========== ОСНОВНЫЕ ОБРАБОТЧИКИ ==========
@dp.message(CommandStart())
async def start_cmd(message: Message, bot: Bot):
    if is_banned(message.from_user.id):
        await message.answer("❌ Вы забанены и не можете использовать бота!")
        return
    
    # Обновляем информацию о пользователе
    update_user_info(
        message.from_user.id,
        message.from_user.username,
        message.from_user.first_name,
        message.from_user.last_name
    )
    
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

@dp.message(Command("cancel"))
async def cancel_game(message: Message, state: FSMContext):
    user_id = message.from_user.id
    if user_id in active_games:
        game_data = active_games.pop(user_id)
        # Возвращаем ставку если игра не началась
        if game_data.get("bet") and not game_data.get("started"):
            update_balance(user_id, game_data["currency"], game_data["bet"])
            await message.answer("✅ Игра отменена. Ставка возвращена на баланс.")
        else:
            await message.answer("✅ Игра отменена.")
    else:
        await message.answer("❌ У вас нет активной игры.")
    await state.clear()

@dp.message(Command("info"))
async def info_user(message: Message):
    if not is_admin(message.from_user.id):
        await message.answer("⛔ Только для админов!")
        return
    
    parts = message.text.split()
    if len(parts) != 2:
        await message.answer("📝 Формат: /info ID_пользователя или @username")
        return
    
    target = parts[1]
    conn = get_db()
    
    # Поиск по ID или username
    if target.startswith("@"):
        row = conn.execute("SELECT * FROM users WHERE username = ?", (target[1:],)).fetchone()
    else:
        row = conn.execute("SELECT * FROM users WHERE user_id = ?", (target,)).fetchone()
    
    conn.close()
    
    if not row:
        await message.answer("❌ Пользователь не найден!")
        return
    
    wins = row["total_wins"] or 0
    bets = row["total_bets"] or 1
    wr = (wins / bets) * 100
    
    status = "👑 Администратор" if row["is_admin"] else "👤 Пользователь"
    if row["is_banned"]:
        status += " 🔒 Забанен"
    
    reg_date = datetime.fromtimestamp(row["registered_at"] or 0).strftime("%d.%m.%Y %H:%M") if row["registered_at"] else "Неизвестно"
    last_seen = datetime.fromtimestamp(row["last_seen"] or 0).strftime("%d.%m.%Y %H:%M") if row["last_seen"] else "Неизвестно"
    
    text = (
        f"📊 <b>Информация о пользователе</b>\n\n"
        f"🆔 ID: <code>{row['user_id']}</code>\n"
        f"📝 Username: @{row['username'] or 'Нет'}\n"
        f"👤 Имя: {row['first_name'] or 'Нет'}\n"
        f"📊 Статус: {status}\n\n"
        f"💰 <b>Баланс:</b>\n"
        f"💎 {GRAM_NAME}: {fmt_gram(row['gram'])}\n"
        f"🏅 {GOLD_NAME}: {fmt_gold(row['gold'])}\n\n"
        f"📊 <b>Статистика:</b>\n"
        f"🎲 Ставок: {bets}\n"
        f"🏆 Побед: {wins} ({wr:.1f}%)\n"
        f"💎 Пополнено: {fmt_gram(row['total_deposited_gram'] or 0)}\n"
        f"🏅 Пополнено: {fmt_gold(row['total_deposited_gold'] or 0)}\n"
        f"📤 Выведено: {fmt_gram(row['total_withdrawn_gram'] or 0)} / {fmt_gold(row['total_withdrawn_gold'] or 0)}\n\n"
        f"📅 Регистрация: {reg_date}\n"
        f"🕐 Последний визит: {last_seen}"
    )
    await message.answer(text)

@dp.message(Command("give"))
async def give_money(message: Message):
    if not is_admin(message.from_user.id):
        await message.answer("⛔ Только для админов!")
        return
    
    parts = message.text.split()
    if len(parts) != 4:
        await message.answer("📝 Формат: /give ID_пользователя ВАЛЮТА СУММА\nВалюта: gram или gold\nПример: /give 123456789 gram 1000")
        return
    
    try:
        target_id = int(parts[1])
        currency = parts[2].lower()
        if currency not in ["gram", "gold"]:
            await message.answer("❌ Валюта должна быть 'gram' или 'gold'")
            return
        amount = float(parts[3])
        if amount <= 0:
            await message.answer("❌ Сумма должна быть положительной")
            return
        
        # Проверяем существует ли пользователь
        user = get_user(target_id)
        if not user:
            await message.answer("❌ Пользователь не найден!")
            return
        
        new_balance = update_balance(target_id, currency, amount)
        add_admin_log(message.from_user.id, f"give_{currency}", target_id, amount)
        
        await message.answer(f"✅ Выдано {fmt_money(currency, amount)} пользователю {target_id}\n💰 Новый баланс: {fmt_money(currency, new_balance)}")
        
        # Уведомляем пользователя
        try:
            await message.bot.send_message(
                target_id,
                f"✅ Вам начислено {fmt_money(currency, amount)}!\n💰 Новый баланс: {fmt_money(currency, new_balance)}"
            )
        except:
            pass
    except ValueError:
        await message.answer("❌ Ошибка! Пример: /give 123456789 gram 1000")

@dp.message(Command("take"))
async def take_money(message: Message):
    if not is_admin(message.from_user.id):
        await message.answer("⛔ Только для админов!")
        return
    
    parts = message.text.split()
    if len(parts) != 4:
        await message.answer("📝 Формат: /take ID_пользователя ВАЛЮТА СУММА\nВалюта: gram или gold\nПример: /take 123456789 gram 500")
        return
    
    try:
        target_id = int(parts[1])
        currency = parts[2].lower()
        if currency not in ["gram", "gold"]:
            await message.answer("❌ Валюта должна быть 'gram' или 'gold'")
            return
        amount = float(parts[3])
        if amount <= 0:
            await message.answer("❌ Сумма должна быть положительной")
            return
        
        user = get_user(target_id)
        if not user:
            await message.answer("❌ Пользователь не найден!")
            return
        
        if user[currency] < amount:
            await message.answer(f"❌ У пользователя недостаточно средств! Баланс: {fmt_money(currency, user[currency])}")
            return
        
        new_balance = update_balance(target_id, currency, -amount)
        add_admin_log(message.from_user.id, f"take_{currency}", target_id, amount)
        
        await message.answer(f"✅ Забрано {fmt_money(currency, amount)} у пользователя {target_id}\n💰 Новый баланс: {fmt_money(currency, new_balance)}")
        
        # Уведомляем пользователя
        try:
            await message.bot.send_message(
                target_id,
                f"⚠️ С вашего баланса списано {fmt_money(currency, amount)}!\n💰 Новый баланс: {fmt_money(currency, new_balance)}"
            )
        except:
            pass
    except ValueError:
        await message.answer("❌ Ошибка! Пример: /take 123456789 gram 500")

@dp.message(Command("setadmin"))
async def set_admin_cmd(message: Message):
    if message.from_user.id != MAIN_ADMIN_ID:
        await message.answer("⛔ Только для главного админа!")
        return
    
    parts = message.text.split()
    if len(parts) != 2:
        await message.answer("📝 Формат: /setadmin ID_пользователя")
        return
    
    try:
        target_id = int(parts[1])
        set_admin(target_id, True)
        add_admin_log(message.from_user.id, "set_admin", target_id)
        await message.answer(f"✅ Пользователь {target_id} назначен администратором!")
        
        try:
            await message.bot.send_message(target_id, "👑 Вам выдан статус администратора бота!")
        except:
            pass
    except:
        await message.answer("❌ Ошибка!")

@dp.message(Command("removeadmin"))
async def remove_admin_cmd(message: Message):
    if message.from_user.id != MAIN_ADMIN_ID:
        await message.answer("⛔ Только для главного админа!")
        return
    
    parts = message.text.split()
    if len(parts) != 2:
        await message.answer("📝 Формат: /removeadmin ID_пользователя")
        return
    
    try:
        target_id = int(parts[1])
        if target_id == MAIN_ADMIN_ID:
            await message.answer("❌ Нельзя снять админа с главного администратора!")
            return
        set_admin(target_id, False)
        add_admin_log(message.from_user.id, "remove_admin", target_id)
        await message.answer(f"✅ Пользователь {target_id} лишён статуса администратора!")
        
        try:
            await message.bot.send_message(target_id, "⚠️ Ваш статус администратора бота снят!")
        except:
            pass
    except:
        await message.answer("❌ Ошибка!")

@dp.message(Command("ban"))
async def ban_user(message: Message):
    if not is_admin(message.from_user.id):
        await message.answer("⛔ Только для админов!")
        return
    
    parts = message.text.split()
    if len(parts) != 2:
        await message.answer("📝 Формат: /ban ID_пользователя")
        return
    
    try:
        target_id = int(parts[1])
        if target_id in ADMIN_IDS:
            await message.answer("❌ Нельзя заблокировать администратора!")
            return
        
        set_ban(target_id, True)
        add_admin_log(message.from_user.id, "ban", target_id)
        await message.answer(f"✅ Пользователь {target_id} заблокирован!")
        
        try:
            await message.bot.send_message(target_id, "🔒 Вы заблокированы в боте!")
        except:
            pass
    except:
        await message.answer("❌ Ошибка!")

@dp.message(Command("unban"))
async def unban_user(message: Message):
    if not is_admin(message.from_user.id):
        await message.answer("⛔ Только для админов!")
        return
    
    parts = message.text.split()
    if len(parts) != 2:
        await message.answer("📝 Формат: /unban ID_пользователя")
        return
    
    try:
        target_id = int(parts[1])
        set_ban(target_id, False)
        add_admin_log(message.from_user.id, "unban", target_id)
        await message.answer(f"✅ Пользователь {target_id} разблокирован!")
        
        try:
            await message.bot.send_message(target_id, "🔓 Вы разблокированы в боте!")
        except:
            pass
    except:
        await message.answer("❌ Ошибка!")

@dp.message(Command("stats"))
async def stats_cmd(message: Message):
    if not is_admin(message.from_user.id):
        await message.answer("⛔ Только для админов!")
        return
    
    stats = get_bot_stats()
    await message.answer(
        f"📊 <b>Статистика бота</b>\n\n"
        f"👥 Всего пользователей: {stats['total_users']}\n"
        f"🎲 Всего ставок: {stats['total_bets']}\n"
        f"🏆 Всего побед: {stats['total_wins']}\n"
        f"💎 Пополнено грамм: {fmt_gram(stats['total_deposited_gram'])}\n"
        f"🏅 Пополнено Gold: {fmt_gold(stats['total_deposited_gold'])}\n"
        f"📤 Выведено грамм: {fmt_gram(stats['total_withdrawn_gram'])}\n"
        f"📤 Выведено Gold: {fmt_gold(stats['total_withdrawn_gold'])}"
    )

@dp.message(Command("logs"))
async def logs_cmd(message: Message):
    if not is_admin(message.from_user.id):
        await message.answer("⛔ Только для админов!")
        return
    
    logs = get_admin_logs(20)
    if not logs:
        await message.answer("📭 Логов пока нет")
        return
    
    text = "📜 <b>Последние действия админов</b>\n\n"
    for log in logs:
        date = datetime.fromtimestamp(log["timestamp"]).strftime("%d.%m %H:%M")
        text += f"🕐 {date} | 👤 {log['admin_id']} | {log['action']}"
        if log['target_id']:
            text += f" | 🎯 {log['target_id']}"
        if log['amount']:
            text += f" | 💰 {log['amount']}"
        text += "\n"
    
    await message.answer(text)

@dp.message(Command("broadcast"))
async def broadcast_start(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        await message.answer("⛔ Только для админов!")
        return
    
    await state.set_state(AdminStates.waiting_broadcast)
    await message.answer("📢 Введите сообщение для рассылки:")

@dp.message(AdminStates.waiting_broadcast)
async def broadcast_send(message: Message, state: FSMContext):
    users = get_all_users()
    success = 0
    fail = 0
    
    await message.answer("🚀 Начинаю рассылку...")
    
    for user in users:
        try:
            await message.bot.send_message(int(user["user_id"]), message.text)
            success += 1
            await asyncio.sleep(0.05)
        except:
            fail += 1
    
    await message.answer(f"✅ Рассылка завершена!\n📨 Доставлено: {success}\n❌ Ошибок: {fail}")
    await state.clear()

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
    if is_banned(call.from_user.id):
        await call.message.answer("❌ Вы забанены!")
        return
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

# ========== ПРОФИЛЬ ==========
@dp.callback_query(F.data == "profile")
async def profile_cmd(call: CallbackQuery):
    if is_banned(call.from_user.id):
        await call.answer("❌ Вы забанены!", show_alert=True)
        return
    user = get_user(call.from_user.id)
    wins = user["total_wins"] or 0
    bets = user["total_bets"] or 1
    wr = (wins / bets) * 100
    admin_status = "👑 Администратор" if user["is_admin"] else "👤 Пользователь"
    await call.message.edit_text(
        f"👤 <b>Профиль</b>\n\n"
        f"🆔 ID: <code>{call.from_user.id}</code>\n"
        f"📊 Статус: {admin_status}\n\n"
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
    if is_banned(call.from_user.id):
        await call.answer("❌ Вы забанены!", show_alert=True)
        return
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

# ========== ИГРЫ ==========
@dp.callback_query(F.data == "games")
async def games_list(call: CallbackQuery):
    if is_banned(call.from_user.id):
        await call.answer("❌ Вы забанены!", show_alert=True)
        return
    await call.message.edit_text("🎮 Выберите игру:", reply_markup=games_menu())
    await call.answer()

@dp.callback_query(F.data.startswith("game_"))
async def game_choice(call: CallbackQuery, state: FSMContext):
    if is_banned(call.from_user.id):
        await call.answer("❌ Вы забанены!", show_alert=True)
        return
    
    # Проверка на активную игру
    if call.from_user.id in active_games:
        await call.answer("❌ У вас уже есть активная игра! Используйте /cancel для отмены.", show_alert=True)
        return
    
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
    if is_banned(call.from_user.id):
        await call.answer("❌ Вы забанены!", show_alert=True)
        return
    
    currency = call.data.split("_")[1]
    await state.update_data(currency=currency)
    await state.set_state(GameStates.waiting_bet_amount)
    min_bet = MIN_BET_GRAM if currency == "gram" else MIN_BET_GOLD
    max_bet = MAX_BET_GRAM if currency == "gram" else MAX_BET_GOLD
    await call.message.edit_text(
        f"💰 Введите сумму ставки в {GRAM_NAME if currency=='gram' else GOLD_NAME}\n"
        f"Лимиты: {fmt_money(currency, min_bet)} - {fmt_money(currency, max_bet)}\n\n"
        f"Для отмены игры используйте /cancel",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="◀️ Назад", callback_data="games")]])
    )
    await call.answer()

@dp.message(GameStates.waiting_bet_amount)
async def process_bet(message: Message, state: FSMContext):
    if is_banned(message.from_user.id):
        await message.answer("❌ Вы забанены!")
        return
    
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
        
        # Создаём активную игру
        active_games[message.from_user.id] = {
            "game": game,
            "currency": currency,
            "bet": bet,
            "started": False
        }
        
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
    user_id = message.from_user.id
    
    if game == "roulette":
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔴 Красное (x1.8)", callback_data=f"bet_{user_id}_{game}_red_{currency}"),
             InlineKeyboardButton(text="⚫ Чёрное (x1.8)", callback_data=f"bet_{user_id}_{game}_black_{currency}")],
            [InlineKeyboardButton(text="2️⃣ Чёт (x1.8)", callback_data=f"bet_{user_id}_{game}_even_{currency}"),
             InlineKeyboardButton(text="1️⃣ Нечет (x1.8)", callback_data=f"bet_{user_id}_{game}_odd_{currency}")],
            [InlineKeyboardButton(text="0️⃣ Зеро (x25)", callback_data=f"bet_{user_id}_{game}_zero_{currency}")],
            [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_game")]
        ])
    elif game == "cube":
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="1️⃣", callback_data=f"bet_{user_id}_{game}_1_{currency}"),
             InlineKeyboardButton(text="2️⃣", callback_data=f"bet_{user_id}_{game}_2_{currency}"),
             InlineKeyboardButton(text="3️⃣", callback_data=f"bet_{user_id}_{game}_3_{currency}")],
            [InlineKeyboardButton(text="4️⃣", callback_data=f"bet_{user_id}_{game}_4_{currency}"),
             InlineKeyboardButton(text="5️⃣", callback_data=f"bet_{user_id}_{game}_5_{currency}"),
             InlineKeyboardButton(text="6️⃣", callback_data=f"bet_{user_id}_{game}_6_{currency}")],
            [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_game")]
        ])
    else:  # dice
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📈 Больше 7 (x3.5)", callback_data=f"bet_{user_id}_{game}_high_{currency}")],
            [InlineKeyboardButton(text="📉 Меньше 7 (x3.5)", callback_data=f"bet_{user_id}_{game}_low_{currency}")],
            [InlineKeyboardButton(text="🎯 Равно 7 (x3.5)", callback_data=f"bet_{user_id}_{game}_seven_{currency}")],
            [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_game")]
        ])
    
    await message.answer("🎲 Выберите вариант ставки:", reply_markup=kb)
    await state.clear()

@dp.callback_query(F.data == "cancel_game")
async def cancel_game_callback(call: CallbackQuery, state: FSMContext):
    user_id = call.from_user.id
    if user_id in active_games:
        game_data = active_games.pop(user_id)
        if not game_data.get("started"):
            update_balance(user_id, game_data["currency"], game_data["bet"])
            await call.message.edit_text("✅ Игра отменена. Ставка возвращена на баланс.", reply_markup=games_menu())
        else:
            await call.message.edit_text("✅ Игра отменена.", reply_markup=games_menu())
    else:
        await call.message.edit_text("❌ У вас нет активной игры.", reply_markup=games_menu())
    await call.answer()

@dp.callback_query(F.data.startswith("bet_"))
async def handle_bet_callback(call: CallbackQuery):
    parts = call.data.split("_")
    if len(parts) < 5:
        await call.answer("❌ Ошибка", show_alert=True)
        return
    
    owner_id = int(parts[1])
    game = parts[2]
    choice = parts[3]
    currency = parts[4]
    
    if call.from_user.id != owner_id:
        await call.answer("❌ Это не ваша кнопка!", show_alert=True)
        return
    
    if owner_id not in active_games:
        await call.answer("❌ Игра устарела. Начните заново.", show_alert=True)
        return
    
    game_data = active_games.pop(owner_id)
    bet = game_data["bet"]
    currency = game_data["currency"]
    
    # Отмечаем что игра началась
    game_data["started"] = True
    
    # Списываем ставку
    update_balance(owner_id, currency, -bet)
    
    if game == "roulette":
        win, mult, num, color = roulette_spin(choice)
        color_emoji = "🟢" if color == "green" else ("🔴" if color == "red" else "⚫")
        payout = bet * mult if win else 0
        if win:
            update_balance(owner_id, currency, payout)
        add_bet_record(owner_id, bet, win, "roulette", currency)
        result_text = "ПОБЕДА 🎉" if win else "ПРОИГРЫШ 😔"
        await call.message.edit_text(
            f"🎡 <b>Рулетка</b>\n\n"
            f"🎲 Выпало: <b>{num}</b> {color_emoji}\n"
            f"💰 Ставка: {fmt_money(currency, bet)}\n"
            f"💸 Выплата: {fmt_money(currency, payout)}\n"
            f"📊 Результат: <b>{result_text}</b>",
            reply_markup=games_menu()
        )
    elif game == "cube":
        guess = int(choice)
        result = await call.message.answer_dice(emoji="🎲")
        value = result.dice.value
        win = guess == value
        mult = CUBE_MULTIPLIERS["three"] if guess == 3 else CUBE_MULTIPLIERS["normal"]
        payout = bet * mult if win else 0
        if win:
            update_balance(owner_id, currency, payout)
        add_bet_record(owner_id, bet, win, "cube", currency)
        result_text = "ПОБЕДА 🎉" if win else "ПРОИГРЫШ 😔"
        await call.message.answer(
            f"🎲 <b>Кубик</b>\n\n"
            f"🎯 Твой выбор: <b>{guess}</b>\n"
            f"🎲 Выпало: <b>{value}</b>\n"
            f"💰 Ставка: {fmt_money(currency, bet)}\n"
            f"💸 Выплата: {fmt_money(currency, payout)}\n"
            f"📊 Результат: <b>{result_text}</b>",
            reply_markup=games_menu()
        )
    elif game == "dice":
        d1 = await call.message.answer_dice(emoji="🎲")
        d2 = await call.message.answer_dice(emoji="🎲")
        total = d1.dice.value + d2.dice.value
        
        win = False
        if choice == "high" and total > 7:
            win = True
        elif choice == "low" and total < 7:
            win = True
        elif choice == "seven" and total == 7:
            win = True
        
        payout = bet * DICE_MULTIPLIER if win else 0
        if win:
            update_balance(owner_id, currency, payout)
        add_bet_record(owner_id, bet, win, "dice", currency)
        result_text = "ПОБЕДА 🎉" if win else "ПРОИГРЫШ 😔"
        await call.message.answer(
            f"🎯 <b>Кости</b>\n\n"
            f"🎲 Выпало: <b>{d1.dice.value}</b> + <b>{d2.dice.value}</b> = <b>{total}</b>\n"
            f"💰 Ставка: {fmt_money(currency, bet)}\n"
            f"💸 Выплата: {fmt_money(currency, payout)}\n"
            f"📊 Результат: <b>{result_text}</b>",
            reply_markup=games_menu()
        )
    await call.answer()

async def play_instant_game(message: Message, state: FSMContext, game: str, bet: float, currency: str):
    user_id = message.from_user.id
    
    if game == "football":
        result = await message.answer_dice(emoji="⚽")
        value = result.dice.value
        win = value >= 4
        mult = FOOTBALL_MULTIPLIERS["gol"] if win else FOOTBALL_MULTIPLIERS["mimo"]
        payout = bet * mult if win else 0
        if win:
            update_balance(user_id, currency, payout)
        else:
            update_balance(user_id, currency, -bet)
        add_bet_record(user_id, bet, win, "football", currency)
        outcome = "ГОЛ 🎉" if win else "МИМО 😔"
        await message.answer(
            f"⚽ <b>Футбол</b>\n\n"
            f"🎲 Результат: <b>{outcome}</b>\n"
            f"💰 Ставка: {fmt_money(currency, bet)}\n"
            f"💸 Выплата: {fmt_money(currency, payout)}\n"
            f"📊 Результат: <b>{'ПОБЕДА 🎉' if win else 'ПРОИГРЫШ 😔'}</b>",
            reply_markup=games_menu()
        )
    elif game == "basket":
        result = await message.answer_dice(emoji="🏀")
        value = result.dice.value
        win = value in [4, 5]
        mult = BASKET_MULTIPLIERS["tochniy"] if win else BASKET_MULTIPLIERS["promah"]
        payout = bet * mult if win else 0
        if win:
            update_balance(user_id, currency, payout)
        else:
            update_balance(user_id, currency, -bet)
        add_bet_record(user_id, bet, win, "basket", currency)
        outcome = "ТОЧНЫЙ БРОСОК 🎉" if win else "ПРОМАХ 😔"
        await message.answer(
            f"🏀 <b>Баскетбол</b>\n\n"
            f"🎲 Результат: <b>{outcome}</b>\n"
            f"💰 Ставка: {fmt_money(currency, bet)}\n"
            f"💸 Выплата: {fmt_money(currency, payout)}\n"
            f"📊 Результат: <b>{'ПОБЕДА 🎉' if win else 'ПРОИГРЫШ 😔'}</b>",
            reply_markup=games_menu()
        )
    elif game == "crash":
        # Краш обрабатывается отдельно
        pass
    
    if user_id in active_games:
        del active_games[user_id]
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
        user_id = message.from_user.id
        
        crash_mult = crash_game()
        win = crash_mult >= mult
        payout = bet * mult if win else 0
        
        # Списываем ставку
        update_balance(user_id, currency, -bet)
        if win:
            update_balance(user_id, currency, payout)
        
        add_bet_record(user_id, bet, win, "crash", currency)
        
        await message.answer(
            f"📈 <b>Краш</b>\n\n"
            f"🎲 Множитель игры: <b>x{crash_mult:.2f}</b>\n"
            f"🎯 Твой множитель: <b>x{mult:.2f}</b>\n"
            f"💰 Ставка: {fmt_money(currency, bet)}\n"
            f"💸 Выплата: {fmt_money(currency, payout)}\n"
            f"📊 Результат: <b>{'ПОБЕДА 🎉' if win else 'ПРОИГРЫШ 😔'}</b>",
            reply_markup=games_menu()
        )
        
        if user_id in active_games:
            del active_games[user_id]
        await state.clear()
    except:
        await message.answer("❌ Введите корректный множитель!")

# ========== ПОПОЛНЕНИЕ ==========
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

@dp.callback_query(F.data.startswith("deposit_stars_"))
async def deposit_stars_method(call: CallbackQuery):
    currency = call.data.split("_")[2]
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
    currency = parts[1]
    stars = int(parts[2])
    amount = stars * (STAR_TO_GRAM if currency == "gram" else STAR_TO_GOLD)
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

@dp.callback_query(F.data.startswith("deposit_transfer_"))
async def deposit_transfer_method(call: CallbackQuery, state: FSMContext):
    currency = call.data.split("_")[2]
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
            f"1️⃣ Переведите Gold на @{BOT_USERNAME}\n"
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
        for admin in ADMIN_IDS:
            try:
                await message.bot.send_message(
                    admin,
                    f"📥 <b>Заявка на пополнение</b>\n"
                    f"👤 {mention_user(message.from_user.id)}\n"
                    f"💎 {GRAM_NAME if currency=='gram' else GOLD_NAME}: {fmt_money(currency, amount)}\n"
                    f"🆔 Заявка #{req_id}\n\n"
                    f"✅ /approve_transfer {req_id} - подтвердить\n"
                    f"❌ /decline_transfer {req_id} - отклонить"
                )
            except:
                pass
        await state.clear()
    except:
        await message.answer("❌ Введите корректную сумму")

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
        try:
            await message.bot.send_message(admin, f"💎 Новое пополнение!\n👤 {mention_user(message.from_user.id)}\n⭐ {stars} Stars → {fmt_money(currency, amount)}")
        except:
            pass

# ========== ВЫВОД ==========
@dp.callback_query(F.data == "withdraw")
async def withdraw_start(call: CallbackQuery):
    await call.message.edit_text("💰 Выберите валюту для вывода:", reply_markup=withdraw_menu())
    await call.answer()

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
        try:
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
        except:
            pass
    await state.clear()

# ========== АДМИН-ПАНЕЛЬ ==========
@dp.callback_query(F.data == "admin_panel")
async def admin_panel(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        await call.answer("⛔ Доступ запрещён!", show_alert=True)
        return
    await call.message.edit_text("⚙️ <b>Админ-панель</b>\n\nВыберите действие:", reply_markup=admin_panel_menu())
    await call.answer()

@dp.callback_query(F.data == "admin_all_users")
async def admin_all_users(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        await call.answer("⛔ Доступ запрещён!", show_alert=True)
        return
    users = get_all_users()
    if not users:
        await call.message.edit_text("📭 Нет пользователей")
        return
    text = "👥 <b>Все пользователи</b>\n\n"
    for u in users[:20]:  # Показываем первых 20
        status = "👑" if u["is_admin"] else "👤"
        if u["is_banned"]:
            status += "🔒"
        text += f"{status} <code>{u['user_id']}</code> | 💎 {fmt_gram(u['gram'])} | 🏅 {fmt_gold(u['gold'])}\n"
    if len(users) > 20:
        text += f"\n... и ещё {len(users) - 20} пользователей"
    await call.message.edit_text(text, reply_markup=back_button())
    await call.answer()

@dp.callback_query(F.data == "admin_give")
async def admin_give_start(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id):
        await call.answer("⛔ Доступ запрещён!", show_alert=True)
        return
    await state.set_state(AdminStates.waiting_user_id)
    await call.message.edit_text("💰 Введите ID пользователя для выдачи валюты:", reply_markup=back_button())
    await call.answer()

@dp.callback_query(F.data == "admin_take")
async def admin_take_start(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id):
        await call.answer("⛔ Доступ запрещён!", show_alert=True)
        return
    await state.set_state(AdminStates.waiting_user_id)
    await state.update_data(action="take")
    await call.message.edit_text("🔫 Введите ID пользователя для списания валюты:", reply_markup=back_button())
    await call.answer()

@dp.callback_query(F.data == "admin_set_admin")
async def admin_set_admin_start(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id):
        await call.answer("⛔ Доступ запрещён!", show_alert=True)
        return
    await state.set_state(AdminStates.waiting_user_id)
    await state.update_data(action="set_admin")
    await call.message.edit_text("👑 Введите ID пользователя для выдачи прав администратора:", reply_markup=back_button())
    await call.answer()

@dp.callback_query(F.data == "admin_remove_admin")
async def admin_remove_admin_start(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id):
        await call.answer("⛔ Доступ запрещён!", show_alert=True)
        return
    await state.set_state(AdminStates.waiting_user_id)
    await state.update_data(action="remove_admin")
    await call.message.edit_text("👑 Введите ID пользователя для снятия прав администратора:", reply_markup=back_button())
    await call.answer()

@dp.callback_query(F.data == "admin_ban")
async def admin_ban_start(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id):
        await call.answer("⛔ Доступ запрещён!", show_alert=True)
        return
    await state.set_state(AdminStates.waiting_user_id)
    await state.update_data(action="ban")
    await call.message.edit_text("🔒 Введите ID пользователя для блокировки:", reply_markup=back_button())
    await call.answer()

@dp.callback_query(F.data == "admin_unban")
async def admin_unban_start(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id):
        await call.answer("⛔ Доступ запрещён!", show_alert=True)
        return
    await state.set_state(AdminStates.waiting_user_id)
    await state.update_data(action="unban")
    await call.message.edit_text("🔓 Введите ID пользователя для разблокировки:", reply_markup=back_button())
    await call.answer()

@dp.message(AdminStates.waiting_user_id)
async def admin_get_user_id(message: Message, state: FSMContext):
    try:
        target_id = int(message.text)
        data = await state.get_data()
        action = data.get("action", "give")
        
        if action == "give":
            await state.update_data(target_id=target_id)
            await state.set_state(AdminStates.waiting_currency)
            await message.answer("💎 Введите валюту (gram или gold):")
        elif action == "take":
            await state.update_data(target_id=target_id)
            await state.set_state(AdminStates.waiting_currency)
            await message.answer("💎 Введите валюту (gram или gold):")
        elif action == "set_admin":
            set_admin(target_id, True)
            add_admin_log(message.from_user.id, "set_admin", target_id)
            await message.answer(f"✅ Пользователь {target_id} назначен администратором!", reply_markup=admin_panel_menu())
            await state.clear()
        elif action == "remove_admin":
            if target_id == MAIN_ADMIN_ID:
                await message.answer("❌ Нельзя снять админа с главного администратора!")
            else:
                set_admin(target_id, False)
                add_admin_log(message.from_user.id, "remove_admin", target_id)
                await message.answer(f"✅ Пользователь {target_id} лишён прав администратора!", reply_markup=admin_panel_menu())
            await state.clear()
        elif action == "ban":
            if target_id in ADMIN_IDS:
                await message.answer("❌ Нельзя заблокировать администратора!")
            else:
                set_ban(target_id, True)
                add_admin_log(message.from_user.id, "ban", target_id)
                await message.answer(f"✅ Пользователь {target_id} заблокирован!", reply_markup=admin_panel_menu())
            await state.clear()
        elif action == "unban":
            set_ban(target_id, False)
            add_admin_log(message.from_user.id, "unban", target_id)
            await message.answer(f"✅ Пользователь {target_id} разблокирован!", reply_markup=admin_panel_menu())
            await state.clear()
    except:
        await message.answer("❌ Введите корректный ID пользователя!")

@dp.message(AdminStates.waiting_currency)
async def admin_get_currency(message: Message, state: FSMContext):
    currency = message.text.lower()
    if currency not in ["gram", "gold"]:
        await message.answer("❌ Валюта должна быть 'gram' или 'gold'")
        return
    await state.update_data(currency=currency)
    await state.set_state(AdminStates.waiting_amount)
    await message.answer("💰 Введите сумму:")

@dp.message(AdminStates.waiting_amount)
async def admin_get_amount(message: Message, state: FSMContext):
    try:
        amount = float(message.text.replace(",", "."))
        if amount <= 0:
            await message.answer("❌ Сумма должна быть положительной")
            return
        data = await state.get_data()
        target_id = data["target_id"]
        currency = data["currency"]
        action = data.get("action", "give")
        
        if action == "give":
            new_balance = update_balance(target_id, currency, amount)
            add_admin_log(message.from_user.id, f"give_{currency}", target_id, amount)
            await message.answer(f"✅ Выдано {fmt_money(currency, amount)} пользователю {target_id}\n💰 Новый баланс: {fmt_money(currency, new_balance)}", reply_markup=admin_panel_menu())
            try:
                await message.bot.send_message(target_id, f"✅ Вам начислено {fmt_money(currency, amount)}!\n💰 Новый баланс: {fmt_money(currency, new_balance)}")
            except:
                pass
        elif action == "take":
            user = get_user(target_id)
            if user[currency] < amount:
                await message.answer(f"❌ У пользователя недостаточно средств! Баланс: {fmt_money(currency, user[currency])}")
                return
            new_balance = update_balance(target_id, currency, -amount)
            add_admin_log(message.from_user.id, f"take_{currency}", target_id, amount)
            await message.answer(f"✅ Забрано {fmt_money(currency, amount)} у пользователя {target_id}\n💰 Новый баланс: {fmt_money(currency, new_balance)}", reply_markup=admin_panel_menu())
            try:
                await message.bot.send_message(target_id, f"⚠️ С вашего баланса списано {fmt_money(currency, amount)}!\n💰 Новый баланс: {fmt_money(currency, new_balance)}")
            except:
                pass
        
        await state.clear()
    except:
        await message.answer("❌ Введите корректную сумму!")

@dp.callback_query(F.data == "admin_withdraw_requests")
async def admin_withdraw_requests(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        await call.answer("⛔ Доступ запрещён!", show_alert=True)
        return
    requests = get_pending_withdraws()
    if not requests:
        await call.message.edit_text("📭 Нет активных заявок на вывод", reply_markup=back_button())
        await call.answer()
        return
    text = "📥 <b>Заявки на вывод</b>\n\n"
    for r in requests:
        text += f"🆔 #{r['id']} | {mention_user(int(r['user_id']))} | {fmt_money(r['currency'], r['amount'])} | {r['wallet']}\n"
    await call.message.edit_text(text, reply_markup=back_button())
    await call.answer()

@dp.callback_query(F.data == "admin_transfer_requests")
async def admin_transfer_requests(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        await call.answer("⛔ Доступ запрещён!", show_alert=True)
        return
    requests = get_pending_transfers()
    if not requests:
        await call.message.edit_text("📭 Нет активных заявок на пополнение", reply_markup=back_button())
        await call.answer()
        return
    text = "💸 <b>Заявки на пополнение</b>\n\n"
    for r in requests:
        text += f"🆔 #{r['id']} | {mention_user(int(r['user_id']))} | {fmt_money(r['currency'], r['amount'])}\n"
    await call.message.edit_text(text, reply_markup=back_button())
    await call.answer()

@dp.callback_query(F.data == "admin_stats")
async def admin_stats(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        await call.answer("⛔ Доступ запрещён!", show_alert=True)
        return
    stats = get_bot_stats()
    await call.message.edit_text(
        f"📊 <b>Статистика бота</b>\n\n"
        f"👥 Всего пользователей: {stats['total_users']}\n"
        f"🎲 Всего ставок: {stats['total_bets']}\n"
        f"🏆 Всего побед: {stats['total_wins']}\n"
        f"💎 Пополнено грамм: {fmt_gram(stats['total_deposited_gram'])}\n"
        f"🏅 Пополнено Gold: {fmt_gold(stats['total_deposited_gold'])}\n"
        f"📤 Выведено грамм: {fmt_gram(stats['total_withdrawn_gram'])}\n"
        f"📤 Выведено Gold: {fmt_gold(stats['total_withdrawn_gold'])}",
        reply_markup=back_button()
    )
    await call.answer()

@dp.callback_query(F.data == "admin_logs")
async def admin_logs(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        await call.answer("⛔ Доступ запрещён!", show_alert=True)
        return
    logs = get_admin_logs(20)
    if not logs:
        await call.message.edit_text("📭 Логов пока нет", reply_markup=back_button())
        await call.answer()
        return
    text = "📜 <b>Последние действия админов</b>\n\n"
    for log in logs:
        date = datetime.fromtimestamp(log["timestamp"]).strftime("%d.%m %H:%M")
        text += f"🕐 {date} | 👤 {log['admin_id']} | {log['action']}"
        if log['target_id']:
            text += f" | 🎯 {log['target_id']}"
        if log['amount']:
            text += f" | 💰 {log['amount']}"
        text += "\n"
    await call.message.edit_text(text, reply_markup=back_button())
    await call.answer()

@dp.callback_query(F.data == "admin_broadcast")
async def admin_broadcast_start(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id):
        await call.answer("⛔ Доступ запрещён!", show_alert=True)
        return
    await state.set_state(AdminStates.waiting_broadcast)
    await call.message.edit_text("📢 Введите сообщение для рассылки:", reply_markup=back_button())
    await call.answer()

@dp.message(AdminStates.waiting_broadcast)
async def admin_broadcast_send(message: Message, state: FSMContext):
    users = get_all_users()
    success = 0
    fail = 0
    
    await message.answer("🚀 Начинаю рассылку...")
    
    for user in users:
        try:
            await message.bot.send_message(int(user["user_id"]), message.text)
            success += 1
            await asyncio.sleep(0.05)
        except:
            fail += 1
    
    await message.answer(f"✅ Рассылка завершена!\n📨 Доставлено: {success}\n❌ Ошибок: {fail}", reply_markup=admin_panel_menu())
    await state.clear()

@dp.callback_query(F.data == "admin_create_promo")
async def admin_create_promo_start(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id):
        await call.answer("⛔ Доступ запрещён!", show_alert=True)
        return
    await state.set_state(AdminStates.waiting_promo_code)
    await call.message.edit_text("🎟 Введите код промокода:", reply_markup=back_button())
    await call.answer()

@dp.message(AdminStates.waiting_promo_code)
async def admin_create_promo_code(message: Message, state: FSMContext):
    code = message.text.strip().upper()
    await state.update_data(promo_code=code)
    await state.set_state(AdminStates.waiting_promo_reward_gram)
    await message.answer("💎 Введите награду в Граммах (число):")

@dp.message(AdminStates.waiting_promo_reward_gram)
async def admin_create_promo_reward_gram(message: Message, state: FSMContext):
    try:
        reward_gram = float(message.text.replace(",", "."))
        await state.update_data(promo_reward_gram=reward_gram)
        await state.set_state(AdminStates.waiting_promo_reward_gold)
        await message.answer("🏅 Введите награду в Iris-Gold (число):")
    except:
        await message.answer("❌ Введите число!")

@dp.message(AdminStates.waiting_promo_reward_gold)
async def admin_create_promo_reward_gold(message: Message, state: FSMContext):
    try:
        reward_gold = float(message.text.replace(",", "."))
        await state.update_data(promo_reward_gold=reward_gold)
        await state.set_state(AdminStates.waiting_promo_activations)
        await message.answer("🔢 Введите количество активаций (целое число):")
    except:
        await message.answer("❌ Введите число!")

@dp.message(AdminStates.waiting_promo_activations)
async def admin_create_promo_activations(message: Message, state: FSMContext):
    try:
        activations = int(message.text)
        if activations <= 0:
            await message.answer("❌ Количество активаций должно быть больше 0")
            return
        data = await state.get_data()
        code = data["promo_code"]
        reward_gram = data["promo_reward_gram"]
        reward_gold = data["promo_reward_gold"]
        
        create_promo(code, reward_gram, reward_gold, activations)
        add_admin_log(message.from_user.id, "create_promo", None, None)
        
        await message.answer(
            f"✅ Промокод создан!\n"
            f"🎫 Код: <code>{code}</code>\n"
            f"💎 Награда: {fmt_gram(reward_gram)}\n"
            f"🏅 Награда: {fmt_gold(reward_gold)}\n"
            f"🔢 Активаций: {activations}",
            reply_markup=admin_panel_menu()
        )
        await state.clear()
    except:
        await message.answer("❌ Введите целое число!")

# ========== ЧЕКИ ==========
@dp.callback_query(F.data == "checks_menu")
async def checks_menu(call: CallbackQuery):
    await call.message.edit_text("🧾 Меню чеков:", reply_markup=checks_menu_kb())
    await call.answer()

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

# ========== ПРОМОКОДЫ ==========
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

# ========== АДМИН-КОМАНДЫ ДЛЯ ЗАЯВОК ==========
@dp.message(Command("approve_transfer"))
async def approve_transfer_cmd(message: Message):
    if not is_admin(message.from_user.id):
        await message.answer("⛔ Только для админов!")
        return
    parts = message.text.split()
    if len(parts) != 2:
        await message.answer("📝 /approve_transfer ID")
        return
    try:
        req_id = int(parts[1])
        if approve_transfer(req_id):
            conn = get_db()
            row = conn.execute("SELECT user_id, currency, amount FROM transfer_requests WHERE id = ?", (req_id,)).fetchone()
            conn.close()
            if row:
                await message.bot.send_message(int(row["user_id"]), f"✅ Ваша заявка на пополнение #{req_id} одобрена!\n💰 Начислено: {fmt_money(row['currency'], row['amount'])}")
            add_admin_log(message.from_user.id, "approve_transfer", None, None)
            await message.answer(f"✅ Заявка #{req_id} подтверждена")
        else:
            await message.answer(f"❌ Заявка #{req_id} не найдена")
    except:
        await message.answer("❌ Ошибка!")

@dp.message(Command("decline_transfer"))
async def decline_transfer_cmd(message: Message):
    if not is_admin(message.from_user.id):
        await message.answer("⛔ Только для админов!")
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
                await message.bot.send_message(int(row["user_id"]), f"❌ Ваша заявка на пополнение #{req_id} отклонена.")
            add_admin_log(message.from_user.id, "decline_transfer", None, None)
            await message.answer(f"✅ Заявка #{req_id} отклонена")
        else:
            await message.answer(f"❌ Заявка #{req_id} не найдена")
    except:
        await message.answer("❌ Ошибка!")

@dp.message(Command("approve_withdraw"))
async def approve_withdraw_cmd(message: Message):
    if not is_admin(message.from_user.id):
        await message.answer("⛔ Только для админов!")
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
                await message.bot.send_message(int(row["user_id"]), f"✅ Ваша заявка на вывод #{req_id} одобрена!\n💰 Сумма: {fmt_money(row['currency'], row['amount'])}")
            add_admin_log(message.from_user.id, "approve_withdraw", None, None)
            await message.answer(f"✅ Заявка #{req_id} подтверждена")
        else:
            await message.answer(f"❌ Заявка #{req_id} не найдена")
    except:
        await message.answer("❌ Ошибка!")

@dp.message(Command("decline_withdraw"))
async def decline_withdraw_cmd(message: Message):
    if not is_admin(message.from_user.id):
        await message.answer("⛔ Только для админов!")
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
                await message.bot.send_message(int(row["user_id"]), f"❌ Ваша заявка на вывод #{req_id} отклонена.")
            add_admin_log(message.from_user.id, "decline_withdraw", None, None)
            await message.answer(f"✅ Заявка #{req_id} отклонена")
        else:
            await message.answer(f"❌ Заявка #{req_id} не найдена")
    except:
        await message.answer("❌ Ошибка!")

# ========== ЗАПУСК ==========
async def main():
    bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    await bot.delete_webhook(drop_pending_updates=True)
    print("✅ Бот запущен!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
