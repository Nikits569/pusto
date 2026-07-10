import asyncio
import time
import pymysql

from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from config import TOKEN, DB_CONFIG

# ------------------- CONFIG -------------------
DEBUG = False

TABLES = ["ads_thingspost", "ads_jobpost", "ads_neighborpost"]

TG_MIRROR = {
    "ads_thingspost": "productsTest",
    "ads_jobpost": "jobsTest",
    "ads_neighborpost": "neighborsTest",
}

PROFILE_TABLE = "accounts_profile"
LINK_CODES_TABLE = "tg_link_codes"
POST_OWNER_FIELD = "telegram_id"

# pending action per tg user:
# tg_id -> {"mode": "single"|"all", "table": str|None, "post_id": int|None, "posts": list[(table, id)]}
PENDING_ACTION = {}

# --- Anti brute force (codes) ---
MAX_ATTEMPTS = 5
WINDOW_SEC = 10 * 60      # 10 minutes
LOCK_SEC = 10 * 60        # 10 minutes
ATTEMPTS = {}             # tg_id -> [timestamps]
LOCKED_UNTIL = {}         # tg_id -> timestamp

def now_ts() -> float:
    return time.time()

def is_locked(tg_id: int) -> int:
    """return seconds remaining if locked, else 0"""
    until = LOCKED_UNTIL.get(tg_id)
    if not until:
        return 0
    rem = int(until - now_ts())
    if rem <= 0:
        LOCKED_UNTIL.pop(tg_id, None)
        return 0
    return rem

def register_attempt(tg_id: int) -> tuple[bool, int]:
    """
    returns (allowed, remaining_seconds_if_locked)
    """
    rem = is_locked(tg_id)
    if rem > 0:
        return (False, rem)

    t = now_ts()
    lst = ATTEMPTS.get(tg_id, [])
    # keep only attempts within window
    lst = [x for x in lst if t - x <= WINDOW_SEC]
    lst.append(t)
    ATTEMPTS[tg_id] = lst

    if len(lst) > MAX_ATTEMPTS:
        LOCKED_UNTIL[tg_id] = t + LOCK_SEC
        return (False, LOCK_SEC)

    return (True, 0)

# ------------------- MySQL -------------------
conn = pymysql.connect(**DB_CONFIG)
cursor = conn.cursor()

DB_LOCK = asyncio.Lock()

async def db_fetchone(query: str, params: tuple = ()):
    async with DB_LOCK:
        return await asyncio.to_thread(_db_fetchone_sync, query, params)

def _db_fetchone_sync(query: str, params: tuple):
    cursor.execute(query, params)
    return cursor.fetchone()

async def db_fetchall(query: str, params: tuple = ()):
    async with DB_LOCK:
        return await asyncio.to_thread(_db_fetchall_sync, query, params)

def _db_fetchall_sync(query: str, params: tuple):
    cursor.execute(query, params)
    return cursor.fetchall()

async def db_execute(query: str, params: tuple = ()) -> int:
    async with DB_LOCK:
        return await asyncio.to_thread(_db_execute_sync, query, params)

def _db_execute_sync(query: str, params: tuple) -> int:
    cursor.execute(query, params)
    return cursor.rowcount

async def db_commit():
    async with DB_LOCK:
        await asyncio.to_thread(conn.commit)

async def db_rollback():
    async with DB_LOCK:
        await asyncio.to_thread(conn.rollback)

# ------------------- Bot -------------------
bot = Bot(token=TOKEN)
dp = Dispatcher(storage=MemoryStorage())

# ------------------- Helpers -------------------
async def get_profile_id_by_tg(tg_id: int) -> int | None:
    tg_id_str = str(tg_id)

    row = await db_fetchone(
        f"""
        SELECT id
        FROM `{PROFILE_TABLE}`
        WHERE CAST(user_id AS CHAR) = %s
        LIMIT 1
        """,
        (tg_id_str,)
    )

    if not row:
        return None

    return int(row["id"])

def norm_username(u: str) -> str:
    return (u or "").strip().lstrip("@").lower()

def start_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="показати мої пости", callback_data="list_posts")]]
    )

def posts_kb(found_posts: list[tuple[str, int]]) -> InlineKeyboardMarkup:
    kb = []
    for table, post_id in found_posts:
        kb.append([InlineKeyboardButton(text=f"Пост #{post_id} ({table})", callback_data="noop")])
        kb.append([
            InlineKeyboardButton(text="🗑 видалити", callback_data=f"del:{table}:{post_id}"),
            InlineKeyboardButton(text="➡️ перенести на аккаунт", callback_data=f"mv:{table}:{post_id}"),
        ])

    # UX: move all
    kb.append([InlineKeyboardButton(text="➡️ перенести ВСІ пости", callback_data="mv_all")])
    kb.append([InlineKeyboardButton(text="🔄 оновити", callback_data="list_posts")])
    return InlineKeyboardMarkup(inline_keyboard=kb)

def delete_confirm_kb(table: str, post_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[
            InlineKeyboardButton(text="✅ так, видалити", callback_data=f"del_yes:{table}:{post_id}"),
            InlineKeyboardButton(text="❌ скасування", callback_data="del_no"),
        ]]
    )

def account_choice_kb(table: str | None, post_id: int | None, is_all: bool = False) -> InlineKeyboardMarkup:
    # callback carries mode
    if is_all:
        has = "mv_has_all"
        new = "mv_new_all"
    else:
        has = f"mv_has:{table}:{post_id}"
        new = f"mv_new:{table}:{post_id}"

    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="✅ в мене вже є аккаунт", callback_data=has)],
            [InlineKeyboardButton(text="➕ створити новий аккаунт", callback_data=new)],
            [InlineKeyboardButton(text="❌ скасувати", callback_data="mv_cancel")],
        ]
    )

def after_register_kb(table: str | None, post_id: int | None, is_all: bool = False) -> InlineKeyboardMarkup:
    has = "mv_has_all" if is_all else f"mv_has:{table}:{post_id}"
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🌐 відкрити сайт(реєстрація)", url="https://bursa.sk/register")],
            [InlineKeyboardButton(text="✅ я зареєструвався — перенести", callback_data=has)],
            [InlineKeyboardButton(text="❌ скасувати", callback_data="mv_cancel")],
        ]
    )

async def ensure_owner(table: str, post_id: int, tg_id: int) -> bool:
    profile_id = await get_profile_id_by_tg(tg_id)
    if not profile_id:
        return False

    row = await db_fetchone(
        f"""
        SELECT id
        FROM `{table}`
        WHERE id = %s AND `{POST_OWNER_FIELD}` = %s
        LIMIT 1
        """,
        (post_id, profile_id)
    )

    return row is not None

async def delete_from_mirror_by_tg_ids(tg_table: str, chat_id: str | None, message_id: str | None) -> bool:
    if not message_id:
        return False

    cols = await db_fetchall(f"SHOW COLUMNS FROM `{tg_table}`")
    colset = {r["Field"] for r in cols}

    if "chat_id" in colset and chat_id and "message_id" in colset:
        rc = await db_execute(
            f"DELETE FROM `{tg_table}` WHERE chat_id=%s AND message_id=%s",
            (chat_id, message_id)
        )
        return rc > 0

    if "message_id" in colset:
        rc = await db_execute(f"DELETE FROM `{tg_table}` WHERE message_id=%s", (message_id,))
        return rc > 0

    return False

async def get_posts_for_user(tg_id: int) -> list[tuple[str, int]]:
    found: list[tuple[str, int]] = []

    profile_id = await get_profile_id_by_tg(tg_id)
    if not profile_id:
        return found

    for table in TABLES:
        rows = await db_fetchall(
            f"""
            SELECT id
            FROM `{table}`
            WHERE `{POST_OWNER_FIELD}` = %s
            """,
            (profile_id,)
        )
        for r in rows:
            found.append((table, int(r["id"])))

    return found

# ------------------- Handlers -------------------
@dp.message(Command("start"))
async def start_handler(message: types.Message):
    await message.answer(
        "Натисніть кнопку, щоб побачити усі пости, пов'язані з твоїм Telegram:",
        reply_markup=start_kb()
    )

@dp.callback_query(lambda c: c.data == "list_posts")
async def list_posts_callback(callback: types.CallbackQuery):
    tg_id_str = str(callback.from_user.id)
    tg_username_norm = norm_username(callback.from_user.username)

    found_posts = await get_posts_for_user(tg_id_str, tg_username_norm)

    if not found_posts:
        await callback.message.answer("Пости пов'язаних з вашим Telegram, не знайдено.")
        await callback.answer()
        return

    await callback.message.answer("Знайдено пости. Виберіть дію:", reply_markup=posts_kb(found_posts))
    await callback.answer()

@dp.callback_query(lambda c: c.data.startswith("del:"))
async def delete_ask_confirm(callback: types.CallbackQuery):
    _, table, post_id_str = callback.data.split(":")
    post_id = int(post_id_str)
    if table not in TABLES:
        await callback.answer("некоректна таблиця", show_alert=True)
        return

    await callback.message.answer(f"точно видалити пост #{post_id}?", reply_markup=delete_confirm_kb(table, post_id))
    await callback.answer()

@dp.callback_query(lambda c: c.data.startswith("del_yes:"))
async def delete_confirmed(callback: types.CallbackQuery):
    tg_id_str = str(callback.from_user.id)
    tg_username_norm = norm_username(callback.from_user.username)

    _, table, post_id_str = callback.data.split(":")
    post_id = int(post_id_str)

    if table not in TABLES:
        await callback.answer("некоректна таблиця", show_alert=True)
        return

    tg_table = TG_MIRROR.get(table)

    try:
        row = await db_fetchone(f"SELECT chat_id, message_id FROM `{table}` WHERE id=%s", (post_id,))
        if not row or not await ensure_owner(table, post_id, tg_id_str, tg_username_norm):
            await callback.message.answer("❌ Не вдалося видалити (немає прав чи пост не знайдено).")
            await callback.answer()
            return

        chat_id = row.get("chat_id")
        message_id = row.get("message_id")

        tg_deleted = False
        if tg_table:
            tg_deleted = await delete_from_mirror_by_tg_ids(tg_table, chat_id, message_id)

        await db_execute(f"DELETE FROM `{table}` WHERE id=%s", (post_id,))
        await db_commit()

        await callback.message.answer(
            f"🗑 пост #{post_id} видален.\n"
            f"TG запис: {'видалино' if tg_deleted else 'не знайдено'}"
        )

    except Exception as e:
        await db_rollback()
        await callback.message.answer(f"❌ помилка видалення: {e}")

    await callback.answer()

@dp.callback_query(lambda c: c.data == "del_no")
async def delete_cancel(callback: types.CallbackQuery):
    await callback.message.answer("добре, видалення скасовано.")
    await callback.answer()

# --- Move single: ask choice ---
@dp.callback_query(lambda c: c.data.startswith("mv:"))
async def move_to_account_ask(callback: types.CallbackQuery):
    tg_id_str = str(callback.from_user.id)
    tg_username_norm = norm_username(callback.from_user.username)

    _, table, post_id_str = callback.data.split(":")
    post_id = int(post_id_str)

    if table not in TABLES:
        await callback.answer("некоректна таблиц.", show_alert=True)
        return

    if not await ensure_owner(table, post_id, tg_id_str, tg_username_norm):
        await callback.answer("пост не найден или не ваш", show_alert=True)
        return

    await callback.message.answer(
        "перенос поста на аккаунт.\n виберіть дію:",
        reply_markup=account_choice_kb(table, post_id, is_all=False)
    )
    await callback.answer()

# --- Move all: ask choice ---
@dp.callback_query(lambda c: c.data == "mv_all")
async def move_all_ask(callback: types.CallbackQuery):
    tg_id_str = str(callback.from_user.id)
    tg_username_norm = norm_username(callback.from_user.username)

    found_posts = await get_posts_for_user(tg_id_str, tg_username_norm)
    if not found_posts:
        await callback.answer("у вас немає постов для переноса.", show_alert=True)
        return

    await callback.message.answer(
        f"перенос ВСІХ постов на аккаунт.\nзнайдено: {len(found_posts)}.\nоберіть варіант:",
        reply_markup=account_choice_kb(None, None, is_all=True)
    )
    await callback.answer()

# --- Already has account (single): ask for code ---
@dp.callback_query(lambda c: c.data.startswith("mv_has:"))
async def move_to_account_has(callback: types.CallbackQuery):
    tg_id = callback.from_user.id
    tg_id_str = str(tg_id)
    tg_username_norm = norm_username(callback.from_user.username)

    _, table, post_id_str = callback.data.split(":")
    post_id = int(post_id_str)

    if table not in TABLES:
        await callback.answer("некоректна таблиця", show_alert=True)
        return

    if not await ensure_owner(table, post_id, tg_id_str, tg_username_norm):
        await callback.answer("пост не знайден або він не ваш.", show_alert=True)
        return

    PENDING_ACTION[tg_id] = {"mode": "single", "table": table, "post_id": post_id, "posts": []}

    await callback.message.answer(
        f"добре. Введіть код прив'язки із профілю на сайті.\n"
        f"переносимо пост #{post_id}.\n"
        f"відправьте код сюди (приклад: 482913)."
    )
    await callback.answer()

# --- Already has account (all): ask for code ---
@dp.callback_query(lambda c: c.data == "mv_has_all")
async def move_all_has(callback: types.CallbackQuery):
    tg_id = callback.from_user.id
    tg_id_str = str(tg_id)
    tg_username_norm = norm_username(callback.from_user.username)

    found_posts = await get_posts_for_user(tg_id_str, tg_username_norm)
    if not found_posts:
        await callback.answer("у вас немає постов для переноса.", show_alert=True)
        return

    PENDING_ACTION[tg_id] = {"mode": "all", "table": None, "post_id": None, "posts": found_posts}

    await callback.message.answer(
        f"добре. Введіть код прив'язки із профілю на сайті.\n"
        f"переносимо ВСі пости: {len(found_posts)}.\n"
        f"відправьте код сюди (приклад: 482913)."
    )
    await callback.answer()

# --- Create new account (single/all) ---
@dp.callback_query(lambda c: c.data.startswith("mv_new:"))
async def move_to_account_new(callback: types.CallbackQuery):
    _, table, post_id_str = callback.data.split(":")
    post_id = int(post_id_str)
    await callback.message.answer(
        "Ок. Створи обліковий запис на сайті і натисніть кнопку нижче:",
        reply_markup=after_register_kb(table, post_id, is_all=False)
    )
    await callback.answer()

@dp.callback_query(lambda c: c.data == "mv_new_all")
async def move_all_new(callback: types.CallbackQuery):
    await callback.message.answer(
        "Ок. Створи обліковий запис на сайті і натисніть кнопку нижче:",
        reply_markup=after_register_kb(None, None, is_all=True)
    )
    await callback.answer()

@dp.callback_query(lambda c: c.data == "mv_cancel")
async def mv_cancel(callback: types.CallbackQuery):
    PENDING_ACTION.pop(callback.from_user.id, None)
    await callback.message.answer("Ок, отменил.")
    await callback.answer()

@dp.callback_query(lambda c: c.data == "noop")
async def noop(callback: types.CallbackQuery):
    await callback.answer()

# --- Receive code: move single/all ---
@dp.message()
async def handle_move_code(message: types.Message):
    tg_id = message.from_user.id
    if tg_id not in PENDING_ACTION:
        return

    # anti brute force
    allowed, rem = register_attempt(tg_id)
    if not allowed:
        await message.answer(f"⛔ Занадто багато спроб. Спробуй через {rem} сек.")
        return

    tg_id_str = str(tg_id)
    tg_username_norm = norm_username(message.from_user.username)
    code = message.text.strip()

    action = PENDING_ACTION[tg_id]
    mode = action["mode"]

    try:
        # 1) validate code -> profile_id
        row = await db_fetchone(
            f"""
            SELECT user_id
            FROM `{LINK_CODES_TABLE}`
            WHERE code=%s AND used=0 AND expires_at > UTC_TIMESTAMP()
            LIMIT 1
            """,
            (code,)
        )
        if not row:
            await message.answer("❌ Код неправильний або минув. Згенеруйте новий на сайті та спробуйте знову.")
            return

        profile_id = int(row["user_id"])

        # 2) bind telegram to profile (nice UX)
        await db_execute(
            f"""
            UPDATE `{PROFILE_TABLE}`
            SET user_id=%s, telegram_username=%s
            WHERE id=%s
            """,
            (tg_id, (message.from_user.username or ""), profile_id)
        )

        moved = 0
        already = 0
        skipped = 0

        if mode == "single":
            table = action["table"]
            post_id = int(action["post_id"])

            if not await ensure_owner(table, post_id, tg_id_str, tg_username_norm):
                await db_rollback()
                await message.answer("❌ Ця посада не збігається з вашим Telegram (telegram id/username в БД інші).")
                PENDING_ACTION.pop(tg_id, None)
                return

            post_row = await db_fetchone(
                f"SELECT `{POST_OWNER_FIELD}` FROM `{table}` WHERE id=%s LIMIT 1",
                (post_id,)
            )
            if not post_row:
                await db_rollback()
                await message.answer("❌ Пост не знайдено. Натисніть 'Показати мої пости' і спробуй знову.")
                PENDING_ACTION.pop(tg_id, None)
                return

            current_owner = int(post_row[POST_OWNER_FIELD])
            if current_owner == profile_id:
                already = 1
            else:
                await db_execute(
                    f"UPDATE `{table}` SET `{POST_OWNER_FIELD}`=%s WHERE id=%s",
                    (profile_id, post_id)
                )
                moved = 1

        else:
            posts: list[tuple[str, int]] = action["posts"]

            for table, post_id in posts:
                # ownership check
                if not await ensure_owner(table, post_id, tg_id_str, tg_username_norm):
                    skipped += 1
                    continue

                post_row = await db_fetchone(
                    f"SELECT `{POST_OWNER_FIELD}` FROM `{table}` WHERE id=%s LIMIT 1",
                    (post_id,)
                )
                if not post_row:
                    skipped += 1
                    continue

                current_owner = int(post_row[POST_OWNER_FIELD])
                if current_owner == profile_id:
                    already += 1
                    continue

                await db_execute(
                    f"UPDATE `{table}` SET `{POST_OWNER_FIELD}`=%s WHERE id=%s",
                    (profile_id, post_id)
                )
                moved += 1

        # 3) mark code used
        await db_execute(f"UPDATE `{LINK_CODES_TABLE}` SET used=1 WHERE code=%s", (code,))
        await db_commit()

        if mode == "single":
            await message.answer(
                f"✅ готово!\n"
                f"перенесено: {moved}\n"
                f"вже було прив'язано: {already}"
            )
        else:
            await message.answer(
                f"✅ готово! Перенос ВСІХ постов завершено.\n"
                f"перенесено: {moved}\n"
                f"вже було прив'язано: {already}\n"
                f"Пропущено (не збіглися telegram поля/не знайдено): {skipped}"
            )

        PENDING_ACTION.pop(tg_id, None)

    except Exception as e:
        await db_rollback()
        await message.answer(f"❌ помилка переноса: {e}")

# ------------------- Run -------------------
async def main():
    print("Бот запущенно...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    finally:
        cursor.close()
        conn.close()
