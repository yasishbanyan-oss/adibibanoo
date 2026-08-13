import html
import json
import logging
import os
import random
import re
import shutil
import sys
import asyncio
import threading
import traceback
from http.server import HTTPServer, BaseHTTPRequestHandler
from datetime import datetime
from zoneinfo import ZoneInfo

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)
from telegram.constants import ParseMode, ChatMemberStatus
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ChatMemberHandler,
    ContextTypes,
    ApplicationHandlerStop,
    filters,
)

# ==========================================
# CONFIGURATION & LOGGING
# ==========================================
BOT_TOKEN = "8618205537:AAFCjx1_PkdC43ezimZgp-z5PAx0JKEmJqI"
OWNER_ID = 6749949992
DB_FILE = "db.json"
TEMP_DB_FILE = "db.json.tmp"
BROKEN_DB_FILE = "db.json.broken"

MAX_FUN_MESSAGES = 20
BROADCAST_CANCEL_FLAG = False

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ==========================================
# DUMMY HTTP SERVER FOR RENDER WEB SERVICE
# ==========================================
class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Bot is alive!")

    def log_message(self, format, *args):
        return

def run_health_check_server():
    port = int(os.environ.get("PORT", 8080))
    server = HTTPServer(("0.0.0.0", port), HealthCheckHandler)
    logger.info(f"Dummy HTTP server running on port {port}")
    server.serve_forever()

# ==========================================
# ADVANCED REGEX PATTERNS & TEXT NORMALIZER
# ==========================================
LEF_PATTERN = re.compile(
    r"(?:\b|(?<=\s))ل+[فف]*[عع]*[هه]*(?:\s*(?:داد|بده|میده|میدم|میخوام))?(?=\s|[.,!?؛؟]|$)",
    re.IGNORECASE
)

DODOL_PATTERN = re.compile(
    r"(دولتو|دودولتو|شومبولتو|کیرتو|دولتو|دودولت|دول|شومبول|کیر)\s*(ببینم|نشون بده|نشون بپوش|بده|ببینیم)",
    re.IGNORECASE
)

PIN_PATTERNS = ["سنجاق", "پین", "pin"]
UNPIN_PATTERNS = ["حذف پین", "حذف سنجاق", "آن پین", "ان‌پین", "حذف‌سنجاق", "حذف‌پین", "آن‌پین", "unpin", "un pin"]

CLEANUP_PATTERN = re.compile(r"^\s*حذف\s+(?P<count>-?\d+|[a-zA-Z]+)?\s*$", re.IGNORECASE)
FUN_NAMED_PATTERN = re.compile(r"^\s*ناموسی\s+بده(?:\s+(?P<count>\d+))?\s*$", re.IGNORECASE)
FUN_NORMAL_PATTERN = re.compile(r"^\s*فحش\s+بده(?:\s+(?P<count>\d+))?\s*$", re.IGNORECASE)

PERSIAN_PERMUTATIONS = {
    '0': '0', '1': '1', '2': '2', '3': '3', '4': '4', '5': '5', '6': '6', '7': '7', '8': '8', '9': '9',
    '۰': '0', '۱': '1', '۲': '2', '۳': '3', '۴': '4', '۵': '5', '۶': '6', '۷': '7', '٨': '8', '۹': '9',
    '٠': '0', '١': '1', '٢': '2', '٣': '3', '٤': '4', '٥': '5', '٦': '6', '٧': '7', '٨': '8', '٩': '9'
}

def fa_to_en_digits(text: str) -> str:
    if not text:
        return "1"
    res = "".join(PERSIAN_PERMUTATIONS.get(ch, ch) for ch in text)
    try:
        val = float(res)
        return str(int(val)) if val.is_integer() else str(val)
    except ValueError:
        return "1"

def normalize_text(text: str) -> str:
    if not text:
        return ""
    text = re.sub(r"[؟?\.,!؛\-_]", " ", text)
    text = text.replace("\u200c", " ")
    text = re.sub(r"(.)\1{2,}", r"\1", text)
    text = re.sub(r"ه{2,}", "ه", text)
    text = re.sub(r"و{2,}", "و", text)
    text = re.sub(r"ی{2,}", "ی", text)
    words = text.strip().split()
    return " ".join(words)

def get_persian_date_info():
    weekdays = ["دوشنبه", "سه‌شنبه", "چهارشنبه", "پنج‌شنبه", "جمعه", "شنبه", "یکشنبه"]
    now = datetime.now(ZoneInfo("Asia/Tehran"))
    wd = weekdays[now.weekday()]
    time_str = now.strftime("%H:%M")
    return wd, time_str

def get_persian_date_str():
    wd, time_str = get_persian_date_info()
    return f"{wd} ، ساعت {time_str}"

# ==========================================
# GLOBAL DB CACHE & DIRTY FLAG
# ==========================================
_DB_CACHE = None
_DB_DIRTY = False

DEFAULT_FOODS = [
    "قرمه سبزی", "قیمه سیب‌زمینی", "قیمه نثار", "فسنجان", "دیزی / آبگوشت",
    "کباب کوبیده", "جوجه کباب", "شیشلیک", "کباب برگ", "کباب سلطانی",
    "کباب بختیاری", "کباب تابه ای", "ماهی کباب", "چلو گوشت", "زرشک پلو با مرغ",
    "باقالی پلو با گوشت", "باقالی پلو با مرغ", "آلبالو پلو", "شیرین پلو", "کلم پلو شیرازی",
    "عدس پلو با گوشت", "لوبیا پلو", "رشته پلو", "استامبولی", "دمپختک",
    "ته‌چین مرغ", "ته‌چین گوشت", "ته‌چین بادمجان", "کوفته تبریزی", "کوفته ریزه",
    "دلمه برگ مو", "دلمه بادمجان", "دلمه فلفل دلمه‌ای", "دلمه کدو", "میرزا قاسمی",
    "کشک بادمجان", "حلیم بادمجون", "خورشت بادمجان", "خورشت کدو", "خورشت کرفس",
    "پیتزا مخلوط", "پیتزا پپرونی", "برگر مخصوص", "چیزبرگر", "پاستا آلفردو", "لازانیا", "سوخاری"
]

DEFAULT_POEMS = [
    "{name} خواست منو خراب کنه، بردن تو خرابه کردنش!",
    "در ناامیدی بسی امید است، زیر لباس {name} کصی سفید است!",
    "از دیشب تا حالا شبیه‌خون زدن، {name} رو بردن و جف‌کون زدن!",
    "ای که از کوچه معشوقه ما می‌گذری، بی‌خبر از دل ما {name} رو یواشکی می‌بری!",
    "نه جانی ماند و نه دلداری ماند، {name} ماند و یک کونِ بادکرده!"
]

def get_default_db_structure() -> dict:
    return {
        "members": {},
        "hourly_messages": {},
        "recent_active_users": {},
        "last_job_reset": 0,
        "active_chats": [],
        "foods": list(DEFAULT_FOODS),
        "custom_names": [],
        "poems": list(DEFAULT_POEMS),
        "media_lef": None,
        "cooldown_minutes": 10,
        "cooldowns": {},
        "couples": {},
        "reports": {},
        "xo_games": {},
        "user_stats": {},
        "action_records": {},
        "welcome_settings": {},
        "comment_settings": {},
        "commented_channel_posts": [],
        "started_users": {},
        "admin_logs": [],
        "fun_named_responses": [],
        "fun_normal_responses": [],
        "features": {
            "world_time": True,
            "handsome": True,
            "jende": True,
            "koni": True,
            "jaghi": True,
            "ship": True,
            "food": True,
            "lef": True,
            "goh_khor": True,
            "koni_percent": True,
            "poems": True,
            "koskhal": True,
            "sexy": True,
            "jazab": True
        },
        "states": {
            "waiting_lef_media": [],
            "waiting_add_food": [],
            "waiting_del_food": [],
            "waiting_cooldown": [],
            "waiting_poem_names": [],
            "waiting_add_poem": [],
            "waiting_broadcast_group": [],
            "waiting_broadcast_msg": {},
            "waiting_welcome_msg": {},
            "waiting_comment_msg": {},
            "waiting_user_broadcast_msg": [],
            "waiting_fun_named_msg": [],
            "waiting_fun_normal_msg": []
        }
    }

def load_db() -> dict:
    global _DB_CACHE
    if _DB_CACHE is not None:
        return _DB_CACHE

    default_struct = get_default_db_structure()

    if not os.path.exists(DB_FILE):
        _DB_CACHE = default_struct
        save_db(force=True)
        return _DB_CACHE

    try:
        with open(DB_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            for key, val in default_struct.items():
                if key not in data:
                    data[key] = val
            _DB_CACHE = data
            return _DB_CACHE
    except (json.JSONDecodeError, Exception) as e:
        logger.error(f"Database corrupted! Error: {e}")
        _DB_CACHE = default_struct
        save_db(force=True)
        return _DB_CACHE

def mark_db_dirty():
    global _DB_DIRTY
    _DB_DIRTY = True

def save_db(force: bool = False):
    global _DB_DIRTY, _DB_CACHE
    if not force and not _DB_DIRTY:
        return
    if _DB_CACHE is None:
        return

    try:
        with open(TEMP_DB_FILE, "w", encoding="utf-8") as f:
            json.dump(_DB_CACHE, f, ensure_ascii=False, indent=4)
        os.replace(TEMP_DB_FILE, DB_FILE)
        _DB_DIRTY = False
    except Exception as e:
        logger.error(f"Error saving DB: {e}")

# ==========================================
# USER RESOLUTION & ADMIN LOGGING SYSTEM
# ==========================================
def resolve_target_user(update: Update, context: ContextTypes.DEFAULT_TYPE) -> tuple[int | None, str, str, str]:
    user = None
    if update.message and update.message.reply_to_message and update.message.reply_to_message.from_user:
        user = update.message.reply_to_message.from_user
    elif update.effective_user:
        user = update.effective_user

    if not user:
        return None, "کاربر مجهول", "", "کاربر مجهول"

    uid = user.id
    fname = user.full_name or user.first_name or "کاربر"
    uname = user.username or ""
    mention = get_user_mention(uid, fname)

    return uid, fname, uname, mention

def log_admin_action(db: dict, admin_id: int, admin_name: str, chat_title: str, chat_id: int, action_type: str, details: str):
    admin_logs = db.setdefault("admin_logs", [])
    now_str = get_persian_date_str()

    log_entry = {
        "admin_id": admin_id,
        "admin_name": admin_name,
        "chat_title": chat_title or "پیوی/نامشخص",
        "chat_id": chat_id,
        "action_type": action_type,
        "details": details,
        "timestamp": now_str
    }

    admin_logs.append(log_entry)
    if len(admin_logs) > 1000:
        admin_logs.pop(0)

    mark_db_dirty()
    save_db()

# ==========================================
# HELPER FUNCTIONS & STATS
# ==========================================
def get_user_mention(user_id: int, fullname: str) -> str:
    clean_name = html.escape(fullname)
    return f'<a href="tg://user?id={user_id}">{clean_name}</a>'

def get_user_stat(db: dict, user_id: int, stat_key: str) -> int:
    uid = str(user_id)
    return db.get("user_stats", {}).get(uid, {}).get(stat_key, 0)

def increment_user_stat(db: dict, user_id: int, stat_key: str, amount: int = 1):
    uid = str(user_id)
    if "user_stats" not in db:
        db["user_stats"] = {}
    if uid not in db["user_stats"]:
        db["user_stats"][uid] = {}
    db["user_stats"][uid][stat_key] = db["user_stats"][uid].get(stat_key, 0) + amount
    mark_db_dirty()
    save_db()

async def is_user_in_chat(context: ContextTypes.DEFAULT_TYPE, chat_id: int, user_id: int) -> bool:
    try:
        member = await context.bot.get_chat_member(chat_id, user_id)
        return member.status in [ChatMemberStatus.MEMBER, ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER]
    except Exception:
        return False

async def is_admin_or_owner(context: ContextTypes.DEFAULT_TYPE, chat_id: int, user_id: int) -> bool:
    if user_id == OWNER_ID:
        return True
    try:
        member = await context.bot.get_chat_member(chat_id, user_id)
        return member.status in [ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER]
    except Exception:
        return False

async def register_member(update: Update, db: dict):
    user = update.effective_user
    chat = update.effective_chat
    if not user or user.is_bot:
        return
        
    user_id = str(user.id)
    fullname = user.full_name or "کاربر"
    username = user.username or ""
    
    if user_id not in db["members"] or db["members"][user_id].get("fullname") != fullname:
        db["members"][user_id] = {"username": username, "fullname": fullname}
        mark_db_dirty()
    
    if chat and chat.type in ["group", "supergroup"]:
        chat_str = str(chat.id)
        if chat.id not in db["active_chats"]:
            db["active_chats"].append(chat.id)
            mark_db_dirty()
            
        if "hourly_messages" not in db: db["hourly_messages"] = {}
        if chat_str not in db["hourly_messages"]: db["hourly_messages"][chat_str] = {}
        db["hourly_messages"][chat_str][user_id] = db["hourly_messages"][chat_str].get(user_id, 0) + 1

        if "recent_active_users" not in db: db["recent_active_users"] = {}
        if chat_str not in db["recent_active_users"]: db["recent_active_users"][chat_str] = []
        recent_list = db["recent_active_users"][chat_str]
        
        recent_list = [u for u in recent_list if u[0] != user_id]
        recent_list.append((user_id, {"fullname": fullname, "username": username}))
        if len(recent_list) > 10:
            recent_list.pop(0)
        db["recent_active_users"][chat_str] = recent_list
        mark_db_dirty()
        
    save_db()

async def get_fast_random_member(context: ContextTypes.DEFAULT_TYPE, chat_id: int, db: dict) -> tuple:
    chat_str = str(chat_id)
    recent = db.get("recent_active_users", {}).get(chat_str, [])
    valid_recent = []
    for uid_str, info in recent:
        if await is_user_in_chat(context, chat_id, int(uid_str)):
            valid_recent.append((uid_str, info))
            
    if valid_recent:
        return random.choice(valid_recent)
    
    members = db.get("members", {})
    valid_members = []
    for uid_str, info in members.items():
        if await is_user_in_chat(context, chat_id, int(uid_str)):
            valid_members.append((uid_str, info))
    if valid_members:
        return random.choice(valid_members)
    return None

# ==========================================
# COOLDOWN SYSTEM
# ==========================================
def get_cooldown_remaining(db: dict, chat_id: int, feature: str) -> tuple[bool, int, dict]:
    chat_str = str(chat_id)
    cooldowns = db.get("cooldowns", {}).get(chat_str, {})
    if feature not in cooldowns:
        return False, 0, {}
    
    last_time = cooldowns[feature].get("timestamp", 0)
    cooldown_limit = db.get("cooldown_minutes", 10) * 60
    elapsed = datetime.now().timestamp() - last_time
    
    if elapsed < cooldown_limit:
        remaining_seconds = int(cooldown_limit - elapsed)
        return True, remaining_seconds, cooldowns[feature].get("data", {})
    return False, 0, {}

def set_cooldown_data(db: dict, chat_id: int, feature: str, data: dict):
    chat_str = str(chat_id)
    if "cooldowns" not in db: db["cooldowns"] = {}
    if chat_str not in db["cooldowns"]: db["cooldowns"][chat_str] = {}
        
    db["cooldowns"][chat_str][feature] = {
        "timestamp": datetime.now().timestamp(),
        "data": data
    }
    mark_db_dirty()
    save_db()

# ==========================================
# WELCOME & AUTOMATIC CHANNEL COMMENT & JOBS
# ==========================================
async def track_chats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    result = update.my_chat_member
    if not result:
        return

    new_status = result.new_chat_member.status
    if new_status in [ChatMemberStatus.MEMBER, ChatMemberStatus.ADMINISTRATOR]:
        welcome_msg = (
            "<b>سلام نینیا ، گودی اینجاست...! </b>"
            '<tg-emoji emoji-id="5276251363313996750">😊</tg-emoji>\n\n'
            "<b>شروع کنید به مسخره بازی که حال کنیم! </b>"
            '<tg-emoji emoji-id="5274211661870295868">😌</tg-emoji>'
        )
        try:
            await context.bot.send_message(chat_id=result.chat.id, text=welcome_msg, parse_mode=ParseMode.HTML)
        except Exception as e:
            logger.error(f"Failed to send welcome message: {e}")

async def handle_new_chat_members(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.new_chat_members:
        return

    chat = update.effective_chat
    chat_id_str = str(chat.id)
    db = load_db()

    welcome_settings = db.get("welcome_settings", {}).get(chat_id_str, {})
    
    if not welcome_settings.get("enabled", True):
        return

    day_fa, time_str = get_persian_date_info()
    chat_title = html.escape(chat.title or "گروه")

    for member in update.message.new_chat_members:
        if member.is_bot:
            continue

        user_mention = get_user_mention(member.id, member.full_name)

        if not welcome_settings.get("custom", False):
            default_text = f"سلام {user_mention} ، به گروه {chat_title} خوش آمدید!\nساعت {time_str} روز {day_fa}!"
            try:
                await update.message.reply_text(default_text, parse_mode=ParseMode.HTML)
            except Exception as e:
                logger.error(f"Error sending default welcome: {e}")
            continue

        saved_msg_id = welcome_settings.get("saved_msg_id")
        from_chat_id = welcome_settings.get("saved_from_chat_id")

        if saved_msg_id and from_chat_id:
            try:
                await context.bot.copy_message(
                    chat_id=chat.id,
                    from_chat_id=from_chat_id,
                    message_id=saved_msg_id,
                    reply_to_message_id=update.message.message_id
                )
            except Exception as e:
                logger.exception(f"Error copying custom welcome message: {e}")

async def handle_automatic_channel_comments(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if not msg:
        return

    if not getattr(msg, "is_automatic_forward", False):
        return

    chat = update.effective_chat
    if not chat or chat.type not in ["group", "supergroup"]:
        return

    chat_id_str = str(chat.id)
    db = load_db()

    comment_settings = db.get("comment_settings", {}).get(chat_id_str, {})
    if not comment_settings.get("enabled", False):
        return

    msg_key = f"{chat.id}_{msg.message_id}"
    commented_posts = db.setdefault("commented_channel_posts", [])
    if msg_key in commented_posts:
        return

    saved_msg_id = comment_settings.get("saved_msg_id")
    from_chat_id = comment_settings.get("saved_from_chat_id")

    if not saved_msg_id or not from_chat_id:
        logger.warning(f"Comment enabled for chat {chat.id} but no comment message saved.")
        return

    try:
        await context.bot.copy_message(
            chat_id=chat.id,
            from_chat_id=from_chat_id,
            message_id=saved_msg_id,
            reply_to_message_id=msg.message_id
        )
        
        commented_posts.append(msg_key)
        if len(commented_posts) > 500:
            commented_posts.pop(0)
        mark_db_dirty()
        save_db()

        logger.info(f"[CHANNEL_COMMENT_SENT] Reply to post {msg.message_id} in chat {chat.id}")
    except Exception as e:
        logger.exception(f"Error sending automatic channel comment: {e}")

async def hourly_goh_khor_job(context: ContextTypes.DEFAULT_TYPE):
    db = load_db()
    if not db["features"].get("goh_khor", True):
        return
        
    target_chat_id = context.job.chat_id
    if not target_chat_id:
        return
        
    chat_str = str(target_chat_id)
    messages_data = db.get("hourly_messages", {}).get(chat_str, {})
    if not messages_data:
        return
        
    top_user_id = max(messages_data, key=lambda k: messages_data[k])
    max_msgs = messages_data[top_user_id]
    
    if max_msgs > 0:
        member_info = db["members"].get(top_user_id, {})
        fullname = member_info.get("fullname", "کاربر")
        mention = get_user_mention(int(top_user_id), fullname)
        increment_user_stat(db, int(top_user_id), "goh_khor_hour")
        
        text = f'<tg-emoji emoji-id="5854843712181378616">🏆</tg-emoji> <b>گوه خور این ساعت</b>\n\n{mention}\n\nتو این یک ساعت خیلی حرف زدی <tg-emoji emoji-id="6033112209612082866">😂</tg-emoji>'
        try:
            await context.bot.send_message(chat_id=target_chat_id, text=text, parse_mode=ParseMode.HTML)
        except Exception as e:
            logger.error(f"Job send error: {e}")

    db["hourly_messages"][chat_str] = {}
    mark_db_dirty()
    save_db(force=True)

def setup_chat_jobs(job_queue, active_chats: list):
    if not job_queue:
        return
    for chat_id in active_chats:
        job_name = f"goh_khor_{chat_id}"
        existing_jobs = job_queue.get_jobs_by_name(job_name)
        if not existing_jobs:
            job_queue.run_repeating(hourly_goh_khor_job, interval=3600, first=3600, chat_id=chat_id, name=job_name)

async def post_init(application: Application):
    db = load_db()
    setup_chat_jobs(application.job_queue, db.get("active_chats", []))

# ==========================================
# ADMIN PANEL RENDERING
# ==========================================
def get_owner_panel_content(db: dict) -> tuple[str, InlineKeyboardMarkup]:
    """جداسازی منطق تولید متن و کیبورد پنل مالک جهت استفاده در پیام جدید یا ویرایش پیام"""
    user_count = len(db.get("started_users", {}))
    text = "<b>مالک محترم ربات 👑\n\nبه پنل اصلی مدیریت ربات خوش آمدید. گزینه مورد نظر را انتخاب کنید:</b>"
    buttons = [
        [InlineKeyboardButton("🖼 رسانه لف", callback_data="panel_media_lef", style="primary")],
        [InlineKeyboardButton("⏱ زمان محدودیت (Cooldown)", callback_data="panel_cooldown", style="primary")],
        [InlineKeyboardButton("⚙ مدیریت قابلیت ها", callback_data="panel_features", style="primary")],
        [InlineKeyboardButton("📢 پیام همگانی گروه ها", callback_data="panel_broadcast", style="primary")],
        [InlineKeyboardButton(f"📢 پیام همگانی کاربران ({user_count})", callback_data="panel_user_broadcast", style="success")],
        [InlineKeyboardButton("😈 تنظیم فحش ناموسی", callback_data="panel_fun_named", style="danger")],
        [InlineKeyboardButton("😂 تنظیم فحش عادی", callback_data="panel_fun_normal", style="primary")],
        [InlineKeyboardButton("📋 ادمین لاگ", callback_data="panel_admin_logs", style="primary")]
    ]
    return text, InlineKeyboardMarkup(buttons)

async def render_owner_panel_message(target):
    """
    پشتیبانی از هر دو ورودی CallbackQuery و Message جهت نمایش بدون خطا
    """
    db = load_db()
    text, keyboard = get_owner_panel_content(db)
    
    if hasattr(target, "edit_text"): # اگر CallbackQuery بود
        await target.edit_text(text, reply_markup=keyboard, parse_mode=ParseMode.HTML)
    elif hasattr(target, "reply_text"): # اگر Message بود
        await target.reply_text(text, reply_markup=keyboard, parse_mode=ParseMode.HTML)

# بازطراحی ساختار جدید پنل مدیریت گروه
async def render_group_admin_panel_message(query):
    text = (
        "<b>🛠 پنل مدیریت گروه</b>\n\n"
        "سلام عزیزم، به پنل مدیریت گروه خوش اومدی! 👋\n\n"
        "از طریق دکمه‌های زیر می‌تونی تنظیمات گروه رو مدیریت کنی."
    )
    buttons = [
        [
            InlineKeyboardButton("🔒 قفل ها", callback_data="panel_group_locks", style="primary"),
            InlineKeyboardButton("📋 لیست ها", callback_data="panel_group_lists", style="primary")
        ],
        [
            InlineKeyboardButton("⚙️ تنظیمات پیشرفته", callback_data="panel_group_advanced", style="primary")
        ],
        [
            InlineKeyboardButton("🔙 بستن", callback_data="panel_group_close", style="danger")
        ]
    ]
    keyboard = InlineKeyboardMarkup(buttons)
    await query.message.edit_text(text, reply_markup=keyboard, parse_mode=ParseMode.HTML)

async def render_welcome_panel_message(query, chat_id: int, db: dict):
    chat_id_str = str(chat_id)
    w_set = db.get("welcome_settings", {}).get(chat_id_str, {})
    is_enabled = w_set.get("enabled", True)
    has_custom = w_set.get("custom", False)

    status_str = "✅ فعال" if is_enabled else "❌ غیرفعال"
    custom_str = "اختصاصی تنظیم شده" if has_custom else "پیش‌فرض سیستم"

    text = (
        f"👋 <b>مدیریت خوش‌آمدگویی گروه</b>\n\n"
        f"<b>وضعیت فعلی:</b> {status_str}\n"
        f"<b>نوع پیام:</b> {custom_str}"
    )

    toggle_btn_text = "❌ غیرفعال کردن" if is_enabled else "✅ فعال کردن"
    buttons = [
        [InlineKeyboardButton(toggle_btn_text, callback_data="welcome_toggle", style="primary")],
        [InlineKeyboardButton("⚙️ تنظیم پیام خوش‌آمد", callback_data="welcome_set", style="success")],
        [InlineKeyboardButton("🗑 حذف پیام اختصاصی", callback_data="welcome_delete_confirm", style="danger")],
        [InlineKeyboardButton("🔙 بازگشت", callback_data="panel_group_advanced", style="primary")]
    ]
    await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(buttons), parse_mode=ParseMode.HTML)

async def render_comment_panel_message(query, chat_id: int, db: dict):
    chat_id_str = str(chat_id)
    c_set = db.get("comment_settings", {}).get(chat_id_str, {})
    is_enabled = c_set.get("enabled", False)
    has_custom = c_set.get("custom", False)

    status_str = "✅ فعال" if is_enabled else "❌ خاموش"
    custom_str = "ذخیره شده" if has_custom else "تنظیم نشده"

    text = (
        f"💬 <b>سیستم مدیریت کامنت اتوماتیک کانال</b>\n\n"
        f"<b>وضعیت سیستم:</b> {status_str}\n"
        f"<b>پیام کامنت:</b> {custom_str}"
    )

    toggle_btn_text = "❌ خاموش کردن" if is_enabled else "✅ فعال کردن"
    buttons = [
        [InlineKeyboardButton("💬 تنظیم کامنت", callback_data="comment_set", style="success")],
        [InlineKeyboardButton(toggle_btn_text, callback_data="comment_toggle", style="primary")],
        [InlineKeyboardButton("🗑 حذف کامنت ذخیره‌شده", callback_data="comment_delete", style="danger")],
        [InlineKeyboardButton("🔙 بازگشت", callback_data="panel_group_advanced", style="primary")]
    ]
    await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(buttons), parse_mode=ParseMode.HTML)

async def render_user_broadcast_panel_message(query, db: dict):
    started_users = db.get("started_users", {})
    user_count = len(started_users)

    text = (
        f"📢 <b>پیام همگانی به تمام کاربران خصوصی ربات</b>\n\n"
        f"👥 <b>تعداد کاربران دریافت‌کننده (Start شده):</b> <code>{user_count}</code> نفر\n\n"
        f"با کلیک روی دکمه زیر، پیام خود را بفرستید."
    )

    buttons = [
        [InlineKeyboardButton("✉️ ارسال پیام همگانی", callback_data="user_broadcast_send", style="success")],
        [InlineKeyboardButton("🔙 بازگشت", callback_data="panel_owner_main", style="primary")]
    ]
    await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(buttons), parse_mode=ParseMode.HTML)

async def render_fun_panel(query, fun_type: str, db: dict):
    title = "😈 مدیریت فحش ناموسی" if fun_type == "named" else "😂 مدیریت فحش عادی"
    key = "fun_named_responses" if fun_type == "named" else "fun_normal_responses"
    items = db.get(key, [])
    
    text = (
        f"<b>{title}</b>\n\n"
        f"<b>تعداد پاسخ‌های ثبت‌شده:</b> <code>{len(items)}</code> عدد"
    )

    add_cb = f"fun_{fun_type}_add"
    list_cb = f"fun_{fun_type}_list"
    del_all_cb = f"fun_{fun_type}_del_all"

    buttons = [
        [InlineKeyboardButton("➕ افزودن پاسخ", callback_data=add_cb, style="success")],
        [InlineKeyboardButton("📋 مشاهده پاسخ‌ها", callback_data=list_cb, style="primary")],
        [InlineKeyboardButton("🧹 حذف همه", callback_data=del_all_cb, style="danger")],
        [InlineKeyboardButton("🔙 بازگشت", callback_data="panel_owner_main", style="primary")]
    ]
    await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(buttons), parse_mode=ParseMode.HTML)

async def render_admin_logs_panel(query, db: dict):
    logs = db.get("admin_logs", [])
    recent_logs = logs[-20:][::-1]

    if not recent_logs:
        text = "📋 <b>هیچ لاگ مدیریتی ثبت نشده است.</b>"
    else:
        text = "📋 <b>۲۰ عملیات اخیر ادمین‌ها:</b>\n\n"
        for idx, l in enumerate(recent_logs, 1):
            admin_mention = get_user_mention(l["admin_id"], l["admin_name"])
            text += (
                f"<b>{idx}. {html.escape(l['action_type'])}</b>\n"
                f"👮 <b>ادمین:</b> {admin_mention}\n"
                f"🆔 <b>User ID:</b> <code>{l['admin_id']}</code>\n"
                f"👥 <b>گروه:</b> {html.escape(l['chat_title'])}\n"
                f"🆔 <b>Chat ID:</b> <code>{l['chat_id']}</code>\n"
                f"📝 <b>جزئیات:</b> {html.escape(l['details'])}\n"
                f"🕐 <b>زمان:</b> {l['timestamp']}\n"
                f"----------------------------\n"
            )

    buttons = [[InlineKeyboardButton("🔙 بازگشت", callback_data="panel_owner_main", style="primary")]]
    await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(buttons), parse_mode=ParseMode.HTML)

async def render_features_panel_message(query, db: dict):
    feats = db.get("features", {})
    def status(key):
        return "✅" if feats.get(key, True) else "❌"

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton(f"{status('world_time')} 🌍 ساعت جهانی", callback_data="toggle_world_time", style="primary")],
        [InlineKeyboardButton(f"{status('handsome')} 😎 خوشتیپ", callback_data="toggle_handsome", style="primary")],
        [InlineKeyboardButton(f"{status('jende')} 😂 جنده", callback_data="toggle_jende", style="primary")],
        [InlineKeyboardButton(f"{status('koni')} 🤣 کونی", callback_data="toggle_koni", style="primary")],
        [InlineKeyboardButton(f"{status('jaghi')} 🍌 جقی", callback_data="toggle_jaghi", style="primary")],
        [InlineKeyboardButton(f"{status('koskhal')} 🤪 کصخل", callback_data="toggle_koskhal", style="primary")],
        [InlineKeyboardButton(f"{status('sexy')} 😈 سکسی", callback_data="toggle_sexy", style="primary")],
        [InlineKeyboardButton(f"{status('jazab')} ☕️ جذاب", callback_data="toggle_jazab", style="primary")],
        [InlineKeyboardButton(f"{status('ship')} ❤️ شیپ", callback_data="toggle_ship", style="primary")],
        [InlineKeyboardButton(f"{status('food')} 🍽 غذا", callback_data="toggle_food", style="primary")],
        [InlineKeyboardButton(f"{status('lef')} 🖼 لف", callback_data="toggle_lef", style="primary")],
        [InlineKeyboardButton(f"{status('goh_khor')} 🏆 گوه خور", callback_data="toggle_goh_khor", style="primary")],
        [InlineKeyboardButton(f"{status('koni_percent')} 📊 درصد", callback_data="toggle_koni_percent", style="primary")],
        [InlineKeyboardButton("🔙 بازگشت", callback_data="panel_owner_main", style="primary")]
    ])
    await query.message.edit_text("⚙ <b>مدیریت قابلیت‌ها</b>\n\nبا کلیک روی هر دکمه، وضعیت آن را روشن یا خاموش کنید:", reply_markup=keyboard, parse_mode=ParseMode.HTML)

# Helper for TIC-TAC-TOE
def check_xo_winner(board):
    lines = [
        [0, 1, 2], [3, 4, 5], [6, 7, 8],
        [0, 3, 6], [1, 4, 7], [2, 5, 8],
        [0, 4, 8], [2, 4, 6]
    ]
    for a, b, c in lines:
        if board[a] and board[a] == board[b] == board[c]:
            return board[a]
    if None not in board:
        return "draw"
    return None

def build_xo_keyboard(game_id: str, board: list, is_finished: bool = False) -> InlineKeyboardMarkup:
    buttons = []
    
    for i in range(0, 9, 3):
        row = []
        for j in range(i, i + 3):
            cell = board[j]
            if cell == "O":
                btn = InlineKeyboardButton("O", callback_data=f"xo_move:{game_id}:{j}", icon_custom_emoji_id="5857031396723269245")
            elif cell == "X":
                btn = InlineKeyboardButton("X", callback_data=f"xo_move:{game_id}:{j}", icon_custom_emoji_id="5857415006022278161")
            else:
                btn = InlineKeyboardButton(" ", callback_data=f"xo_move:{game_id}:{j}", icon_custom_emoji_id="5911319564301376749")
            row.append(btn)
        buttons.append(row)
    
    if not is_finished:
        buttons.append([InlineKeyboardButton("تسلیم", callback_data=f"xo_surrender:{game_id}", style="danger", icon_custom_emoji_id="5839270298205035832")])
    return InlineKeyboardMarkup(buttons)

# ==========================================
# DWOZ / TIC-TAC-TOE INDEPENDENT LOGIC
# ==========================================
async def start_dwoz_game(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message:
        return
    try:
        db = load_db()
        chat_id = update.effective_chat.id
        user_id = update.effective_user.id

        game_id = f"{chat_id}_{update.message.message_id}"
        games = db.setdefault("xo_games", {})
        
        games[game_id] = {
            "host_id": user_id,
            "p1_id": None,
            "p1_name": None,
            "p2_id": None,
            "p2_name": None,
            "board": [None] * 9,
            "turn": None,
            "status": "waiting"
        }
        mark_db_dirty()
        save_db()

        txt = (
            '<b><tg-emoji emoji-id="5816739230482701944">⚡️</tg-emoji> میبینم به یکم هیجان نیاز دارین! <tg-emoji emoji-id="5818785846823755322">😻</tg-emoji></b>\n\n'
            '<b>آماده بازی دوز هستین بچهااااا؟ <tg-emoji emoji-id="5818984798298841943">⏳</tg-emoji></b>\n\n'
            '<b>با استفاده از دکمه زیر به دوز بپیوندید :</b>'
        )
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("شرکت", callback_data=f"xo_join:{game_id}", style="success", icon_custom_emoji_id="5889002570633977838")],
            [InlineKeyboardButton("بیخیال", callback_data=f"xo_cancel:{game_id}", style="danger", icon_custom_emoji_id="5848202125078699135")]
        ])
        
        await update.message.reply_text(txt, reply_markup=kb, parse_mode=ParseMode.HTML)

    except Exception:
        logger.exception("Error in start_dwoz_game:")

async def dwoz_message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return

    raw_text = update.message.text.strip().lower()
    clean = raw_text.replace("\u200c", " ")
    clean = re.sub(r"[؟?\.,!؛\-_]", "", clean).strip()

    valid_triggers = ["دوز", "گودی دوز", "گودی دوز بزار", "گودی دوز بذار", "بازی دوز"]

    if clean in valid_triggers or raw_text in valid_triggers:
        await start_dwoz_game(update, context)
        raise ApplicationHandlerStop()

# ==========================================
# CALLBACK QUERY HANDLER
# ==========================================
async def handle_callback_query(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global BROADCAST_CANCEL_FLAG
    query = update.callback_query
    data = query.data
    user_id = query.from_user.id
    chat_id = query.message.chat.id if query.message else 0
    db = load_db()

    # ۱. کمک / راهنما
    if data.startswith("help_"):
        await query.answer("Coming soon..!", show_alert=True)
        return

    # ۲. نویگیشن جدید پنل مدیریت گروه
    elif data == "panel_group_locks":
        if not await is_admin_or_owner(context, chat_id, user_id):
            await query.answer("❌ دسترسی غیرمجاز!", show_alert=True)
            return
        text = "🚧 <b>این بخش به‌زودی فعال می‌شود!</b>\n\nComing Soon"
        kb = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 بازگشت", callback_data="panel_admin_main", style="primary")]])
        await query.message.edit_text(text, reply_markup=kb, parse_mode=ParseMode.HTML)
        return

    elif data == "panel_group_advanced":
        if not await is_admin_or_owner(context, chat_id, user_id):
            await query.answer("❌ دسترسی غیرمجاز!", show_alert=True)
            return
        buttons = [
            [InlineKeyboardButton("👋 پیام خوش‌آمدگویی", callback_data="panel_welcome", style="primary")],
            [InlineKeyboardButton("💬 کامنت", callback_data="panel_comment", style="primary")],
            [InlineKeyboardButton("🍽 مدیریت غذاها", callback_data="panel_foods", style="primary")],
            [InlineKeyboardButton("📜 اسامی شعرها", callback_data="panel_poem_names", style="primary")],
            [InlineKeyboardButton("➕ افزودن شعر جدید", callback_data="panel_add_poem", style="success")],
            [InlineKeyboardButton("🔙 بازگشت", callback_data="panel_admin_main", style="primary")]
        ]
        await query.message.edit_text("<b>⚙️ تنظیمات پیشرفته گروه:</b>\n\nلطفاً گزینه مورد نظر را انتخاب کنید:", reply_markup=InlineKeyboardMarkup(buttons), parse_mode=ParseMode.HTML)
        return

    elif data == "panel_group_lists":
        if not await is_admin_or_owner(context, chat_id, user_id):
            await query.answer("❌ دسترسی غیرمجاز!", show_alert=True)
            return
        buttons = [
            [InlineKeyboardButton("📢 شعارها", callback_data="panel_list_poems", style="primary")],
            [InlineKeyboardButton("🍽 لیست غذاها", callback_data="food_page_1", style="primary")],
            [InlineKeyboardButton("🔙 بازگشت", callback_data="panel_admin_main", style="primary")]
        ]
        await query.message.edit_text("<b>📋 لیست‌های قابل مدیریت گروه:</b>", reply_markup=InlineKeyboardMarkup(buttons), parse_mode=ParseMode.HTML)
        return

    elif data == "panel_list_poems":
        if not await is_admin_or_owner(context, chat_id, user_id):
            await query.answer("❌ دسترسی غیرمجاز!", show_alert=True)
            return
        poems_list = db.get("poems", [])
        if not poems_list:
            text = "📭 <b>هنوز موردی ثبت نشده است.</b>"
        else:
            text = "📢 <b>لیست شعارهای فعال گروه:</b>\n\n"
            for idx, p in enumerate(poems_list, 1):
                clean_p = html.escape(p).replace("{name}", "نام‌کاربر")
                text += f"{idx}. {clean_p}\n"

        buttons = [[InlineKeyboardButton("🔙 بازگشت", callback_data="panel_group_lists", style="primary")]]
        await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(buttons), parse_mode=ParseMode.HTML)
        return

    elif data == "panel_group_close":
        try:
            await query.message.delete()
        except Exception:
            pass
        return

    # ۳. ادمین لاگ
    elif data == "panel_admin_logs":
        if user_id != OWNER_ID:
            await query.answer("این بخش مخصوص مالک اصلی است.", show_alert=True)
            return
        await render_admin_logs_panel(query, db)
        return

    # ۴. مدیریت فحش عادی و ناموسی
    elif data in ["panel_fun_named", "panel_fun_normal"]:
        if user_id != OWNER_ID:
            await query.answer("این بخش مخصوص مالک اصلی است.", show_alert=True)
            return
        fun_type = "named" if data == "panel_fun_named" else "normal"
        await render_fun_panel(query, fun_type, db)
        return

    elif data in ["fun_named_add", "fun_normal_add"]:
        if user_id != OWNER_ID:
            await query.answer("این بخش مخصوص مالک اصلی است.", show_alert=True)
            return
        fun_type = "named" if data == "fun_named_add" else "normal"
        state_key = "waiting_fun_named_msg" if fun_type == "named" else "waiting_fun_normal_msg"
        
        if user_id not in db["states"][state_key]:
            db["states"][state_key].append(user_id)
            mark_db_dirty()
            save_db()

        title = "ناموسی" if fun_type == "named" else "عادی"
        kb = InlineKeyboardMarkup([[InlineKeyboardButton("✅ دان", callback_data=f"fun_{fun_type}_done", style="success")]])
        await query.message.edit_text(f"<b>➕ لطفاً پاسخ‌های فحش {title} را ارسال کنید (پیام، عکس، GIF، ویدیو، Premium Emoji و...):\n\nهر زمان تمام شد دکمه «✅ دان» را بزنید یا /done را ارسال کنید.</b>", reply_markup=kb, parse_mode=ParseMode.HTML)
        return

    elif data in ["fun_named_done", "fun_normal_done"]:
        fun_type = "named" if data == "fun_named_done" else "normal"
        state_key = "waiting_fun_named_msg" if fun_type == "named" else "waiting_fun_normal_msg"
        if user_id in db["states"][state_key]:
            db["states"][state_key].remove(user_id)
            mark_db_dirty()
            save_db(force=True)
        await query.answer("تنظیم پاسخ‌ها به پایان رسید.", show_alert=True)
        await render_fun_panel(query, fun_type, db)
        return

    elif data in ["fun_named_del_all", "fun_normal_del_all"]:
        if user_id != OWNER_ID:
            await query.answer("این بخش مخصوص مالک اصلی است.", show_alert=True)
            return
        fun_type = "named" if data == "fun_named_del_all" else "normal"
        key = "fun_named_responses" if fun_type == "named" else "fun_normal_responses"
        db[key] = []
        mark_db_dirty()
        save_db(force=True)
        await query.answer("تمام پاسخ‌ها پاک شدند.", show_alert=True)
        await render_fun_panel(query, fun_type, db)
        return

    elif data in ["fun_named_list", "fun_normal_list"]:
        fun_type = "named" if data == "fun_named_list" else "normal"
        key = "fun_named_responses" if fun_type == "named" else "fun_normal_responses"
        items = db.get(key, [])
        if not items:
            await query.answer("هیچ پاسخی ثبت نشده است.", show_alert=True)
            return
        await query.answer(f"تعداد {len(items)} پاسخ ثبت گردیده است.", show_alert=True)
        return

    # ۵. پنل BROADCAST کاربران
    elif data == "panel_user_broadcast":
        if user_id != OWNER_ID:
            await query.answer("این بخش مخصوص مالک اصلی است.", show_alert=True)
            return
        await render_user_broadcast_panel_message(query, db)
        return

    elif data == "user_broadcast_send":
        if user_id != OWNER_ID:
            await query.answer("این بخش مخصوص مالک اصلی است.", show_alert=True)
            return
        db["states"]["waiting_user_broadcast_msg"] = [user_id]
        mark_db_dirty()
        save_db()
        await query.message.edit_text(
            "<b>✉️ پیام مورد نظر برای ارسال به تمام کاربران خصوصی ربات را بفرستید:</b>\n\n"
            "می‌توانید متن، عکس، GIF، ویدیو، Premium Emoji و... ارسال کنید.\n"
            "برای لغو دستور /cancel را بزنید.",
            parse_mode=ParseMode.HTML
        )
        return

    elif data == "user_broadcast_cancel":
        if user_id != OWNER_ID:
            await query.answer("این بخش مخصوص مالک اصلی است.", show_alert=True)
            return
        BROADCAST_CANCEL_FLAG = True
        await query.answer("دستور لغو ارسال شد. ارسال پیام متوقف می‌شود...", show_alert=True)
        return

    # ۶. پنل مدیریت کامنت
    elif data == "panel_comment":
        if not await is_admin_or_owner(context, chat_id, user_id):
            await query.answer("❌ دسترسی غیرمجاز!", show_alert=True)
            return
        await render_comment_panel_message(query, chat_id, db)
        return

    elif data == "comment_toggle":
        if not await is_admin_or_owner(context, chat_id, user_id):
            await query.answer("❌ دسترسی غیرمجاز!", show_alert=True)
            return
        chat_id_str = str(chat_id)
        if "comment_settings" not in db: db["comment_settings"] = {}
        c_set = db["comment_settings"].setdefault(chat_id_str, {"enabled": False, "custom": False})
        c_set["enabled"] = not c_set.get("enabled", False)
        
        log_admin_action(db, user_id, query.from_user.full_name, query.message.chat.title, chat_id, "تغییر کامنت", f"وضعیت کامنت: {c_set['enabled']}")
        
        mark_db_dirty()
        save_db()
        await render_comment_panel_message(query, chat_id, db)
        return

    elif data == "comment_set":
        if not await is_admin_or_owner(context, chat_id, user_id):
            await query.answer("❌ دسترسی غیرمجاز!", show_alert=True)
            return
        db["states"]["waiting_comment_msg"][user_id] = chat_id
        mark_db_dirty()
        save_db()
        prompt_text = (
            "<b>💬 پیام کامنتی که می‌خواهید ربات زیر پست‌های کانال ارسال کند را بفرستید:</b>\n\n"
            "می‌توانید <b>متن، عکس، GIF، ویدیو، استیکر، صوت یا فایل</b> به همراه Premium Emoji ارسال کنید.\n\n"
            "برای لغو /cancel را ارسال کنید."
        )
        await query.message.edit_text(prompt_text, parse_mode=ParseMode.HTML)
        return

    elif data == "comment_delete":
        if not await is_admin_or_owner(context, chat_id, user_id):
            await query.answer("❌ دسترسی غیرمجاز!", show_alert=True)
            return
        chat_id_str = str(chat_id)
        if "comment_settings" in db and chat_id_str in db["comment_settings"]:
            db["comment_settings"][chat_id_str]["custom"] = False
            db["comment_settings"][chat_id_str].pop("saved_msg_id", None)
            db["comment_settings"][chat_id_str].pop("saved_from_chat_id", None)
            mark_db_dirty()
            save_db()
        await query.answer("کامنت ذخیره‌شده با موفقیت حذف شد.", show_alert=True)
        await render_comment_panel_message(query, chat_id, db)
        return

    # ۷. بخش مدیریت خوش‌آمدگویی
    elif data == "panel_welcome":
        if not await is_admin_or_owner(context, chat_id, user_id):
            await query.answer("❌ دسترسی غیرمجاز!", show_alert=True)
            return
        await render_welcome_panel_message(query, chat_id, db)
        return

    elif data == "welcome_toggle":
        if not await is_admin_or_owner(context, chat_id, user_id):
            await query.answer("❌ دسترسی غیرمجاز!", show_alert=True)
            return
        chat_id_str = str(chat_id)
        if "welcome_settings" not in db: db["welcome_settings"] = {}
        w_set = db["welcome_settings"].setdefault(chat_id_str, {"enabled": True, "custom": False})
        w_set["enabled"] = not w_set.get("enabled", True)
        
        log_admin_action(db, user_id, query.from_user.full_name, query.message.chat.title, chat_id, "تغییر خوش‌آمدگویی", f"وضعیت Welcome: {w_set['enabled']}")

        mark_db_dirty()
        save_db()
        await render_welcome_panel_message(query, chat_id, db)
        return

    elif data == "welcome_set":
        if not await is_admin_or_owner(context, chat_id, user_id):
            await query.answer("❌ دسترسی غیرمجاز!", show_alert=True)
            return
        db["states"]["waiting_welcome_msg"][user_id] = chat_id
        mark_db_dirty()
        save_db()
        prompt_text = (
            "<b>👋 تنظیم پیام خوش‌آمدگویی اختصاصی:</b>\n\n"
            "لطفاً پیام خوش‌آمدگویی جدید را ارسال کنید.\n"
            "می‌توانید <b>متن، عکس، GIF، ویدیو، فایل یا صوت</b> ارسال کنید.\n\n"
            "<b>متغیرهای قابل استفاده در متن یا کپشن:</b>\n"
            "• <code>USERNAME</code> ➔ منشن واقعی کاربر جدید\n"
            "• <code>XXXX</code> ➔ نام گروه\n"
            "• <code>TIME</code> ➔ ساعت فعلی\n"
            "• <code>DAY</code> ➔ روز هفته (فارسی)\n\n"
            "برای لغو /cancel را ارسال کنید."
        )
        await query.message.edit_text(prompt_text, parse_mode=ParseMode.HTML)
        return

    elif data == "welcome_delete_confirm":
        if not await is_admin_or_owner(context, chat_id, user_id):
            await query.answer("❌ دسترسی غیرمجاز!", show_alert=True)
            return
        kb = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("✅ بله، حذف شود", callback_data="welcome_delete_do", style="danger"),
                InlineKeyboardButton("❌ لغو", callback_data="panel_welcome", style="primary")
            ]
        ])
        await query.message.edit_text("<b>آیا از حذف پیام خوش‌آمد اختصاصی و بازگشت به حالت پیش‌فرض اطمینان دارید؟</b>", reply_markup=kb, parse_mode=ParseMode.HTML)
        return

    elif data == "welcome_delete_do":
        if not await is_admin_or_owner(context, chat_id, user_id):
            await query.answer("❌ دسترسی غیرمجاز!", show_alert=True)
            return
        chat_id_str = str(chat_id)
        if "welcome_settings" in db and chat_id_str in db["welcome_settings"]:
            db["welcome_settings"][chat_id_str]["custom"] = False
            db["welcome_settings"][chat_id_str].pop("saved_msg_id", None)
            db["welcome_settings"][chat_id_str].pop("saved_from_chat_id", None)
            mark_db_dirty()
            save_db()
        await query.answer("پیام اختصاصی حذف شد و به حالت پیش‌فرض برگشت.", show_alert=True)
        await render_welcome_panel_message(query, chat_id, db)
        return

    # ۸. دوز آنلاین
    elif data.startswith("xo_"):
        parts = data.split(":")
        act = parts[0]
        game_id = parts[1]
        
        games = db.setdefault("xo_games", {})
        if game_id not in games:
            await query.answer("این بازی به اتمام رسیده است.", show_alert=True)
            return
        
        game = games[game_id]

        if act == "xo_cancel":
            if user_id != game["host_id"]:
                await query.answer("فقط ایجادکننده بازی می‌تواند بازی را لغو کند!", show_alert=True)
                return
            del games[game_id]
            mark_db_dirty()
            save_db()
            await query.message.edit_text('<b>حله! هروقت خواستید من اینجام تا راوی رقابت شما باشم! <tg-emoji emoji-id="5816531766382436821">🛠</tg-emoji></b>', parse_mode=ParseMode.HTML)
            return

        elif act == "xo_leave":
            if user_id == game.get("p1_id"):
                game["p1_id"] = game.get("p2_id")
                game["p1_name"] = game.get("p2_name")
                game["p2_id"] = None
                game["p2_name"] = None
            elif user_id == game.get("p2_id"):
                game["p2_id"] = None
                game["p2_name"] = None
            else:
                await query.answer("شما عضو این میز نیستید!", show_alert=True)
                return

            db["xo_games"][game_id] = game
            mark_db_dirty()
            save_db()

            m1_txt = get_user_mention(game["p1_id"], game["p1_name"]) if game.get("p1_id") else ""

            if m1_txt:
                txt = (
                    '<b><tg-emoji emoji-id="5816739230482701944">⚡️</tg-emoji> میبینم به یکم هیجان نیاز دارین! <tg-emoji emoji-id="5818785846823755322">😻</tg-emoji></b>\n\n'
                    '<b>آماده بازی دوز هستین بچهااااا؟ <tg-emoji emoji-id="5818984798298841943">⏳</tg-emoji></b>\n\n'
                    f'<b>شرکت کنندگان :</b>\n<b>{m1_txt}</b>\n\n'
                    '<b>- یک نفر دیگه تموممممه! کسی نبودد؟ <tg-emoji emoji-id="5431776939465516694">🔥</tg-emoji></b>\n'
                    '<b>با استفاده از دکمه زیر به دوز بپیوندید :</b>'
                )
                kb = InlineKeyboardMarkup([
                    [InlineKeyboardButton("شرکت", callback_data=f"xo_join:{game_id}", style="success", icon_custom_emoji_id="5889002570633977838"), InlineKeyboardButton("انصراف", callback_data=f"xo_leave:{game_id}", style="danger", icon_custom_emoji_id="5888594273862950655")],
                    [InlineKeyboardButton("بیخیال", callback_data=f"xo_cancel:{game_id}", style="danger", icon_custom_emoji_id="5848202125078699135")]
                ])
            else:
                txt = (
                    '<b><tg-emoji emoji-id="5816739230482701944">⚡️</tg-emoji> میبینم به یکم هیجان نیاز دارین! <tg-emoji emoji-id="5818785846823755322">😻</tg-emoji></b>\n\n'
                    '<b>آماده بازی دوز هستین بچهااااا؟ <tg-emoji emoji-id="5818984798298841943">⏳</tg-emoji></b>\n\n'
                    '<b>با استفاده از دکمه زیر به دوز بپیوندید :</b>'
                )
                kb = InlineKeyboardMarkup([
                    [InlineKeyboardButton("شرکت", callback_data=f"xo_join:{game_id}", style="success", icon_custom_emoji_id="5889002570633977838")],
                    [InlineKeyboardButton("بیخیال", callback_data=f"xo_cancel:{game_id}", style="danger", icon_custom_emoji_id="5848202125078699135")]
                ])

            await query.message.edit_text(txt, reply_markup=kb, parse_mode=ParseMode.HTML)
            await query.answer("شما از بازی انصراف دادید.")
            return

        elif act == "xo_join":
            if user_id in [game.get("p1_id"), game.get("p2_id")]:
                await query.answer("شما از قبل در بازی حضور دارید.", show_alert=True)
                return

            if not game.get("p1_id"):
                game["p1_id"] = user_id
                game["p1_name"] = query.from_user.full_name
            elif not game.get("p2_id"):
                game["p2_id"] = user_id
                game["p2_name"] = query.from_user.full_name

            db["xo_games"][game_id] = game
            mark_db_dirty()
            save_db()

            m1 = get_user_mention(game["p1_id"], game["p1_name"]) if game.get("p1_id") else ""
            m2 = get_user_mention(game["p2_id"], game["p2_name"]) if game.get("p2_id") else ""

            if game.get("p1_id") and game.get("p2_id"):
                txt = (
                    '<b><tg-emoji emoji-id="5816739230482701944">⚡️</tg-emoji> میبینم به یکم هیجان نیاز دارین! <tg-emoji emoji-id="5818785846823755322">😻</tg-emoji></b>\n\n'
                    '<b>آماده بازی دوز هستین بچهااااا؟ <tg-emoji emoji-id="5818984798298841943">⏳</tg-emoji></b>\n\n'
                    f'<b>شرکت کنندگان :</b>\n<b>{m1}</b>\n<b>{m2}</b>\n\n'
                    '<b><tg-emoji emoji-id="5474531397571986677">🚬</tg-emoji> اگر آماده‌اید روی دکمه شروع بازی کلیک کنید تا حال کنیممم!</b>'
                )
                kb = InlineKeyboardMarkup([
                    [InlineKeyboardButton("شروع بازی", callback_data=f"xo_start:{game_id}", style="success", icon_custom_emoji_id="5832397371278892338")],
                    [InlineKeyboardButton("انصراف", callback_data=f"xo_leave:{game_id}", style="danger", icon_custom_emoji_id="5888594273862950655")]
                ])
            else:
                txt = (
                    '<b><tg-emoji emoji-id="5816739230482701944">⚡️</tg-emoji> میبینم به یکم هیجان نیاز دارین! <tg-emoji emoji-id="5818785846823755322">😻</tg-emoji></b>\n\n'
                    '<b>آماده بازی دوز هستین بچهااااا؟ <tg-emoji emoji-id="5818984798298841943">⏳</tg-emoji></b>\n\n'
                    f'<b>شرکت کنندگان :</b>\n<b>{m1}</b>\n\n'
                    '<b>- یک نفر دیگه تموممممه! کسی نبودد؟ <tg-emoji emoji-id="5431776939465516694">🔥</tg-emoji></b>\n'
                    '<b>با استفاده از دکمه زیر به دوز بپیوندید :</b>'
                )
                kb = InlineKeyboardMarkup([
                    [InlineKeyboardButton("شرکت", callback_data=f"xo_join:{game_id}", style="success", icon_custom_emoji_id="5889002570633977838"), InlineKeyboardButton("انصراف", callback_data=f"xo_leave:{game_id}", style="danger", icon_custom_emoji_id="5888594273862950655")],
                    [InlineKeyboardButton("بیخیال", callback_data=f"xo_cancel:{game_id}", style="danger", icon_custom_emoji_id="5848202125078699135")]
                ])

            await query.message.edit_text(txt, reply_markup=kb, parse_mode=ParseMode.HTML)
            return

        elif act == "xo_start":
            if user_id != game.get("p1_id"):
                await query.answer("شما توانایی شروع بازی را ندارید.", show_alert=True)
                return

            game["status"] = "playing"
            game["turn"] = game["p1_id"]
            db["xo_games"][game_id] = game
            mark_db_dirty()
            save_db()

            turn_mention = get_user_mention(game['p1_id'], game['p1_name'])
            o_emoji = '<tg-emoji emoji-id="5857031396723269245">⭕️</tg-emoji>'
            txt = (
                '<b>بازی شروع شد! ببینیم برنده میدان کیه! <tg-emoji emoji-id="5818704981179505821">🕹</tg-emoji></b>\n\n'
                f'<b><tg-emoji emoji-id="5816739230482701944">⚡️</tg-emoji> نوبت بازی: {turn_mention} ({o_emoji})</b>'
            )
            kb = build_xo_keyboard(game_id, game["board"])
            await query.message.edit_text(txt, reply_markup=kb, parse_mode=ParseMode.HTML)
            return

        elif act == "xo_surrender":
            if user_id not in [game.get("p1_id"), game.get("p2_id")]:
                await query.answer("شما جزو بازیکنان این بازی نیستید!", show_alert=True)
                return

            surrender_user = query.from_user.full_name
            winner_id = game["p2_id"] if user_id == game["p1_id"] else game["p1_id"]
            winner_name = game["p2_name"] if user_id == game["p1_id"] else game["p1_name"]
            
            del games[game_id]
            mark_db_dirty()
            save_db()

            s_mention = get_user_mention(user_id, surrender_user)
            w_mention = get_user_mention(winner_id, winner_name)

            txt = (
                f'<b>اوووه! بازیکن {s_mention} تسلیم شد! <tg-emoji emoji-id="5816531766382436821">🛠</tg-emoji></b>\n'
                f'<b>- بازی با برتری بازیکن {w_mention} به اتمام رسید. <tg-emoji emoji-id="5866225658983617570">😈</tg-emoji></b>'
            )
            await query.message.edit_text(txt, parse_mode=ParseMode.HTML)
            return

        elif act == "xo_move":
            if game.get("status") != "playing":
                await query.answer("این بازی به اتمام رسیده است.", show_alert=True)
                return

            if user_id not in [game["p1_id"], game["p2_id"]]:
                await query.answer("شما جزو بازیکنان این بازی نیستید!", show_alert=True)
                return

            if user_id != game.get("turn"):
                await query.answer("نوبت شما نیست!", show_alert=True)
                return

            idx = int(parts[2])
            if game["board"][idx] is not None:
                await query.answer("این خانه قبلاً انتخاب شده است!", show_alert=True)
                return

            symbol = "O" if user_id == game["p1_id"] else "X"
            game["board"][idx] = symbol
            winner_symbol = check_xo_winner(game["board"])

            if winner_symbol:
                game["status"] = "finished"
                db["xo_games"][game_id] = game
                mark_db_dirty()
                save_db()

                kb = build_xo_keyboard(game_id, game["board"], is_finished=True)

                if winner_symbol == "draw":
                    res_txt = (
                        '<b>اوووه! میبینم که بازی تموم شده!</b>\n'
                        '<b>- ای بابا حیف شد ، دو طرف خیلی قوی بودن و بازی مساوی شد. <tg-emoji emoji-id="5870693988339553767">🦸‍♀️</tg-emoji></b>'
                    )
                else:
                    winner_id = game["p1_id"] if winner_symbol == "O" else game["p2_id"]
                    winner_name = game["p1_name"] if winner_symbol == "O" else game["p2_name"]
                    w_mention = get_user_mention(winner_id, winner_name)
                    res_txt = (
                        '<b>اوووه! میبینم که بازی تموم شده!</b>\n'
                        f'<b>- بازی با برتری بازیکن {w_mention} به اتمام رسید. <tg-emoji emoji-id="5866225658983617570">😈</tg-emoji></b>'
                    )

                try:
                    await query.message.edit_text(res_txt, reply_markup=kb, parse_mode=ParseMode.HTML)
                except Exception:
                    pass
                return

            else:
                next_turn_id = game["p2_id"] if user_id == game["p1_id"] else game["p1_id"]
                next_turn_name = game["p2_name"] if user_id == game["p1_id"] else game["p1_name"]
                next_symbol = "X" if symbol == "O" else "O"
                
                game["turn"] = next_turn_id
                db["xo_games"][game_id] = game
                mark_db_dirty()
                save_db()

                turn_mention = get_user_mention(next_turn_id, next_turn_name)
                symbol_emoji = '<tg-emoji emoji-id="5857415006022278161">❌</tg-emoji>' if next_symbol == "X" else '<tg-emoji emoji-id="5857031396723269245">⭕️</tg-emoji>'
                
                txt = (
                    '<b>بازی در جریان است... <tg-emoji emoji-id="5818704981179505821">🕹</tg-emoji></b>\n\n'
                    f'<b><tg-emoji emoji-id="5816739230482701944">⚡️</tg-emoji> نوبت بازی: {turn_mention} ({symbol_emoji})</b>'
                )

                kb = build_xo_keyboard(game_id, game["board"])
                try:
                    await query.message.edit_text(txt, reply_markup=kb, parse_mode=ParseMode.HTML)
                except Exception:
                    pass
                return

    # ۹. سیستم گزارش
    elif data.startswith("report_"):
        rep_id = data.replace("report_resolve:", "").replace("report_cancel:", "")
        reports = db.get("reports", {})
        
        if rep_id not in reports:
            await query.answer("اطلاعات این گزارش یافت نشد!", show_alert=True)
            return

        rep = reports[rep_id]

        if data.startswith("report_cancel:"):
            if user_id != rep["reporter_id"]:
                await query.answer("فقط فرد گزارش‌دهنده می‌تواند این گزارش را لغو کند!", show_alert=True)
                return
            
            del reports[rep_id]
            mark_db_dirty()
            save_db()

            txt = '<b><tg-emoji emoji-id="5829923384217050622">❓</tg-emoji> گزارش شما لغو گردید.</b>'
            await query.message.edit_text(txt, parse_mode=ParseMode.HTML)
            return

        elif data.startswith("report_resolve:"):
            if not await is_admin_or_owner(context, query.message.chat.id, user_id):
                await query.answer("فقط مدیران گروه می‌توانند گزارش را بررسی کنند!", show_alert=True)
                return

            del reports[rep_id]
            mark_db_dirty()
            save_db()

            txt = '<b><tg-emoji emoji-id="5830144944399981619">✅</tg-emoji> گزارش شما توسط مدیران بررسی شد.</b>'
            await query.message.edit_text(txt, parse_mode=ParseMode.HTML)
            return

    # ۱۰. امضای شاهدان
    if data.startswith("sign_action:"):
        rec_id = data.replace("sign_action:", "")
        records = db.get("action_records", {})
        
        if rec_id not in records:
            await query.answer("❌ اطلاعات این ثبت منقضی شده است!", show_alert=True)
            return

        rec = records[rec_id]
        if user_id == rec["target_id"]:
            await query.answer("داش کصخلی؟ میخوای به اتهام خودت رای بدی؟ 😐😂", show_alert=True)
            return

        if user_id == rec["creator_id"]:
            await query.answer(f"جقی تو نمیتونی {rec['action_title']} ای که خودت ثبت کردی رو امضاء کنی بقیه باید امضا کنن 🛑", show_alert=True)
            return

        if any(u["id"] == user_id for u in rec["signers"]):
            await query.answer("شما قبلاً این ثبت را امضا کرده‌اید!", show_alert=True)
            return

        signer_info = {"id": user_id, "name": query.from_user.full_name}
        rec["signers"].append(signer_info)
        db["action_records"][rec_id] = rec
        mark_db_dirty()
        save_db()

        await query.answer("امضای شما با موفقیت ثبت شد! ✍️")

        target_mention = get_user_mention(rec["target_id"], rec["target_name"])
        creator_mention = get_user_mention(rec["creator_id"], rec["creator_name"])
        signers_list = ", ".join([get_user_mention(u["id"], u["name"]) for u in rec["signers"]])

        new_text = (
            f"<b>{html.escape(rec['action_title'])} {target_mention} با موفقیت ثبت شد! <tg-emoji emoji-id=\"5206607081334906820\">✔️</tg-emoji></b>\n"
            f"<b>ثبت کننده {html.escape(rec['action_title'])}: {creator_mention} <tg-emoji emoji-id=\"4956745198521549627\">🌟</tg-emoji></b>\n"
            f"<b><tg-emoji emoji-id=\"5803348359972393936\">⚙️</tg-emoji> در انتظار امضای شاهدان...</b>\n\n"
            f"<b>{rec['funny_text']}</b>\n"
            f"<b>شاهدان {html.escape(rec['action_title'])}: <tg-emoji emoji-id=\"5458382591121964689\">✍️</tg-emoji></b>\n"
            f"{signers_list}"
        )

        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton(f"امضای شاهدان ({len(rec['signers'])})", callback_data=f"sign_action:{rec_id}", style="success", icon_custom_emoji_id="5859527571586161695")],
            [InlineKeyboardButton(f"آمار کل {rec['action_title']} این کاربر", callback_data=f"stat_action:{rec_id}", style="primary", icon_custom_emoji_id="5888937012253171131")]
        ])

        try:
            await query.message.edit_text(new_text, reply_markup=kb, parse_mode=ParseMode.HTML)
        except Exception:
            pass
        return

    # ۱۱. مشاهده آمار تک‌موردی
    elif data.startswith("stat_action:"):
        rec_id = data.replace("stat_action:", "")
        records = db.get("action_records", {})
        if rec_id in records:
            rec = records[rec_id]
            current_count = get_user_stat(db, rec["target_id"], rec["stat_key"])
            alert_msg = f"📊 آمار ثبت‌شده {rec['action_title']} برای {rec['target_name']} در این گروه: {current_count} بار"
            await query.answer(alert_msg, show_alert=True)
        else:
            await query.answer("اطلاعات یافت نشد!", show_alert=True)
        return

    # ۱۲. کاپل
    elif data in ["couple_agree", "couple_disagree"]:
        msg_id = str(query.message.message_id)
        couples = db.get("couples", {})
        
        if msg_id not in couples:
            await query.answer("❌ اطلاعات این شیپ منقضی شده است!", show_alert=True)
            return

        couple_data = couples[msg_id]
        created_at = couple_data.get("created_at", 0)
        
        if datetime.now().timestamp() - created_at > 30:
            await query.answer("⏳ مهلت ۳۰ ثانیه‌ای رای‌گیری به پایان رسیده است!", show_alert=True)
            try:
                await query.message.edit_reply_markup(reply_markup=None)
            except Exception:
                pass
            return

        agrees = couple_data["agrees"]
        disagrees = couple_data["disagrees"]
        user_info = {"id": user_id, "name": query.from_user.full_name}

        if data == "couple_agree":
            disagrees = [u for u in disagrees if u["id"] != user_id]
            if not any(u["id"] == user_id for u in agrees):
                agrees.append(user_info)
                await query.answer("موافقت شما ثبت شد! 👍")
            else:
                await query.answer("شما قبلاً موافقت کرده‌اید!")
        else:
            agrees = [u for u in agrees if u["id"] != user_id]
            if not any(u["id"] == user_id for u in disagrees):
                disagrees.append(user_info)
                await query.answer("مخالفت شما ثبت شد! 👎")
            else:
                await query.answer("شما قبلاً مخالفت کرده‌اید!")

        couple_data["agrees"] = agrees
        couple_data["disagrees"] = disagrees
        db["couples"][msg_id] = couple_data
        mark_db_dirty()
        save_db()

        u1, u2 = couple_data["u1"], couple_data["u2"]
        name1 = get_user_mention(u1["id"], u1["name"])
        name2 = get_user_mention(u2["id"], u2["name"])

        agrees_text = ", ".join([get_user_mention(u["id"], u["name"]) for u in agrees]) if agrees else "هیچکس"
        disagrees_text = ", ".join([get_user_mention(u["id"], u["name"]) for u in disagrees]) if disagrees else "هیچکس"

        new_text = (
            f'<b><tg-emoji emoji-id="5830106027701314719">❤️</tg-emoji> دو عدد کفتر عاشقمون این رفقان:</b>\n\n'
            f'<b><tg-emoji emoji-id="5834477789012564986">💕</tg-emoji> | {name1} <tg-emoji emoji-id="6048558196203720407">❤️</tg-emoji> {name2}</b>\n\n'
            f'<b><tg-emoji emoji-id="5819032824623144971">➕</tg-emoji>موافقان: {agrees_text}</b>\n'
            f'<b><tg-emoji emoji-id="5819154526816444042">❌</tg-emoji> مخالفان: {disagrees_text}</b>'
        )

        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("موافقم", callback_data="couple_agree", style="success", icon_custom_emoji_id="5411228694935012881"),
                InlineKeyboardButton("افتضاح", callback_data="couple_disagree", style="danger", icon_custom_emoji_id="5411484842489578182")
            ]
        ])

        try:
            await query.message.edit_text(new_text, reply_markup=keyboard, parse_mode=ParseMode.HTML)
        except Exception:
            pass
        return

    elif data == "panel_broadcast":
        if user_id != OWNER_ID:
            await query.answer("این بخش فقط برای مالک اصلی ربات می‌باشد.", show_alert=True)
            return
        
        active_chats = db.get("active_chats", [])
        if not active_chats:
            await query.answer("هیچ گروه فعالی یافت نشد!", show_alert=True)
            return

        buttons = []
        for cid in active_chats:
            try:
                chat_obj = await context.bot.get_chat(cid)
                title = chat_obj.title or str(cid)
                buttons.append([InlineKeyboardButton(f"👥 {title}", callback_data=f"bcast_chat:{cid}", style="primary")])
            except Exception:
                pass
        buttons.append([InlineKeyboardButton("🔙 بازگشت", callback_data="panel_owner_main", style="primary")])
        await query.message.edit_text("📢 <b>انتخاب گروه جهت ارسال پیام همگانی:</b>", reply_markup=InlineKeyboardMarkup(buttons), parse_mode=ParseMode.HTML)
        return

    elif data.startswith("bcast_chat:"):
        if user_id != OWNER_ID:
            await query.answer("این بخش فقط برای مالک اصلی ربات می‌باشد.", show_alert=True)
            return
        target_cid = data.replace("bcast_chat:", "")
        db["states"]["waiting_broadcast_msg"][user_id] = int(target_cid)
        mark_db_dirty()
        save_db()
        await query.message.edit_text("✉️ لطفاً پیام خود را جهت ارسال به این گروه بفرستید (از BOLD و ایموجی پشتیبانی می‌شود):\n\nبرای لغو /cancel را بزنید.")
        return

    if data == "noop":
        await query.answer()
        return

    if data == "panel_owner_main":
        if user_id != OWNER_ID:
            await query.answer("این بخش مخصوص مالک اصلی است.", show_alert=True)
            return
        await render_owner_panel_message(query)
        return

    if data == "panel_admin_main":
        if not await is_admin_or_owner(context, chat_id, user_id):
            await query.answer("❌ دسترسی غیرمجاز!", show_alert=True)
            return
        await render_group_admin_panel_message(query)
        return

    if data == "panel_media_lef":
        if user_id != OWNER_ID:
            await query.answer("این بخش مخصوص مالک اصلی است.", show_alert=True)
            return
        if user_id not in db["states"]["waiting_lef_media"]:
            db["states"]["waiting_lef_media"].append(user_id)
            mark_db_dirty()
            save_db()
        await query.message.edit_text("🖼 لطفاً رسانه مورد نظر را ارسال کنید.\n\nبرای لغو /cancel را بزنید.")
    elif data == "panel_foods":
        if not await is_admin_or_owner(context, update.effective_chat.id if update.effective_chat else 0, user_id):
            await query.answer("❌ دسترسی غیرمجاز!", show_alert=True)
            return
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("➕ افزودن غذا", callback_data="food_add", style="success")],
            [InlineKeyboardButton("➖ حذف غذا", callback_data="food_del", style="danger")],
            [InlineKeyboardButton("📋 لیست غذاها", callback_data="food_page_1", style="primary")],
            [InlineKeyboardButton("🔙 بازگشت", callback_data="panel_group_advanced", style="primary")]
        ])
        await query.message.edit_text("🍽 <b>مدیریت غذاها</b>\n\nگزینه مورد نظر را انتخاب کنید:", reply_markup=keyboard, parse_mode=ParseMode.HTML)
    elif data == "food_add":
        if not await is_admin_or_owner(context, update.effective_chat.id if update.effective_chat else 0, user_id):
            await query.answer("❌ دسترسی غیرمجاز!", show_alert=True)
            return
        if user_id not in db["states"]["waiting_add_food"]:
            db["states"]["waiting_add_food"].append(user_id)
            mark_db_dirty()
            save_db()
        await query.message.edit_text("➕ نام غذایی که می‌خواهید اضافه شود را بنویسید:\n\nبرای لغو /cancel را بزنید.")
    elif data == "food_del":
        if not await is_admin_or_owner(context, update.effective_chat.id if update.effective_chat else 0, user_id):
            await query.answer("❌ دسترسی غیرمجاز!", show_alert=True)
            return
        if user_id not in db["states"]["waiting_del_food"]:
            db["states"]["waiting_del_food"].append(user_id)
            mark_db_dirty()
            save_db()
        await query.message.edit_text("➖ نام دقیق غذایی که می‌خواهید حذف شود را بنویسید:\n\nبرای لغو /cancel را بزنید.")
    elif data == "panel_cooldown":
        if user_id != OWNER_ID:
            await query.answer("این بخش مخصوص مالک اصلی است.", show_alert=True)
            return
        if user_id not in db["states"]["waiting_cooldown"]:
            db["states"]["waiting_cooldown"].append(user_id)
            mark_db_dirty()
            save_db()
        await query.message.edit_text(f"⏱ زمان فعلی محدودیت (Cooldown): <b>{db.get('cooldown_minutes', 10)} دقیقه</b>\n\nلطفاً زمان جدید را به دقیقه (عدد انگلیسی) وارد کنید:\n\nبرای لغو /cancel را بزنید.", parse_mode=ParseMode.HTML)
    elif data == "panel_poem_names":
        if not await is_admin_or_owner(context, update.effective_chat.id if update.effective_chat else 0, user_id):
            await query.answer("❌ دسترسی غیرمجاز!", show_alert=True)
            return
        if user_id not in db["states"]["waiting_poem_names"]:
            db["states"]["waiting_poem_names"].append(user_id)
            mark_db_dirty()
            save_db()
        current_names = ", ".join(db.get("custom_names", [])) or "هیچ اسمی ثبت نشده"
        await query.message.edit_text(f"📜 <b>اسامی فعلی برای شعرها:</b>\n{current_names}\n\nلطفاً اسامی جدید را یکی‌یکی بفرستید. وقتی تمام شد دستور <code>/done</code> را ارسال کنید.\nبرای لغو دستور /cancel را بزنید.", parse_mode=ParseMode.HTML)
    elif data == "panel_add_poem":
        if not await is_admin_or_owner(context, update.effective_chat.id if update.effective_chat else 0, user_id):
            await query.answer("❌ دسترسی غیرمجاز!", show_alert=True)
            return
        if user_id not in db["states"]["waiting_add_poem"]:
            db["states"]["waiting_add_poem"].append(user_id)
            mark_db_dirty()
            save_db()
        await query.message.edit_text("➕ لطفاً شعر جدید را بفرستید. می‌تونید از کلمه <code>یوزرنیم</code> یا <code>{name}</code> برای جای‌گذاری اسم استفاده کنید:\nمثال: <code>یوزرنیم خواست منو خراب کنه بردن خرابه کردنش</code>\n\nبرای لغو /cancel را بزنید.", parse_mode=ParseMode.HTML)
    elif data == "panel_features":
        if user_id != OWNER_ID:
            await query.answer("این بخش مخصوص مالک اصلی است.", show_alert=True)
            return
        await render_features_panel_message(query, db)
    elif data.startswith("toggle_"):
        if user_id != OWNER_ID:
            await query.answer("این بخش مخصوص مالک اصلی است.", show_alert=True)
            return
        fk = data.replace("toggle_", "")
        if fk in db["features"]:
            db["features"][fk] = not db["features"][fk]
            mark_db_dirty()
            save_db()
        await render_features_panel_message(query, db)

    await query.answer()

# ==========================================
# COMMAND HANDLERS
# ==========================================
async def command_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message:
        return
    chat_type = update.effective_chat.type
    bot_info = await context.bot.get_me()
    db = load_db()
    user = update.effective_user

    if user and not user.is_bot and chat_type == "private":
        uid_str = str(user.id)
        started_users = db.setdefault("started_users", {})
        now_ts = datetime.now().timestamp()
        if uid_str not in started_users:
            started_users[uid_str] = {
                "user_id": user.id,
                "username": user.username or "",
                "fullname": user.full_name or "کاربر",
                "first_seen": now_ts,
                "last_seen": now_ts
            }
        else:
            started_users[uid_str]["last_seen"] = now_ts
            started_users[uid_str]["fullname"] = user.full_name or "کاربر"
            started_users[uid_str]["username"] = user.username or ""
        mark_db_dirty()
        save_db()
    
    if chat_type == "private":
        start_pv_msg = (
            '<b>سلام عزیزم! به ربات جذاب من خوش اومدی! <tg-emoji emoji-id="5816739230482701944">⚡️</tg-emoji></b>\n'
            '<b>با استفاده از دکمه شیشه‌ای زیر منو به گروهت اضافه کن! <tg-emoji emoji-id="5818785846823755322">😻</tg-emoji></b>\n\n'
            '<b>بعد از اضافه کردن با ارسال دستور راهنما میتونی با من آشنا بشی! <tg-emoji emoji-id="5818984798298841943">⏳</tg-emoji></b>'
        )
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("اضافه کردن گودی به گروه", url=f"https://t.me/{bot_info.username}?startgroup=true", style="success", icon_custom_emoji_id="4956745198521549627")]
        ])
        await update.message.reply_text(start_pv_msg, reply_markup=kb, parse_mode=ParseMode.HTML)
    else:
        start_group_msg = '<b>بله عزیزم؟ من تو گروهم آماده و حاضر! <tg-emoji emoji-id="5283268017025736027">🤨</tg-emoji></b>'
        await update.message.reply_text(start_group_msg, parse_mode=ParseMode.HTML)

async def command_owner_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message:
        return

    user_id = update.effective_user.id

    if user_id != OWNER_ID:
        await update.message.reply_text(
            "❌ این دستور فقط مخصوص مالک اصلی ربات می‌باشد!"
        )
        return

    await render_owner_panel_message(update.message)

async def command_admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message:
        return
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    
    if not await is_admin_or_owner(context, chat_id, user_id):
        await update.message.reply_text("❌ شما دسترسی مدیریت این گروه را ندارید.")
        return

    text = (
        "<b>🛠 پنل مدیریت گروه</b>\n\n"
        "سلام عزیزم، به پنل مدیریت گروه خوش اومدی! 👋\n\n"
        "از طریق دکمه‌های زیر می‌تونی تنظیمات گروه رو مدیریت کنی."
    )
    buttons = [
        [
            InlineKeyboardButton("🔒 قفل ها", callback_data="panel_group_locks", style="primary"),
            InlineKeyboardButton("📋 لیست ها", callback_data="panel_group_lists", style="primary")
        ],
        [
            InlineKeyboardButton("⚙️ تنظیمات پیشرفته", callback_data="panel_group_advanced", style="primary")
        ],
        [
            InlineKeyboardButton("🔙 بستن", callback_data="panel_group_close", style="danger")
        ]
    ]
    keyboard = InlineKeyboardMarkup(buttons)
    await update.message.reply_text(text, reply_markup=keyboard, parse_mode=ParseMode.HTML)

async def command_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message:
        return
    user_id = update.effective_user.id
    db = load_db()
    
    cancelled = False
    states = db.get("states", {})
    for k in ["waiting_lef_media", "waiting_add_food", "waiting_del_food", "waiting_cooldown", "waiting_poem_names", "waiting_add_poem", "waiting_fun_named_msg", "waiting_fun_normal_msg"]:
        if user_id in states.get(k, []):
            states[k].remove(user_id)
            cancelled = True
            
    if user_id in states.get("waiting_broadcast_msg", {}):
        del states["waiting_broadcast_msg"][user_id]
        cancelled = True

    if user_id in states.get("waiting_welcome_msg", {}):
        del states["waiting_welcome_msg"][user_id]
        cancelled = True

    if user_id in states.get("waiting_comment_msg", {}):
        del states["waiting_comment_msg"][user_id]
        cancelled = True

    if user_id in states.get("waiting_user_broadcast_msg", []):
        states["waiting_user_broadcast_msg"].remove(user_id)
        cancelled = True

    if cancelled:
        mark_db_dirty()
        save_db(force=True)
        await update.message.reply_text("🚫 عملیات لغو شد.")
    else:
        await update.message.reply_text("ℹ️ شما در هیچ حالت انتظاری قرار ندارید.")

async def command_done(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message:
        return
    user_id = update.effective_user.id
    db = load_db()
    
    states = db.get("states", {})
    done_anything = False

    if user_id in states.get("waiting_poem_names", []):
        states["waiting_poem_names"].remove(user_id)
        count = len(db.get("custom_names", []))
        await update.message.reply_text(f"✅ تنظیم اسامی به پایان رسید. تعداد کل اسامی ثبت‌شده: <b>{count}</b>", parse_mode=ParseMode.HTML)
        done_anything = True

    if user_id in states.get("waiting_fun_named_msg", []):
        states["waiting_fun_named_msg"].remove(user_id)
        count = len(db.get("fun_named_responses", []))
        await update.message.reply_text(f"✅ ثبت پاسخ‌های فحش ناموسی پایان یافت. تعداد کل: <b>{count}</b>", parse_mode=ParseMode.HTML)
        done_anything = True

    if user_id in states.get("waiting_fun_normal_msg", []):
        states["waiting_fun_normal_msg"].remove(user_id)
        count = len(db.get("fun_normal_responses", []))
        await update.message.reply_text(f"✅ ثبت پاسخ‌های فحش عادی پایان یافت. تعداد کل: <b>{count}</b>", parse_mode=ParseMode.HTML)
        done_anything = True

    if done_anything:
        mark_db_dirty()
        save_db(force=True)
    else:
        await update.message.reply_text("ℹ️ شما در هیچ حالت انتظاری قرار ندارید.")

# ==========================================
# MESSAGE HANDLER
# ==========================================
async def handle_messages(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global BROADCAST_CANCEL_FLAG
    if not update.message:
        return

    try:
        db = load_db()
        await register_member(update, db)
        
        if update.effective_chat and update.effective_chat.type in ["group", "supergroup"]:
            setup_chat_jobs(context.job_queue, [update.effective_chat.id])

        user_id = update.effective_user.id
        chat_id = update.effective_chat.id
        raw_text = update.message.text or ""
        clean_raw = raw_text.strip().lower()
        norm_text = normalize_text(raw_text)

        # --------------------------------------
        # HANDLER CLEANUP / پاکسازی سریع پیام‌ها
        # --------------------------------------
        match_cleanup = CLEANUP_PATTERN.match(raw_text)
        if match_cleanup:
            if not await is_admin_or_owner(context, chat_id, user_id):
                await update.message.reply_text("❌ فقط مدیران گروه دسترسی اجرای این دستور را دارند.")
                return

            count_str = match_cleanup.group("count")
            if not count_str or not count_str.isdigit() or int(count_str) <= 0:
                await update.message.reply_text("<b>فرمت دستور پاکسازی اشتباه است!\nمثال صحیح: <code>حذف 20</code></b>", parse_mode=ParseMode.HTML)
                return

            req_count = int(count_str)
            target_msg_id = update.message.message_id
            
            deleted_count = 0
            try:
                try:
                    await context.bot.delete_message(chat_id=chat_id, message_id=target_msg_id)
                except Exception:
                    pass

                for i in range(1, req_count + 1):
                    msg_id_to_del = target_msg_id - i
                    if msg_id_to_del <= 0:
                        break
                    try:
                        await context.bot.delete_message(chat_id=chat_id, message_id=msg_id_to_del)
                        deleted_count += 1
                        await asyncio.sleep(0.02)
                    except Exception as e:
                        err_s = str(e).lower()
                        if "message to delete not found" in err_s or "message can't be deleted" in err_s:
                            continue
                        elif "chat_admin_required" in err_s:
                            await update.message.reply_text("ربات دسترسی حذف پیام‌ها را ندارد.")
                            return
                        break

                log_admin_action(db, user_id, update.effective_user.full_name, update.effective_chat.title, chat_id, "پاکسازی", f"پاکسازی {deleted_count} پیام اخیر")

                success_msg = f"<b>پاکسازی {deleted_count} پیام اخیر با موفقیت انجام شد! <tg-emoji emoji-id=\"5206607081334906820\">✔️</tg-emoji></b>"
                confirm_msg = await context.bot.send_message(chat_id=chat_id, text=success_msg, parse_mode=ParseMode.HTML)
                
                await asyncio.sleep(5)
                try:
                    await context.bot.delete_message(chat_id=chat_id, message_id=confirm_msg.message_id)
                except Exception:
                    pass

            except Exception as e:
                logger.error(f"Cleanup Error: {e}")
                await update.message.reply_text("خطا در انجام پاکسازی. مطمئن شوید ربات دسترسی حذف پیام دارد.")
            return

        # --------------------------------------
        # HANDLER FUN COMMANDS: «ناموسی بده» & «فحش بده»
        # --------------------------------------
        match_fun_named = FUN_NAMED_PATTERN.match(raw_text)
        match_fun_normal = FUN_NORMAL_PATTERN.match(raw_text)

        if match_fun_named or match_fun_normal:
            is_named = bool(match_fun_named)
            match_obj = match_fun_named if is_named else match_fun_normal
            cnt_str = match_obj.group("count")
            req_cnt = int(cnt_str) if cnt_str else 1
            req_cnt = min(req_cnt, MAX_FUN_MESSAGES)

            if update.message.reply_to_message and update.message.reply_to_message.from_user and update.message.reply_to_message.from_user.id == context.bot.id:
                await update.message.reply_text(
                    '<b>منظورت چیه؟ <tg-emoji emoji-id="5829923384217050622">❓</tg-emoji></b>',
                    parse_mode=ParseMode.HTML
                )
                return

            key = "fun_named_responses" if is_named else "fun_normal_responses"
            responses_list = db.get(key, [])

            if not responses_list:
                title = "ناموسی" if is_named else "عادی"
                await update.message.reply_text(f"<b>هنوز هیچ پاسخ فحش {title} توسط مالک ثبت نشده است!</b>", parse_mode=ParseMode.HTML)
                return

            target_msg_id = update.message.reply_to_message.message_id if update.message.reply_to_message else None

            try:
                await context.bot.delete_message(chat_id=chat_id, message_id=update.message.message_id)
            except Exception:
                pass

            for _ in range(req_cnt):
                resp_item = random.choice(responses_list)
                f_chat_id = resp_item.get("from_chat_id")
                f_msg_id = resp_item.get("msg_id")

                try:
                    await context.bot.copy_message(
                        chat_id=chat_id,
                        from_chat_id=f_chat_id,
                        message_id=f_msg_id,
                        reply_to_message_id=target_msg_id
                    )
                    await asyncio.sleep(0.3)
                except Exception as e:
                    logger.error(f"Error sending fun response: {e}")
                    break
            return

        # --------------------------------------
        # HANDLER PIN / UNPIN COMMANDS (ADMIN ONLY)
        # --------------------------------------
        if clean_raw in PIN_PATTERNS or clean_raw in UNPIN_PATTERNS:
            if not await is_admin_or_owner(context, chat_id, user_id):
                await update.message.reply_text("❌ فقط مدیران گروه دسترسی اجرای این دستور را دارند.")
                return

            if not update.message.reply_to_message:
                await update.message.reply_text("<b>برای استفاده از این دستور باید روی پیام مورد نظر ریپلای کنید!</b>", parse_mode=ParseMode.HTML)
                return

            target_msg_id = update.message.reply_to_message.message_id

            if clean_raw in PIN_PATTERNS:
                try:
                    await context.bot.pin_chat_message(chat_id=chat_id, message_id=target_msg_id)
                    log_admin_action(db, user_id, update.effective_user.full_name, update.effective_chat.title, chat_id, "پین پیام", f"Message ID: {target_msg_id}")
                    await update.message.reply_text(
                        '<b>پیامتو پین کردم عزیزم! <tg-emoji emoji-id="5870593825407243361">👋</tg-emoji></b>',
                        parse_mode=ParseMode.HTML
                    )
                except Exception as e:
                    logger.error(f"Pin Error: {e}")
                    await update.message.reply_text("ربات دسترسی سنجاق کردن پیام‌ها را ندارد.")
                return

            elif clean_raw in UNPIN_PATTERNS:
                try:
                    await context.bot.unpin_chat_message(chat_id=chat_id, message_id=target_msg_id)
                    log_admin_action(db, user_id, update.effective_user.full_name, update.effective_chat.title, chat_id, "آن‌پین پیام", f"Message ID: {target_msg_id}")
                    await update.message.reply_text(
                        '<b>پیامو از پین دراوردم رفیق! <tg-emoji emoji-id="5870593825407243361">👋</tg-emoji></b>',
                        parse_mode=ParseMode.HTML
                    )
                except Exception as e:
                    logger.error(f"Unpin Error: {e}")
                    await update.message.reply_text("ربات دسترسی تغییر پیام‌های سنجاق‌شده را ندارد.")
                return

        # --------------------------------------
        # COMMAND 'کامنت روشن' / 'گودی کامنت روشن'
        # --------------------------------------
        if clean_raw in ["کامنت روشن", "گودی کامنت روشن"]:
            if not await is_admin_or_owner(context, chat_id, user_id):
                await update.message.reply_text("❌ فقط مدیران گروه دسترسی به این دستور را دارند.")
                return

            chat_id_str = str(chat_id)
            if "comment_settings" not in db: db["comment_settings"] = {}
            c_set = db["comment_settings"].setdefault(chat_id_str, {"enabled": False, "custom": False})
            c_set["enabled"] = True
            mark_db_dirty()
            save_db(force=True)

            await update.message.reply_text("✅ <b>سیستم کامنت اتوماتیک کانال برای این گروه فعال شد.</b>", parse_mode=ParseMode.HTML)
            return

        # --------------------------------------
        # TEXT COMMAND 'پنل'
        # --------------------------------------
        if clean_raw in ["پنل", "admin", "/admin"] and await is_admin_or_owner(context, chat_id, user_id):
            await command_admin_panel(update, context)
            return

        # --------------------------------------
        # ADMIN & OWNER WAITING STATES
        # --------------------------------------
        if await is_admin_or_owner(context, chat_id, user_id):
            if user_id in db["states"].get("waiting_fun_named_msg", []) and user_id == OWNER_ID:
                named_list = db.setdefault("fun_named_responses", [])
                named_list.append({
                    "msg_id": update.message.message_id,
                    "from_chat_id": update.message.chat_id
                })
                mark_db_dirty()
                save_db(force=True)
                kb = InlineKeyboardMarkup([[InlineKeyboardButton("✅ دان", callback_data="fun_named_done", style="success")]])
                await update.message.reply_text(f"✅ <b>پاسخ فحش ناموسی ذخیره شد (تعداد کل: {len(named_list)}). پاسخ بعدی را بفرستید یا «✅ دان» را بزنید.</b>", reply_markup=kb, parse_mode=ParseMode.HTML)
                return

            if user_id in db["states"].get("waiting_fun_normal_msg", []) and user_id == OWNER_ID:
                normal_list = db.setdefault("fun_normal_responses", [])
                normal_list.append({
                    "msg_id": update.message.message_id,
                    "from_chat_id": update.message.chat_id
                })
                mark_db_dirty()
                save_db(force=True)
                kb = InlineKeyboardMarkup([[InlineKeyboardButton("✅ دان", callback_data="fun_normal_done", style="success")]])
                await update.message.reply_text(f"✅ <b>پاسخ فحش عادی ذخیره شد (تعداد کل: {len(normal_list)}). پاسخ بعدی را بفرستید یا «✅ دان» را بزنید.</b>", reply_markup=kb, parse_mode=ParseMode.HTML)
                return

            if user_id in db["states"].get("waiting_user_broadcast_msg", []) and user_id == OWNER_ID:
                db["states"]["waiting_user_broadcast_msg"].remove(user_id)
                mark_db_dirty()
                save_db(force=True)

                started_users = db.get("started_users", {})
                total_users = len(started_users)

                if total_users == 0:
                    await update.message.reply_text("❌ هیچ کاربری یافت نشد.")
                    return

                status_msg = await update.message.reply_text(f"⏳ <b>شروع ارسال پیام همگانی به {total_users} کاربر...</b>", parse_mode=ParseMode.HTML)

                success_count = 0
                failed_count = 0
                blocked_count = 0
                BROADCAST_CANCEL_FLAG = False

                for uid_str, u_data in list(started_users.items()):
                    if BROADCAST_CANCEL_FLAG:
                        break

                    target_uid = u_data["user_id"]
                    try:
                        await context.bot.copy_message(
                            chat_id=target_uid,
                            from_chat_id=update.message.chat_id,
                            message_id=update.message.message_id
                        )
                        success_count += 1
                        await asyncio.sleep(0.05)
                    except Exception as e:
                        err_str = str(e).lower()
                        if "blocked" in err_str or "user is declassified" in err_str or "chat not found" in err_str:
                            blocked_count += 1
                        else:
                            failed_count += 1

                report_text = (
                    f"📢 <b>عملیات ارسال پیام همگانی پایان یافت.</b>\n\n"
                    f"👥 <b>کل کاربران:</b> {total_users}\n"
                    f"✅ <b>ارسال موفق:</b> {success_count}\n"
                    f"❌ <b>ناموفق:</b> {failed_count}\n"
                    f"🚫 <b>بلاک / لغو شده:</b> {blocked_count}"
                )
                try:
                    await status_msg.edit_text(report_text, parse_mode=ParseMode.HTML)
                except Exception:
                    await update.message.reply_text(report_text, parse_mode=ParseMode.HTML)
                return

            if user_id in db["states"].get("waiting_comment_msg", {}):
                target_chat_id = db["states"]["waiting_comment_msg"][user_id]
                del db["states"]["waiting_comment_msg"][user_id]

                chat_id_str = str(target_chat_id)
                if "comment_settings" not in db: db["comment_settings"] = {}
                
                db["comment_settings"][chat_id_str] = {
                    "enabled": True,
                    "custom": True,
                    "saved_msg_id": update.message.message_id,
                    "saved_from_chat_id": update.message.chat_id
                }
                mark_db_dirty()
                save_db(force=True)

                await update.message.reply_text("✅ <b>پیام کامنت اتوماتیک با موفقیت ذخیره و فعال شد!</b>", parse_mode=ParseMode.HTML)
                return

            if user_id in db["states"].get("waiting_welcome_msg", {}):
                target_chat_id = db["states"]["waiting_welcome_msg"][user_id]
                del db["states"]["waiting_welcome_msg"][user_id]

                chat_id_str = str(target_chat_id)
                if "welcome_settings" not in db: db["welcome_settings"] = {}
                db["welcome_settings"][chat_id_str] = {
                    "enabled": True,
                    "custom": True,
                    "saved_msg_id": update.message.message_id,
                    "saved_from_chat_id": update.message.chat_id
                }
                mark_db_dirty()
                save_db(force=True)

                await update.message.reply_text("✅ <b>پیام خوش‌آمدگویی اختصاصی این گروه با موفقیت ذخیره شد!</b>", parse_mode=ParseMode.HTML)
                return

            if user_id in db["states"].get("waiting_broadcast_msg", {}) and user_id == OWNER_ID:
                target_cid = db["states"]["waiting_broadcast_msg"][user_id]
                del db["states"]["waiting_broadcast_msg"][user_id]
                mark_db_dirty()
                save_db(force=True)
                try:
                    sent = await context.bot.send_message(
                        chat_id=target_cid,
                        text=update.message.text or "",
                        entities=update.message.entities
                    )
                    try:
                        await context.bot.pin_chat_message(chat_id=target_cid, message_id=sent.message_id)
                    except Exception:
                        logger.warning("Bot does not have pin rights in target chat, skipping pin.")
                    await update.message.reply_text("✅ پیام همگانی با موفقیت ارسال شد.")
                except Exception as e:
                    await update.message.reply_text(f"❌ خطا در ارسال پیام همگانی: {e}")
                return

            if user_id in db["states"].get("waiting_lef_media", []) and user_id == OWNER_ID:
                media = None
                if update.message.sticker: media = {"type": "sticker", "file_id": update.message.sticker.file_id}
                elif update.message.photo: media = {"type": "photo", "file_id": update.message.photo[-1].file_id}
                elif update.message.animation: media = {"type": "animation", "file_id": update.message.animation.file_id}
                elif update.message.video: media = {"type": "video", "file_id": update.message.video.file_id}
                    
                if media:
                    db["media_lef"] = media
                    db["states"]["waiting_lef_media"].remove(user_id)
                    mark_db_dirty()
                    save_db(force=True)
                    await update.message.reply_text("✅ رسانه لف ذخیره شد.")
                    return

            if user_id in db["states"].get("waiting_add_food", []):
                if raw_text:
                    food_item = raw_text.strip()
                    if food_item.lower() in [f.strip().lower() for f in db["foods"]]:
                        await update.message.reply_text("❌ این غذا قبلاً وجود داشته!")
                    else:
                        db["foods"].append(food_item)
                        await update.message.reply_text(f"✅ «{food_item}» اضافه شد.")
                    db["states"]["waiting_add_food"].remove(user_id)
                    mark_db_dirty()
                    save_db(force=True)
                    return

            if user_id in db["states"].get("waiting_del_food", []):
                if raw_text:
                    food_item = raw_text.strip()
                    target_idx = next((i for i, f in enumerate(db["foods"]) if f.strip().lower() == food_item.lower()), None)
                    if target_idx is not None:
                        rm = db["foods"].pop(target_idx)
                        await update.message.reply_text(f"✅ «{rm}» حذف شد.")
                    else:
                        await update.message.reply_text("❌ این غذا یافت نشد!")
                    db["states"]["waiting_del_food"].remove(user_id)
                    mark_db_dirty()
                    save_db(force=True)
                    return

            if user_id in db["states"].get("waiting_cooldown", []) and user_id == OWNER_ID:
                if raw_text and raw_text.isdigit():
                    val = int(raw_text)
                    if val > 0:
                        db["cooldown_minutes"] = val
                        await update.message.reply_text(f"✅ زمان محدودیت با موفقیت روی <b>{val} دقیقه</b> تنظیم شد.", parse_mode=ParseMode.HTML)
                    db["states"]["waiting_cooldown"].remove(user_id)
                    mark_db_dirty()
                    save_db(force=True)
                    return

            if user_id in db["states"].get("waiting_poem_names", []):
                if raw_text and not raw_text.startswith("/"):
                    name_item = raw_text.strip()
                    if "custom_names" not in db: db["custom_names"] = []
                    db["custom_names"].append(name_item)
                    mark_db_dirty()
                    save_db(force=True)
                    await update.message.reply_text(f"✅ اسم «{name_item}» ثبت شد. اسم بعدی را بفرستید یا /done را بزنید.")
                    return

            if user_id in db["states"].get("waiting_add_poem", []):
                if raw_text and not raw_text.startswith("/"):
                    poem_item = raw_text.strip().replace("یوزرنیم", "{name}")
                    if "poems" not in db: db["poems"] = []
                    db["poems"].append(poem_item)
                    db["states"]["waiting_add_poem"].remove(user_id)
                    mark_db_dirty()
                    save_db(force=True)
                    await update.message.reply_text("✅ شعر جدید با موفقیت اضافه شد.")
                    return

        features = db.get("features", {})

        # --------------------------------------
        # HELP / راهنما PANEL با ایموجی پریمیوم و عنوان جدید «راهنمای مدیریتی»
        # --------------------------------------
        help_triggers = [
            "راهنما", "/help", "گودی راهنما", "گودی معرفی کن", 
            "گودی چیا بلدی؟", "چیا بلدی؟", "چیا بلدی", "گودی چیا بلدی"
        ]
        if clean_raw in help_triggers:
            txt = (
                '<b>سلام عزیزم به ربات من خوش اومدی! <tg-emoji emoji-id="5352750090974929602">😍</tg-emoji></b>\n\n'
                '<b>از طریق دکمه‌های زیر میتونی کاملا با گودی که یه میمون کوچولو هست آشنا بشی! <tg-emoji emoji-id="5413391520206169048">🐻</tg-emoji></b>\n'
                '<b>- برخی از دستورات بدون ادمین بودن کار می‌کنند ولی برخی دیگر نیازمند دسترسی مدیریت هستند.</b>'
            )

            kb = InlineKeyboardMarkup([
                [
                    InlineKeyboardButton("راهنمای سرگرمی", callback_data="help_fun", style="primary", icon_custom_emoji_id="5415940089375106928"),
                    InlineKeyboardButton("راهنمای بی ادبی", callback_data="help_rude", style="primary", icon_custom_emoji_id="5832633418386513259")
                ],
                [
                    InlineKeyboardButton("راهنمای کاربردی", callback_data="help_useful", style="primary", icon_custom_emoji_id="5830338333892418460"),
                    InlineKeyboardButton("راهنمای مدیریتی", callback_data="help_admin", style="primary", icon_custom_emoji_id="5803348359972393936")
                ]
            ])
            await update.message.reply_text(txt, reply_markup=kb, parse_mode=ParseMode.HTML)
            return

        # --------------------------------------
        # REPORT SYSTEM / سیستم گزارش با ایموجی پریمیوم & پاسخ دفاعی ربات
        # --------------------------------------
        if clean_raw in ["گزارش", "report"] and update.message.reply_to_message:
            target_msg = update.message.reply_to_message
            if target_msg.from_user and target_msg.from_user.id == context.bot.id:
                reply_bot_text = '<b>منو گزارش میدی؟! <tg-emoji emoji-id="5818704981179505821">🕹</tg-emoji></b>'
                await update.message.reply_text(reply_bot_text, parse_mode=ParseMode.HTML)
                return

            rep_id = f"{chat_id}_{update.message.message_id}"
            if "reports" not in db: db["reports"] = {}
            db["reports"][rep_id] = {
                "reporter_id": user_id,
                "target_msg_id": target_msg.message_id
            }
            mark_db_dirty()
            save_db()

            admin_mentions = ""
            try:
                admins = await context.bot.get_chat_administrators(chat_id)
                admin_mentions = "".join([f'<a href="tg://user?id={a.user.id}">&#8203;</a>' for a in admins if not a.user.is_bot])
            except Exception:
                pass

            txt = f'<b><tg-emoji emoji-id="5819051035284479206">🚨</tg-emoji> گزارش شما برای مدیران گروه ارسال شد!</b>{admin_mentions}'
            kb = InlineKeyboardMarkup([
                [
                    InlineKeyboardButton("بررسی شد", callback_data=f"report_resolve:{rep_id}", style="success", icon_custom_emoji_id="5206607081334906820"),
                    InlineKeyboardButton("حذف", callback_data=f"report_cancel:{rep_id}", style="danger", icon_custom_emoji_id="5819154526816444042")
                ]
            ])
            await update.message.reply_text(txt, reply_markup=kb, parse_mode=ParseMode.HTML)
            return

        # --------------------------------------
        # DODOL / FUN RESPONSE با اصلاح ASCII ART
        # --------------------------------------
        if DODOL_PATTERN.search(raw_text):
            ascii_penis = (
                "⣿⣿⣿⣿⣿⣿⣿⣿⣿⠟⠛⢉⢉⢉⢉⠻⣿⣿⣿⣿⣿⣿\n"
                "⣿⣿⣿⣿⣿⣿⣿⠟⠠⡰⣕⣗⣷⣧⣝⣅⠘⣿⣿⣿⣿⣿\n"
                "⣿⣿⣿⣿⣿⣿⠃⣠⣳⣟⣿⣿⣷⣿⡿⣜⠄⣿⣿⣿⣿⣿\n"
                "⣿⣿⣿⣿⡿⠁⠄⣳⢷⣿⣿⣿⣿⡿ issue⠖⠄⣿⣿⣿⣿⣿\n"
                "⣿⣿⣿⣿⠃⠄⢢⡹⣿⢷⣯⢿⢷⡫⣗⠍ military⢰⣿⣿⣿⣿⣿\n"
                "⣿⣿⣿⡏⢀⢄⠤⣁⠋⠿⣗⣟⡯⡏⢎⠁⢸⣿⣿⣿⣿⣿\n"
                "⣿⣿⣿⠄⢔⢕⣯⣿⣿⡲⡤⡄⡤⠄⡀⢠⣿⣿⣿⣿⣿⣿\n"
                "⣿⣿⠇⠠⡳⣯⣿⣿⣾⢵⣫⢎⢎⠆⢀⣿⣿⣿⣿⣿⣿⣿\n"
                "⣿⣿⠄⢨⣫⣿⣿⡿⣿⣻⢎⡗⡕⡅⢸⣿⣿⣿⣿⣿⣿⣿\n"
                "⣿⣿⠄⢜⢾⣾⣿⣿⣟⣗⡪⡳⡀⢸⣿⣿⣿⣿⣿⣿⣿\n"
                "⣿⣿⠄⢸⢽⣿⣷⣿⣻⡮⡧⡳⡱⡁⢸⣿⣿⣿⣿⣿⣿⣿\n"
                "⣿⣿⡄⢨⣻⣽⣿⣟⣿⣞⣗⡽⡸⡐⢸⣿⣿⣿⣿⣿⣿⣿\n"
                "⣿⣿⡇⢀⢗⣿⣿⣿⣿⡿⣞⡵⡣⣊⢸⣿⣿⣿⣿⣿⣿⣿\n"
                "⣿⣿⣿⡀⡣⣗⣿⣿⣿⣿⣯⡯⡺⣼⠎⣿⣿⣿⣿⣿⣿⣿\n"
                "⣿⣿⣿⣧⠐⡵⣻⣟⣯⣿⣷⣟⣝⢞⡿⢹⣿⣿⣿⣿⣿⣿\n"
                "⣿⣿⣿⣿⡆⢘⡺⣽⢿⣻⣿⣗⡷⣹⢩⢃⢿⣿⣿⣿⣿⣿\n"
                "⣿⣿⣿⣿⣷⠄⠪⣯⣟⣿⢯⣿⣻⣜⢎⢆⠜⣿⣿⣿⣿⣿\n"
                "⣿⣿⣿⣿⣿⡆⠄⢣⣻⣽⣿⣿⣟⣾⡮⡺⡸⠸⣿⣿⣿⣿\n"
                "⣿⣿⠛⠉⠁⠄⢕⡳⣽⡾⣿⢽⣯⡿⣮⢚⣅⠹⣿⣿⣿\n"
                "⡿⠋⠄⠄⠄⠄⢀⠒⠝⣞⢿⡿⣿⣽⢿⡽⣧⣳⡅⠌⠻⣿\n"
                "⠁⠄⠄⠄⠄⠄⠐⡐ screen⠱⡱⣻⡻⣝⣮⣟⣿⣿⣿⣿⣿⣿⣿"
            )
            clean_ascii = re.sub(r"[a-zA-Z]+", "", ascii_penis)
            msg1 = await update.message.reply_text(f"<code>{clean_ascii}</code>", parse_mode=ParseMode.HTML)
            await msg1.reply_text('<b>میخوریش برام؟؟ <tg-emoji emoji-id="5431423351987916271">👅</tg-emoji></b>', parse_mode=ParseMode.HTML)
            return

        # --------------------------------------
        # BOT NAME RESPONSES با ایموجی پریمیوم (پاسخ به «گودی» بدون نیاز به Reply)
        # --------------------------------------
        is_reply_to_bot = (
            update.message.reply_to_message and 
            update.message.reply_to_message.from_user and 
            update.message.reply_to_message.from_user.id == context.bot.id
        )

        # دفاع خودکار گودی با ایموجی پریمیوم
        if is_reply_to_bot and (clean_raw.startswith("درصد ") or clean_raw.startswith("این چقدر ") or clean_raw.startswith("این چقد ")):
            topic = clean_raw.replace("درصد ", "").replace("این چقدر ", "").replace("این چقد ", "").replace(" بودن", "").replace("ش", "").replace("ه", "").strip()
            topic_clean = html.escape(topic)
            await update.message.reply_text(
                f'<b>{topic_clean} خودتی! <tg-emoji emoji-id="5886539179256450622">🤪</tg-emoji></b>',
                parse_mode=ParseMode.HTML
            )
            return

        if (is_reply_to_bot and clean_raw in ["تو کی هستی", "تو کی هستی؟"]):
            await update.message.reply_text('<b>من گودی هستم خوشگله! <tg-emoji emoji-id="5321415182109401472">😽</tg-emoji></b>', parse_mode=ParseMode.HTML)
            return

        elif clean_raw == "گودی" or (is_reply_to_bot and clean_raw in ["گودی", "گودی؟"]):
            await update.message.reply_text('<b>بله خودم هستم چیکارم دارین؟ <tg-emoji emoji-id="5276088141671846201">🌟</tg-emoji></b>', parse_mode=ParseMode.HTML)
            return

        # --------------------------------------
        # ACTION REGISTRATION SYSTEM با ایموجی پریمیوم (استفاده از سیستم جدید Resolve User)
        # --------------------------------------
        action_type = None
        if any(k in clean_raw for k in ["ثبت گوه خوری", "ثبت گوهخوری"]): action_type = "goh_khori"
        elif any(k in clean_raw for k in ["ثبت کصلیسی", "ثبت کص لیسی"]): action_type = "kos_lisi"
        elif any(k in clean_raw for k in ["ثبت خایمالی", "ثبت خایه مالی"]): action_type = "khaymali"
        elif any(k in clean_raw for k in ["ثبت کصخلی", "ثبت کص خلی"]): action_type = "kos_khali"
        elif any(k in clean_raw for k in ["ثبت جندگی", "ثبت جنده گی"]): action_type = "jendegi"

        if action_type:
            if not update.message.reply_to_message:
                await update.message.reply_text("<b>❌ برای ثبت باید روی پیام یک نفر ریپلای کنی!</b>", parse_mode=ParseMode.HTML)
                return

            target_uid, target_fname, target_uname, target_mention = resolve_target_user(update, context)

            if target_uid:
                if target_uid == context.bot.id:
                    await update.message.reply_text('<b><tg-emoji emoji-id="6041764253726150869">😐</tg-emoji> خیلی کارت زشت بود!</b>', parse_mode=ParseMode.HTML)
                    return
                
                if target_uid == user_id:
                    await update.message.reply_text('<b><tg-emoji emoji-id="6044308162855571406">😒</tg-emoji> داری سعی میکنی روی خودت انجام بدی؟ خود درگیری داری مگه داداش!</b>', parse_mode=ParseMode.HTML)
                    return

                action_configs = {
                    "goh_khori": {
                        "title": "گوه‌خوری",
                        "stat_key": "goh_khori",
                        "icon_id": "5819051035284479206",
                        "funny_text": "گوه‌خوری نوین مشاهده شد!"
                    },
                    "kos_lisi": {
                        "title": "کصلیسی",
                        "stat_key": "kos_lisi",
                        "icon_id": "5832692422647226240",
                        "funny_text": "مدال شجاعت کصلیسی تعلق گرفت!"
                    },
                    "khaymali": {
                        "title": "خایمالی",
                        "stat_key": "khaymali",
                        "icon_id": "5920300405341820405",
                        "funny_text": "خایمال‌نامه جدید صادر شد!"
                    },
                    "kos_khali": {
                        "title": "کصخلی",
                        "stat_key": "kos_khali",
                        "icon_id": "5443038326535759644",
                        "funny_text": "پرونده پزشکی کصخلی تنظیم شد!"
                    },
                    "jendegi": {
                        "title": "جندگی",
                        "stat_key": "jendegi",
                        "icon_id": "4974615079971455718",
                        "funny_text": "ثبت جندگی جدید در سیستم با موفقیت ثبت شد!"
                    }
                }
                cfg = action_configs[action_type]
                rec_id = f"{chat_id}_{update.message.message_id}"
                
                increment_user_stat(db, target_uid, cfg["stat_key"])

                if "action_records" not in db: db["action_records"] = {}
                db["action_records"][rec_id] = {
                    "target_id": target_uid,
                    "target_name": target_fname,
                    "creator_id": user_id,
                    "creator_name": update.effective_user.full_name,
                    "action_title": cfg["title"],
                    "stat_key": cfg["stat_key"],
                    "funny_text": cfg["funny_text"],
                    "signers": []
                }
                mark_db_dirty()
                save_db()

                creator_mention = get_user_mention(user_id, update.effective_user.full_name)

                init_msg = (
                    f"<b>{cfg['title']} {target_mention} با موفقیت ثبت شد! <tg-emoji emoji-id=\"5206607081334906820\">✔️</tg-emoji></b>\n"
                    f"<b>ثبت کننده {cfg['title']}: {creator_mention} <tg-emoji emoji-id=\"4956745198521549627\">🌟</tg-emoji></b>\n"
                    f"<b><tg-emoji emoji-id=\"5803348359972393936\">⚙️</tg-emoji> در انتظار امضای شاهدان...</b>\n\n"
                    f"<b>{cfg['funny_text']} <tg-emoji emoji-id=\"{cfg['icon_id']}\">🔥</tg-emoji></b>"
                )

                kb = InlineKeyboardMarkup([
                    [InlineKeyboardButton("امضای شاهدان (۰)", callback_data=f"sign_action:{rec_id}", style="success", icon_custom_emoji_id="5859527571586161695")],
                    [InlineKeyboardButton(f"آمار کل {cfg['title']} این کاربر", callback_data=f"stat_action:{rec_id}", style="primary", icon_custom_emoji_id="5888937012253171131")]
                ])

                await update.message.reply_text(init_msg, reply_markup=kb, parse_mode=ParseMode.HTML)
                return

        # --------------------------------------
        # STATS & OVERALL USER STATUS با ایموجی پریمیوم
        # --------------------------------------
        is_asking_own_stats = clean_raw in ["آمارم", "آمار من", "وضعیت من"]
        is_asking_other_stats = clean_raw in ["اوضاع این", "اوضاعش", "آمار این", "وضعیت این", "وضعیت"] and update.message.reply_to_message

        if is_asking_own_stats or is_asking_other_stats:
            if is_asking_own_stats:
                target_id = user_id
                header_str = '<b><tg-emoji emoji-id="5375056987174216702">😏</tg-emoji> آمار شما به شرح ذیل می‌باشد :</b>\n\n'
            else:
                target_uid, target_fname, target_uname, target_mention = resolve_target_user(update, context)
                target_id = target_uid
                header_str = f'<b><tg-emoji emoji-id="5375056987174216702">😏</tg-emoji> آمار {target_mention} به شرح ذیل می‌باشد :</b>\n\n'

            stats_msg = (
                f"{header_str}"
                f'<b><tg-emoji emoji-id="5433681959324754801">💩</tg-emoji> تعداد گوه‌خوری : {get_user_stat(db, target_id, "goh_khori")}</b>\n'
                f'<b><tg-emoji emoji-id="5863828384332647680">👅</tg-emoji> تعداد کصلیسی : {get_user_stat(db, target_id, "kos_lisi")}</b>\n'
                f'<b><tg-emoji emoji-id="5429327730070009271">🤲</tg-emoji> تعداد خایمالی : {get_user_stat(db, target_id, "khaymali")}</b>\n'
                f'<b><tg-emoji emoji-id="5983342699816685361">👑</tg-emoji> تعداد جندگی : {get_user_stat(db, target_id, "jendegi")}</b>\n'
                f'<b><tg-emoji emoji-id="5886539179256450622">🤪</tg-emoji> تعداد کصخلی : {get_user_stat(db, target_id, "kos_khali")}</b>\n'
                f'<b><tg-emoji emoji-id="5195297917048462460">🍌</tg-emoji> تعداد جقی بودن : {get_user_stat(db, target_id, "jaghi")}</b>\n'
                f'<b><tg-emoji emoji-id="5922483378304586599">🐙</tg-emoji> تعداد کونی بودن : {get_user_stat(db, target_id, "koni")}</b>\n'
                f'<b><tg-emoji emoji-id="5314297755579986373">😊</tg-emoji> تعداد سکسی شدن : {get_user_stat(db, target_id, "sexy")}</b>\n'
                f'<b><tg-emoji emoji-id="5771442740147523468">❤️</tg-emoji> تعداد جذاب شدن : {get_user_stat(db, target_id, "jazab")}</b>\n'
                f'<b><tg-emoji emoji-id="5283151000641757020">😎</tg-emoji> تعداد خوژتیپ شدن : {get_user_stat(db, target_id, "handsome")}</b>\n'
                f'<b><tg-emoji emoji-id="5406926593698312391">❤️</tg-emoji> تعداد کاپل شدن : {get_user_stat(db, target_id, "ship")}</b>\n'
                f'<b><tg-emoji emoji-id="5854843712181378616">🏆</tg-emoji> تعداد پر حرف بودن : {get_user_stat(db, target_id, "goh_khor_hour")}</b>'
            )
            await update.message.reply_text(stats_msg, parse_mode=ParseMode.HTML)
            return

        # --------------------------------------
        # GENERAL PERCENTAGE SYSTEM با ایموجی پریمیوم
        # --------------------------------------
        if clean_raw.startswith("درصد ") or clean_raw.startswith("این چقدر ") or clean_raw.startswith("این چقد "):
            target_uid, target_fname, target_uname, target_mention = resolve_target_user(update, context)
            topic = clean_raw.replace("درصد ", "").replace("این چقدر ", "").replace("این چقد ", "").replace(" بودن", "").strip()
            val = random.randint(0, 100)
            
            rand_emoji_id = random.choice([
                "5886539179256450622", "5922483378304586599", 
                "5195297917048462460", "5983342699816685361"
            ])
            
            await update.message.reply_text(
                f"{target_mention}\n\n"
                f'<tg-emoji emoji-id="{rand_emoji_id}">🎲</tg-emoji> <b>{val}٪ {html.escape(topic)}ه</b>',
                parse_mode=ParseMode.HTML
            )
            return

        # --------------------------------------
        # INDIVIDUAL COUNTRY WORLD TIME با آیدی پریمیوم پرچم‌ها
        # --------------------------------------
        country_zones = {
            "ایران": ("Asia/Tehran", "5271878966347601947", "🇮🇷"),
            "آمریکا": ("America/New_York", "5927292517610426176", "🇺🇸"),
            "امریکا": ("America/New_York", "5927292517610426176", "🇺🇸"),
            "آلمان": ("Europe/Berlin", "5409360418520967565", "🇩🇪"),
            "انگلیس": ("Europe/London", "5229192892710402006", "🏴󠁧󠁢󠁥󠁮󠁧󠁿"),
            "ترکیه": ("Europe/Istanbul", "5226948110873278599", "🇹🇷"),
            "هندوستان": ("Asia/Kolkata", "6136551252781172945", "🇮🇳"),
            "هند": ("Asia/Kolkata", "6136551252781172945", "🇮🇳"),
            "عربستان": ("Asia/Riyadh", "5202079966761590204", "🇸🇦"),
            "فرانسه": ("Europe/Paris", "5931269906434624310", "🇫🇷"),
            "چین": ("Asia/Shanghai", "5431782733376399004", "🇨🇳"),
            "ویتنام": ("Asia/Bangkok", "5474542319673812606", "🇻🇳"),
            "قطر": ("Asia/Qatar", "5228799250367788944", "🇶🇦"),
            "کره جنوبی": ("Asia/Seoul", "5456531898304047227", "🇰🇷"),
            "کره": ("Asia/Seoul", "5456531898304047227", "🇰🇷"),
            "ژاپن": ("Asia/Tokyo", "5456261908069885892", "🇯🇵"),
            "فنلاند": ("Europe/Helsinki", "5382151560182642075", "🇫🇮"),
        }

        if norm_text.startswith("ساعت "):
            c_name = norm_text.replace("ساعت ", "").strip()
            if c_name in country_zones:
                tz, emoji_id, fallback = country_zones[c_name]
                c_time = datetime.now(ZoneInfo(tz)).strftime("%H:%M:%S")
                await update.message.reply_text(f'<b><tg-emoji emoji-id="{emoji_id}">{fallback}</tg-emoji> ساعت {c_name}: <code>{c_time}</code></b>', parse_mode=ParseMode.HTML)
                return

        # ۱. ساعت جهانی کامل با دستورات «ساعت» و «ساعت جهانی»
        if norm_text in ["ساعت جهانی", "ساعت"] and features.get("world_time", True):
            now_tehran = datetime.now(ZoneInfo("Asia/Tehran")).strftime("%H:%M:%S")
            now_ny = datetime.now(ZoneInfo("America/New_York")).strftime("%H:%M:%S")
            now_germany = datetime.now(ZoneInfo("Europe/Berlin")).strftime("%H:%M:%S")
            now_london = datetime.now(ZoneInfo("Europe/London")).strftime("%H:%M:%S")
            now_istanbul = datetime.now(ZoneInfo("Europe/Istanbul")).strftime("%H:%M:%S")
            now_mumbai = datetime.now(ZoneInfo("Asia/Kolkata")).strftime("%H:%M:%S")
            now_riyadh = datetime.now(ZoneInfo("Asia/Riyadh")).strftime("%H:%M:%S")
            now_paris = datetime.now(ZoneInfo("Europe/Paris")).strftime("%H:%M:%S")
            now_beijing = datetime.now(ZoneInfo("Asia/Shanghai")).strftime("%H:%M:%S")
            now_hanoi = datetime.now(ZoneInfo("Asia/Bangkok")).strftime("%H:%M:%S")
            now_doha = datetime.now(ZoneInfo("Asia/Qatar")).strftime("%H:%M:%S")
            now_seoul = datetime.now(ZoneInfo("Asia/Seoul")).strftime("%H:%M:%S")
            now_tokyo = datetime.now(ZoneInfo("Asia/Tokyo")).strftime("%H:%M:%S")
            now_helsinki = datetime.now(ZoneInfo("Europe/Helsinki")).strftime("%H:%M:%S")

            msg = (
                '<b><tg-emoji emoji-id="5399898266265475100">🌍</tg-emoji> ساعت جهانی برخی از کشورها :</b>\n\n'
                f'<b><tg-emoji emoji-id="5271878966347601947">🇮🇷</tg-emoji> ایران: {now_tehran}</b>\n'
                f'<b><tg-emoji emoji-id="5927292517610426176">🇺🇸</tg-emoji> آمریکا: {now_ny}</b>\n'
                f'<b><tg-emoji emoji-id="5409360418520967565">🇩🇪</tg-emoji> آلمان: {now_germany}</b>\n'
                f'<b><tg-emoji emoji-id="5229192892710402006">🏴󠁧󠁢󠁥󠁮󠁧󠁿</tg-emoji> انگلیس: {now_london}</b>\n'
                f'<b><tg-emoji emoji-id="5226948110873278599">🇹🇷</tg-emoji> ترکیه: {now_istanbul}</b>\n'
                f'<b><tg-emoji emoji-id="6136551252781172945">🇮🇳</tg-emoji> هندوستان: {now_mumbai}</b>\n'
                f'<b><tg-emoji emoji-id="5202079966761590204">🇸🇦</tg-emoji> عربستان: {now_riyadh}</b>\n'
                f'<b><tg-emoji emoji-id="5931269906434624310">🇫🇷</tg-emoji> فرانسه: {now_paris}</b>\n'
                f'<b><tg-emoji emoji-id="5431782733376399004">🇨🇳</tg-emoji> چین: {now_beijing}</b>\n'
                f'<b><tg-emoji emoji-id="5474542319673812606">🇻🇳</tg-emoji> ویتنام: {now_hanoi}</b>\n'
                f'<b><tg-emoji emoji-id="5228799250367788944">🇶🇦</tg-emoji> قطر: {now_doha}</b>\n'
                f'<b><tg-emoji emoji-id="5456531898304047227">🇰🇷</tg-emoji> کره جنوبی: {now_seoul}</b>\n'
                f'<b><tg-emoji emoji-id="5456261908069885892">🇯🇵</tg-emoji> ژاپن: {now_tokyo}</b>\n'
                f'<b><tg-emoji emoji-id="5382151560182642075">🇫🇮</tg-emoji> فنلاند: {now_helsinki}</b>'
            )
            await update.message.reply_text(msg, parse_mode=ParseMode.HTML)

        # ۲. خوشتیپ / خوژتیپ با ایموجی پریمیوم
        elif norm_text in ["خوشتیپ کیه", "خوشتیپ کی", "خوژتیپ کیه", "خوژتیپ کی", "خوشتیپ", "خوژتیپ"] and features.get("handsome", True):
            word_label = "خوژتیپ" if "خوژ" in norm_text else "خوشتیپ"
            is_cd, rem_sec, cd_data = get_cooldown_remaining(db, chat_id, "handsome")
            
            if is_cd:
                m_rem = rem_sec // 60
                target_mention = get_user_mention(cd_data["id"], cd_data["fullname"])
                msg = (
                    f'<b><tg-emoji emoji-id="5332699109168013117">🌟</tg-emoji> {word_label} گروه اینه :</b>\n\n'
                    f'<b><tg-emoji emoji-id="5321484996802797866">😎</tg-emoji> | {target_mention}</b>\n\n'
                    f'<b>- ولی خب {m_rem} دقیقه دیگه {word_label} بعدی معرفی میشه! <tg-emoji emoji-id="5323417298294298902">🙂</tg-emoji></b>'
                )
                await update.message.reply_text(msg, parse_mode=ParseMode.HTML)
            else:
                m_tuple = await get_fast_random_member(context, chat_id, db)
                if m_tuple:
                    tid, info = m_tuple
                    target_mention = get_user_mention(int(tid), info["fullname"])
                    set_cooldown_data(db, chat_id, "handsome", {"id": int(tid), "fullname": info["fullname"]})
                    increment_user_stat(db, int(tid), "handsome")
                    
                    msg = (
                        f'<b><tg-emoji emoji-id="5332699109168013117">🌟</tg-emoji> {word_label} گروه اینه :</b>\n\n'
                        f'<b><tg-emoji emoji-id="5321484996802797866">😎</tg-emoji> | {target_mention}</b>'
                    )
                    await update.message.reply_text(msg, parse_mode=ParseMode.HTML)

        # ۳. جنده با ایموجی پریمیوم
        elif norm_text in ["جنده کیه", "جنده کی", "جنده"] and features.get("jende", True):
            is_cd, rem_sec, cd_data = get_cooldown_remaining(db, chat_id, "jende")
            if is_cd:
                m_rem = rem_sec // 60
                target_mention = get_user_mention(cd_data["id"], cd_data["fullname"])
                msg = (
                    f'<b><tg-emoji emoji-id="4974615079971455718">🖤</tg-emoji> جنده گروه اینه :</b>\n\n'
                    f'<b><tg-emoji emoji-id="4974545355472372800">🖤</tg-emoji> | {target_mention}</b>\n\n'
                    f'<b>+ ولی خب هر جندگی دائمی نیست! {m_rem} دقیقه دیگه جنده بعدی معرفی میشه! <tg-emoji emoji-id="4974573543342736117">🖤</tg-emoji></b>'
                )
                await update.message.reply_text(msg, parse_mode=ParseMode.HTML)
            else:
                m_tuple = await get_fast_random_member(context, chat_id, db)
                if m_tuple:
                    tid, info = m_tuple
                    target_mention = get_user_mention(int(tid), info["fullname"])
                    set_cooldown_data(db, chat_id, "jende", {"id": int(tid), "fullname": info["fullname"]})
                    increment_user_stat(db, int(tid), "jendegi")
                    
                    msg = (
                        f'<b><tg-emoji emoji-id="4974615079971455718">🖤</tg-emoji> جنده گروه اینه :</b>\n\n'
                        f'<b><tg-emoji emoji-id="4974545355472372800">🖤</tg-emoji> | {target_mention}</b>'
                    )
                    await update.message.reply_text(msg, parse_mode=ParseMode.HTML)

        # ۴. کونی با ایموجی پریمیوم
        elif norm_text in ["کونی کیه", "کونی کی", "کونی"] and features.get("koni", True):
            is_cd, rem_sec, cd_data = get_cooldown_remaining(db, chat_id, "koni")
            if is_cd:
                m_rem = rem_sec // 60
                target_mention = get_user_mention(cd_data["id"], cd_data["fullname"])
                msg = (
                    f'<b><tg-emoji emoji-id="4976598744976851674">🍌</tg-emoji> کونی گروه اینه :</b>\n\n'
                    f'<b><tg-emoji emoji-id="4974439226830488153">🔞</tg-emoji> | {target_mention}</b>\n\n'
                    f'<b>+ ولی خب {m_rem} دقیقه دیگه کونی بعدی معرفی میشه! <tg-emoji emoji-id="4974672507979170737">🍌</tg-emoji></b>'
                )
                await update.message.reply_text(msg, parse_mode=ParseMode.HTML)
            else:
                m_tuple = await get_fast_random_member(context, chat_id, db)
                if m_tuple:
                    tid, info = m_tuple
                    target_mention = get_user_mention(int(tid), info["fullname"])
                    set_cooldown_data(db, chat_id, "koni", {"id": int(tid), "fullname": info["fullname"]})
                    increment_user_stat(db, int(tid), "koni")
                    
                    msg = (
                        f'<b><tg-emoji emoji-id="4976598744976851674">🍌</tg-emoji> کونی گروه اینه :</b>\n\n'
                        f'<b><tg-emoji emoji-id="4974439226830488153">🔞</tg-emoji> | {target_mention}</b>'
                    )
                    await update.message.reply_text(msg, parse_mode=ParseMode.HTML)

        # ۵. جقی با ایموجی پریمیوم
        elif norm_text in ["جقی", "جقی کیه", "جقی گروه"] and features.get("jaghi", True):
            is_cd, rem_sec, cd_data = get_cooldown_remaining(db, chat_id, "jaghi")
            if is_cd:
                m_rem = rem_sec // 60
                target_mention = get_user_mention(cd_data["id"], cd_data["fullname"])
                msg = (
                    f'<b><tg-emoji emoji-id="4974338329458770518">🍌</tg-emoji> جقی گروه اینه :</b>\n\n'
                    f'<b><tg-emoji emoji-id="4974362376980660892">🍌</tg-emoji> | {target_mention}</b>\n\n'
                    f'<b>+ بزن که خوب میزنی رفیق گلم! <tg-emoji emoji-id="6033112209612082866">😂</tg-emoji></b>\n'
                    f'<b>- ولی این جق ابدی نیست! {m_rem} دقیقه دیگه جقی بعدیو معرفی میکنم.</b>'
                )
                await update.message.reply_text(msg, parse_mode=ParseMode.HTML)
            else:
                m_tuple = await get_fast_random_member(context, chat_id, db)
                if m_tuple:
                    tid, info = m_tuple
                    target_mention = get_user_mention(int(tid), info["fullname"])
                    set_cooldown_data(db, chat_id, "jaghi", {"id": int(tid), "fullname": info["fullname"]})
                    increment_user_stat(db, int(tid), "jaghi")
                    
                    msg = (
                        f'<b><tg-emoji emoji-id="4974338329458770518">🍌</tg-emoji> جقی گروه اینه :</b>\n\n'
                        f'<b><tg-emoji emoji-id="4974362376980660892">🍌</tg-emoji> | {target_mention}</b>\n\n'
                        f'<b>+ بزن که خوب میزنی رفیق گلم! <tg-emoji emoji-id="6033112209612082866">😂</tg-emoji></b>'
                    )
                    await update.message.reply_text(msg, parse_mode=ParseMode.HTML)

        # ۶. کصخل / کسخل با ایموجی پریمیوم
        elif norm_text in ["کصخل", "کسخل", "کصخل گروه", "کسخل گروه"] and features.get("koskhal", True):
            is_cd, rem_sec, cd_data = get_cooldown_remaining(db, chat_id, "koskhal")
            if is_cd:
                m_rem = rem_sec // 60
                target_mention = get_user_mention(cd_data["id"], cd_data["fullname"])
                msg = (
                    f'<b><tg-emoji emoji-id="5886539179256450622">🤪</tg-emoji> کصخل گروه اینه :</b>\n\n'
                    f'<b><tg-emoji emoji-id="5861747442612964510">🤙</tg-emoji> | {target_mention}</b>\n\n'
                    f'<b>+ هر کصخلی درمانی دارد! {m_rem} دقیقه دیگه کصخل بعدیو معرفی میکنم.</b>'
                )
                await update.message.reply_text(msg, parse_mode=ParseMode.HTML)
            else:
                m_tuple = await get_fast_random_member(context, chat_id, db)
                if m_tuple:
                    tid, info = m_tuple
                    target_mention = get_user_mention(int(tid), info["fullname"])
                    set_cooldown_data(db, chat_id, "koskhal", {"id": int(tid), "fullname": info["fullname"]})
                    increment_user_stat(db, int(tid), "kos_khali")
                    
                    msg = (
                        f'<b><tg-emoji emoji-id="5886539179256450622">🤪</tg-emoji> کصخل گروه اینه :</b>\n\n'
                        f'<b><tg-emoji emoji-id="5861747442612964510">🤙</tg-emoji> | {target_mention}</b>\n\n'
                        f'<b>+ هر کصخلی درمانی دارد!</b>'
                    )
                    await update.message.reply_text(msg, parse_mode=ParseMode.HTML)

        # ۷. سکسی با ایموجی پریمیوم
        elif norm_text in ["سکسی", "سکسی گروه"] and features.get("sexy", True):
            is_cd, rem_sec, cd_data = get_cooldown_remaining(db, chat_id, "sexy")
            if is_cd:
                m_rem = rem_sec // 60
                target_mention = get_user_mention(cd_data["id"], cd_data["fullname"])
                msg = (
                    f'<b><tg-emoji emoji-id="5920075812911976155">😈</tg-emoji> سکسی گروه اینه :</b>\n\n'
                    f'<b><tg-emoji emoji-id="5247009821508537591">🚬</tg-emoji> | {target_mention}</b>\n\n'
                    f'<b>+ ولی خب {m_rem} دقیقه دیگه سکسی بعدیو معرفی میکنم.</b>'
                )
                await update.message.reply_text(msg, parse_mode=ParseMode.HTML)
            else:
                m_tuple = await get_fast_random_member(context, chat_id, db)
                if m_tuple:
                    tid, info = m_tuple
                    target_mention = get_user_mention(int(tid), info["fullname"])
                    set_cooldown_data(db, chat_id, "sexy", {"id": int(tid), "fullname": info["fullname"]})
                    increment_user_stat(db, int(tid), "sexy")
                    
                    msg = (
                        f'<b><tg-emoji emoji-id="5920075812911976155">😈</tg-emoji> سکسی گروه اینه :</b>\n\n'
                        f'<b><tg-emoji emoji-id="5247009821508537591">🚬</tg-emoji> | {target_mention}</b>'
                    )
                    await update.message.reply_text(msg, parse_mode=ParseMode.HTML)

        # ۸. جذاب با ایموجی پریمیوم
        elif norm_text in ["جذاب", "جذاب گروه"] and features.get("jazab", True):
            is_cd, rem_sec, cd_data = get_cooldown_remaining(db, chat_id, "jazab")
            if is_cd:
                m_rem = rem_sec // 60
                target_mention = get_user_mention(cd_data["id"], cd_data["fullname"])
                msg = (
                    f'<b><tg-emoji emoji-id="5771629206152679502">☕️</tg-emoji> جذاب گروه اینه :</b>\n\n'
                    f'<b><tg-emoji emoji-id="5774059410317905809">❤️</tg-emoji> | {target_mention}</b>\n\n'
                    f'<b>عشقمممم شماره میدی پاره کنیم؟؟؟ <tg-emoji emoji-id="5773636884320226590">💋</tg-emoji></b>\n'
                    f'<b>+ {m_rem} دقیقه دیگه جذاب بعدیو معرفی میکنم.</b>'
                )
                await update.message.reply_text(msg, parse_mode=ParseMode.HTML)
            else:
                m_tuple = await get_fast_random_member(context, chat_id, db)
                if m_tuple:
                    tid, info = m_tuple
                    target_mention = get_user_mention(int(tid), info["fullname"])
                    set_cooldown_data(db, chat_id, "jazab", {"id": int(tid), "fullname": info["fullname"]})
                    increment_user_stat(db, int(tid), "jazab")
                    
                    msg = (
                        f'<b><tg-emoji emoji-id="5771629206152679502">☕️</tg-emoji> جذاب گروه اینه :</b>\n\n'
                        f'<b><tg-emoji emoji-id="5774059410317905809">❤️</tg-emoji> | {target_mention}</b>\n\n'
                        f'<b>عشقمممم شماره میدی پاره کنیم؟؟؟ <tg-emoji emoji-id="5773636884320226590">💋</tg-emoji></b>'
                    )
                    await update.message.reply_text(msg, parse_mode=ParseMode.HTML)

        # ۹. شیپ / کاپل با ایموجی پریمیوم
        elif norm_text in ["شیپ کن", "شیپ", "کاپل", "کاپل کن"] and features.get("ship", True):
            is_cd, rem_sec, cd_data = get_cooldown_remaining(db, chat_id, "ship")
            if is_cd:
                m_rem = rem_sec // 60
                name1 = get_user_mention(cd_data["u1"]["id"], cd_data["u1"]["name"])
                name2 = get_user_mention(cd_data["u2"]["id"], cd_data["u2"]["name"])
                
                last_msg_id = cd_data.get("last_msg_id")
                couple_data = db.get("couples", {}).get(str(last_msg_id), {}) if last_msg_id else {}
                agrees = couple_data.get("agrees", [])
                disagrees = couple_data.get("disagrees", [])

                agrees_text = ", ".join([get_user_mention(u["id"], u["name"]) for u in agrees]) if agrees else "هیچکس"
                disagrees_text = ", ".join([get_user_mention(u["id"], u["name"]) for u in disagrees]) if disagrees else "هیچکس"

                msg = (
                    f'<b><tg-emoji emoji-id="5830106027701314719">❤️</tg-emoji> دو عدد کفتر عاشقمون این رفقان:</b>\n\n'
                    f'<b><tg-emoji emoji-id="5834477789012564986">💕</tg-emoji> | {name1} <tg-emoji emoji-id="6048558196203720407">❤️</tg-emoji> {name2}</b>\n\n'
                    f'<b><tg-emoji emoji-id="5819032824623144971">➕</tg-emoji>موافقان ثبت شده: {agrees_text}</b>\n'
                    f'<b><tg-emoji emoji-id="5819154526816444042">❌</tg-emoji> مخالفان ثبت شده : {disagrees_text}</b>\n\n'
                    f'<b>+ {m_rem} دقیقه دیگه کاپل بعدیو میگم بچهااااا!<tg-emoji emoji-id="5816460319601467354">😺</tg-emoji></b>'
                )
                await update.message.reply_text(msg, parse_mode=ParseMode.HTML)
            else:
                m1 = await get_fast_random_member(context, chat_id, db)
                m2 = await get_fast_random_member(context, chat_id, db)
                if m1 and m2 and m1[0] != m2[0]:
                    u1_dict = {"id": int(m1[0]), "name": m1[1]['fullname']}
                    u2_dict = {"id": int(m2[0]), "name": m2[1]['fullname']}
                    
                    increment_user_stat(db, u1_dict["id"], "ship")
                    increment_user_stat(db, u2_dict["id"], "ship")

                    name1 = get_user_mention(u1_dict["id"], u1_dict["name"])
                    name2 = get_user_mention(u2_dict["id"], u2_dict["name"])

                    kb = InlineKeyboardMarkup([
                        [
                            InlineKeyboardButton("موافقم", callback_data="couple_agree", style="success", icon_custom_emoji_id="5411228694935012881"),
                            InlineKeyboardButton("افتضاح", callback_data="couple_disagree", style="danger", icon_custom_emoji_id="5411484842489578182")
                        ]
                    ])

                    sent_msg = await update.message.reply_text(
                        f'<b><tg-emoji emoji-id="5830106027701314719">❤️</tg-emoji> دو عدد کفتر عاشقمون این رفقان:</b>\n\n'
                        f'<b><tg-emoji emoji-id="5834477789012564986">💕</tg-emoji> | {name1} <tg-emoji emoji-id="6048558196203720407">❤️</tg-emoji> {name2}</b>\n\n'
                        f'<b><tg-emoji emoji-id="5819032824623144971">➕</tg-emoji>موافقان: هیچکس</b>\n'
                        f'<b><tg-emoji emoji-id="5819154526816444042">❌</tg-emoji> مخالفان: هیچکس</b>',
                        reply_markup=kb,
                        parse_mode=ParseMode.HTML
                    )

                    if "couples" not in db: db["couples"] = {}
                    db["couples"][str(sent_msg.message_id)] = {
                        "u1": u1_dict,
                        "u2": u2_dict,
                        "agrees": [],
                        "disagrees": [],
                        "created_at": datetime.now().timestamp()
                    }
                    set_cooldown_data(db, chat_id, "ship", {"u1": u1_dict, "u2": u2_dict, "last_msg_id": sent_msg.message_id})
                else:
                    await update.message.reply_text(
                        '<b>❌ اعضای کافی موجود نیست! <tg-emoji emoji-id="5857415006022278161">❌</tg-emoji></b>',
                        parse_mode=ParseMode.HTML
                    )

        # ۱۰. پیشنهاد غذا با ایموجی پریمیوم
        elif ("غذا" in norm_text or "غدا" in norm_text) and features.get("food", True):
            fl = db.get("foods", [])
            if fl:
                selected_food = random.choice(fl)
                msg = (
                    f'<b><tg-emoji emoji-id="5418248505447698083">🧽</tg-emoji> دنبال غذایی؟ بنظرم بهترین ایده غذا برای تو اینه :</b>\n\n'
                    f'<b><tg-emoji emoji-id="5357066069250948384">🐱</tg-emoji> | {html.escape(selected_food)}</b>'
                )
                await update.message.reply_text(msg, parse_mode=ParseMode.HTML)

        # ۱۱. سیستم شعرخوانی همراه با ایموجی پریمیوم قلم ✍️
        elif norm_text in ["شعر", "شعر بگو", "شاعر شو"] and features.get("poems", True):
            custom_names = db.get("custom_names", [])
            if custom_names:
                target_name = random.choice(custom_names)
            else:
                m_tuple = await get_fast_random_member(context, chat_id, db)
                if m_tuple:
                    tid, info = m_tuple
                    target_name = get_user_mention(int(tid), info["fullname"])
                else:
                    target_name = "رفیق"

            all_poems = db.get("poems", DEFAULT_POEMS)
            poem_template = random.choice(all_poems)
            final_poem = poem_template.format(name=target_name)
            await update.message.reply_text(f'<tg-emoji emoji-id="5859527571586161695">✍️</tg-emoji> <b>{final_poem}</b>', parse_mode=ParseMode.HTML)

        # ۱۲. تشخیص «لف»
        elif LEF_PATTERN.search(raw_text) and features.get("lef", True):
            ml = db.get("media_lef")
            if ml:
                mt, fi = ml["type"], ml["file_id"]
                if mt == "sticker": await update.message.reply_sticker(fi)
                elif mt == "photo": await update.message.reply_photo(fi)
                elif mt == "animation": await update.message.reply_animation(fi)
                elif mt == "video": await update.message.reply_video(fi)

    except Exception:
        logger.exception("Error in handle_messages:")

# ==========================================
# GLOBAL ERROR HANDLER & MAIN
# ==========================================
async def global_error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    logger.error(f"Error: {context.error}", exc_info=context.error)

def main():
    if not BOT_TOKEN or BOT_TOKEN == "YOUR_BOT_TOKEN_HERE":
        logger.critical("FATAL: BOT_TOKEN is missing!")
        sys.exit(1)

    load_db()
    threading.Thread(target=run_health_check_server, daemon=True).start()

    app = Application.builder().token(BOT_TOKEN).post_init(post_init).build()

    app.add_handler(ChatMemberHandler(track_chats, ChatMemberHandler.MY_CHAT_MEMBER))
    app.add_handler(CallbackQueryHandler(handle_callback_query))
    app.add_handler(CommandHandler("start", command_start))
    app.add_handler(CommandHandler("panel", command_owner_panel))
    app.add_handler(CommandHandler("cancel", command_cancel))
    app.add_handler(CommandHandler("done", command_done))

    # 1. سیستم کامنت خودکار برای پست‌های کانال متصل به گروه بحث
    app.add_handler(MessageHandler(filters.ChatType.GROUPS & filters.IS_AUTOMATIC_FORWARD, handle_automatic_channel_comments), group=-3)

    # 2. سیستم خوش‌آمادگویی اعضای جدید
    app.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, handle_new_chat_members), group=-2)

    # 3. اختصاصی برای بازی دوز با بالاترین اولویت (group=-1)
    app.add_handler(
        MessageHandler(filters.TEXT & (~filters.COMMAND), dwoz_message_handler),
        group=-1
    )

    # 4. هاندر عمومی پیام‌ها
    app.add_handler(
        MessageHandler(filters.TEXT & (~filters.COMMAND), handle_messages)
    )

    app.add_error_handler(global_error_handler)

    logger.info("Bot is running...")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
