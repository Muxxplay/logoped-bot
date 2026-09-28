# -*- coding: utf-8 -*-
"""
LOGOPED YORDAMCHISI — Telegram bot (to'liq inline menyu, 3 tilli versiya)
---------------------------------------------------------------------------
Nutq terapiyasi (logopediya) mashqlari, foydalanuvchi progressi,
fikr-mulohaza tizimi, xavfsiz admin panel va 3 tilli interfeys
(o'zbekcha, ruscha, inglizcha) ga ega bot.

Foydalanuvchi tomonidagi BARCHA menyu ekrandagi (inline) tugmalar orqali
ishlaydi — pastki reply-klaviatura ishlatilmaydi, shu bilan "ikki xil
menyu aralashib ketishi" muammosi butunlay yo'qoladi.

Kutubxona: aiogram 3.x
Baza: SQLite (standart Python kutubxonasi)

ISHGA TUSHIRISH (Windows):
    1) pip install -r requirements.txt
    2) ".env" faylida BOT_TOKEN, ADMIN_IDS, ADMIN_PASSWORD to'ldirilgan bo'lsin
    3) python logoped_bot.py

ESLATMA: Admin panel (o'zbek tilida, pastki tugmalar bilan) faqat admin/ustoz
uchun — u alohida /admin buyrug'i orqali ochiladi, foydalanuvchilarga
ko'rinmaydi.
"""

import asyncio
import logging
import os
import sqlite3
import threading
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from dotenv import load_dotenv
from aiogram import Bot, Dispatcher, Router, F
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardMarkup,
    ReplyKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardRemove,
)
from aiogram.utils.keyboard import InlineKeyboardBuilder

# ============================================================
#                        SOZLAMALAR
# ============================================================

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD")

_admin_ids_raw = os.getenv("ADMIN_IDS", "")
ADMIN_IDS = [int(x.strip()) for x in _admin_ids_raw.split(",") if x.strip()]

if not BOT_TOKEN or not ADMIN_PASSWORD or not ADMIN_IDS:
    raise RuntimeError(
        "BOT_TOKEN, ADMIN_IDS yoki ADMIN_PASSWORD topilmadi. "
        "'.env' faylini yaratganingizga va to'g'ri to'ldirganingizga ishonch hosil qiling."
    )

MAX_LOGIN_ATTEMPTS = 3

# Bazа fayli joylashuvi (serverda o'zgaradi, masalan: /data/logoped.db)
DB_NAME = os.getenv("DB_PATH", "logoped.db")

# Render / Fly / HF Spaces kabi platformalar PORT da eshilish kutadi —
# shuning uchun kichik health-check serveri ishga tushiriladi.
PORT = int(os.getenv("PORT", "0") or 0)
HEALTH_PATH = os.getenv("HEALTH_PATH", "/health")

# Bot qayta ishga tushganda navbatdagi xabarlar YO'QOLMASLIGI uchun False qiling.
# (Faqat birinchi marta o'rnatishda True qo'yish yetarli.)
DROP_PENDING_UPDATES = os.getenv("DROP_PENDING_UPDATES", "false").lower() in ("1", "true", "yes")

LANGUAGES = ["uz", "ru", "en"]

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())
router = Router()
dp.include_router(router)

failed_attempts: dict[int, int] = {}
blocked_users: set[int] = set()

# ============================================================
#                    TARJIMALAR LUG'ATI (T)
# ============================================================

LANG_NAMES = {"uz": "O'zbekcha 🇺🇿", "ru": "Русский 🇷🇺", "en": "English 🇬🇧"}

T = {
    "choose_language": {
        "uz": "Iltimos, tilni tanlang 👇",
        "ru": "Пожалуйста, выберите язык 👇",
        "en": "Please choose a language 👇",
    },
    "language_set": {
        "uz": "✅ Til o'zbekcha qilib o'rnatildi.",
        "ru": "✅ Язык установлен: русский.",
        "en": "✅ Language set to English.",
    },
    "welcome": {
        "uz": "Assalomu alaykum, {name}! 👋\n\nMen — <b>Logoped Yordamchisi</b> botiman.\nBu yerda nutq va talaffuzni yaxshilash uchun mashqlarni topasiz, natijalaringizni kuzatib borasiz va fikr-mulohaza qoldirishingiz mumkin.\n\nQuyidagi menyudan foydalaning 👇",
        "ru": "Здравствуйте, {name}! 👋\n\nЯ — бот «Помощник логопеда».\nЗдесь вы найдёте упражнения для улучшения речи и произношения, сможете отслеживать свой прогресс и оставить отзыв.\n\nИспользуйте меню ниже 👇",
        "en": "Hello, {name}! 👋\n\nI'm your Speech Therapy Assistant bot.\nHere you'll find exercises to improve speech and pronunciation, track your progress, and leave feedback.\n\nUse the menu below 👇",
    },
    "menu_exercises": {"uz": "📚 Mashqlar", "ru": "📚 Упражнения", "en": "📚 Exercises"},
    "menu_progress": {"uz": "📊 Mening natijalarim", "ru": "📊 Мой прогресс", "en": "📊 My progress"},
    "menu_feedback": {"uz": "💬 Fikr-mulohaza", "ru": "💬 Обратная связь", "en": "💬 Feedback"},
    "menu_help": {"uz": "❓ Yordam", "ru": "❓ Помощь", "en": "❓ Help"},
    "menu_language": {"uz": "🌐 Til", "ru": "🌐 Язык", "en": "🌐 Language"},
    "help_text": {
        "uz": "<b>📖 Yordam bo'limi</b>\n\n📚 <b>Mashqlar</b> — tovushlar bo'yicha logopedik mashqlar.\n📊 <b>Natijalar</b> — necha mashq bajarganingiz.\n💬 <b>Fikr-mulohaza</b> — admin(ustoz)ga xabar yuborish.\n🌐 <b>Til</b> — interfeys tilini o'zgartirish.",
        "ru": "<b>📖 Раздел помощи</b>\n\n📚 <b>Упражнения</b> — логопедические упражнения по звукам.\n📊 <b>Прогресс</b> — сколько упражнений выполнено.\n💬 <b>Обратная связь</b> — сообщение администратору.\n🌐 <b>Язык</b> — сменить язык интерфейса.",
        "en": "<b>📖 Help section</b>\n\n📚 <b>Exercises</b> — speech-therapy exercises by sound.\n📊 <b>Progress</b> — how many exercises completed.\n💬 <b>Feedback</b> — send a message to the admin.\n🌐 <b>Language</b> — change interface language.",
    },
    "choose_category": {
        "uz": "Quyidagi kategoriyalardan birini tanlang 👇",
        "ru": "Выберите одну из категорий 👇",
        "en": "Choose one of the categories 👇",
    },
    "choose_exercise": {
        "uz": "Mashqni tanlang:",
        "ru": "Выберите упражнение:",
        "en": "Choose an exercise:",
    },
    "no_exercises_for_language": {
        "uz": "😕 Bu kategoriyada hozircha sizning tilingizda mashq yo'q.",
        "ru": "😕 В этой категории пока нет упражнений на вашем языке.",
        "en": "😕 There are no exercises in this category for your language yet.",
    },
    "back": {"uz": "⬅️ Orqaga", "ru": "⬅️ Назад", "en": "⬅️ Back"},
    "home_menu": {"uz": "🏠 Bosh menyu", "ru": "🏠 Главное меню", "en": "🏠 Main menu"},
    "done_btn": {"uz": "✅ Bajardim", "ru": "✅ Выполнено", "en": "✅ Done"},
    "already_done": {
        "uz": "Siz bu mashqni allaqachon bajargansiz ✅",
        "ru": "Вы уже выполнили это упражнение ✅",
        "en": "You've already completed this exercise ✅",
    },
    "marked_done": {
        "uz": "Ajoyib! Mashq bajarilgan deb belgilandi 🎉",
        "ru": "Отлично! Упражнение отмечено как выполненное 🎉",
        "en": "Great! Exercise marked as completed 🎉",
    },
    "difficulty_label": {"uz": "Daraja", "ru": "Уровень", "en": "Level"},
    "diff_easy": {"uz": "Oson", "ru": "Лёгкий", "en": "Easy"},
    "diff_medium": {"uz": "O'rta", "ru": "Средний", "en": "Medium"},
    "diff_hard": {"uz": "Qiyin", "ru": "Сложный", "en": "Hard"},
    "progress_title": {
        "uz": "<b>📊 Sizning natijalaringiz</b>",
        "ru": "<b>📊 Ваш прогресс</b>",
        "en": "<b>📊 Your progress</b>",
    },
    "progress_done_of": {
        "uz": "Bajarilgan mashqlar: {done} / {total}",
        "ru": "Выполнено упражнений: {done} / {total}",
        "en": "Completed exercises: {done} / {total}",
    },
    "progress_encourage_done": {
        "uz": "Ajoyib davom etyapsiz! 💪",
        "ru": "Отличная работа, продолжайте! 💪",
        "en": "Great job, keep it up! 💪",
    },
    "progress_encourage_none": {
        "uz": "Hali mashq bajarmagansiz, 📚 Mashqlar bo'limiga o'ting!",
        "ru": "Вы ещё не выполнили ни одного упражнения, перейдите в раздел 📚 Упражнения!",
        "en": "You haven't completed any exercises yet — check out 📚 Exercises!",
    },
    "feedback_prompt": {
        "uz": "Fikr, taklif yoki savolingizni yozing. Xabaringiz to'g'ridan-to'g'ri administratorga yuboriladi:",
        "ru": "Напишите свой отзыв, предложение или вопрос. Сообщение будет отправлено администратору напрямую:",
        "en": "Write your feedback, suggestion, or question. Your message will be sent directly to the admin:",
    },
    "feedback_thanks": {
        "uz": "✅ Fikringiz uchun rahmat! Xabaringiz administratorga yuborildi.",
        "ru": "✅ Спасибо за ваш отзыв! Сообщение отправлено администратору.",
        "en": "✅ Thanks for your feedback! Your message has been sent to the admin.",
    },
    "cancel": {"uz": "❌ Bekor qilish", "ru": "❌ Отмена", "en": "❌ Cancel"},
}


def t(key: str, lang: str, **kwargs) -> str:
    lang = lang if lang in LANGUAGES else "uz"
    text = T.get(key, {}).get(lang) or T.get(key, {}).get("uz", key)
    return text.format(**kwargs) if kwargs else text


CATEGORY_NAMES = {
    "r_sound": {"uz": "R tovushi mashqlari", "ru": "Упражнения на звук Р", "en": "Exercises for sound R"},
    "sz_sound": {"uz": "S-Z tovushlari mashqlari", "ru": "Упражнения на звуки С-З", "en": "Exercises for S-Z sounds"},
    "shj_sound": {"uz": "Sh-J tovushlari mashqlari", "ru": "Упражнения на звуки Ш-Ж", "en": "Exercises for Sh-J sounds"},
    "l_sound": {"uz": "L tovushi mashqlari", "ru": "Упражнения на звук Л", "en": "Exercises for sound L"},
    "general": {"uz": "Umumiy artikulyatsiya mashqlari", "ru": "Общие артикуляционные упражнения", "en": "General articulation exercises"},
    "breathing": {"uz": "Nafas mashqlari", "ru": "Дыхательные упражнения", "en": "Breathing exercises"},
}

DIFFICULTY_KEYS = ["easy", "medium", "hard"]


def difficulty_label(diff_key: str, lang: str) -> str:
    mapping = {"easy": "diff_easy", "medium": "diff_medium", "hard": "diff_hard"}
    return t(mapping.get(diff_key, "diff_easy"), lang)


# ============================================================
#                     MA'LUMOTLAR BAZASI
# ============================================================

def get_conn():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn


def _column_exists(cur, table, column) -> bool:
    cur.execute(f"PRAGMA table_info({table})")
    return any(row[1] == column for row in cur.fetchall())


def init_db():
    conn = get_conn()
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id     INTEGER PRIMARY KEY,
            username    TEXT,
            full_name   TEXT,
            joined_at   TEXT,
            is_banned   INTEGER DEFAULT 0
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS categories (
            id      INTEGER PRIMARY KEY AUTOINCREMENT,
            name    TEXT UNIQUE
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS exercises (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            category_id  INTEGER,
            title        TEXT,
            content      TEXT,
            difficulty   TEXT,
            created_at   TEXT,
            FOREIGN KEY (category_id) REFERENCES categories(id)
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS progress (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id       INTEGER,
            exercise_id   INTEGER,
            completed_at  TEXT
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS feedback (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id       INTEGER,
            username      TEXT,
            message       TEXT,
            created_at    TEXT,
            status        TEXT DEFAULT 'yangi',
            admin_reply   TEXT
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS admin_logs (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            admin_id    INTEGER,
            action      TEXT,
            timestamp   TEXT
        )
    """)
    conn.commit()

    if not _column_exists(cur, "users", "language"):
        cur.execute("ALTER TABLE users ADD COLUMN language TEXT DEFAULT 'uz'")
    if not _column_exists(cur, "categories", "key"):
        cur.execute("ALTER TABLE categories ADD COLUMN key TEXT")
    if not _column_exists(cur, "exercises", "language"):
        cur.execute("ALTER TABLE exercises ADD COLUMN language TEXT DEFAULT 'uz'")
    conn.commit()

    # Eskiroq bazada 'kaa' tilidagi foydalanuvchilar bo'lsa, ularni 'uz' ga o'tkazamiz
    cur.execute("UPDATE users SET language='uz' WHERE language NOT IN ('uz','ru','en') OR language IS NULL")
    conn.commit()

    cur.execute("SELECT COUNT(*) AS c FROM categories")
    if cur.fetchone()["c"] == 0:
        seed_categories = [
            ("r_sound", CATEGORY_NAMES["r_sound"]["uz"]),
            ("sz_sound", CATEGORY_NAMES["sz_sound"]["uz"]),
            ("shj_sound", CATEGORY_NAMES["shj_sound"]["uz"]),
            ("l_sound", CATEGORY_NAMES["l_sound"]["uz"]),
            ("general", CATEGORY_NAMES["general"]["uz"]),
            ("breathing", CATEGORY_NAMES["breathing"]["uz"]),
        ]
        for key, name in seed_categories:
            cur.execute("INSERT INTO categories (name, key) VALUES (?,?)", (name, key))
        conn.commit()

        seed_exercises = [
            ("r_sound", "Til uchini tishlash", "Tilingiz uchini yuqori tishlar orqasiga qo'yib, 'ddd-rrr' tovushini 10 marta takrorlang.", "easy"),
            ("r_sound", "Tez aytish — 'Rrra-rro-rru'", "Rra-rro-rru, rra-rro-rru — ohista boshlab, tezlikni oshirib boring (5 marta).", "medium"),
            ("sz_sound", "Ilon tovushi", "Tishlaringizni ozgina ochib, 'sss...' tovushini 15 soniya davomida cho'zib ayting.", "easy"),
            ("sz_sound", "Sa-so-su-se", "Sa-so-su-se bo'g'inlarini aniq va sekin talaffuz qiling, so'ng tezlashtiring.", "medium"),
            ("shj_sound", "Momaqaldiroq tovushi", "'Sh-sh-sh' tovushini lablaringizni yumaloq shaklda tutib ayting (10 marta).", "easy"),
            ("l_sound", "Soat mayatnigi", "Tilingizni chap va o'ng lab burchagiga tegizib, mayatnik kabi harakatlantiring (10 marta).", "medium"),
            ("general", "Kulcha va naycha", "Lablaringizni keng tabassum holatiga, so'ng naycha shakliga keltiring — 8 marta takrorlang.", "easy"),
            ("breathing", "Sham o'chirish", "Chuqur nafas oling va sham o'chirayotgandek 'fu' deb sekin puflang (5 marta).", "easy"),
        ]
        for cat_key, title, content, diff in seed_exercises:
            cat_id = cur.execute("SELECT id FROM categories WHERE key=?", (cat_key,)).fetchone()["id"]
            cur.execute(
                "INSERT INTO exercises (category_id, title, content, difficulty, created_at, language) VALUES (?,?,?,?,?,?)",
                (cat_id, title, content, diff, datetime.now().isoformat(), "uz"),
            )
        conn.commit()

    conn.close()


def register_user(user_id: int, username: str, full_name: str) -> bool:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT user_id FROM users WHERE user_id=?", (user_id,))
    is_new = cur.fetchone() is None
    if is_new:
        cur.execute(
            "INSERT INTO users (user_id, username, full_name, joined_at, language) VALUES (?,?,?,?,?)",
            (user_id, username, full_name, datetime.now().isoformat(), "uz"),
        )
        conn.commit()
    conn.close()
    return is_new


def get_user_language(user_id: int) -> str:
    conn = get_conn()
    row = conn.execute("SELECT language FROM users WHERE user_id=?", (user_id,)).fetchone()
    conn.close()
    lang = row["language"] if row and row["language"] else "uz"
    return lang if lang in LANGUAGES else "uz"


def set_user_language(user_id: int, lang: str):
    conn = get_conn()
    conn.execute("UPDATE users SET language=? WHERE user_id=?", (lang, user_id))
    conn.commit()
    conn.close()


def is_user_banned(user_id: int) -> bool:
    conn = get_conn()
    row = conn.execute("SELECT is_banned FROM users WHERE user_id=?", (user_id,)).fetchone()
    conn.close()
    return bool(row and row["is_banned"])


def log_admin_action(admin_id: int, action: str):
    conn = get_conn()
    conn.execute(
        "INSERT INTO admin_logs (admin_id, action, timestamp) VALUES (?,?,?)",
        (admin_id, action, datetime.now().isoformat()),
    )
    conn.commit()
    conn.close()


def category_display_name(row, lang: str) -> str:
    key = row["key"] if "key" in row.keys() else None
    if key and key in CATEGORY_NAMES:
        return CATEGORY_NAMES[key][lang]
    return row["name"]


# ============================================================
#                       HOLATLAR (FSM)
# ============================================================

class LanguageSelect(StatesGroup):
    waiting_choice = State()


class AdminAuth(StatesGroup):
    waiting_password = State()


class AdminAddCategory(StatesGroup):
    waiting_name = State()


class AdminDeleteCategory(StatesGroup):
    waiting_id = State()


class AdminAddExercise(StatesGroup):
    waiting_category = State()
    waiting_language = State()
    waiting_title = State()
    waiting_content = State()
    waiting_difficulty = State()


class AdminBroadcast(StatesGroup):
    waiting_text = State()


class AdminDeleteExercise(StatesGroup):
    waiting_id = State()


class UserFeedback(StatesGroup):
    waiting_message = State()


# ============================================================
#                 INLINE KLAVIATURALAR (FOYDALANUVCHI)
# ============================================================

def main_menu_inline_kb(lang: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text=t("menu_exercises", lang), callback_data="go_exercises")
    builder.button(text=t("menu_progress", lang), callback_data="go_progress")
    builder.button(text=t("menu_feedback", lang), callback_data="go_feedback")
    builder.button(text=t("menu_help", lang), callback_data="go_help")
    builder.button(text=t("menu_language", lang), callback_data="go_language")
    builder.adjust(1, 2, 2)
    return builder.as_markup()


def back_home_kb(lang: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text=t("home_menu", lang), callback_data="home_menu")
    return builder.as_markup()


def cancel_kb(lang: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text=t("cancel", lang), callback_data="home_menu")
    return builder.as_markup()


def language_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for code in LANGUAGES:
        builder.button(text=LANG_NAMES[code], callback_data=f"setlang_{code}")
    builder.adjust(1)
    return builder.as_markup()


def categories_kb(lang: str) -> InlineKeyboardMarkup:
    conn = get_conn()
    cats = conn.execute("SELECT * FROM categories ORDER BY id").fetchall()
    conn.close()
    builder = InlineKeyboardBuilder()
    for cat in cats:
        builder.button(text=category_display_name(cat, lang), callback_data=f"cat_{cat['id']}")
    builder.button(text=t("home_menu", lang), callback_data="home_menu")
    builder.adjust(1)
    return builder.as_markup()


def exercises_kb(category_id: int, lang: str):
    conn = get_conn()
    items = conn.execute(
        "SELECT * FROM exercises WHERE category_id=? AND language=? ORDER BY id", (category_id, lang)
    ).fetchall()
    conn.close()
    builder = InlineKeyboardBuilder()
    for ex in items:
        builder.button(text=f"{ex['title']} ({difficulty_label(ex['difficulty'], lang)})", callback_data=f"ex_{ex['id']}")
    builder.button(text=t("back", lang), callback_data="back_to_categories")
    builder.adjust(1)
    return builder.as_markup(), len(items)


def exercise_done_kb(exercise_id: int, category_id: int, lang: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text=t("done_btn", lang), callback_data=f"done_{exercise_id}")
    builder.button(text=t("back", lang), callback_data=f"cat_{category_id}")
    builder.adjust(1)
    return builder.as_markup()


# ============================================================
#                ADMIN UCHUN INLINE KLAVIATURALAR
# ============================================================

def admin_menu_kb() -> ReplyKeyboardMarkup:
    kb = [
        [KeyboardButton(text="➕ Mashq qo'shish"), KeyboardButton(text="🗂 Kategoriya qo'shish")],
        [KeyboardButton(text="🗑 Mashqni o'chirish"), KeyboardButton(text="🗑 Kategoriyani o'chirish")],
        [KeyboardButton(text="📈 Statistika"), KeyboardButton(text="📥 Fikr-mulohazalar")],
        [KeyboardButton(text="📢 Xabar yuborish")],
        [KeyboardButton(text="⬅️ Chiqish")],
    ]
    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)


def difficulty_pick_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for d in DIFFICULTY_KEYS:
        builder.button(text=difficulty_label(d, "uz"), callback_data=f"diff_{d}")
    builder.adjust(3)
    return builder.as_markup()


def language_pick_kb_for_admin() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for code in LANGUAGES:
        builder.button(text=LANG_NAMES[code], callback_data=f"exlang_{code}")
    builder.adjust(1)
    return builder.as_markup()


def category_pick_kb_for_admin() -> InlineKeyboardMarkup:
    conn = get_conn()
    cats = conn.execute("SELECT * FROM categories ORDER BY id").fetchall()
    conn.close()
    builder = InlineKeyboardBuilder()
    for cat in cats:
        builder.button(text=cat["name"], callback_data=f"pickcat_{cat['id']}")
    builder.adjust(1)
    return builder.as_markup()


# ============================================================
#                    XAVFSIZLIK YORDAMCHISI
# ============================================================

def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS


async def deny_access(message: Message):
    await message.answer("⛔️ Sizda bu bo'limga kirish huquqi yo'q.")


# ============================================================
#            FOYDALANUVCHI — /start VA BOSH MENYU OQIMI
# ============================================================

@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    await state.clear()

    # Agar oldingi admin sessiyasidan pastki (reply) tugmalar ekranda osilib
    # qolgan bo'lsa, ularni sezilmas tarzda tozalaymiz (yuborib, darhol o'chiramiz)
    try:
        cleanup_msg = await message.answer("⏳", reply_markup=ReplyKeyboardRemove())
        await cleanup_msg.delete()
    except Exception:
        pass

    if is_user_banned(message.from_user.id):
        await message.answer("⛔️ Siz botdan foydalanishdan bloklangansiz.")
        return

    is_new = register_user(message.from_user.id, message.from_user.username or "", message.from_user.full_name)

    if is_new:
        await message.answer(t("choose_language", "uz"), reply_markup=language_kb())
        await state.set_state(LanguageSelect.waiting_choice)
        return

    lang = get_user_language(message.from_user.id)
    await message.answer(
        t("welcome", lang, name=message.from_user.full_name),
        parse_mode="HTML",
        reply_markup=main_menu_inline_kb(lang),
    )


@router.callback_query(LanguageSelect.waiting_choice, F.data.startswith("setlang_"))
async def language_selected_first_time(callback: CallbackQuery, state: FSMContext):
    lang = callback.data.split("_", 1)[1]
    set_user_language(callback.from_user.id, lang)
    await state.clear()
    await callback.message.edit_text(
        t("welcome", lang, name=callback.from_user.full_name),
        parse_mode="HTML",
        reply_markup=main_menu_inline_kb(lang),
    )
    await callback.answer(t("language_set", lang))


@router.callback_query(F.data == "home_menu")
async def go_home(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    lang = get_user_language(callback.from_user.id)
    await callback.message.edit_text(
        t("welcome", lang, name=callback.from_user.full_name),
        parse_mode="HTML",
        reply_markup=main_menu_inline_kb(lang),
    )
    await callback.answer()


@router.callback_query(F.data == "go_language")
async def go_language(callback: CallbackQuery):
    lang = get_user_language(callback.from_user.id)
    await callback.message.edit_text(t("choose_language", lang), reply_markup=language_kb())
    await callback.answer()


@router.callback_query(F.data.startswith("setlang_"))
async def language_changed(callback: CallbackQuery):
    lang = callback.data.split("_", 1)[1]
    set_user_language(callback.from_user.id, lang)
    await callback.message.edit_text(
        t("welcome", lang, name=callback.from_user.full_name),
        parse_mode="HTML",
        reply_markup=main_menu_inline_kb(lang),
    )
    await callback.answer(t("language_set", lang))


@router.callback_query(F.data == "go_help")
async def go_help(callback: CallbackQuery):
    lang = get_user_language(callback.from_user.id)
    await callback.message.edit_text(t("help_text", lang), parse_mode="HTML", reply_markup=back_home_kb(lang))
    await callback.answer()


@router.message(Command("help"))
async def cmd_help(message: Message):
    lang = get_user_language(message.from_user.id)
    await message.answer(t("help_text", lang), parse_mode="HTML", reply_markup=back_home_kb(lang))


# ============================================================
#                FOYDALANUVCHI — MASHQLAR OQIMI
# ============================================================

@router.callback_query(F.data == "go_exercises")
async def show_categories(callback: CallbackQuery):
    if is_user_banned(callback.from_user.id):
        return
    lang = get_user_language(callback.from_user.id)
    await callback.message.edit_text(t("choose_category", lang), reply_markup=categories_kb(lang))
    await callback.answer()


@router.callback_query(F.data.startswith("cat_"))
async def show_exercises(callback: CallbackQuery):
    lang = get_user_language(callback.from_user.id)
    category_id = int(callback.data.split("_")[1])
    conn = get_conn()
    cat = conn.execute("SELECT * FROM categories WHERE id=?", (category_id,)).fetchone()
    conn.close()

    kb, count = exercises_kb(category_id, lang)
    header = f"📂 <b>{category_display_name(cat, lang)}</b>\n\n"
    body = t("choose_exercise", lang) if count else t("no_exercises_for_language", lang)

    await callback.message.edit_text(header + body, parse_mode="HTML", reply_markup=kb)
    await callback.answer()


@router.callback_query(F.data == "back_to_categories")
async def back_to_categories(callback: CallbackQuery):
    lang = get_user_language(callback.from_user.id)
    await callback.message.edit_text(t("choose_category", lang), reply_markup=categories_kb(lang))
    await callback.answer()


@router.callback_query(F.data.startswith("ex_"))
async def show_exercise_detail(callback: CallbackQuery):
    lang = get_user_language(callback.from_user.id)
    exercise_id = int(callback.data.split("_")[1])
    conn = get_conn()
    ex = conn.execute("SELECT * FROM exercises WHERE id=?", (exercise_id,)).fetchone()
    conn.close()
    if not ex:
        await callback.answer("Not found", show_alert=True)
        return
    await callback.message.edit_text(
        f"🏷 <b>{ex['title']}</b>\n"
        f"{t('difficulty_label', lang)}: {difficulty_label(ex['difficulty'], lang)}\n\n"
        f"{ex['content']}",
        parse_mode="HTML",
        reply_markup=exercise_done_kb(exercise_id, ex["category_id"], lang),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("done_"))
async def mark_done(callback: CallbackQuery):
    lang = get_user_language(callback.from_user.id)
    exercise_id = int(callback.data.split("_")[1])
    conn = get_conn()
    already = conn.execute(
        "SELECT id FROM progress WHERE user_id=? AND exercise_id=?",
        (callback.from_user.id, exercise_id),
    ).fetchone()
    if already:
        await callback.answer(t("already_done", lang), show_alert=True)
    else:
        conn.execute(
            "INSERT INTO progress (user_id, exercise_id, completed_at) VALUES (?,?,?)",
            (callback.from_user.id, exercise_id, datetime.now().isoformat()),
        )
        conn.commit()
        await callback.answer(t("marked_done", lang), show_alert=True)
    conn.close()


# ============================================================
#              FOYDALANUVCHI — NATIJALAR VA FIKR-MULOHAZA
# ============================================================

@router.callback_query(F.data == "go_progress")
async def my_progress(callback: CallbackQuery):
    lang = get_user_language(callback.from_user.id)
    conn = get_conn()
    total_exercises = conn.execute("SELECT COUNT(*) AS c FROM exercises WHERE language=?", (lang,)).fetchone()["c"]
    done = conn.execute(
        "SELECT COUNT(*) AS c FROM progress p JOIN exercises e ON p.exercise_id=e.id "
        "WHERE p.user_id=? AND e.language=?",
        (callback.from_user.id, lang),
    ).fetchone()["c"]
    conn.close()

    percent = round((done / total_exercises) * 100) if total_exercises else 0
    bar_filled = "▓" * (percent // 10)
    bar_empty = "░" * (10 - percent // 10)

    text = (
        f"{t('progress_title', lang)}\n\n"
        f"{t('progress_done_of', lang, done=done, total=total_exercises)}\n"
        f"[{bar_filled}{bar_empty}] {percent}%\n\n"
        + (t("progress_encourage_done", lang) if done > 0 else t("progress_encourage_none", lang))
    )
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=back_home_kb(lang))
    await callback.answer()


@router.callback_query(F.data == "go_feedback")
async def ask_feedback(callback: CallbackQuery, state: FSMContext):
    lang = get_user_language(callback.from_user.id)
    await callback.message.edit_text(t("feedback_prompt", lang), reply_markup=cancel_kb(lang))
    await state.set_state(UserFeedback.waiting_message)
    await callback.answer()


@router.message(UserFeedback.waiting_message)
async def save_feedback(message: Message, state: FSMContext):
    lang = get_user_language(message.from_user.id)
    conn = get_conn()
    conn.execute(
        "INSERT INTO feedback (user_id, username, message, created_at) VALUES (?,?,?,?)",
        (message.from_user.id, message.from_user.username or "", message.text, datetime.now().isoformat()),
    )
    conn.commit()
    conn.close()

    await state.clear()
    await message.answer(t("feedback_thanks", lang), reply_markup=back_home_kb(lang))

    for admin_id in ADMIN_IDS:
        try:
            await bot.send_message(
                admin_id,
                f"📩 <b>Yangi fikr-mulohaza</b>\n"
                f"Foydalanuvchi: @{message.from_user.username or 'nomaʼlum'} (ID: {message.from_user.id})\n\n"
                f"{message.text}",
                parse_mode="HTML",
            )
        except Exception as e:
            logger.warning(f"Adminga xabar yuborib bo'lmadi ({admin_id}): {e}")


# ============================================================
#                    ADMIN PANEL — KIRISH
# ============================================================

@router.message(Command("admin"))
async def cmd_admin(message: Message, state: FSMContext):
    user_id = message.from_user.id

    if user_id in blocked_users:
        await message.answer("⛔️ Siz ko'p marta noto'g'ri parol kiritganingiz uchun bloklangansiz.")
        return

    if not is_admin(user_id):
        logger.warning(f"Ruxsatsiz /admin urinishi: user_id={user_id}, username={message.from_user.username}")
        await deny_access(message)
        return

    await message.answer("🔐 Admin panelga kirish uchun parolni kiriting:", reply_markup=ReplyKeyboardRemove())
    await state.set_state(AdminAuth.waiting_password)


@router.message(AdminAuth.waiting_password)
async def check_admin_password(message: Message, state: FSMContext):
    user_id = message.from_user.id

    if message.text == ADMIN_PASSWORD:
        failed_attempts[user_id] = 0
        await state.clear()
        log_admin_action(user_id, "Admin panelga muvaffaqiyatli kirdi")
        await message.answer("✅ Xush kelibsiz, Admin!", reply_markup=admin_menu_kb())
    else:
        failed_attempts[user_id] = failed_attempts.get(user_id, 0) + 1
        remaining = MAX_LOGIN_ATTEMPTS - failed_attempts[user_id]

        if remaining <= 0:
            blocked_users.add(user_id)
            await state.clear()
            log_admin_action(user_id, "Ko'p marta noto'g'ri parol — bloklandi")
            await message.answer("⛔️ Noto'g'ri parol 3 marta kiritildi. Siz bloklandingiz.")
        else:
            await message.answer(f"❌ Noto'g'ri parol. Qolgan urinishlar: {remaining}")


@router.message(F.text == "⬅️ Chiqish")
async def admin_exit(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    await state.clear()
    lang = get_user_language(message.from_user.id)
    await message.answer("Admin paneldan chiqdingiz.", reply_markup=ReplyKeyboardRemove())
    await message.answer(t("welcome", lang, name=message.from_user.full_name), parse_mode="HTML", reply_markup=main_menu_inline_kb(lang))


# ============================================================
#                 ADMIN PANEL — STATISTIKA
# ============================================================

@router.message(F.text == "📈 Statistika")
async def admin_stats(message: Message):
    if not is_admin(message.from_user.id):
        return await deny_access(message)

    conn = get_conn()
    total_users = conn.execute("SELECT COUNT(*) AS c FROM users").fetchone()["c"]
    banned = conn.execute("SELECT COUNT(*) AS c FROM users WHERE is_banned=1").fetchone()["c"]
    total_exercises = conn.execute("SELECT COUNT(*) AS c FROM exercises").fetchone()["c"]
    total_categories = conn.execute("SELECT COUNT(*) AS c FROM categories").fetchone()["c"]
    total_done = conn.execute("SELECT COUNT(*) AS c FROM progress").fetchone()["c"]
    new_feedback = conn.execute("SELECT COUNT(*) AS c FROM feedback WHERE status='yangi'").fetchone()["c"]
    by_lang = conn.execute("SELECT language, COUNT(*) AS c FROM users GROUP BY language").fetchall()
    conn.close()

    lang_lines = "\n".join([f"  • {row['language']}: {row['c']}" for row in by_lang])

    await message.answer(
        "<b>📈 Bot statistikasi</b>\n\n"
        f"👥 Jami foydalanuvchilar: {total_users}\n"
        f"🌐 Tillar bo'yicha:\n{lang_lines}\n"
        f"🚫 Bloklangan: {banned}\n"
        f"🗂 Kategoriyalar: {total_categories}\n"
        f"📚 Mashqlar: {total_exercises}\n"
        f"✅ Bajarilgan mashqlar (jami): {total_done}\n"
        f"📩 Yangi fikr-mulohazalar: {new_feedback}",
        parse_mode="HTML",
    )


# ============================================================
#              ADMIN PANEL — KATEGORIYA QO'SHISH / O'CHIRISH
# ============================================================

@router.message(F.text == "🗂 Kategoriya qo'shish")
async def admin_add_category_start(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return await deny_access(message)
    await message.answer("Yangi kategoriya nomini kiriting:", reply_markup=ReplyKeyboardRemove())
    await state.set_state(AdminAddCategory.waiting_name)


@router.message(AdminAddCategory.waiting_name)
async def admin_add_category_save(message: Message, state: FSMContext):
    conn = get_conn()
    try:
        conn.execute("INSERT INTO categories (name, key) VALUES (?, NULL)", (message.text,))
        conn.commit()
        log_admin_action(message.from_user.id, f"Kategoriya qo'shdi: {message.text}")
        await message.answer(f"✅ '{message.text}' kategoriyasi qo'shildi.", reply_markup=admin_menu_kb())
    except sqlite3.IntegrityError:
        await message.answer("⚠️ Bu nomdagi kategoriya allaqachon mavjud.", reply_markup=admin_menu_kb())
    conn.close()
    await state.clear()


@router.message(F.text == "🗑 Kategoriyani o'chirish")
async def admin_delete_category_start(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return await deny_access(message)

    conn = get_conn()
    cats = conn.execute("SELECT id, name FROM categories ORDER BY id").fetchall()
    conn.close()

    if not cats:
        await message.answer("Hozircha hech qanday kategoriya yo'q.", reply_markup=admin_menu_kb())
        return

    text = "🗑 O'chirmoqchi bo'lgan kategoriya ID raqamini yuboring:\n"
    text += "⚠️ Diqqat: kategoriyani o'chirsangiz, ichidagi barcha mashqlar ham o'chadi!\n\n"
    text += "\n".join([f"#{c['id']} — {c['name']}" for c in cats])
    await message.answer(text, reply_markup=ReplyKeyboardRemove())
    await state.set_state(AdminDeleteCategory.waiting_id)


@router.message(AdminDeleteCategory.waiting_id)
async def admin_delete_category_finish(message: Message, state: FSMContext):
    if not message.text.isdigit():
        await message.answer("Iltimos, faqat ID raqamini yuboring.")
        return

    cat_id = int(message.text)
    conn = get_conn()
    cat = conn.execute("SELECT name FROM categories WHERE id=?", (cat_id,)).fetchone()

    if not cat:
        await message.answer("Bunday ID topilmadi.", reply_markup=admin_menu_kb())
    else:
        ex_ids = [row["id"] for row in conn.execute("SELECT id FROM exercises WHERE category_id=?", (cat_id,)).fetchall()]
        for ex_id in ex_ids:
            conn.execute("DELETE FROM progress WHERE exercise_id=?", (ex_id,))
        conn.execute("DELETE FROM exercises WHERE category_id=?", (cat_id,))
        conn.execute("DELETE FROM categories WHERE id=?", (cat_id,))
        conn.commit()
        log_admin_action(message.from_user.id, f"Kategoriyani o'chirdi: {cat['name']}")
        await message.answer(f"✅ '{cat['name']}' kategoriyasi va uning mashqlari o'chirildi.", reply_markup=admin_menu_kb())

    conn.close()
    await state.clear()


# ============================================================
#                ADMIN PANEL — MASHQ QO'SHISH
# ============================================================

@router.message(F.text == "➕ Mashq qo'shish")
async def admin_add_exercise_start(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return await deny_access(message)

    conn = get_conn()
    has_categories = conn.execute("SELECT COUNT(*) AS c FROM categories").fetchone()["c"]
    conn.close()

    if not has_categories:
        await message.answer("Avval kamida bitta kategoriya qo'shing.", reply_markup=admin_menu_kb())
        return

    await message.answer("Mashq qaysi kategoriyaga tegishli?", reply_markup=category_pick_kb_for_admin())
    await state.set_state(AdminAddExercise.waiting_category)


@router.callback_query(AdminAddExercise.waiting_category, F.data.startswith("pickcat_"))
async def admin_add_exercise_category(callback: CallbackQuery, state: FSMContext):
    category_id = int(callback.data.split("_")[1])
    await state.update_data(category_id=category_id)
    await callback.message.answer("Bu mashq qaysi til uchun? (foydalanuvchi shu tilni tanlaganda ko'radi)", reply_markup=language_pick_kb_for_admin())
    await state.set_state(AdminAddExercise.waiting_language)
    await callback.answer()


@router.callback_query(AdminAddExercise.waiting_language, F.data.startswith("exlang_"))
async def admin_add_exercise_language(callback: CallbackQuery, state: FSMContext):
    ex_lang = callback.data.split("_", 1)[1]
    await state.update_data(ex_language=ex_lang)
    await callback.message.answer(f"Til: {LANG_NAMES[ex_lang]}\n\nMashq nomini (sarlavhasini) shu tilda kiriting:")
    await state.set_state(AdminAddExercise.waiting_title)
    await callback.answer()


@router.message(AdminAddExercise.waiting_title)
async def admin_add_exercise_title(message: Message, state: FSMContext):
    await state.update_data(title=message.text)
    await message.answer("Mashq matnini (tavsifini) shu tilda kiriting:")
    await state.set_state(AdminAddExercise.waiting_content)


@router.message(AdminAddExercise.waiting_content)
async def admin_add_exercise_content(message: Message, state: FSMContext):
    await state.update_data(content=message.text)
    await message.answer("Qiyinlik darajasini tanlang:", reply_markup=difficulty_pick_kb())
    await state.set_state(AdminAddExercise.waiting_difficulty)


@router.callback_query(AdminAddExercise.waiting_difficulty, F.data.startswith("diff_"))
async def admin_add_exercise_finish(callback: CallbackQuery, state: FSMContext):
    difficulty = callback.data.split("_", 1)[1]
    data = await state.get_data()

    conn = get_conn()
    conn.execute(
        "INSERT INTO exercises (category_id, title, content, difficulty, created_at, language) VALUES (?,?,?,?,?,?)",
        (data["category_id"], data["title"], data["content"], difficulty, datetime.now().isoformat(), data["ex_language"]),
    )
    conn.commit()
    conn.close()

    log_admin_action(callback.from_user.id, f"Mashq qo'shdi: {data['title']} ({data['ex_language']})")
    await callback.message.answer(f"✅ '{data['title']}' mashqi ({LANG_NAMES[data['ex_language']]}) qo'shildi!", reply_markup=admin_menu_kb())
    await state.clear()
    await callback.answer()


# ============================================================
#              ADMIN PANEL — MASHQNI O'CHIRISH
# ============================================================

@router.message(F.text == "🗑 Mashqni o'chirish")
async def admin_delete_exercise_start(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return await deny_access(message)

    conn = get_conn()
    items = conn.execute("SELECT id, title, language FROM exercises ORDER BY id").fetchall()
    conn.close()

    if not items:
        await message.answer("Hozircha hech qanday mashq yo'q.", reply_markup=admin_menu_kb())
        return

    text = "🗑 O'chirmoqchi bo'lgan mashq ID raqamini yuboring:\n\n"
    text += "\n".join([f"#{i['id']} — {i['title']} [{i['language']}]" for i in items])
    await message.answer(text, reply_markup=ReplyKeyboardRemove())
    await state.set_state(AdminDeleteExercise.waiting_id)


@router.message(AdminDeleteExercise.waiting_id)
async def admin_delete_exercise_finish(message: Message, state: FSMContext):
    if not message.text.isdigit():
        await message.answer("Iltimos, faqat ID raqamini yuboring.")
        return

    ex_id = int(message.text)
    conn = get_conn()
    ex = conn.execute("SELECT title FROM exercises WHERE id=?", (ex_id,)).fetchone()

    if not ex:
        await message.answer("Bunday ID topilmadi.", reply_markup=admin_menu_kb())
    else:
        conn.execute("DELETE FROM exercises WHERE id=?", (ex_id,))
        conn.execute("DELETE FROM progress WHERE exercise_id=?", (ex_id,))
        conn.commit()
        log_admin_action(message.from_user.id, f"Mashqni o'chirdi: {ex['title']}")
        await message.answer(f"✅ '{ex['title']}' mashqi o'chirildi.", reply_markup=admin_menu_kb())

    conn.close()
    await state.clear()


# ============================================================
#              ADMIN PANEL — XABAR YUBORISH (BROADCAST)
# ============================================================

@router.message(F.text == "📢 Xabar yuborish")
async def admin_broadcast_start(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return await deny_access(message)
    await message.answer("Barcha foydalanuvchilarga yuboriladigan xabar matnini kiriting:", reply_markup=ReplyKeyboardRemove())
    await state.set_state(AdminBroadcast.waiting_text)


@router.message(AdminBroadcast.waiting_text)
async def admin_broadcast_send(message: Message, state: FSMContext):
    conn = get_conn()
    users = conn.execute("SELECT user_id FROM users WHERE is_banned=0").fetchall()
    conn.close()

    sent, failed = 0, 0
    for u in users:
        try:
            await bot.send_message(u["user_id"], f"📢 <b>E'lon</b>\n\n{message.text}", parse_mode="HTML")
            sent += 1
        except Exception:
            failed += 1
        await asyncio.sleep(0.05)

    log_admin_action(message.from_user.id, f"Broadcast yubordi: {sent} ta muvaffaqiyatli, {failed} ta xato")
    await message.answer(f"✅ Xabar yuborildi.\nMuvaffaqiyatli: {sent}\nXatolik: {failed}", reply_markup=admin_menu_kb())
    await state.clear()


# ============================================================
#            ADMIN PANEL — FIKR-MULOHAZALARNI KO'RISH
# ============================================================

@router.message(F.text == "📥 Fikr-mulohazalar")
async def admin_view_feedback(message: Message):
    if not is_admin(message.from_user.id):
        return await deny_access(message)

    conn = get_conn()
    items = conn.execute("SELECT * FROM feedback ORDER BY id DESC LIMIT 10").fetchall()
    conn.close()

    if not items:
        await message.answer("Hozircha fikr-mulohazalar yo'q.")
        return

    text = "<b>📥 So'nggi 10 ta fikr-mulohaza:</b>\n\n"
    for f in items:
        text += (
            f"#{f['id']} | @{f['username'] or 'nomaʼlum'} | {f['status']}\n"
            f"{f['message']}\n"
            f"—————————\n"
        )
    await message.answer(text, parse_mode="HTML")


# ============================================================
#                          ISHGA TUSHIRISH
# ============================================================

async def main():
    # --- Health-check serveri (Render / Fly / HF Spaces / Koyeb uchun) ---
    if PORT:
        class _Handler(BaseHTTPRequestHandler):
            def do_GET(self):  # noqa: N802
                if self.path.rstrip("/") in (HEALTH_PATH.rstrip("/"), ""):
                    self.send_response(200)
                    self.send_header("Content-Type", "text/plain; charset=utf-8")
                    self.end_headers()
                    self.wfile.write(b"logoped-bot: ok")
                else:
                    self.send_response(404)
                    self.end_headers()

            def log_message(self, *args):  # noqa: A003
                pass

        httpd = ThreadingHTTPServer(("0.0.0.0", PORT), _Handler)
        threading.Thread(target=httpd.serve_forever, daemon=True).start()
        logger.info(f"Health-check server: 0.0.0.0:{PORT}{HEALTH_PATH}")

    init_db()
    logger.info(f"Baza tayyor ({DB_NAME}). Bot ishga tushmoqda...")

    try:
        await bot.delete_webhook(drop_pending_updates=DROP_PENDING_UPDATES)
    except Exception as e:
        # Internet vaqtincha uzilib qolsa — bu jiddiy xato emas, polling'ni davom ettiramiz
        logger.warning(f"delete_webhook muvaffaqiyatsiz ({e}), polling boshlanmoqda...")

    await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot to'xtatildi.")