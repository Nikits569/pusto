import asyncio
import os
import time
from datetime import datetime
from typing import Any

import pymysql
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from config import TOKEN, ADMIN_CHAT_ID, DB_CONFIG

# ------------------- CONFIG -------------------
DEBUG = True

TABLES = ["ads_thingspost", "ads_jobpost", "ads_neighborpost"]

TG_MIRROR = {
    "ads_thingspost": "productsTest",
    "ads_jobpost": "jobsTest",
    "ads_neighborpost": "neighborsTest",
}

PROFILE_TABLE = "accounts_profile"
LINK_CODES_TABLE = "tg_link_codes"

POST_OWNER_FIELD = "user_id"
POST_TELEGRAM_FIELD = "telegram_id"

# ВАЖНО:
# Если после переноса пост должен стать "обычным аккаунтным",
# лучше очистить telegram_id.
CLEAR_TELEGRAM_AFTER_TRANSFER = True

if not TOKEN:
    raise RuntimeError("BOT_TOKEN is not set")

PENDING_ACTION: dict[int, dict[str, Any]] = {}
PENDING_SUPPORT: dict[int, bool] = {}

MAX_ATTEMPTS = 5
WINDOW_SEC = 10 * 60
LOCK_SEC = 10 * 60
ATTEMPTS: dict[int, list[float]] = {}
LOCKED_UNTIL: dict[int, float] = {}


def debug_log(*args):
    if DEBUG:
        print("[DEBUG]", *args)


def now_ts() -> float:
    return time.time()


def is_locked(tg_id: int) -> int:
    until = LOCKED_UNTIL.get(tg_id)
    if not until:
        return 0

    rem = int(until - now_ts())
    if rem <= 0:
        LOCKED_UNTIL.pop(tg_id, None)
        return 0
    return rem


def register_attempt(tg_id: int) -> tuple[bool, int]:
    rem = is_locked(tg_id)
    if rem > 0:
        return False, rem

    t = now_ts()
    lst = ATTEMPTS.get(tg_id, [])
    lst = [x for x in lst if t - x <= WINDOW_SEC]
    lst.append(t)
    ATTEMPTS[tg_id] = lst

    if len(lst) > MAX_ATTEMPTS:
        LOCKED_UNTIL[tg_id] = t + LOCK_SEC
        return False, LOCK_SEC

    return True, 0


# ------------------- MySQL -------------------
conn = pymysql.connect(**DB_CONFIG)

DB_LOCK = asyncio.Lock()


def ensure_connection():
    global conn

    try:
        conn.ping(reconnect=True)
    except Exception:
        try:
            conn.close()
        except Exception:
            pass

        conn = pymysql.connect(**DB_CONFIG)
        


def _db_fetchone_sync(query: str, params: tuple = ()) -> dict | None:
    ensure_connection()
    with conn.cursor() as cursor:
        cursor.execute(query, params)
        return cursor.fetchone()


def _db_fetchall_sync(query: str, params: tuple = ()) -> list[dict]:
    ensure_connection()
    with conn.cursor() as cursor:
        cursor.execute(query, params)
        return cursor.fetchall()


def _db_execute_sync(query: str, params: tuple = ()) -> int:
    ensure_connection()
    with conn.cursor() as cursor:
        cursor.execute(query, params)
        return cursor.rowcount


async def db_commit():
    async with DB_LOCK:
        await asyncio.to_thread(lambda: (ensure_connection(), conn.commit()))


async def db_rollback():
    async with DB_LOCK:
        await asyncio.to_thread(lambda: (ensure_connection(), conn.rollback()))


async def db_fetchone(query: str, params: tuple = ()) -> dict | None:
    async with DB_LOCK:
        return await asyncio.to_thread(_db_fetchone_sync, query, params)


async def db_fetchall(query: str, params: tuple = ()) -> list[dict]:
    async with DB_LOCK:
        return await asyncio.to_thread(_db_fetchall_sync, query, params)


async def db_execute(query: str, params: tuple = ()) -> int:
    async with DB_LOCK:
        return await asyncio.to_thread(_db_execute_sync, query, params)





# ------------------- Bot -------------------
bot = Bot(token=TOKEN)
dp = Dispatcher(storage=MemoryStorage())


# ------------------- UI -------------------
def start_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="показати мої пости", callback_data="list_posts")]
        ]
    )


def posts_kb(found_posts: list[tuple[str, int, str]]) -> InlineKeyboardMarkup:
    kb = []
    for table, post_id, title in found_posts:
        kb.append([
            InlineKeyboardButton(text=f"{title} (#{post_id})", callback_data="noop")
        ])
        kb.append([
            InlineKeyboardButton(text="🗑 видалити", callback_data=f"del:{table}:{post_id}"),
            InlineKeyboardButton(text="➡️ перенести на аккаунт", callback_data=f"mv:{table}:{post_id}"),
        ])

    kb.append([InlineKeyboardButton(text="➡️ перенести ВСІ пости", callback_data="mv_all")])
    kb.append([InlineKeyboardButton(text="🔄 оновити", callback_data="list_posts")])
    return InlineKeyboardMarkup(inline_keyboard=kb)


def no_posts_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="✉️ написати адміністратору", callback_data="contact_admin")],
            [InlineKeyboardButton(text="🔄 спробувати ще раз", callback_data="list_posts")],
        ]
    )


def delete_confirm_kb(table: str, post_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[
            InlineKeyboardButton(text="✅ так, видалити", callback_data=f"del_yes:{table}:{post_id}"),
            InlineKeyboardButton(text="❌ скасування", callback_data="del_no"),
        ]]
    )


def account_choice_kb(table: str | None, post_id: int | None, is_all: bool = False) -> InlineKeyboardMarkup:
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
            [InlineKeyboardButton(text="🌐 відкрити сайт (реєстрація)", url="https://bursa.sk/register")],
            [InlineKeyboardButton(text="✅ я зареєструвався — перенести", callback_data=has)],
            [InlineKeyboardButton(text="❌ скасувати", callback_data="mv_cancel")],
        ]
    )


def support_cancel_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="❌ скасувати", callback_data="cancel_support")]
        ]
    )


# ------------------- Helpers -------------------
#def is_code_expired(expires_at) -> bool:
#    if expires_at is None:
#        return False
#
#    if isinstance(expires_at, datetime):
#        return expires_at < datetime.now()
#
#    try:
#        parsed = datetime.fromisoformat(str(expires_at))
#        return parsed < datetime.now()
#    except Exception:
#        return False


async def get_posts_for_user(tg_id: int) -> list[tuple[str, int, str]]:
    found = []

    for table in TABLES:
        rows = await db_fetchall(
            f"""
            SELECT id, title, `{POST_OWNER_FIELD}`, `{POST_TELEGRAM_FIELD}`
            FROM `{table}`
            WHERE `{POST_TELEGRAM_FIELD}` = %s
            ORDER BY id DESC
            """,
            (tg_id,)
        )

        debug_log("get_posts_for_user:", table, "tg_id=", tg_id, "rows=", rows)

        for r in rows:
            found.append((table, int(r["id"]), r.get("title") or "Без назви"))

    return found


async def ensure_owner_by_tg(table: str, post_id: int, tg_id: int) -> bool:
    row = await db_fetchone(
        f"""
        SELECT id
        FROM `{table}`
        WHERE id=%s AND `{POST_TELEGRAM_FIELD}`=%s
        LIMIT 1
        """,
        (post_id, tg_id)
    )
    debug_log("ensure_owner_by_tg:", table, post_id, tg_id, row)
    return row is not None


async def send_admin_request(user: types.User, text: str):
    username = f"@{user.username}" if user.username else "немає"
    full_name = user.full_name or "без імені"

    msg = (
        "📩 Нове звернення до адміністратора\n\n"
        f"👤 User: {full_name}\n"
        f"🆔 TG ID: {user.id}\n"
        f"🔗 Username: {username}\n\n"
        f"Повідомлення:\n{text}"
    )
    await bot.send_message(ADMIN_CHAT_ID, msg)


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
        rc = await db_execute(
            f"DELETE FROM `{tg_table}` WHERE message_id=%s",
            (message_id,)
        )
        return rc > 0

    return False


async def transfer_post_to_user(table: str, post_id: int, tg_id: int, profile_id: int) -> tuple[str, str]:
    """
    Возвращает:
    - status: moved / already / skipped
    - detail: пояснение
    """
    post_row = await db_fetchone(
        f"""
        SELECT id, `{POST_OWNER_FIELD}`, `{POST_TELEGRAM_FIELD}`, title
        FROM `{table}`
        WHERE id=%s
        LIMIT 1
        """,
        (post_id,)
    )
    debug_log("transfer_post_to_user post_row =", post_row)

    if not post_row:
        return "skipped", "post not found"

    current_owner = post_row.get(POST_OWNER_FIELD)
    current_tg = post_row.get(POST_TELEGRAM_FIELD)

    if current_owner is not None:
        current_owner = int(current_owner)
    if current_tg is not None:
        current_tg = int(current_tg)

    debug_log(
        "transfer state:",
        {
            "table": table,
            "post_id": post_id,
            "current_owner": current_owner,
            "current_tg": current_tg,
            "target_profile_id": profile_id,
            "incoming_tg_id": tg_id,
        }
    )

    # Уже привязан и telegram_id уже очищен/нормальный
    if current_owner == profile_id and (
        not CLEAR_TELEGRAM_AFTER_TRANSFER or current_tg is None or current_tg != tg_id
    ):
        return "already", "already assigned"

    if CLEAR_TELEGRAM_AFTER_TRANSFER:
        await db_execute(
            f"""
            UPDATE `{table}`
            SET `{POST_OWNER_FIELD}`=%s,
                `{POST_TELEGRAM_FIELD}`=NULL
            WHERE id=%s
            """,
            (profile_id, post_id)
        )
        return "moved", "owner set and telegram_id cleared"
    else:
        await db_execute(
            f"""
            UPDATE `{table}`
            SET `{POST_OWNER_FIELD}`=%s
            WHERE id=%s
            """,
            (profile_id, post_id)
        )
        return "moved", "owner set"


# ------------------- Handlers -------------------
@dp.message(Command("start"))
async def start_handler(message: types.Message):
    await message.answer(
        "Натисніть кнопку, щоб побачити усі пости, пов'язані з вашим Telegram:",
        reply_markup=start_kb()
    )


@dp.message(Command("id"))
async def my_id_handler(message: types.Message):
    await message.answer(f"Ваш Telegram ID: {message.from_user.id}")


@dp.callback_query(lambda c: c.data == "list_posts")
async def list_posts_callback(callback: types.CallbackQuery):
    tg_id = callback.from_user.id

    try:
        found_posts = await get_posts_for_user(tg_id)

        if not found_posts:
            await callback.message.answer("Пости не знайдено.", reply_markup=no_posts_kb())
            await callback.answer()
            return

        await callback.message.answer(
            "Знайдено пости. Виберіть дію:",
            reply_markup=posts_kb(found_posts)
        )
        await callback.answer()


    except Exception as e:
        import traceback
        traceback.print_exc()
        await callback.message.answer(
            f"❌ Помилка пошуку постів: {type(e).__name__}: {repr(e)}"

        )
        await callback.answer()


@dp.callback_query(lambda c: c.data == "contact_admin")
async def contact_admin_start(callback: types.CallbackQuery):
    PENDING_SUPPORT[callback.from_user.id] = True
    await callback.message.answer(
        "Опишіть проблему одним повідомленням. Я перешлю його адміністратору.",
        reply_markup=support_cancel_kb()
    )
    await callback.answer()


@dp.callback_query(lambda c: c.data == "cancel_support")
async def cancel_support(callback: types.CallbackQuery):
    PENDING_SUPPORT.pop(callback.from_user.id, None)
    await callback.message.answer("Звернення до адміністратора скасовано.")
    await callback.answer()


@dp.callback_query(lambda c: c.data.startswith("del:"))
async def delete_ask_confirm(callback: types.CallbackQuery):
    _, table, post_id_str = callback.data.split(":")
    post_id = int(post_id_str)

    if table not in TABLES:
        await callback.answer("Некоректна таблиця", show_alert=True)
        return

    await callback.message.answer(
        f"Точно видалити пост #{post_id}?",
        reply_markup=delete_confirm_kb(table, post_id)
    )
    await callback.answer()


@dp.callback_query(lambda c: c.data.startswith("del_yes:"))
async def delete_confirmed(callback: types.CallbackQuery):
    tg_id = callback.from_user.id
    _, table, post_id_str = callback.data.split(":")
    post_id = int(post_id_str)

    if table not in TABLES:
        await callback.answer("Некоректна таблиця", show_alert=True)
        return

    tg_table = TG_MIRROR.get(table)

    try:
        if not await ensure_owner_by_tg(table, post_id, tg_id):
            await callback.message.answer("❌ Не вдалося видалити: пост не знайдено або він не ваш.")
            await callback.answer()
            return

        row = await db_fetchone(
            f"SELECT chat_id, message_id FROM `{table}` WHERE id=%s LIMIT 1",
            (post_id,)
        )
        if not row:
            await callback.message.answer("❌ Пост не знайдено.")
            await callback.answer()
            return

        tg_deleted = False
        if tg_table:
            tg_deleted = await delete_from_mirror_by_tg_ids(
                tg_table,
                row.get("chat_id"),
                row.get("message_id")
            )

        await db_execute(f"DELETE FROM `{table}` WHERE id=%s", (post_id,))
        await db_commit()

        await callback.message.answer(
            f"🗑 Пост #{post_id} видалено.\n"
            f"TG запис: {'видалено' if tg_deleted else 'не знайдено'}"
        )

    except Exception as e:
        await db_rollback()
        await callback.message.answer(f"❌ Помилка видалення: {e}")

    await callback.answer()


@dp.callback_query(lambda c: c.data == "del_no")
async def delete_cancel(callback: types.CallbackQuery):
    await callback.message.answer("Добре, видалення скасовано.")
    await callback.answer()


@dp.callback_query(lambda c: c.data.startswith("mv:"))
async def move_to_account_ask(callback: types.CallbackQuery):
    tg_id = callback.from_user.id
    _, table, post_id_str = callback.data.split(":")
    post_id = int(post_id_str)

    if table not in TABLES:
        await callback.answer("Некоректна таблиця", show_alert=True)
        return

    if not await ensure_owner_by_tg(table, post_id, tg_id):
        await callback.answer("Пост не знайдено або він не ваш", show_alert=True)
        return

    await callback.message.answer(
        "Перенесення поста на акаунт.\nВиберіть дію:",
        reply_markup=account_choice_kb(table, post_id, is_all=False)
    )
    await callback.answer()


@dp.callback_query(lambda c: c.data == "mv_all")
async def move_all_ask(callback: types.CallbackQuery):
    tg_id = callback.from_user.id
    found_posts = await get_posts_for_user(tg_id)

    if not found_posts:
        await callback.answer("У вас немає постів для перенесення.", show_alert=True)
        return

    await callback.message.answer(
        f"Перенесення ВСІХ постів на акаунт.\nЗнайдено: {len(found_posts)}.\nОберіть варіант:",
        reply_markup=account_choice_kb(None, None, is_all=True)
    )
    await callback.answer()


@dp.callback_query(lambda c: c.data.startswith("mv_has:"))
async def move_to_account_has(callback: types.CallbackQuery):
    tg_id = callback.from_user.id
    _, table, post_id_str = callback.data.split(":")
    post_id = int(post_id_str)

    if table not in TABLES:
        await callback.answer("Некоректна таблиця", show_alert=True)
        return

    if not await ensure_owner_by_tg(table, post_id, tg_id):
        await callback.answer("Пост не знайдено або він не ваш.", show_alert=True)
        return

    PENDING_ACTION[tg_id] = {
        "mode": "single",
        "table": table,
        "post_id": post_id,
        "posts": [],
    }

    debug_log("PENDING_ACTION single =", PENDING_ACTION[tg_id])

    await callback.message.answer(
        f"Добре. Введіть код прив'язки із профілю на сайті.\n"
        f"Переносимо пост #{post_id}.\n"
        f"Надішліть код сюди."
    )
    await callback.answer()


@dp.callback_query(lambda c: c.data == "mv_has_all")
async def move_all_has(callback: types.CallbackQuery):
    tg_id = callback.from_user.id
    found_posts = await get_posts_for_user(tg_id)

    if not found_posts:
        await callback.answer("У вас немає постів для перенесення.", show_alert=True)
        return

    PENDING_ACTION[tg_id] = {
        "mode": "all",
        "table": None,
        "post_id": None,
        "posts": found_posts,
    }

    debug_log("PENDING_ACTION all =", PENDING_ACTION[tg_id])

    await callback.message.answer(
        f"Добре. Введіть код прив'язки із профілю на сайті.\n"
        f"Переносимо ВСІ пости: {len(found_posts)}.\n"
        f"Надішліть код сюди."
    )
    await callback.answer()


@dp.callback_query(lambda c: c.data.startswith("mv_new:"))
async def move_to_account_new(callback: types.CallbackQuery):
    _, table, post_id_str = callback.data.split(":")
    post_id = int(post_id_str)

    await callback.message.answer(
        "Ок. Створіть обліковий запис на сайті і натисніть кнопку нижче:",
        reply_markup=after_register_kb(table, post_id, is_all=False)
    )
    await callback.answer()


@dp.callback_query(lambda c: c.data == "mv_new_all")
async def move_all_new(callback: types.CallbackQuery):
    await callback.message.answer(
        "Ок. Створіть обліковий запис на сайті і натисніть кнопку нижче:",
        reply_markup=after_register_kb(None, None, is_all=True)
    )
    await callback.answer()


@dp.callback_query(lambda c: c.data == "mv_cancel")
async def mv_cancel(callback: types.CallbackQuery):
    PENDING_ACTION.pop(callback.from_user.id, None)
    await callback.message.answer("Ок, дію скасовано.")
    await callback.answer()


@dp.callback_query(lambda c: c.data == "noop")
async def noop(callback: types.CallbackQuery):
    await callback.answer()


@dp.message()
async def handle_text_message(message: types.Message):
    tg_id = message.from_user.id
    text = (message.text or "").strip()

    if tg_id in PENDING_SUPPORT:
        if not text:
            await message.answer("Надішліть текстове повідомлення для адміністратора.")
            return

        try:
            await send_admin_request(message.from_user, text)
            await message.answer("✅ Повідомлення адміністратору відправлено.")
        except Exception as e:
            await message.answer(f"❌ Не вдалося відправити повідомлення адміністратору: {e}")
        finally:
            PENDING_SUPPORT.pop(tg_id, None)
        return

    if tg_id not in PENDING_ACTION:
        await message.answer(
            "👋 Щоб почати роботу з ботом, напишіть /start"
        )
        return

    allowed, rem = register_attempt(tg_id)
    if not allowed:
        await message.answer(f"⛔ Забагато спроб. Спробуйте через {rem} сек.")
        return

    code = text.strip()

    if not code:
        await message.answer("❌ Надішліть код.")
        return

    action = PENDING_ACTION[tg_id]
    mode = action["mode"]

    debug_log("INPUT tg_id =", tg_id)
    debug_log("INPUT code =", repr(code))
    debug_log("INPUT action =", action)

    try:
        # 1. Найти код
        code_row = await db_fetchone(
            f"""
            SELECT id, user_id, code, used, expires_at
            FROM `{LINK_CODES_TABLE}`
            WHERE code=%s
            LIMIT 1
            """,
            (code,)
        )
        debug_log("code_row =", code_row)

        if not code_row:
            await message.answer("❌ Код не знайдено.")
            return

        if int(code_row["used"]) == 1:
            await message.answer("❌ Цей код вже використано. Згенеруйте новий код у профілі.")
            return

        #if is_code_expired(code_row.get("expires_at")):
        #    await message.answer("❌ Термін дії коду закінчився. Згенеруйте новий код у профілі.")
        #    return

        profile_id = int(code_row["user_id"])
        debug_log("profile_id =", profile_id)

        # 2. Проверить пользователя
        profile_row = await db_fetchone(
            f"""
            SELECT id, telegram_id, email
            FROM `{PROFILE_TABLE}`
            WHERE id=%s
            LIMIT 1
            """,
            (profile_id,)
        )
        debug_log("profile_row =", profile_row)

        if not profile_row:
            await message.answer("❌ Профіль для цього коду не знайдено.")
            return

        # 3. Проверка: не привязан ли этот TG к другому аккаунту
        existing_profile = await db_fetchone(
            f"""
            SELECT id, telegram_id
            FROM `{PROFILE_TABLE}`
            WHERE telegram_id=%s
            LIMIT 1
            """,
            (tg_id,)
        )
        debug_log("existing_profile =", existing_profile)

        if existing_profile and int(existing_profile["id"]) != profile_id:
            await message.answer("❌ Цей Telegram вже прив'язаний до іншого акаунта.")
            PENDING_ACTION.pop(tg_id, None)
            return

        # 4. Привязать telegram_id к аккаунту
        await db_execute(
            f"""
            UPDATE `{PROFILE_TABLE}`
            SET telegram_id=%s
            WHERE id=%s
            """,
            (tg_id, profile_id)
        )

        # 5. Перенос постов
        moved = 0
        already = 0
        skipped = 0

        # 5. Перенос постов
        if mode == "single":
            table = action["table"]
            post_id = int(action["post_id"])

            post_row = await db_fetchone(
                f"""
                SELECT id, `{POST_OWNER_FIELD}`, `{POST_TELEGRAM_FIELD}`, title
                FROM `{table}`
                WHERE id=%s
                LIMIT 1
                """,
                (post_id,)
            )
            debug_log("single post_row =", post_row)

            if not post_row:
                await db_rollback()
                await message.answer("❌ Пост не знайдено.")
                PENDING_ACTION.pop(tg_id, None)
                return

            current_owner = post_row.get(POST_OWNER_FIELD)
            current_tg = post_row.get(POST_TELEGRAM_FIELD)

            if current_owner is not None:
                current_owner = int(current_owner)
            if current_tg is not None:
                current_tg = int(current_tg)

            # Если owner уже тот же, но telegram_id ещё остался —
            # всё равно надо "дожать" перенос и очистить telegram_id
            if current_owner == profile_id and current_tg != tg_id:
                already = 1
            else:
                await db_execute(
                    f"""
                    UPDATE `{table}`
                    SET `{POST_OWNER_FIELD}`=%s,
                        `{POST_TELEGRAM_FIELD}`=NULL
                    WHERE id=%s
                    """,
                    (profile_id, post_id)
                )
                moved = 1

        else:
            posts = action["posts"]

            for table, post_id, _title in posts:
                post_row = await db_fetchone(
                    f"""
                    SELECT id, `{POST_OWNER_FIELD}`, `{POST_TELEGRAM_FIELD}`, title
                    FROM `{table}`
                    WHERE id=%s
                    LIMIT 1
                    """,
                    (post_id,)
                )
                debug_log("all post_row =", post_row)

                if not post_row:
                    skipped += 1
                    continue

                current_owner = post_row.get(POST_OWNER_FIELD)
                current_tg = post_row.get(POST_TELEGRAM_FIELD)

                if current_owner is not None:
                    current_owner = int(current_owner)
                if current_tg is not None:
                    current_tg = int(current_tg)

                # Уже полностью перенесён только если owner тот же
                # и telegram_id уже не равен текущему tg_id
                if current_owner == profile_id and current_tg != tg_id:
                    already += 1
                    continue

                await db_execute(
                    f"""
                    UPDATE `{table}`
                    SET `{POST_OWNER_FIELD}`=%s,
                        `{POST_TELEGRAM_FIELD}`=NULL
                    WHERE id=%s
                    """,
                    (profile_id, post_id)
                )
                moved += 1

        # 6. Пометить код использованным
        await db_execute(
            f"""
            UPDATE `{LINK_CODES_TABLE}`
            SET used=1
            WHERE id=%s
            """,
            (code_row["id"],)
        )

        await db_commit()

        if mode == "single":
            await message.answer(
                f"✅ Готово!\n"
                f"Перенесено: {moved}\n"
                f"Вже було прив'язано: {already}\n"
                f"Пропущено: {skipped}"
            )
        else:
            await message.answer(
                f"✅ Готово! Перенесення ВСІХ постів завершено.\n"
                f"Перенесено: {moved}\n"
                f"Вже було прив'язано: {already}\n"
                f"Пропущено: {skipped}"
            )

        PENDING_ACTION.pop(tg_id, None)

    except Exception as e:
        await db_rollback()
        debug_log("ERROR =", repr(e))
        await message.answer(f"❌ Помилка перенесення: {e}")


# ------------------- Run -------------------
async def main():
    print("Бот запущено...")
    await dp.start_polling(bot)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    finally:
        conn.close()