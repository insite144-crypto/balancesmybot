import asyncio
import logging
import os
import sqlite3
from datetime import datetime

from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command, CommandObject
from aiogram.types import Message
from aiogram.enums import ChatType

# ================== НАСТРОЙКИ ==================
BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise ValueError("Не указан BOT_TOKEN! Добавь переменную окружения.")
# ===============================================

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def init_db():
    conn = sqlite3.connect("balance.db")
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS balances (
            chat_id INTEGER PRIMARY KEY,
            balance REAL DEFAULT 0.0
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS cheats (
            user_id INTEGER PRIMARY KEY,
            enabled INTEGER DEFAULT 0
        )
    """)
    conn.commit()
    conn.close()

def get_balance(chat_id: int) -> float:
    conn = sqlite3.connect("balance.db")
    cursor = conn.cursor()
    cursor.execute("SELECT balance FROM balances WHERE chat_id = ?", (chat_id,))
    row = cursor.fetchone()
    conn.close()
    return row[0] if row else 0.0

def set_balance(chat_id: int, balance: float):
    conn = sqlite3.connect("balance.db")
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO balances (chat_id, balance) VALUES (?, ?)
        ON CONFLICT(chat_id) DO UPDATE SET balance = excluded.balance
    """, (chat_id, balance))
    conn.commit()
    conn.close()

def is_cheats_enabled(user_id: int) -> bool:
    conn = sqlite3.connect("balance.db")
    cursor = conn.cursor()
    cursor.execute("SELECT enabled FROM cheats WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    conn.close()
    return bool(row[0]) if row else False

def set_cheats(user_id: int, enabled: bool):
    conn = sqlite3.connect("balance.db")
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO cheats (user_id, enabled) VALUES (?, ?)
        ON CONFLICT(user_id) DO UPDATE SET enabled = excluded.enabled
    """, (user_id, 1 if enabled else 0))
    conn.commit()
    conn.close()

def format_amount(amount: float) -> str:
    return f"{amount:,.2f}"

def get_current_time() -> str:
    return datetime.now().strftime("%H:%M")

async def cmd_start(message: Message):
    text = (
        "Команды:\n"
        "/баланс — показать баланс\n"
        "/обнулить — сбросить\n"
        "/минус 10.5 — списать\n"
        "Или просто напиши сумму для пополнения (например, 100)."
        
    )
    await message.answer(text)

async def cmd_balance(message: Message):
    balance = get_balance(message.chat.id)
    await message.answer(f"💰 Текущий баланс: {format_amount(balance)}")

async def cmd_reset(message: Message):
    set_balance(message.chat.id, 0.0)
    await message.answer("🔄 Баланс обнулён.")

async def cmd_minus(message: Message, command: CommandObject):
    if not command.args:
        await message.answer("Укажи сумму. Пример: /минус 15000")
        return

    try:
        amount = float(command.args.replace(",", ".").replace(" ", ""))
        if amount <= 0:
            await message.answer("Сумма должна быть больше нуля.")
            return
    except ValueError:
        await message.answer("Не удалось распознать сумму. Пример: /минус 15000")
        return

    chat_id = message.chat.id
    user_id = message.from_user.id
    is_private = message.chat.type == ChatType.PRIVATE

    real_amount = amount
    if is_private and is_cheats_enabled(user_id):
        real_amount = amount * 0.1

    current = get_balance(chat_id)
    new_balance = current - real_amount
    set_balance(chat_id, new_balance)

    text = f"➖ Списано: {format_amount(amount)} | Баланс: {format_amount(new_balance)}"
    await message.answer(text)

async def cmd_cheats(message: Message, command: CommandObject):
    if message.chat.type != ChatType.PRIVATE:
        await message.answer("Режим читов работает только в личных сообщениях.")
        return

    if not command.args:
        status = "включён" if is_cheats_enabled(message.from_user.id) else "выключен"
        await message.answer(f"Читы сейчас: {status}\n\nИспользование:\n/cheats on\n/cheats off")
        return

    arg = command.args.lower().strip()
    if arg in ("on", "вкл", "1", "true"):
        set_cheats(message.from_user.id, True)
        await message.answer("✅ Читы включены. Теперь к балансу применяется ×0.1, но показывается полная сумма.")
    elif arg in ("off", "выкл", "0", "false"):
        set_cheats(message.from_user.id, False)
        await message.answer("❌ Читы выключены.")
    else:
        await message.answer("Использование: /cheats on или /cheats off")

async def handle_number(message: Message):
    text = message.text.strip().replace(" ", "").replace(",", ".")

    try:
        amount = float(text)
        if amount <= 0:
            return
    except ValueError:
        return

    chat_id = message.chat.id
    user_id = message.from_user.id
    is_private = message.chat.type == ChatType.PRIVATE

    real_amount = amount
    if is_private and is_cheats_enabled(user_id):
        real_amount = amount * 0.1

    current = get_balance(chat_id)
    new_balance = current + real_amount
    set_balance(chat_id, new_balance)

    time_str = get_current_time()
    reply = f"💰 Зачислено: {format_amount(amount)} (в {time_str}) | Баланс: {format_amount(new_balance)}"
    await message.answer(reply)

async def main():
    init_db()
    bot = Bot(token=BOT_TOKEN)
    dp = Dispatcher()

    dp.message.register(cmd_start, Command("start"))
    dp.message.register(cmd_balance, Command("баланс"))
    dp.message.register(cmd_reset, Command("обнулить"))
    dp.message.register(cmd_minus, Command("минус"))
    dp.message.register(cmd_cheats, Command("cheats"))

    dp.message.register(handle_number, F.text.regexp(r"^[+-]?\d+[.,]?\d*$"))

    logger.info("Бот запущен...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
