# handlers/posts.py
import asyncio
import pymysql
import time

from aiogram import types
from aiogram.filters import Command
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from config import *

# --- состояние ---
PENDING_ACTION = {}

# --- защита от подбора ---
MAX_ATTEMPTS = 5
WINDOW_SEC = 10 * 60
LOCK_SEC = 10 * 60
ATTEMPTS = {}
LOCKED_UNTIL = {}

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
        return (False, rem)

    t = now_ts()
    lst = ATTEMPTS.get(tg_id, [])
    lst = [x for x in lst if t - x <= WINDOW_SEC]
    lst.append(t)
    ATTEMPTS[tg_id] = lst

    if len(lst) > MAX_ATTEMPTS:
        LOCKED_UNTIL[tg_id] = t + LOCK_SEC
        return (False, LOCK_SEC)

    return (True, 0)

def norm_username(u: str) -> str:
    return (u or "").strip().lstrip("@").lower()

# --- MySQL connection (в одном месте) ---
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

# --- Keyboards ---
def start_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="показати пої пости", callback_data="list_posts")]]
    )

def posts_kb(found_posts: list[tuple[str, int, str]]) -> InlineKeyboardMarkup:
    kb = []
    for table, post_id, title in found_posts:
        shown = title if title else f"Пост #{post_id}"
        kb.append([InlineKeyboardButton(text=str(shown)+' ID-'+str(post_id), callback_data="noop")])
        kb.append([
            InlineKeyboardButton(text="🗑 Удалить", callback_data=f"del:{table}:{post_id}"),
            InlineKeyboardButton(text="➡️ Перенести на аккаунт", callback_data=f"mv:{table}:{post_id}"),
        ])
    kb.append([InlineKeyboardButton(text="➡️ Перенести ВСЕ посты", callback_data="mv_all")])
    kb.append([InlineKeyboardButton(text="🔄 Обновить", callback_data="list_posts")])
    return InlineKeyboardMarkup(inline_keyboard=kb)

def delete_confirm_kb(table: str, post_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[
            InlineKeyboardButton(text="✅ Да, удалить", callback_data=f"del_yes:{table}:{post_id}"),
            InlineKeyboardButton(text="❌ Отмена", callback_data="del_no"),
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
            [InlineKeyboardButton(text="✅ У меня уже есть аккаунт", callback_data=has)],
            [InlineKeyboardButton(text="➕ Создать новый аккаунт", callback_data=new)],
            [InlineKeyboardButton(text="❌ Отмена", callback_data="mv_cancel")],
        ]
    )

def after_register_kb(table: str | None, post_id: int | None, is_all: bool = False) -> InlineKeyboardMarkup:
    has = "mv_has_all" if is_all else f"mv_has:{table}:{post_id}"
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🌐 Открыть сайт (регистрация)", url="https://bursa.sk/register")],
            [InlineKeyboardButton(text="✅ Я зарегистрировался — перенести", callback_data=has)],
            [InlineKeyboardButton(text="❌ Отмена", callback_data="mv_cancel")],
        ]
    )

# --- Business helpers ---
async def ensure_owner(table: str, post_id: int, tg_id_str: str, tg_username_norm: str) -> bool:
    row = await db_fetchone(
        f"""
        SELECT id
        FROM `{table}`
        WHERE id=%s
          AND (
                TRIM(telegram_id)=%s
             OR LOWER(REPLACE(TRIM(telegram_username), '@',''))=%s
          )
        LIMIT 1
        """,
        (post_id, tg_id_str, tg_username_norm)
    )
    return row is not None

async def get_posts_for_user(tg_id_str: str, tg_username_norm: str) -> list[tuple[str, int, str]]:
    found: list[tuple[str, int, str]] = []
    for table in TABLES:
        rows = await db_fetchall(
            f"""
            SELECT id, title
            FROM `{table}`
            WHERE TRIM(telegram_id)=%s
               OR LOWER(REPLACE(TRIM(telegram_username), '@',''))=%s
            """,
            (tg_id_str, tg_username_norm)
        )
        for r in rows:
            title = (r.get("title") or "").strip()
            found.append((table, int(r["id"]), title))
    return found

async def delete_from_mirror_by_tg_ids(tg_table: str, chat_id: str | None, message_id: str | None) -> bool:
    if not message_id:
        return False

    cols = await db_fetchall(f"SHOW COLUMNS FROM `{tg_table}`")
    colset = {r["Field"] for r in cols}

    if "chat_id" in colset and chat_id and "message_id" in colset:
        rc = await db_execute(f"DELETE FROM `{tg_table}` WHERE chat_id=%s AND message_id=%s", (chat_id, message_id))
        return rc > 0

    if "message_id" in colset:
        rc = await db_execute(f"DELETE FROM `{tg_table}` WHERE message_id=%s", (message_id,))
        return rc > 0

    return False

# --- Public register() ---
def register(dp):

    @dp.message(Command("start"))
    async def start_handler(message: types.Message):
        await message.answer(
            "Нажми кнопку, чтобы увидеть все посты, связанные с твоим Telegram:",
            reply_markup=start_kb()
        )

    @dp.callback_query(lambda c: c.data == "list_posts")
    async def list_posts_callback(callback: types.CallbackQuery):
        tg_id_str = str(callback.from_user.id)
        tg_username_norm = norm_username(callback.from_user.username)

        found_posts = await get_posts_for_user(tg_id_str, tg_username_norm)
        if not found_posts:
            await callback.message.answer("Посты, связанные с вашим Telegram, не найдены.")
            await callback.answer()
            return

        await callback.message.answer("Найдены посты. Выберите действие:", reply_markup=posts_kb(found_posts))
        await callback.answer()

    @dp.callback_query(lambda c: c.data.startswith("del:"))
    async def delete_ask_confirm(callback: types.CallbackQuery):
        _, table, post_id_str = callback.data.split(":")
        post_id = int(post_id_str)

        if table not in TABLES:
            await callback.answer("Некорректная таблица.", show_alert=True)
            return

        await callback.message.answer(f"Точно удалить пост #{post_id}?", reply_markup=delete_confirm_kb(table, post_id))
        await callback.answer()

    @dp.callback_query(lambda c: c.data.startswith("del_yes:"))
    async def delete_confirmed(callback: types.CallbackQuery):
        tg_id_str = str(callback.from_user.id)
        tg_username_norm = norm_username(callback.from_user.username)

        _, table, post_id_str = callback.data.split(":")
        post_id = int(post_id_str)

        if table not in TABLES:
            await callback.answer("Некорректная таблица.", show_alert=True)
            return

        tg_table = TG_MIRROR.get(table)

        try:
            row = await db_fetchone(f"SELECT chat_id, message_id FROM `{table}` WHERE id=%s", (post_id,))
            if not row or not await ensure_owner(table, post_id, tg_id_str, tg_username_norm):
                await callback.message.answer("❌ Не удалось удалить (нет прав или пост не найден).")
                await callback.answer()
                return

            tg_deleted = False
            if tg_table:
                tg_deleted = await delete_from_mirror_by_tg_ids(tg_table, row.get("chat_id"), row.get("message_id"))

            await db_execute(f"DELETE FROM `{table}` WHERE id=%s", (post_id,))
            await db_commit()

            await callback.message.answer(
                f"🗑 Пост #{post_id} удалён.\n"
                f"TG запись: {'удалена' if tg_deleted else 'не найдена'}"
            )

        except Exception as e:
            await db_rollback()
            await callback.message.answer(f"❌ Ошибка удаления: {e}")

        await callback.answer()

    @dp.callback_query(lambda c: c.data == "del_no")
    async def delete_cancel(callback: types.CallbackQuery):
        await callback.message.answer("Ок, удаление отменено.")
        await callback.answer()

    @dp.callback_query(lambda c: c.data.startswith("mv:"))
    async def move_to_account_ask(callback: types.CallbackQuery):
        tg_id_str = str(callback.from_user.id)
        tg_username_norm = norm_username(callback.from_user.username)

        _, table, post_id_str = callback.data.split(":")
        post_id = int(post_id_str)

        if table not in TABLES:
            await callback.answer("Некорректная таблица.", show_alert=True)
            return

        if not await ensure_owner(table, post_id, tg_id_str, tg_username_norm):
            await callback.answer("Пост не найден или не ваш.", show_alert=True)
            return

        await callback.message.answer(
            "Перенос поста на аккаунт.\nВыбери вариант:",
            reply_markup=account_choice_kb(table, post_id, is_all=False)
        )
        await callback.answer()

    @dp.callback_query(lambda c: c.data == "mv_all")
    async def move_all_ask(callback: types.CallbackQuery):
        tg_id_str = str(callback.from_user.id)
        tg_username_norm = norm_username(callback.from_user.username)

        found_posts = await get_posts_for_user(tg_id_str, tg_username_norm)
        if not found_posts:
            await callback.answer("У вас нет постов для переноса.", show_alert=True)
            return

        await callback.message.answer(
            f"Перенос ВСЕХ постов на аккаунт.\nНайдено: {len(found_posts)}.\nВыбери вариант:",
            reply_markup=account_choice_kb(None, None, is_all=True)
        )
        await callback.answer()

    @dp.callback_query(lambda c: c.data.startswith("mv_has:"))
    async def move_to_account_has(callback: types.CallbackQuery):
        tg_id = callback.from_user.id
        tg_id_str = str(tg_id)
        tg_username_norm = norm_username(callback.from_user.username)

        _, table, post_id_str = callback.data.split(":")
        post_id = int(post_id_str)

        if table not in TABLES:
            await callback.answer("Некорректная таблица.", show_alert=True)
            return

        if not await ensure_owner(table, post_id, tg_id_str, tg_username_norm):
            await callback.answer("Пост не найден или не ваш.", show_alert=True)
            return

        PENDING_ACTION[tg_id] = {"mode": "single", "table": table, "post_id": post_id, "posts": []}

        await callback.message.answer(
            f"Ок. Введите код привязки из профиля на сайте.\n"
            f"Переносим пост #{post_id}.\n"
            f"Отправьте код сюда (например: 482913)."
        )
        await callback.answer()

    @dp.callback_query(lambda c: c.data == "mv_has_all")
    async def move_all_has(callback: types.CallbackQuery):
        tg_id = callback.from_user.id
        tg_id_str = str(tg_id)
        tg_username_norm = norm_username(callback.from_user.username)

        found_posts = await get_posts_for_user(tg_id_str, tg_username_norm)
        if not found_posts:
            await callback.answer("У вас нет постов для переноса.", show_alert=True)
            return

        PENDING_ACTION[tg_id] = {"mode": "all", "table": None, "post_id": None, "posts": found_posts}

        await callback.message.answer(
            f"Ок. Введите код привязки из профиля на сайте.\n"
            f"Переносим ВСЕ посты: {len(found_posts)}.\n"
            f"Отправьте код сюда (например: 482913)."
        )
        await callback.answer()

    @dp.callback_query(lambda c: c.data.startswith("mv_new:"))
    async def move_to_account_new(callback: types.CallbackQuery):
        _, table, post_id_str = callback.data.split(":")
        post_id = int(post_id_str)
        await callback.message.answer(
            "Ок. Создай аккаунт на сайте и затем нажми кнопку ниже:",
            reply_markup=after_register_kb(table, post_id, is_all=False)
        )
        await callback.answer()

    @dp.callback_query(lambda c: c.data == "mv_new_all")
    async def move_all_new(callback: types.CallbackQuery):
        await callback.message.answer(
            "Ок. Создай аккаунт на сайте и затем нажми кнопку ниже:",
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

    @dp.message()
    async def handle_move_code(message: types.Message):
        tg_id = message.from_user.id
        if tg_id not in PENDING_ACTION:
            return

        allowed, rem = register_attempt(tg_id)
        if not allowed:
            await message.answer(f"⛔ Слишком много попыток. Попробуй через {rem} сек.")
            return

        tg_id_str = str(tg_id)
        tg_username_norm = norm_username(message.from_user.username)
        code = message.text.strip()

        action = PENDING_ACTION[tg_id]
        mode = action["mode"]

        try:
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
                await message.answer("❌ Код неверный или истёк. Сгенерируйте новый на сайте и попробуйте снова.")
                return

            profile_id = int(row["user_id"])

            # bind TG to Profile
            await db_execute(
                f"""
                UPDATE `{PROFILE_TABLE}`
                SET telegram_id=%s, telegram_username=%s
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
                    await message.answer("❌ Этот пост не совпадает с вашим Telegram (telegram_id/username в БД другие).")
                    PENDING_ACTION.pop(tg_id, None)
                    return

                post_row = await db_fetchone(
                    f"SELECT `{POST_OWNER_FIELD}` FROM `{table}` WHERE id=%s LIMIT 1",
                    (post_id,)
                )
                if not post_row:
                    await db_rollback()
                    await message.answer("❌ Пост не найден. Нажми 'Показать мои посты' и попробуй снова.")
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

            await db_execute(f"UPDATE `{LINK_CODES_TABLE}` SET used=1 WHERE code=%s", (code,))
            await db_commit()

            if mode == "single":
                await message.answer(f"✅ Готово!\nПеренесено: {moved}\nУже было привязано: {already}")
            else:
                await message.answer(
                    f"✅ Готово! Перенос ВСЕХ постов завершён.\n"
                    f"Перенесено: {moved}\n"
                    f"Уже было привязано: {already}\n"
                    f"Пропущено: {skipped}"
                )

            PENDING_ACTION.pop(tg_id, None)

        except Exception as e:
            await db_rollback()
            await message.answer(f"❌ Ошибка переноса: {e}")

# optional: graceful close hook if you want later
async def close_db():
    cursor.close()
    conn.close()