import html
import io
import json
import logging
import os
import random
import re
import shutil
import sys
import asyncio
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from datetime import datetime
from zoneinfo import ZoneInfo

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    InlineQueryResultArticle,
    InputTextMessageContent,
    ReactionTypeEmoji,
)
from telegram.constants import ParseMode, ChatMemberStatus, PollType, MessageEntityType
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ChatMemberHandler,
    InlineQueryHandler,
    ContextTypes,
    ApplicationHandlerStop,
    filters,
)

# ==========================================
# CONFIGURATION & LOGGING
# ==========================================
BOT_TOKEN = os.getenv("BOT_TOKEN", "8618205537:AAFCjx1_PkdC43ezimZgp-z5PAx0JKEmJqI")
OWNER_ID = int(os.getenv("OWNER_ID", "6749949992"))
DB_FILE = "db.json"
TEMP_DB_FILE = "db.json.tmp"

MAX_FUN_MESSAGES = 20

# Fixed Reaction
FIXED_REACTION = "❤️"

# Custom Emojis
CHECK_CUSTOM_EMOJI_ID = "5830144944399981619"
CROSS_CUSTOM_EMOJI_ID = "5819154526816444042"
CLEANUP_CUSTOM_EMOJI_ID = "5859215993183674044"
CANDY_CUSTOM_EMOJI_ID = "6046300980436278776"
PARTY_CUSTOM_EMOJI_ID = "5818785846823755322"

# Navigation & Actions Custom Emojis
CLOSE_CUSTOM_EMOJI_ID = "5983093054842606366"
NEXT_CUSTOM_EMOJI_ID = "5843732253829503840"
PREV_CUSTOM_EMOJI_ID = "5845874566336880660"
BACK_CUSTOM_EMOJI_ID = "5823664135103061930"
GEAR_CUSTOM_EMOJI_ID = "5901989641204018165"

# Main Admin Panel Custom Emojis
PANEL_SCALE_EMOJI_ID = "5825563515670242868"
PANEL_CASTLE_EMOJI_ID = "5832397371278892338"
PANEL_HASH_EMOJI_ID = "5902054589699465736"
LOCK_CUSTOM_EMOJI_ID = "5818736497649524154"
ADVANCED_CUSTOM_EMOJI_ID = "5819151717907832367"
LISTS_CUSTOM_EMOJI_ID = "5888937012253171131"

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
    try:
        server = HTTPServer(("0.0.0.0", port), HealthCheckHandler)
        logger.info(f"Dummy HTTP server running on port {port}")
        server.serve_forever()
    except Exception as e:
        logger.error(f"Health check server error: {e}")

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

LOCK_COMMAND_PATTERN = re.compile(
    r"^(?:گودی\s+)?(?:(?:(قفل|ببند|باز\s*کن|حذف\s*قفل|بازکردن\s*قفل)\s+(.+))|(?:(.+?)\s+(رو|را)?\s*(قفل\s*کن|ببند|باز\s*کن)))$",
    re.IGNORECASE
)

WELCOME_CMD_PATTERN = re.compile(
    r"^(?:[/!])?(?:گودی\s+)?(خوش\s*آمد|خوشآمد|خوش\s*امد|خوشآمدگویی|خوش\s*آمدگویی|welcome)\s*(روشن|خاموش|on|off)$",
    re.IGNORECASE
)

URL_REGEX = re.compile(r"(https?://\S+|t\.me/\S+|telegram\.me/\S+|www\.\S+)", re.IGNORECASE)
ENGLISH_CHAR_REGEX = re.compile(r"[a-zA-Z]")
PERSIAN_CHAR_REGEX = re.compile(r"[\u0600-\u06FF\uFB8A\u067E\u0686\u06AF\u200C\u200D]")
EMOJI_REGEX = re.compile(
    r"[\U00010000-\U0010ffff\u2600-\u27bf\u1f300-\u1f64f\u1f680-\u1f6ff\u1f900-\u1f9ff\u1fa70-\u1faff]",
    flags=re.UNICODE
)

PERSIAN_PERMUTATIONS = {
    '0': '0', '1': '1', '2': '2', '3': '3', '4': '4', '5': '5', '6': '6', '7': '7', '8': '8', '9': '9',
    '۰': '0', '۱': '1', '۲': '2', '۳': '3', '۴': '4', '۵': '5', '۶': '6', '۷': '7', '٨': '8', '۹': '9',
    '٠': '0', '١': '1', '٢': '2', '٣': '3', '٤': '4', '٥': '5', '٦': '6', '٧': '7', '٨': '8', '٩': '9'
}

WORLD_COUNTRIES = {
    "ایران": {
        "tz": "Asia/Tehran",
        "emoji": '<tg-emoji emoji-id="5271878966347601947">🇮🇷</tg-emoji>'
    },
    "آمریکا": {
        "tz": "America/New_York",
        "emoji": '<tg-emoji emoji-id="5927292517610426176">🇺🇸</tg-emoji>',
        "aliases": ["امریکا"]
    },
    "آلمان": {
        "tz": "Europe/Berlin",
        "emoji": '<tg-emoji emoji-id="5409360418520967565">🇩🇪</tg-emoji>',
        "aliases": ["المان"]
    },
    "انگلیس": {
        "tz": "Europe/London",
        "emoji": '<tg-emoji emoji-id="5229192892710402006">🏴󠁧󠁢󠁥󠁮󠁧󠁿</tg-emoji>',
        "aliases": ["انگلستان"]
    },
    "ترکیه": {
        "tz": "Europe/Istanbul",
        "emoji": '<tg-emoji emoji-id="5226948110873278599">🇹🇷</tg-emoji>',
        "aliases": []
    },
    "هند": {
        "tz": "Asia/Kolkata",
        "emoji": '<tg-emoji emoji-id="6136551252781172945">🇮🇳</tg-emoji>',
        "aliases": ["هندوستان"]
    },
    "عربستان": {
        "tz": "Asia/Riyadh",
        "emoji": '<tg-emoji emoji-id="5202079966761590204">🇸🇦</tg-emoji>',
        "aliases": []
    },
    "فرانسه": {
        "tz": "Europe/Paris",
        "emoji": '<tg-emoji emoji-id="5931269906434624310">🇫🇷</tg-emoji>',
        "aliases": []
    },
    "چین": {
        "tz": "Asia/Shanghai",
        "emoji": '<tg-emoji emoji-id="5431782733376399004">🇨🇳</tg-emoji>',
        "aliases": []
    },
    "ژاپن": {
        "tz": "Asia/Tokyo",
        "emoji": '<tg-emoji emoji-id="5456261908069885892">🇯🇵</tg-emoji>',
        "aliases": []
    }
}

# ==========================================
# LOCK DEFINITIONS & METADATA
# ==========================================
ALL_LOCKS = {
    "mention": {"name": "منشن", "page": 1},
    "tag": {"name": "تگ", "page": 1},
    "spoiler": {"name": "اسپویلر", "page": 1},
    "video": {"name": "فیلم", "page": 1},
    "photo": {"name": "عکس", "page": 1},
    "document": {"name": "فایل", "page": 1},
    "audio": {"name": "آهنگ", "page": 1},
    "sticker": {"name": "استیکر", "page": 1},
    "gif": {"name": "گیف", "page": 1},
    "poll": {"name": "نظرسنجی", "page": 1},
    "voice": {"name": "ویس", "page": 1},
    "location": {"name": "مکان", "page": 1},
    "contact": {"name": "مخاطب", "page": 1},
    "edit_msg": {"name": "ویرایش پیام", "page": 1},
    "edit_media": {"name": "ویرایش رسانه", "page": 1},
    "forward": {"name": "فوروارد", "page": 2},
    "emoji": {"name": "ایموجی", "page": 2},
    "link": {"name": "لینک", "page": 2},
    "english": {"name": "انگلیسی", "page": 2},
    "persian": {"name": "فارسی", "page": 2},
    "hashtag": {"name": "هشتگ", "page": 2},
    "username": {"name": "یوزرنیم", "page": 2},
    "telegram_services": {"name": "سرویس تلگرام", "page": 2, "is_category": True},
    "service_join_link": {"name": "حذف پیام ورود با لینک", "page": 0, "is_service": True},
    "service_add_member": {"name": "حذف پیام افزودن عضو", "page": 0, "is_service": True},
    "service_pinned": {"name": "حذف پیام سنجاق شدن", "page": 0, "is_service": True},
    "service_video_chat": {"name": "حذف پیام‌های ویدیو چت", "page": 0, "is_service": True},
}

TELEGRAM_SERVICE_LOCK_KEYS = [
    "service_join_link",
    "service_add_member",
    "service_pinned",
    "service_video_chat"
]

LOCK_TEXT_ALIASES = {
    "منشن": "mention", "منشنها": "mention",
    "تگ": "tag", "تگها": "tag",
    "اسپویلر": "spoiler", "اسپویل": "spoiler",
    "فیلم": "video", "ویدیو": "video", "ویدئو": "video",
    "عکس": "photo", "تصویر": "photo",
    "فایل": "document", "داکیومنت": "document", "سند": "document",
    "آهنگ": "audio", "اهنگ": "audio", "موزیک": "audio", "صدا": "audio",
    "استیکر": "sticker", "استیکرها": "sticker",
    "گیف": "gif", "انیمیشن": "gif",
    "نظرسنجی": "poll", "پل": "poll",
    "ویس": "voice", "صدا ضبط شده": "voice", "ویسها": "voice",
    "مکان": "location", "لوکیشن": "location", "موقعیت": "location",
    "مخاطب": "contact", "مخاطبین": "contact", "شماره": "contact",
    "ویرایش پیام": "edit_msg", "ادیت پیام": "edit_msg", "ویرایش": "edit_msg",
    "ویرایش رسانه": "edit_media", "ادیت رسانه": "edit_media", "ویرایش مدیا": "edit_media",
    "فوروارد": "forward", "فروارد": "forward", "بازارسال": "forward",
    "ایموجی": "emoji", "اموجی": "emoji", "شکلک": "emoji",
    "لینک": "link", "لینکها": "link", "پیوند": "link",
    "انگلیسی": "english", "لاتین": "english",
    "فارسی": "persian", "پارسی": "persian",
    "هشتگ": "hashtag", "تگ هشتگ": "hashtag",
    "یوزرنیم": "username", "ایدی": "username", "آیدی": "username",
    "پیام ورود با لینک": "service_join_link", "ورود با لینک": "service_join_link",
    "پیام افزودن عضو": "service_add_member", "افزودن عضو": "service_add_member",
    "پیام سنجاق شدن": "service_pinned", "پیام پین": "service_pinned",
    "پیام‌های ویدیو چت": "service_video_chat", "ویدیو چت": "service_video_chat"
}

def fa_to_en_digits(text: str) -> str:
    if not text:
        return "0"
    return "".join(PERSIAN_PERMUTATIONS.get(ch, ch) for ch in text)

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
# GLOBAL DB CACHE & ISOLATION HELPERS
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

def get_default_locks_structure() -> dict:
    return {k: False for k in ALL_LOCKS.keys() if not ALL_LOCKS[k].get("is_category")}

def get_default_group_structure() -> dict:
    return {
        "title": "",
        "fun_named_responses": [],
        "fun_normal_responses": [],
        "foods": list(DEFAULT_FOODS),
        "custom_names": [],
        "poems": list(DEFAULT_POEMS),
        "media_lef": None,
        "cooldowns": {},
        "welcome": {"enabled": True, "custom": False},
        "comment": {"enabled": False, "custom": False},
        "random_reaction": True,
        "invite_link": None,
        "message_logs": [],
        "user_last_messages": {},
        "locks": get_default_locks_structure()
    }

def get_default_db_structure() -> dict:
    return {
        "version": 5,
        "members": {},
        "groups": {},
        "hourly_messages": {},
        "recent_active_users": {},
        "last_job_reset": 0,
        "active_chats": [],
        "cooldown_minutes": 10,
        "couples": {},
        "reports": {},
        "xo_games": {},
        "user_stats": {},
        "action_records": {},
        "commented_channel_posts": [],
        "started_users": {},
        "admin_logs": [],
        "whispers": {},
        "bot_shutdown": False,
        "shutdown_message": None,
        "global_bans": {},
        "global_group_bans": {},
        "global_fun_named": [],
        "global_fun_normal": [],
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
            "waiting_lef_media": {},
            "waiting_add_food": {},
            "waiting_del_food": {},
            "waiting_cooldown": {},
            "waiting_poem_names": {},
            "waiting_add_poem": {},
            "waiting_broadcast_group": {},
            "waiting_broadcast_msg": {},
            "waiting_welcome_msg": {},
            "waiting_comment_msg": {},
            "waiting_user_broadcast_msg": {},
            "waiting_fun_named_msg": {},
            "waiting_fun_normal_msg": {},
            "waiting_search_query": {},
            "broadcast_builder": {},
            "waiting_shutdown_msg": {},
            "ban_flow": {}
        }
    }

def migrate_db_if_needed(data: dict) -> dict:
    if data.get("version") == 5:
        return data

    logger.info("Migrating database to v5...")
    new_db = get_default_db_structure()
    for k in new_db.keys():
        if k in data and k != "states":
            new_db[k] = data[k]

    groups = new_db.setdefault("groups", {})
    for _, g_val in groups.items():
        if "locks" not in g_val or not isinstance(g_val["locks"], dict):
            g_val["locks"] = get_default_locks_structure()
        else:
            for lk in ALL_LOCKS.keys():
                if not ALL_LOCKS[lk].get("is_category") and lk not in g_val["locks"]:
                    g_val["locks"][lk] = False

    new_db["version"] = 5
    return new_db

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
            data = migrate_db_if_needed(data)
            for key, val in default_struct.items():
                if key not in data:
                    data[key] = val
            _DB_CACHE = data
            return _DB_CACHE
    except Exception as e:
        logger.error(f"Database load error! Initializing default. Details: {e}")
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

def get_session_key(user_id: int, chat_id: int) -> str:
    return f"{user_id}_{chat_id}"

def clear_user_all_states(db: dict, user_id: int, chat_id: int | None = None) -> bool:
    u_str = str(user_id)
    cleared = False
    states = db.setdefault("states", {})

    ban_flow = states.setdefault("ban_flow", {})
    keys_to_del = [k for k in ban_flow.keys() if k.startswith(f"{user_id}_")]
    if keys_to_del:
        for k in keys_to_del:
            del ban_flow[k]
        cleared = True

    for state_name in list(states.keys()):
        if state_name == "ban_flow":
            continue
        st_dict = states.get(state_name, {})
        if isinstance(st_dict, dict) and u_str in st_dict:
            del st_dict[u_str]
            cleared = True

    if cleared:
        mark_db_dirty()
        save_db(force=True)
    return cleared

def get_group_data(db: dict, chat_id: int | str) -> dict:
    cid_str = str(chat_id)
    groups = db.setdefault("groups", {})
    if cid_str not in groups:
        groups[cid_str] = get_default_group_structure()
        mark_db_dirty()
    else:
        if "user_last_messages" not in groups[cid_str]:
            groups[cid_str]["user_last_messages"] = {}
        if "locks" not in groups[cid_str] or not isinstance(groups[cid_str]["locks"], dict):
            groups[cid_str]["locks"] = get_default_locks_structure()
            mark_db_dirty()
        else:
            for lk in ALL_LOCKS.keys():
                if not ALL_LOCKS[lk].get("is_category") and lk not in groups[cid_str]["locks"]:
                    groups[cid_str]["locks"][lk] = False
                    mark_db_dirty()
    return groups[cid_str]

# ==========================================
# BAN / UNBAN HELPERS & NOTIFIERS
# ==========================================
def is_user_globally_banned(db: dict, user_id: int) -> tuple[bool, dict | None]:
    uid_str = str(user_id)
    bans = db.get("global_bans", {})
    if uid_str not in bans:
        return False, None

    ban_info = bans[uid_str]
    b_type = ban_info.get("type", "permanent")
    if b_type == "temporary":
        ban_until = ban_info.get("ban_until")
        now_ts = datetime.now().timestamp()
        if ban_until and now_ts > ban_until:
            del bans[uid_str]
            mark_db_dirty()
            save_db()
            return False, None
    return True, ban_info

def is_group_globally_banned(db: dict, chat_id: int) -> tuple[bool, dict | None]:
    cid_str = str(chat_id)
    bans = db.get("global_group_bans", {})
    if cid_str not in bans:
        return False, None

    ban_info = bans[cid_str]
    b_type = ban_info.get("type", "permanent")
    if b_type == "temporary":
        ban_until = ban_info.get("ban_until")
        now_ts = datetime.now().timestamp()
        if ban_until and now_ts > ban_until:
            del bans[cid_str]
            mark_db_dirty()
            save_db()
            return False, None
    return True, ban_info

async def send_premium_ban_notification(bot, chat_id: int, is_group: bool, duration_str: str, reason_str: str) -> bool:
    title = "گروه شما از ربات گودی بن شد!" if is_group else "شما از ربات گودی بن شدید!"
    esc_title = html.escape(title)
    esc_dur = html.escape(duration_str)
    esc_reason = html.escape(reason_str)

    html_text = (
        f'<tg-emoji emoji-id="5819051035284479206">🚨</tg-emoji> <b>{esc_title}</b>\n\n'
        f'<tg-emoji emoji-id="5906896396526560494">⏰</tg-emoji> <b>مدت زمان :</b> {esc_dur}\n'
        f'<tg-emoji emoji-id="5901989641204018165">⚙️</tg-emoji> <b>دلیل :</b> {esc_reason}'
    )

    try:
        await bot.send_message(chat_id=chat_id, text=html_text, parse_mode=ParseMode.HTML)
        return True
    except Exception as e:
        logger.warning(f"Could not deliver Ban notification to chat {chat_id}: {e}")
        return False

async def send_premium_unban_notification(bot, chat_id: int, is_group: bool = False) -> bool:
    sub = "گروه شما از محدودیت ربات خارج شد." if is_group else "شما از محدودیت ربات خارج شدید."
    html_text = (
        f'<b>تبریک! </b><tg-emoji emoji-id="{PARTY_CUSTOM_EMOJI_ID}">🎉</tg-emoji>\n\n'
        f'<b>{sub}</b> <tg-emoji emoji-id="5816739230482701944">✨</tg-emoji>'
    )
    try:
        await bot.send_message(chat_id=chat_id, text=html_text, parse_mode=ParseMode.HTML)
        return True
    except Exception as e:
        logger.warning(f"Could not deliver Unban notification to {chat_id}: {e}")
        return False

def extract_media_payload(msg) -> dict | None:
    if not msg:
        return None
    caption = msg.caption_html if msg.caption else ""
    if msg.text:
        return {"type": "text", "text": msg.text_html}
    if msg.photo:
        return {"type": "photo", "file_id": msg.photo[-1].file_id, "caption": caption}
    if msg.animation:
        return {"type": "animation", "file_id": msg.animation.file_id, "caption": caption}
    if msg.video:
        return {"type": "video", "file_id": msg.video.file_id, "caption": caption}
    if msg.voice:
        return {"type": "voice", "file_id": msg.voice.file_id, "caption": caption}
    if msg.audio:
        return {"type": "audio", "file_id": msg.audio.file_id, "caption": caption}
    if msg.document:
        return {"type": "document", "file_id": msg.document.file_id, "caption": caption}
    if msg.sticker:
        return {"type": "sticker", "file_id": msg.sticker.file_id}
    return None

async def send_media_payload(bot, chat_id: int, payload: dict, reply_to_message_id: int | None = None) -> bool:
    try:
        mtype = payload.get("type")
        fid = payload.get("file_id")
        cap = payload.get("caption", "")
        txt = payload.get("text", "")

        if mtype == "text":
            await bot.send_message(chat_id=chat_id, text=txt, parse_mode=ParseMode.HTML, reply_to_message_id=reply_to_message_id)
        elif mtype == "photo":
            await bot.send_photo(chat_id=chat_id, photo=fid, caption=cap, parse_mode=ParseMode.HTML, reply_to_message_id=reply_to_message_id)
        elif mtype == "animation":
            await bot.send_animation(chat_id=chat_id, animation=fid, caption=cap, parse_mode=ParseMode.HTML, reply_to_message_id=reply_to_message_id)
        elif mtype == "video":
            await bot.send_video(chat_id=chat_id, video=fid, caption=cap, parse_mode=ParseMode.HTML, reply_to_message_id=reply_to_message_id)
        elif mtype == "voice":
            await bot.send_voice(chat_id=chat_id, voice=fid, caption=cap, parse_mode=ParseMode.HTML, reply_to_message_id=reply_to_message_id)
        elif mtype == "audio":
            await bot.send_audio(chat_id=chat_id, audio=fid, caption=cap, parse_mode=ParseMode.HTML, reply_to_message_id=reply_to_message_id)
        elif mtype == "document":
            await bot.send_document(chat_id=chat_id, document=fid, caption=cap, parse_mode=ParseMode.HTML, reply_to_message_id=reply_to_message_id)
        elif mtype == "sticker":
            await bot.send_sticker(chat_id=chat_id, sticker=fid, reply_to_message_id=reply_to_message_id)
        return True
    except Exception as e:
        logger.error(f"Failed to dispatch media payload: {e}")
        return False

async def dispatch_shutdown_message(bot, target_chat_id: int, shutdown_data: dict, reply_to_msg_id: int | None = None):
    if not shutdown_data:
        try:
            await bot.send_message(
                chat_id=target_chat_id,
                text=f'<b><tg-emoji emoji-id="{CROSS_CUSTOM_EMOJI_ID}">❌</tg-emoji> ربات در حال حاضر خاموش می‌باشد.</b>',
                reply_to_message_id=reply_to_msg_id,
                parse_mode=ParseMode.HTML
            )
        except Exception:
            pass
        return

    from_chat = shutdown_data.get("from_chat_id")
    msg_id = shutdown_data.get("message_id")
    if from_chat and msg_id:
        try:
            await bot.copy_message(chat_id=target_chat_id, from_chat_id=from_chat, message_id=msg_id, reply_to_message_id=reply_to_msg_id)
            return
        except Exception:
            pass

    payload = shutdown_data.get("payload")
    if payload:
        await send_media_payload(bot, target_chat_id, payload, reply_to_message_id=reply_to_msg_id)

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
    if int(user_id) == int(OWNER_ID):
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
            
        g_data = get_group_data(db, chat.id)
        g_data["title"] = chat.title or g_data.get("title", "")

        if update.message:
            last_msgs = g_data.setdefault("user_last_messages", {})
            last_msgs[user_id] = update.message.message_id
            if len(last_msgs) > 200:
                oldest_k = next(iter(last_msgs))
                del last_msgs[oldest_k]
            mark_db_dirty()

        if update.message and (update.message.text or update.message.caption or update.message.photo):
            m_logs = g_data.setdefault("message_logs", [])
            log_item = {
                "message_id": update.message.message_id,
                "user_id": user.id,
                "user_name": fullname,
                "date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "text": update.message.text or update.message.caption or "",
                "media_type": "text"
            }
            if update.message.photo:
                log_item["media_type"] = "photo"
                log_item["file_id"] = update.message.photo[-1].file_id
            elif update.message.animation:
                log_item["media_type"] = "animation"
                log_item["file_id"] = update.message.animation.file_id
            elif update.message.video:
                log_item["media_type"] = "video"
                log_item["file_id"] = update.message.video.file_id
            elif update.message.document:
                log_item["media_type"] = "document"
                log_item["file_id"] = update.message.document.file_id

            m_logs.append(log_item)
            if len(m_logs) > 300:
                m_logs.pop(0)
            mark_db_dirty()

        if "hourly_messages" not in db: db["hourly_messages"] = {}
        if chat_str not in db["hourly_messages"]: db["hourly_messages"][chat_str] = {}
        db["hourly_messages"][chat_str][user_id] = db["hourly_messages"][chat_str].get(user_id, 0) + 1

        if "recent_active_users" not in db: db["recent_active_users"] = {}
        if chat_str not in db["recent_active_users"]: db["recent_active_users"][chat_str] = []
        recent_list = db["recent_active_users"][chat_str]
        
        recent_list = [u for u in recent_list if u[0] != user_id]
        recent_list.append((user_id, {"fullname": fullname, "username": username}))
        if len(recent_list) > 20:
            recent_list.pop(0)
        db["recent_active_users"][chat_str] = recent_list
        mark_db_dirty()
        
    save_db()

async def get_fast_random_member(context: ContextTypes.DEFAULT_TYPE, chat_id: int, db: dict) -> tuple | None:
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
    g_data = get_group_data(db, chat_id)
    cooldowns = g_data.get("cooldowns", {})
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
    g_data = get_group_data(db, chat_id)
    cooldowns = g_data.setdefault("cooldowns", {})
    cooldowns[feature] = {
        "timestamp": datetime.now().timestamp(),
        "data": data
    }
    mark_db_dirty()
    save_db()

# ==========================================
# WELCOME SYSTEM
# ==========================================
def check_and_set_welcome_duplicate(db: dict, chat_id: int, user_id: int) -> bool:
    g_data = get_group_data(db, chat_id)
    history = g_data.setdefault("recent_welcomed_users", {})
    now_ts = datetime.now().timestamp()
    uid_str = str(user_id)

    for k in list(history.keys()):
        if now_ts - history[k] > 120:
            del history[k]

    if uid_str in history and (now_ts - history[uid_str]) < 45:
        return True

    history[uid_str] = now_ts
    if len(history) > 20:
        oldest = min(history.keys(), key=lambda k: history[k])
        del history[oldest]

    mark_db_dirty()
    save_db()
    return False

async def send_welcome_to_member(context: ContextTypes.DEFAULT_TYPE, chat, user, reply_to_message_id: int | None = None):
    try:
        if not user or user.is_bot:
            return

        db = load_db()
        g_data = get_group_data(db, chat.id)
        welcome_settings = g_data.get("welcome", {})

        if not welcome_settings.get("enabled", True):
            return

        if check_and_set_welcome_duplicate(db, chat.id, user.id):
            return

        day_fa, time_str = get_persian_date_info()
        chat_title = html.escape(chat.title or "گروه")
        user_mention = get_user_mention(user.id, user.full_name or "کاربر")

        if not welcome_settings.get("custom", False):
            default_text = f"سلام {user_mention} ، به گروه {chat_title} خوش آمدید!\nساعت {time_str} روز {day_fa}!"
            await context.bot.send_message(
                chat_id=chat.id,
                text=default_text,
                parse_mode=ParseMode.HTML,
                reply_to_message_id=reply_to_message_id
            )
            return

        payload = welcome_settings.get("payload")
        if payload:
            raw_text = payload.get("text") or payload.get("caption") or ""
            formatted_text = (
                raw_text.replace("USERNAME", user_mention)
                .replace("{name}", user_mention)
                .replace("XXXX", chat_title)
                .replace("TIME", time_str)
                .replace("DAY", day_fa)
            )
            temp_payload = dict(payload)
            if "text" in temp_payload:
                temp_payload["text"] = formatted_text
            if "caption" in temp_payload:
                temp_payload["caption"] = formatted_text
            await send_media_payload(context.bot, chat.id, temp_payload, reply_to_message_id=reply_to_message_id)

    except Exception as e:
        logger.error(f"Error dispatching welcome in chat: {e}")

async def handle_new_chat_members(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.new_chat_members:
        return
    chat = update.effective_chat
    reply_id = update.message.message_id
    for member in update.message.new_chat_members:
        if not member.is_bot:
            await send_welcome_to_member(context, chat, member, reply_to_message_id=reply_id)

async def handle_chat_member_welcome(update: Update, context: ContextTypes.DEFAULT_TYPE):
    result = update.chat_member
    if not result:
        return

    chat = result.chat
    if not chat or chat.type not in ["group", "supergroup"]:
        return

    user = result.new_chat_member.user
    if not user or user.is_bot:
        return

    old_status = result.old_chat_member.status
    new_status = result.new_chat_member.status

    was_member = old_status in [ChatMemberStatus.MEMBER, ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER]
    is_now_member = new_status in [ChatMemberStatus.MEMBER, ChatMemberStatus.RESTRICTED]

    if not was_member and is_now_member:
        if new_status == ChatMemberStatus.RESTRICTED:
            if not getattr(result.new_chat_member, "is_member", True):
                return
        await send_welcome_to_member(context, chat, user, reply_to_message_id=None)

# ==========================================
# TEXT WELCOME COMMAND HANDLER (ADMIN ONLY)
# ==========================================
async def handle_welcome_text_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if not msg or not msg.text:
        return

    chat = update.effective_chat
    if not chat or chat.type not in ["group", "supergroup"]:
        return

    user = update.effective_user
    if not user:
        return

    raw_text = msg.text.strip()
    norm_cmd = raw_text.replace("\u200c", " ").strip().lower()
    norm_cmd = re.sub(r"\s+", " ", norm_cmd)

    match = WELCOME_CMD_PATTERN.match(norm_cmd)
    if not match:
        return

    chat_id = chat.id
    user_id = user.id

    if not await is_admin_or_owner(context, chat_id, user_id):
        return

    action_term = match.group(2).lower()
    turn_on = action_term in ["روشن", "on"]

    db = load_db()
    g_data = get_group_data(db, chat_id)
    w_set = g_data.setdefault("welcome", {"enabled": True, "custom": False})
    w_set["enabled"] = turn_on

    action_label = "فعال" if turn_on else "غیرفعال"
    log_admin_action(
        db,
        user_id,
        user.full_name or "ادمین",
        chat.title or "گروه",
        chat_id,
        "دستور متنی خوش‌آمدگویی",
        f"وضعیت جدید: {action_label}"
    )
    mark_db_dirty()
    save_db(force=True)

    if turn_on:
        reply_html = f'<b>خوش‌آمدگویی گروه با موفقیت فعال شد!</b> <tg-emoji emoji-id="{CHECK_CUSTOM_EMOJI_ID}">✅</tg-emoji>'
    else:
        reply_html = f'<b>خوش‌آمدگویی گروه با موفقیت غیرفعال شد!</b> <tg-emoji emoji-id="{CROSS_CUSTOM_EMOJI_ID}">❌</tg-emoji>'

    try:
        await msg.reply_text(reply_html, parse_mode=ParseMode.HTML)
    except Exception as e:
        logger.error(f"Failed to respond to welcome command: {e}")

    raise ApplicationHandlerStop()

# ==========================================
# AUTOMATIC CHANNEL COMMENT & JOBS
# ==========================================
async def track_chats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    result = update.my_chat_member
    if not result:
        return

    new_status = result.new_chat_member.status
    chat = result.chat
    db = load_db()
    if new_status in [ChatMemberStatus.MEMBER, ChatMemberStatus.ADMINISTRATOR]:
        g_data = get_group_data(db, chat.id)
        g_data["title"] = chat.title or ""
        if chat.id not in db["active_chats"]:
            db["active_chats"].append(chat.id)
            mark_db_dirty()
            save_db(force=True)

        setup_chat_jobs(context.job_queue, [chat.id])

        welcome_msg = (
            "<b>سلام نینیا ، گودی اینجاست...! </b>"
            '<tg-emoji emoji-id="5276251363313996750">😊</tg-emoji>\n\n'
            "<b>شروع کنید به مسخره بازی که حال کنیم! </b>"
            '<tg-emoji emoji-id="5274211661870295868">😌</tg-emoji>'
        )
        try:
            await context.bot.send_message(chat_id=chat.id, text=welcome_msg, parse_mode=ParseMode.HTML)
        except Exception as e:
            logger.error(f"Failed to send welcome message: {e}")
    elif new_status in [ChatMemberStatus.LEFT, ChatMemberStatus.BANNED]:
        if chat.id in db["active_chats"]:
            db["active_chats"].remove(chat.id)
            mark_db_dirty()
            save_db(force=True)
        if context.job_queue:
            for jname in [f"goh_khor_{chat.id}", f"reaction_{chat.id}"]:
                jobs = context.job_queue.get_jobs_by_name(jname)
                for j in jobs:
                    j.schedule_removal()

async def handle_automatic_channel_comments(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if not msg or not getattr(msg, "is_automatic_forward", False):
        return

    chat = update.effective_chat
    if not chat or chat.type not in ["group", "supergroup"]:
        return

    db = load_db()
    g_data = get_group_data(db, chat.id)
    comment_settings = g_data.get("comment", {})

    if not comment_settings.get("enabled", False):
        return

    msg_key = f"{chat.id}_{msg.message_id}"
    commented_posts = db.setdefault("commented_channel_posts", [])
    if msg_key in commented_posts:
        return

    payload = comment_settings.get("payload")
    if not payload:
        return

    success = await send_media_payload(context.bot, chat.id, payload, reply_to_message_id=msg.message_id)
    if success:
        commented_posts.append(msg_key)
        if len(commented_posts) > 500:
            commented_posts.pop(0)
        mark_db_dirty()
        save_db()

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

async def periodic_group_reaction_job(context: ContextTypes.DEFAULT_TYPE):
    try:
        target_chat_id = context.job.chat_id
        if not target_chat_id:
            return

        db = load_db()
        if db.get("bot_shutdown", False):
            return
        g_banned, _ = is_group_globally_banned(db, target_chat_id)
        if g_banned:
            return

        g_data = get_group_data(db, target_chat_id)
        if not g_data.get("random_reaction", True):
            return

        user_last_msgs = g_data.get("user_last_messages", {})
        if not user_last_msgs:
            return

        candidate_users = list(user_last_msgs.keys())
        random.shuffle(candidate_users)

        for uid_str in candidate_users:
            uid = int(uid_str)
            u_banned, _ = is_user_globally_banned(db, uid)
            if u_banned:
                continue

            msg_id = user_last_msgs.get(uid_str)
            if not msg_id:
                continue

            try:
                await context.bot.set_message_reaction(
                    chat_id=target_chat_id,
                    message_id=msg_id,
                    reaction=[ReactionTypeEmoji(FIXED_REACTION)]
                )
                break
            except Exception:
                continue
    except Exception as e:
        logger.error(f"Error in periodic_group_reaction_job: {e}")

def setup_chat_jobs(job_queue, active_chats: list):
    if not job_queue:
        return
    for chat_id in active_chats:
        job_name_gk = f"goh_khor_{chat_id}"
        if not job_queue.get_jobs_by_name(job_name_gk):
            job_queue.run_repeating(hourly_goh_khor_job, interval=3600, first=3600, chat_id=chat_id, name=job_name_gk)

        job_name_rx = f"reaction_{chat_id}"
        if not job_queue.get_jobs_by_name(job_name_rx):
            job_queue.run_repeating(periodic_group_reaction_job, interval=300, first=300, chat_id=chat_id, name=job_name_rx)

# ==========================================
# GROUP LINK SYSTEM HELPERS
# ==========================================
LINK_COMMAND_PATTERN = re.compile(
    r"^(?:گودی\s+)?("
    r"لینک|دریافت\s+لینک|لینک\s+بده|گودی\s+لینک|گودی\s+لینک\s+بده|گودی\s+لینک\s+بگیر|گودی\s+لینک\s+بفرست|"
    r"گودی\s+لینک\s+عادی\s+بده|لینک\s+عادی|لینک\s+عادی\s+بگیر|لینک\s+عادی\s+بده|"
    r"لینک\s+یک‌بار\s+مصرف|لینک\s+یکبار\s+مصرف|لینک\s+یک‌بار\s+مصرف\s+بده|لینک\s+یکبار\s+مصرف\s+بده|گودی\s+لینک\s+یک‌بار\s+مصرف\s+بده|"
    r"لینک\s+پیوی|لینک\s+پیوی\s+بده|لینک\s+رو\s+پیوی\s+بفرست|لینک\s+در\s+پیوی|"
    r"لینک\s+عکس|لینک\s+به\s+صورت\s+عکس|لینک\s+عکس\s+بده|لینک\s+رو\s+عکس\s+بفرست"
    r")$",
    re.IGNORECASE
)

async def check_bot_admin_and_link_rights(context: ContextTypes.DEFAULT_TYPE, chat_id: int) -> bool:
    try:
        bot_member = await context.bot.get_chat_member(chat_id, context.bot.id)
        if bot_member.status != ChatMemberStatus.ADMINISTRATOR:
            return False
        if not getattr(bot_member, "can_invite_users", True):
            return False
        return True
    except Exception:
        return False

async def get_or_create_group_invite_link(context: ContextTypes.DEFAULT_TYPE, chat_id: int, expire_date: int = None, member_limit: int = None) -> str | None:
    try:
        link_obj = await context.bot.create_chat_invite_link(
            chat_id=chat_id,
            expire_date=expire_date,
            member_limit=member_limit
        )
        return link_obj.invite_link
    except Exception:
        try:
            return await context.bot.export_chat_invite_link(chat_id)
        except Exception:
            return None

def build_link_panel_keyboard(chat_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🗳 دریافت لینک بصورت متن", callback_data=f"link_panel:text:{chat_id}", style="default", icon_custom_emoji_id="5942921379614565429")],
        [InlineKeyboardButton("🗳 دریافت لینک بصورت عکس", callback_data=f"link_panel:photo:{chat_id}", style="default", icon_custom_emoji_id="5942921379614565429")],
        [InlineKeyboardButton("🗳 دریافت لینک یک‌بار مصرف", callback_data=f"link_panel:once:{chat_id}", style="default", icon_custom_emoji_id="5942921379614565429")],
        [InlineKeyboardButton("🗳 دریافت لینک در پیوی", callback_data=f"link_panel:pv:{chat_id}", style="default", icon_custom_emoji_id="5942921379614565429")],
        [InlineKeyboardButton("💠 بستن", callback_data=f"link_panel:close:{chat_id}", style="danger", icon_custom_emoji_id="5983093054842606366")]
    ])

def build_link_sub_keyboard(chat_id: int, is_once: bool = False) -> InlineKeyboardMarkup:
    if is_once:
        return InlineKeyboardMarkup([
            [InlineKeyboardButton("▶️ اشتراک‌گذاری", callback_data=f"link_sub:share:{chat_id}", style="primary", icon_custom_emoji_id="6030354793363413800")],
            [InlineKeyboardButton("💠 بستن", callback_data=f"link_panel:close:{chat_id}", style="danger", icon_custom_emoji_id="5983093054842606366")]
        ])
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("▶️ اشتراک‌گذاری", callback_data=f"link_sub:share:{chat_id}", style="primary", icon_custom_emoji_id="6030354793363413800")],
        [InlineKeyboardButton("🤍 حذف و ساخت لینک جدید", callback_data=f"link_sub:revoke:{chat_id}", style="default", icon_custom_emoji_id="6293870742282965014")],
        [InlineKeyboardButton("⬅️ بازگشت", callback_data=f"link_sub:back:{chat_id}", style="danger", icon_custom_emoji_id="5823664135103061930")]
    ])

async def generate_group_link_text_payload(context: ContextTypes.DEFAULT_TYPE, chat_id: int, is_once: bool = False) -> str:
    chat_obj = await context.bot.get_chat(chat_id)
    title = html.escape(chat_obj.title or "گروه")
    member_count = await context.bot.get_chat_member_count(chat_id)
    
    if is_once:
        import time
        expire_ts = int(time.time()) + 86400
        link = await get_or_create_group_invite_link(context, chat_id, expire_date=expire_ts, member_limit=1)
        link_str = link or "خطا در ساخت لینک"
        return (
            f'<tg-emoji emoji-id="6008070651900861977">📤</tg-emoji> <b>لینک یک‌بار مصرف شما آماده است.</b>\n\n'
            f'<tg-emoji emoji-id="5803420768826038185">🔘</tg-emoji> <b>نام گروه :</b> {title}\n'
            f'<tg-emoji emoji-id="5802963792895678011">⚫️</tg-emoji> <b>تعداد عضو :</b> {member_count}\n'
            f'<tg-emoji emoji-id="5803057229909202251">♻️</tg-emoji> <b>تاریخ انقضا لینک :</b> 24 ساعت\n'
            f'<tg-emoji emoji-id="5803351177470940363">🗣</tg-emoji> <b>افراد مجاز :</b> 1\n\n'
            f'<tg-emoji emoji-id="6008124493610885197">🔗</tg-emoji><tg-emoji emoji-id="6008124493610885197">🔗</tg-emoji><tg-emoji emoji-id="6008124493610885197">🔗</tg-emoji><tg-emoji emoji-id="6008124493610885197">🔗</tg-emoji><tg-emoji emoji-id="6008124493610885197">🔗</tg-emoji><tg-emoji emoji-id="6008124493610885197">🔗</tg-emoji><tg-emoji emoji-id="6008124493610885197">🔗\n\n'
            f'<tg-emoji emoji-id="6032888897082497570">📤</tg-emoji> <b>لینک گروه :</b>\n\n- {link_str}'
        )
    else:
        link = await get_or_create_group_invite_link(context, chat_id)
        link_str = link or "خطا در ساخت لینک"
        return (
            f'<tg-emoji emoji-id="5803420768826038185">🔘</tg-emoji> <b>نام گروه :</b> {title}\n'
            f'<tg-emoji emoji-id="5802963792895678011">⚫️</tg-emoji> <b>تعداد عضو :</b> {member_count}\n\n'
            f'<tg-emoji emoji-id="6008124493610885197">🔗</tg-emoji><tg-emoji emoji-id="6008124493610885197">🔗</tg-emoji><tg-emoji emoji-id="6008124493610885197">🔗</tg-emoji><tg-emoji emoji-id="6008124493610885197">🔗</tg-emoji><tg-emoji emoji-id="6008124493610885197">🔗</tg-emoji><tg-emoji emoji-id="6008124493610885197">🔗</tg-emoji><tg-emoji emoji-id="6008124493610885197">🔗\n\n'
            f'<tg-emoji emoji-id="6032888897082497570">📤</tg-emoji> <b>لینک گروه :</b>\n\n- {link_str}'
        )

async def post_init(application: Application):
    db = load_db()
    setup_chat_jobs(application.job_queue, db.get("active_chats", []))

# ==========================================
# CENTRAL GLOBAL GUARD / MIDDLEWARE
# ==========================================
async def global_security_guard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        user = update.effective_user
        chat = update.effective_chat
        db = load_db()

        if chat and chat.type in ["group", "supergroup"]:
            g_banned, _ = is_group_globally_banned(db, chat.id)
            if g_banned:
                raise ApplicationHandlerStop()

        if user and int(user.id) == int(OWNER_ID):
            return

        if user:
            is_banned, _ = is_user_globally_banned(db, user.id)
            if is_banned:
                raise ApplicationHandlerStop()

        if db.get("bot_shutdown", False):
            is_command = update.message and update.message.text and update.message.text.startswith("/")
            is_private = chat and chat.type == "private"
            
            if is_command or is_private:
                s_data = db.get("shutdown_message")
                target_chat_id = chat.id if chat else (user.id if user else None)
                reply_id = update.message.message_id if update.message else None
                if target_chat_id:
                    await dispatch_shutdown_message(context.bot, target_chat_id, s_data, reply_id)
                raise ApplicationHandlerStop()
            else:
                raise ApplicationHandlerStop()

    except ApplicationHandlerStop:
        raise
    except Exception as e:
        logger.error(f"Error in global_security_guard: {e}")

# ==========================================
# GROUP LOCK ENFORCER (MIDDLEWARE GROUP -5)
# ==========================================
async def enforce_group_locks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    user = update.effective_user
    msg = update.message or update.edited_message

    if not chat or chat.type not in ["group", "supergroup"] or not msg:
        return

    db = load_db()
    g_data = get_group_data(db, chat.id)
    locks = g_data.get("locks", {})

    if not any(locks.values()):
        return

    should_delete = False

    if msg.new_chat_members:
        is_join_by_link = False
        is_added_by_other = False

        if len(msg.new_chat_members) == 1 and user and msg.new_chat_members[0].id == user.id:
            is_join_by_link = True
        elif user and any(m.id != user.id for m in msg.new_chat_members):
            is_added_by_other = True
        else:
            is_join_by_link = True

        if is_join_by_link and locks.get("service_join_link", False):
            should_delete = True
        elif is_added_by_other and locks.get("service_add_member", False):
            should_delete = True

    if not should_delete and locks.get("service_pinned", False) and bool(getattr(msg, "pinned_message", None)):
        should_delete = True

    if not should_delete and locks.get("service_video_chat", False):
        has_vc_event = bool(
            getattr(msg, "video_chat_started", None) or
            getattr(msg, "video_chat_ended", None) or
            getattr(msg, "video_chat_participants_invited", None) or
            getattr(msg, "video_chat_scheduled", None) or
            getattr(msg, "voice_chat_started", None) or
            getattr(msg, "voice_chat_ended", None) or
            getattr(msg, "voice_chat_participants_invited", None)
        )
        if has_vc_event:
            should_delete = True

    if not should_delete:
        if user and (user.is_bot or await is_admin_or_owner(context, chat.id, user.id)):
            return

        is_edited = update.edited_message is not None

        if is_edited:
            has_media = bool(msg.photo or msg.video or msg.animation or msg.audio or msg.voice or msg.document or msg.sticker)
            if has_media and locks.get("edit_media", False):
                should_delete = True
            elif not has_media and locks.get("edit_msg", False):
                should_delete = True

        if not should_delete:
            if locks.get("photo", False) and bool(msg.photo): should_delete = True
            elif locks.get("video", False) and bool(msg.video): should_delete = True
            elif locks.get("gif", False) and bool(msg.animation): should_delete = True
            elif locks.get("audio", False) and bool(msg.audio): should_delete = True
            elif locks.get("voice", False) and bool(msg.voice): should_delete = True
            elif locks.get("document", False) and bool(msg.document): should_delete = True
            elif locks.get("sticker", False) and bool(msg.sticker): should_delete = True
            elif locks.get("location", False) and bool(msg.location or msg.venue): should_delete = True
            elif locks.get("contact", False) and bool(msg.contact): should_delete = True
            elif locks.get("poll", False) and bool(msg.poll): should_delete = True

        if not should_delete and locks.get("forward", False):
            if bool(msg.forward_origin or msg.forward_date or msg.forward_from or msg.forward_from_chat):
                should_delete = True

        if not should_delete:
            text_content = msg.text or msg.caption or ""
            entities = list(msg.entities or []) + list(msg.caption_entities or [])

            if locks.get("link", False):
                if any(e.type in [MessageEntityType.URL, MessageEntityType.TEXT_LINK] for e in entities) or URL_REGEX.search(text_content):
                    should_delete = True

            if not should_delete and locks.get("mention", False):
                if any(e.type in [MessageEntityType.MENTION, MessageEntityType.TEXT_MENTION] for e in entities):
                    should_delete = True

            if not should_delete and locks.get("tag", False):
                if "@" in text_content or any(e.type == MessageEntityType.MENTION for e in entities):
                    should_delete = True

            if not should_delete and locks.get("username", False):
                if any(e.type == MessageEntityType.MENTION for e in entities) or ("@" in text_content and not text_content.startswith("/")):
                    should_delete = True

            if not should_delete and locks.get("hashtag", False):
                if any(e.type == MessageEntityType.HASHTAG for e in entities) or "#" in text_content:
                    should_delete = True

            if not should_delete and locks.get("spoiler", False):
                if any(e.type == MessageEntityType.SPOILER for e in entities):
                    should_delete = True

            if not should_delete and locks.get("emoji", False):
                if any(e.type == MessageEntityType.CUSTOM_EMOJI for e in entities) or EMOJI_REGEX.search(text_content):
                    should_delete = True

            if not should_delete and locks.get("english", False):
                if ENGLISH_CHAR_REGEX.search(text_content):
                    should_delete = True

            if not should_delete and locks.get("persian", False):
                if PERSIAN_CHAR_REGEX.search(text_content):
                    should_delete = True

    if should_delete:
        try:
            await msg.delete()
        except Exception:
            pass
        if not bool(msg.new_chat_members):
            raise ApplicationHandlerStop()

# ==========================================
# ADMIN & OWNER PANEL LOGIC
# ==========================================
def get_owner_panel_content(db: dict) -> tuple[str, InlineKeyboardMarkup]:
    user_count = len(db.get("started_users", {}))
    group_count = len(db.get("active_chats", []))
    banned_users_count = len(db.get("global_bans", {}))
    banned_groups_count = len(db.get("global_group_bans", {}))

    text = "<b>مالک محترم ربات 👑\n\nبه پنل اصلی مدیریت ربات خوش آمدید. گزینه مورد نظر را انتخاب کنید:</b>"
    buttons = [
        [InlineKeyboardButton("🔴 خاموشی ربات", callback_data="panel_shutdown_menu", style="danger")],
        [
            InlineKeyboardButton(f"🚫 بن کاربر ({banned_users_count})", callback_data="ban_user_start", style="danger"),
            InlineKeyboardButton("🟢 انبن کاربر", callback_data="unban_user_start", style="success")
        ],
        [
            InlineKeyboardButton(f"🚫 بن گروه ({banned_groups_count})", callback_data="ban_group_list_1", style="danger"),
            InlineKeyboardButton("🟢 انبن گروه", callback_data="unban_group_list_1", style="success")
        ],
        [
            InlineKeyboardButton("😈 تنظیم فحش ناموسی", callback_data="owner_fun_named", style="danger"),
            InlineKeyboardButton("😂 تنظیم فحش عادی", callback_data="owner_fun_normal", style="primary")
        ],
        [
            InlineKeyboardButton("📢 شعارهای سراسری", callback_data="owner_list_poems", style="primary"),
            InlineKeyboardButton("🍽 غذاهای سراسری", callback_data="owner_list_foods", style="primary")
        ],
        [
            InlineKeyboardButton("➕ افزودن شعر جدید", callback_data="owner_add_poem", style="success"),
            InlineKeyboardButton("➕ افزودن غذا", callback_data="owner_add_food", style="success")
        ],
        [InlineKeyboardButton(f"📋 مشخصات گروه‌ها ({group_count})", callback_data="panel_owner_groups_1", style="primary")],
        [InlineKeyboardButton("⏱ زمان محدودیت (Cooldown)", callback_data="panel_cooldown", style="primary")],
        [InlineKeyboardButton("⚙ مدیریت قابلیت ها", callback_data="panel_features", style="primary")],
        [InlineKeyboardButton("📢 پیام همگانی پیشرفته (Broadcast)", callback_data="panel_bcast_type_select", style="primary")],
        [InlineKeyboardButton(f"📢 پیام همگانی کاربران ({user_count})", callback_data="panel_user_broadcast", style="success")],
        [InlineKeyboardButton("📋 ادمین لاگ", callback_data="panel_admin_logs", style="primary")]
    ]
    return text, InlineKeyboardMarkup(buttons)

async def send_owner_panel_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    db = load_db()
    clear_user_all_states(db, update.effective_user.id, update.effective_chat.id)
    text, keyboard = get_owner_panel_content(db)
    await update.message.reply_text(text, reply_markup=keyboard, parse_mode=ParseMode.HTML)

async def edit_owner_panel_message(query):
    db = load_db()
    clear_user_all_states(db, query.from_user.id, query.message.chat.id)
    text, keyboard = get_owner_panel_content(db)
    await query.message.edit_text(text, reply_markup=keyboard, parse_mode=ParseMode.HTML)

def build_group_admin_panel_content(chat_id: int, title: str) -> tuple[str, InlineKeyboardMarkup]:
    esc_title = html.escape(title or "این گروه")
    text = (
        f'<b>به بخش مدیریت گروه خود خوش‌آمدید! <tg-emoji emoji-id="{PANEL_SCALE_EMOJI_ID}">⚖️</tg-emoji></b>\n'
        f'<b><tg-emoji emoji-id="{PANEL_CASTLE_EMOJI_ID}">🏰</tg-emoji> نام گروه: {esc_title}</b>\n\n'
        f'<b>- لطفا از طریق دکمه های زیر عملیات مدیریتی خود را انجام دهید! <tg-emoji emoji-id="{PANEL_HASH_EMOJI_ID}">#️⃣</tg-emoji></b>'
    )
    buttons = [
        [
            InlineKeyboardButton("قفل‌ها", callback_data=f"panel_group_locks:{chat_id}:1", style="primary", icon_custom_emoji_id=LOCK_CUSTOM_EMOJI_ID),
            InlineKeyboardButton("لیست‌ها", callback_data=f"panel_group_lists:{chat_id}", style="primary", icon_custom_emoji_id=LISTS_CUSTOM_EMOJI_ID)
        ],
        [
            InlineKeyboardButton("تنظیمات پیشرفته", callback_data=f"panel_group_advanced:{chat_id}", style="primary", icon_custom_emoji_id=ADVANCED_CUSTOM_EMOJI_ID)
        ],
        [
            InlineKeyboardButton("بستن", callback_data="panel_group_close", style="danger", icon_custom_emoji_id=CLOSE_CUSTOM_EMOJI_ID)
        ]
    ]
    return text, InlineKeyboardMarkup(buttons)

async def render_group_admin_panel_message(query, chat_id: int):
    db = load_db()
    g_data = get_group_data(db, chat_id)
    text, keyboard = build_group_admin_panel_content(chat_id, g_data.get("title") or "")
    await query.message.edit_text(text, reply_markup=keyboard, parse_mode=ParseMode.HTML)

async def command_admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message:
        return
    if not update.effective_chat or update.effective_chat.type not in ["group", "supergroup"]:
        return

    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    
    if not await is_admin_or_owner(context, chat_id, user_id):
        await update.message.reply_text(
            f'<b><tg-emoji emoji-id="{CROSS_CUSTOM_EMOJI_ID}">❌</tg-emoji> شما دسترسی مدیریت این گروه را ندارید.</b>',
            parse_mode=ParseMode.HTML
        )
        return

    db = load_db()
    g_data = get_group_data(db, chat_id)
    text, keyboard = build_group_admin_panel_content(chat_id, g_data.get("title") or "")
    await update.message.reply_text(text, reply_markup=keyboard, parse_mode=ParseMode.HTML)

# ==========================================
# PER-GROUP LOCKS PANEL RENDERING
# ==========================================
async def render_group_locks_panel(query, chat_id: int, page: int = 1):
    db = load_db()
    g_data = get_group_data(db, chat_id)
    locks = g_data.get("locks", {})

    text = (
        f'<b>به بخش قفل گروه خود خوش آمدید! <tg-emoji emoji-id="{CANDY_CUSTOM_EMOJI_ID}">🍭</tg-emoji></b>\n'
        '<b>چه عملیاتی انجام می‌دهید؟</b>'
    )

    page_locks = [k for k, v in ALL_LOCKS.items() if v["page"] == page]
    buttons = []
    
    for i in range(0, len(page_locks), 2):
        row = []
        k1 = page_locks[i]
        meta1 = ALL_LOCKS[k1]
        name1 = meta1['name']

        if meta1.get("is_category"):
            btn1 = InlineKeyboardButton(name1, callback_data=f"panel_service_locks:{chat_id}", style=None)
        else:
            is_on1 = locks.get(k1, False)
            btn1 = InlineKeyboardButton(
                name1,
                callback_data=f"tgl_lock:{chat_id}:{k1}:{page}",
                style="success" if is_on1 else None,
                icon_custom_emoji_id=CHECK_CUSTOM_EMOJI_ID if is_on1 else None
            )
        row.append(btn1)

        if i + 1 < len(page_locks):
            k2 = page_locks[i + 1]
            meta2 = ALL_LOCKS[k2]
            name2 = meta2['name']
            if meta2.get("is_category"):
                btn2 = InlineKeyboardButton(name2, callback_data=f"panel_service_locks:{chat_id}", style=None)
            else:
                is_on2 = locks.get(k2, False)
                btn2 = InlineKeyboardButton(
                    name2,
                    callback_data=f"tgl_lock:{chat_id}:{k2}:{page}",
                    style="success" if is_on2 else None,
                    icon_custom_emoji_id=CHECK_CUSTOM_EMOJI_ID if is_on2 else None
                )
            row.append(btn2)
        buttons.append(row)

    if page == 1:
        nav_row = [
            InlineKeyboardButton("بازگشت", callback_data=f"panel_group_main:{chat_id}", style="danger", icon_custom_emoji_id=BACK_CUSTOM_EMOJI_ID),
            InlineKeyboardButton("صفحه بعد", callback_data=f"panel_group_locks:{chat_id}:2", style="danger", icon_custom_emoji_id=NEXT_CUSTOM_EMOJI_ID)
        ]
    else:
        nav_row = [
            InlineKeyboardButton("صفحه قبل", callback_data=f"panel_group_locks:{chat_id}:1", style="danger", icon_custom_emoji_id=PREV_CUSTOM_EMOJI_ID),
            InlineKeyboardButton("بازگشت", callback_data=f"panel_group_main:{chat_id}", style="danger", icon_custom_emoji_id=BACK_CUSTOM_EMOJI_ID)
        ]
    buttons.append(nav_row)

    await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(buttons), parse_mode=ParseMode.HTML)

# ==========================================
# TELEGRAM SERVICE LOCKS PANEL RENDERING
# ==========================================
async def render_telegram_service_locks_panel(query, chat_id: int):
    db = load_db()
    g_data = get_group_data(db, chat_id)
    locks = g_data.get("locks", {})

    text = (
        f'<b><tg-emoji emoji-id="{GEAR_CUSTOM_EMOJI_ID}">⚙️</tg-emoji> مدیریت قفل سرویس‌های تلگرام <tg-emoji emoji-id="{CANDY_CUSTOM_EMOJI_ID}">🍭</tg-emoji></b>\n\n'
        '<b>از گزینه‌های زیر برای روشن یا خاموش کردن حذف پیام‌های سرویس استفاده کنید:</b>'
    )

    buttons = []
    for k in TELEGRAM_SERVICE_LOCK_KEYS:
        is_on = locks.get(k, False)
        name = ALL_LOCKS[k]['name']
        btn = InlineKeyboardButton(
            name,
            callback_data=f"tgl_srv_lock:{chat_id}:{k}",
            style="success" if is_on else None,
            icon_custom_emoji_id=CHECK_CUSTOM_EMOJI_ID if is_on else None
        )
        buttons.append([btn])

    buttons.append([InlineKeyboardButton("بازگشت به قفل‌ها", callback_data=f"panel_group_locks:{chat_id}:2", style="danger", icon_custom_emoji_id=BACK_CUSTOM_EMOJI_ID)])

    await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(buttons), parse_mode=ParseMode.HTML)

# ==========================================
# OWNER BAN/UNBAN GROUP PICKERS
# ==========================================
async def render_ban_group_picker(query, page: int, db: dict):
    active_chats = db.get("active_chats", [])
    banned_chats = db.get("global_group_bans", {})
    available_chats = [cid for cid in active_chats if str(cid) not in banned_chats]

    page_size = 5
    total_pages = max(1, (len(available_chats) + page_size - 1) // page_size)
    page = max(1, min(page, total_pages))

    start_idx = (page - 1) * page_size
    current_chats = available_chats[start_idx:start_idx + page_size]

    text = f"🚫 <b>انتخاب گروه برای بن (صفحه {page} از {total_pages})</b>\n\nروی گروه مورد نظر کلیک کنید:"
    buttons = []

    for cid in current_chats:
        g_data = get_group_data(db, cid)
        title = g_data.get("title") or f"گروه {cid}"
        buttons.append([InlineKeyboardButton(f"🚫 {title}", callback_data=f"select_bangrp:{cid}", style="danger")])

    nav_row = []
    if page > 1:
        nav_row.append(InlineKeyboardButton("⬅️ قبلی", callback_data=f"ban_group_list_{page-1}", style="primary"))
    if page < total_pages:
        nav_row.append(InlineKeyboardButton("بعدی ➡️", callback_data=f"ban_group_list_{page+1}", style="primary"))

    if nav_row:
        buttons.append(nav_row)
    buttons.append([InlineKeyboardButton("🔙 بازگشت به پنل اصلی", callback_data="panel_owner_main", style="primary")])

    await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(buttons), parse_mode=ParseMode.HTML)

async def render_unban_group_picker(query, page: int, db: dict):
    banned_chats = list(db.get("global_group_bans", {}).keys())

    if not banned_chats:
        kb = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 بازگشت", callback_data="panel_owner_main", style="primary")]])
        await query.message.edit_text(
            f'<b><tg-emoji emoji-id="{CROSS_CUSTOM_EMOJI_ID}">❌</tg-emoji> هیچ گروهی در لیست بن قرار ندارد.</b>',
            reply_markup=kb,
            parse_mode=ParseMode.HTML
        )
        return

    page_size = 5
    total_pages = max(1, (len(banned_chats) + page_size - 1) // page_size)
    page = max(1, min(page, total_pages))

    start_idx = (page - 1) * page_size
    current_chats = banned_chats[start_idx:start_idx + page_size]

    text = f"🟢 <b>انتخاب گروه برای انبن (صفحه {page} از {total_pages})</b>\n\nروی گروه مورد نظر کلیک کنید:"
    buttons = []

    for cid_str in current_chats:
        g_data = get_group_data(db, cid_str)
        title = g_data.get("title") or f"گروه {cid_str}"
        buttons.append([InlineKeyboardButton(f"🟢 انبن: {title}", callback_data=f"select_unbangrp:{cid_str}", style="success")])

    nav_row = []
    if page > 1:
        nav_row.append(InlineKeyboardButton("⬅️ قبلی", callback_data=f"unban_group_list_{page-1}", style="primary"))
    if page < total_pages:
        nav_row.append(InlineKeyboardButton("بعدی ➡️", callback_data=f"unban_group_list_{page+1}", style="primary"))

    if nav_row:
        buttons.append(nav_row)
    buttons.append([InlineKeyboardButton("🔙 بازگشت به پنل اصلی", callback_data="panel_owner_main", style="primary")])

    await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(buttons), parse_mode=ParseMode.HTML)

async def render_shutdown_panel(query, db: dict):
    is_down = db.get("bot_shutdown", False)
    status_str = "🔴 وضعیت ربات: خاموش" if is_down else "🟢 وضعیت ربات: روشن"

    buttons = [
        [InlineKeyboardButton("🔴 خاموش کردن ربات", callback_data="bot_do_shutdown", style="danger")],
        [InlineKeyboardButton("🟢 روشن کردن ربات", callback_data="bot_do_turn_on", style="success")],
        [InlineKeyboardButton("🔙 بازگشت", callback_data="panel_owner_main", style="primary")]
    ]
    await query.message.edit_text(f"<b>مدیریت خاموشی ربات</b>\n\n{status_str}", reply_markup=InlineKeyboardMarkup(buttons), parse_mode=ParseMode.HTML)

async def render_owner_fun_panel(query, fun_type: str, db: dict):
    title = "😈 مدیریت فحش ناموسی ربات" if fun_type == "named" else "😂 مدیریت فحش عادی ربات"
    key = "global_fun_named" if fun_type == "named" else "global_fun_normal"
    items = db.get(key, [])
    
    text = (
        f"<b>{title}</b>\n\n"
        f"<b>تعداد پاسخ‌های ثبت‌شده:</b> <code>{len(items)}</code> عدد"
    )

    buttons = [
        [InlineKeyboardButton("➕ افزودن پاسخ", callback_data=f"own_fun_add:{fun_type}", style="success")],
        [InlineKeyboardButton("🧹 حذف همه پاسخ‌ها", callback_data=f"own_fun_del_all:{fun_type}", style="danger")],
        [InlineKeyboardButton("🔙 بازگشت به پنل اصلی", callback_data="panel_owner_main", style="primary")]
    ]
    await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(buttons), parse_mode=ParseMode.HTML)

async def render_welcome_panel_message(query, chat_id: int, db: dict):
    g_data = get_group_data(db, chat_id)
    w_set = g_data.get("welcome", {})
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
        [InlineKeyboardButton(toggle_btn_text, callback_data=f"welcome_toggle:{chat_id}", style="primary")],
        [InlineKeyboardButton("⚙️ تنظیم پیام خوش‌آمد", callback_data=f"welcome_set:{chat_id}", style="success")],
        [InlineKeyboardButton("🗑 حذف پیام اختصاصی", callback_data=f"welcome_delete_confirm:{chat_id}", style="danger")],
        [InlineKeyboardButton("🔙 بازگشت", callback_data=f"panel_group_advanced:{chat_id}", style="primary")]
    ]
    await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(buttons), parse_mode=ParseMode.HTML)

async def render_comment_panel_message(query, chat_id: int, db: dict):
    g_data = get_group_data(db, chat_id)
    c_set = g_data.get("comment", {})
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
        [InlineKeyboardButton("💬 تنظیم کامنت", callback_data=f"comment_set:{chat_id}", style="success")],
        [InlineKeyboardButton(toggle_btn_text, callback_data=f"comment_toggle:{chat_id}", style="primary")],
        [InlineKeyboardButton("🗑 حذف کامنت ذخیره‌شده", callback_data=f"comment_delete:{chat_id}", style="danger")],
        [InlineKeyboardButton("🔙 بازگشت", callback_data=f"panel_group_advanced:{chat_id}", style="primary")]
    ]
    await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(buttons), parse_mode=ParseMode.HTML)

async def render_owner_groups_page(query, page: int, db: dict, context: ContextTypes.DEFAULT_TYPE):
    active_chats = db.get("active_chats", [])
    page_size = 5
    total_pages = max(1, (len(active_chats) + page_size - 1) // page_size)
    page = max(1, min(page, total_pages))

    start_idx = (page - 1) * page_size
    current_chats = active_chats[start_idx:start_idx + page_size]

    text = f"📋 <b>مشخصات گروه‌ها (صفحه {page} از {total_pages})</b>\n\nلطفاً گروه موردنظر را انتخاب کنید:"
    buttons = []

    for cid in current_chats:
        g_data = get_group_data(db, cid)
        title = g_data.get("title") or str(cid)
        buttons.append([InlineKeyboardButton(f"🏠 {title}", callback_data=f"ogrp_view:{cid}", style="primary")])

    nav_row = []
    if page > 1:
        nav_row.append(InlineKeyboardButton("⬅️ قبلی", callback_data=f"panel_owner_groups_{page-1}", style="primary"))
    if page < total_pages:
        nav_row.append(InlineKeyboardButton("بعدی ➡️", callback_data=f"panel_owner_groups_{page+1}", style="primary"))

    if nav_row:
        buttons.append(nav_row)
    buttons.append([InlineKeyboardButton("🔙 بازگشت به پنل اصلی", callback_data="panel_owner_main", style="primary")])

    await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(buttons), parse_mode=ParseMode.HTML)

async def render_owner_single_group_panel(query, target_cid: int, db: dict, context: ContextTypes.DEFAULT_TYPE):
    g_data = get_group_data(db, target_cid)
    title = html.escape(g_data.get("title") or "بدون عنوان")
    
    text = (
        f"📋 <b>مشخصات گروه: {title}</b>\n"
        f"🆔 <b>Chat ID:</b> <code>{target_cid}</code>\n\n"
        "یکی از گزینه‌های زیر را انتخاب نمایید:"
    )

    buttons = [
        [InlineKeyboardButton("🔗 لینک گروه", callback_data=f"ogrp_link:{target_cid}", style="primary")],
        [InlineKeyboardButton("👥 اعضای گروه (TXT)", callback_data=f"ogrp_members:{target_cid}", style="primary")],
        [InlineKeyboardButton("🔎 سرچ پیام (TXT)", callback_data=f"ogrp_search:{target_cid}", style="primary")],
        [InlineKeyboardButton("👮 ادمین‌ها (TXT)", callback_data=f"ogrp_admins:{target_cid}", style="primary")],
        [InlineKeyboardButton("🔙 بازگشت به لیست گروه‌ها", callback_data="panel_owner_groups_1", style="primary")]
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

async def start_dwoz_game(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.effective_chat:
        return
    if update.effective_chat.type not in ["group", "supergroup"]:
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
    if not update.effective_chat or update.effective_chat.type not in ["group", "supergroup"]:
        return

    raw_text = update.message.text.strip().lower()
    clean = raw_text.replace("\u200c", " ")
    clean = re.sub(r"[؟?\.,!؛\-_]", "", clean).strip()

    valid_triggers = ["دوز", "گودی دوز", "گودی دوز بزار", "گودی دوز بذار", "بازی دوز"]
    if clean in valid_triggers or raw_text in valid_triggers:
        await start_dwoz_game(update, context)
        raise ApplicationHandlerStop()

# ==========================================
# WHISPER (INLINE NAJVA) SYSTEM
# ==========================================
async def handle_inline_whisper(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query_obj = update.inline_query
    logger.info(f"Received Inline Query from {query_obj.from_user.id}: '{query_obj.query}'")
    
    query = query_obj.query.strip()
    user = query_obj.from_user
       
    if not query:
        help_text = (
            '🔗 <tg-emoji emoji-id="6084584811379299518">🔗</tg-emoji> <b>آموزش نجوا در ربات گودی!</b>\n\n'
            'پیام خود را جلوی یوزرنیم ربات نوشته و در انتهای پیام خود یوزرنیم یا آیدی عددی فرد دریافت کننده را وارد کنید.'
        )
        results = [
            InlineQueryResultArticle(
                id="whisper_help",
                title="🔗 آموزش نجوا در ربات گودی!",
                description="نحوه استفاده از سیستم نجوا",
                input_message_content=InputTextMessageContent(help_text, parse_mode=ParseMode.HTML)
            )
        ]
        await update.inline_query.answer(results, cache_time=0, is_personal=True)
        return

    parts = query.split()
    if len(parts) < 2:
        results = [
            InlineQueryResultArticle(
                id="whisper_error",
                title="❌ فرمت نامعتبر نجوا",
                description="متن پیام + یوزرنیم یا آیدی عددی گیرنده",
                input_message_content=InputTextMessageContent("<b>❌ فرمت نجوا اشتباه است. لطفاً گیرنده را در انتهای پیام مشخص کنید.</b>", parse_mode=ParseMode.HTML)
            )
        ]
        await update.inline_query.answer(results, cache_time=0, is_personal=True)
        return

    target = parts[-1]
    message_text = " ".join(parts[:-1])

    if len(message_text) > 500:
        results = [
            InlineQueryResultArticle(
                id="whisper_too_long",
                title="❌ متن پیام خیلی طولانی است",
                description="حداکثر طول مجاز ۵۰۰ کاراکتر است.",
                input_message_content=InputTextMessageContent("<b>❌ متن نجوا بیش از حد طولانی است.</b>", parse_mode=ParseMode.HTML)
            )
        ]
        await update.inline_query.answer(results, cache_time=0, is_personal=True)
        return

    target_uid = None
    target_uname = None

    clean_target = target.lstrip("@")
    if clean_target.isdigit():
        target_uid = int(clean_target)
    else:
        target_uname = clean_target.lower()

    if target_uid and target_uid == user.id:
        results = [
            InlineQueryResultArticle(
                id="whisper_self",
                title="❌ ارسال نجوا به خودتان مجاز نیست",
                description="نمی‌توانید برای خودتان نجوا بفرستید.",
                input_message_content=InputTextMessageContent("<b>❌ نمی‌توانید به خودتان نجوا بفرستید!</b>", parse_mode=ParseMode.HTML)
            )
        ]
        await update.inline_query.answer(results, cache_time=0, is_personal=True)
        return

    import uuid
    w_id = uuid.uuid4().hex[:12]

    db = load_db()
    whispers = db.setdefault("whispers", {})
    whispers[w_id] = {
        "whisper_id": w_id,
        "sender_id": user.id,
        "sender_username": user.username or "",
        "sender_name": user.full_name or "کاربر",
        "target_uid": target_uid,
        "target_username": target_uname,
        "text": message_text,
        "created_at": datetime.now().timestamp(),
        "read": False,
        "reader_id": None,
        "reader_username": None,
        "reader_name": None,
        "deleted": False
    }
    mark_db_dirty()
    save_db(force=True)

    display_target = f"@{target_uname}" if target_uname else str(target_uid)
    result_title = f"🪪 ارسال پیام نجوا به {display_target}"
    result_html = f'<tg-emoji emoji-id="5843911663203392756">🪪</tg-emoji> ارسال پیام نجوا به {display_target}'

    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🎟 مشاهده نجوا", callback_data=f"wh_read:{w_id}", style="success", icon_custom_emoji_id="5902293707708701317"),
            InlineKeyboardButton("⚠️ حذف نجوا", callback_data=f"wh_del:{w_id}", style="danger", icon_custom_emoji_id="6086969407286808660")
        ]
    ])

    results = [
        InlineQueryResultArticle(
            id=w_id,
            title=result_title,
            description=message_text[:50],
            input_message_content=InputTextMessageContent(result_html, parse_mode=ParseMode.HTML),
            reply_markup=keyboard
        )
    ]
    await update.inline_query.answer(results, cache_time=0, is_personal=True)

def get_advanced_status_text(db: dict, chat_id: int) -> str:
    base_text = '<tg-emoji emoji-id="5765170391383286478">🗂</tg-emoji> <b>تنظیمات پیشرفته :</b>\n\n- عملیات مدیریتی خود را از طریق دکمه‌های زیر انجام دهید.'
    return base_text

async def build_group_lists_status(context: ContextTypes.DEFAULT_TYPE, chat_id: int, db: dict, g_data: dict) -> str:
    # مالکین
    owners_count = 1  # مالک ربات/گروه به عنوان پیش‌فرض
    
    # مدیران (تلاش برای گرفتن تعداد ادمین‌ها از API تلگرام)
    admins_count = 0
    try:
        admins = await context.bot.get_chat_administrators(chat_id)
        admins_count = len(admins)
    except Exception:
        admins_count = 0

    # اعضای ویژه
    special_members_count = len(g_data.get("special_members", []))

    # سکوت‌شده‌ها (Mute)
    muted_count = len(g_data.get("muted_users", []))

    # بن‌شده‌ها
    banned_count = len(db.get("global_group_bans", {}))

    # اخطار گرفتگان
    warned_count = len(g_data.get("warned_users", []))

    # معاف شدگان (Exempt)
    exempt_count = len(g_data.get("exempt_users", []))

    # کلمات فیلتر
    filter_words_count = len(g_data.get("filter_words", []))

    # کامنت‌گذاری
    comment_enabled = g_data.get("comment", {}).get("enabled", False)
    comment_status_str = "فعال" if comment_enabled else "غیرفعال"

    # لیست پاسخ (پاسخ‌دهی خودکار)
    auto_responses_count = len(g_data.get("auto_responses", []))

    text = (
        '<tg-emoji emoji-id="5803057229909202251">♻️</tg-emoji> <b>بخش لیست ها :</b>\n\n'
        f'   ├<tg-emoji emoji-id="5803378592247190638">⚡️</tg-emoji> <b>مالکین : {owners_count}</b>\n'
        f'   ├<tg-emoji emoji-id="5983208078361761545">⚡️</tg-emoji> <b>مدیران : {admins_count}</b>\n'
        f'   ├<tg-emoji emoji-id="5803224441575970112">💼</tg-emoji> <b>ویژه ها : {special_members_count}</b>\n'
        f'   ├<tg-emoji emoji-id="5983227268275638287">💠</tg-emoji> <b>سکوت شدگان : {muted_count}</b>\n'
        f'   ├<tg-emoji emoji-id="5802963792895678011">⚫️</tg-emoji> <b>بن شدگان : {banned_count}</b>\n'
        f'   ├<tg-emoji emoji-id="5803420768826038185">🔘</tg-emoji> <b>اخطار گرفتگان : {warned_count}</b>\n'
        f'   ├<tg-emoji emoji-id="5803257186406634805">🖤</tg-emoji> <b>معاف شدگان : {exempt_count}</b>\n'
        f'   ├<tg-emoji emoji-id="5866017773976555711">⚫️</tg-emoji> <b>کلمات فیلتر : {filter_words_count}</b>\n'
        f'   ├<tg-emoji emoji-id="5981132367912243320">🟢</tg-emoji> <b>کامنت‌گذاری : {comment_status_str}</b>\n'
        f'   ├<tg-emoji emoji-id="5980891235563343409">🤖</tg-emoji> <b>لیست پاسخ : {auto_responses_count}</b>\n'
        '~ ~ ~ ~ ~ ~ ~ ~ ~ ~'
    )
    return text   
# ==========================================
# CALLBACK QUERY HANDLER
# ==========================================
async def handle_callback_query(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data
    user_id = query.from_user.id
    current_chat_id = query.message.chat.id if query.message else 0
    db = load_db()
    session_k = get_session_key(user_id, current_chat_id)

    if data.startswith("help_"):
        await query.answer("Coming soon..!", show_alert=True)
        return

    # LINK PANEL & ACTIONS CALLBACKS
    elif data.startswith("link_panel:"):
        parts = data.split(":")
        action = parts[1]
        cid = int(parts[2])
        if not await is_admin_or_owner(context, cid, user_id):
            await query.answer("❌ دسترسی غیرمجاز!", show_alert=True)
            return
        if action == "close":
            try: await query.message.delete()
            except Exception: pass
            await query.answer()
            return
        if action == "text":
            text_payload = await generate_group_link_text_payload(context, cid, is_once=False)
            await query.message.edit_text(text_payload, reply_markup=build_link_sub_keyboard(cid, is_once=False), parse_mode=ParseMode.HTML)
            return
        elif action == "photo":
            try:
                chat_obj = await context.bot.get_chat(cid)
                caption_text = await generate_group_link_text_payload(context, cid, is_once=False)
                await query.message.delete()
                if chat_obj.photo and chat_obj.photo.big_file_id:
                    await context.bot.send_photo(chat_id=cid, photo=chat_obj.photo.big_file_id, caption=caption_text, parse_mode=ParseMode.HTML)
                else:
                    await context.bot.send_message(chat_id=cid, text=caption_text, parse_mode=ParseMode.HTML)
            except Exception: pass
            return
        elif action == "once":
            text_payload = await generate_group_link_text_payload(context, cid, is_once=True)
            await query.message.edit_text(text_payload, reply_markup=build_link_sub_keyboard(cid, is_once=True), parse_mode=ParseMode.HTML)
            return
        elif action == "pv":
            try:
                text_payload = await generate_group_link_text_payload(context, cid, is_once=False)
                await context.bot.send_message(chat_id=user_id, text=text_payload, parse_mode=ParseMode.HTML)
                await query.answer("✅ لینک گروه در پیوی شما ارسال شد.", show_alert=True)
            except Exception:
                await query.answer("❌ خطا در ارسال به پیوی (ربات را استارت کنید).", show_alert=True)
            return

    elif data.startswith("link_sub:"):
        parts = data.split(":")
        sub_action = parts[1]
        cid = int(parts[2])
        if not await is_admin_or_owner(context, cid, user_id):
            await query.answer("❌ دسترسی غیرمجاز!", show_alert=True)
            return
        if sub_action == "back":
            panel_text = f'<tg-emoji emoji-id="6044084382174552276">📊</tg-emoji> <b>نوع لینک را انتخاب کنید:</b>'
            await query.message.edit_text(panel_text, reply_markup=build_link_panel_keyboard(cid), parse_mode=ParseMode.HTML)
            return
        elif sub_action == "revoke":
            kb = InlineKeyboardMarkup([
                [InlineKeyboardButton("✅ بله", callback_data=f"link_revoke:yes:{cid}", style="success", icon_custom_emoji_id="5830144944399981619"),
                 InlineKeyboardButton("❌ خیر", callback_data=f"link_revoke:no:{cid}", style="danger", icon_custom_emoji_id="5819154526816444042")]
            ])
            await query.message.edit_text("<b>از حذف لینک نهایت اطمینان را دارید؟</b>", reply_markup=kb, parse_mode=ParseMode.HTML)
            return

    elif data.startswith("link_revoke:"):
        parts = data.split(":")
        decision = parts[1]
        cid = int(parts[2])
        if not await is_admin_or_owner(context, cid, user_id):
            await query.answer("❌ دسترسی غیرمجاز!", show_alert=True)
            return
        if decision == "no":
            text_payload = await generate_group_link_text_payload(context, cid, is_once=False)
            await query.message.edit_text(text_payload, reply_markup=build_link_sub_keyboard(cid, is_once=False), parse_mode=ParseMode.HTML)
            return
        elif decision == "yes":
            try:
                links = await context.bot.get_chat_export_invite_links(cid)
                for l in links:
                    try: await context.bot.revoke_chat_invite_link(cid, l.invite_link)
                    except Exception: pass
            except Exception: pass
            success_text = f'<tg-emoji emoji-id="5830144944399981619">✅</tg-emoji> <b>لینک شما با موفقیت حذف و با لینک جدید جایگزین شد.</b>'
            kb = InlineKeyboardMarkup([
                [InlineKeyboardButton("💠 بازگشت", callback_data=f"link_panel:text:{cid}", style="danger", icon_custom_emoji_id="5983093054842606366")]
            ])
            await query.message.edit_text(success_text, reply_markup=kb, parse_mode=ParseMode.HTML)
            return    

    # LOCKS PANEL NAVIGATION & TOGGLE
    elif data.startswith("panel_group_locks:"):
        parts = data.split(":")
        cid = int(parts[1])
        page = int(parts[2]) if len(parts) > 2 else 1
        if not await is_admin_or_owner(context, cid, user_id):
            await query.answer("❌ دسترسی غیرمجاز!", show_alert=True)
            return
        await render_group_locks_panel(query, cid, page)
        return

    elif data.startswith("panel_service_locks:"):
        cid = int(data.split(":")[1])
        if not await is_admin_or_owner(context, cid, user_id):
            await query.answer("❌ دسترسی غیرمجاز!", show_alert=True)
            return
        await render_telegram_service_locks_panel(query, cid)
        return

     # WHISPER (NAJVA) CALLBACKS
    elif data.startswith("wh_read:"):
        w_id = data.replace("wh_read:", "")
        whispers = db.get("whispers", {})
        
        if w_id not in whispers:
            await query.answer("❌ این نجوا منقضی یا حذف شده است!", show_alert=True)
            return

        w_data = whispers[w_id]
        sender_id = w_data["sender_id"]
        target_uid = w_data.get("target_uid")
        target_uname = w_data.get("target_username")

        u_uname = (query.from_user.username or "").lower()
        u_id = query.from_user.id

        is_sender = (u_id == sender_id)
        is_target = (target_uid and u_id == target_uid) or (target_uname and u_uname == target_uname)

        if not is_sender and not is_target:
            await query.answer("😐 فضولی نکن! این نجوا برای شما نیست.", show_alert=True)
            return

        await query.answer(f"🔒 متن نجوا:\n\n{w_data['text']}", show_alert=True)

        if is_target and not w_data.get("read", False):
            w_data["read"] = True
            w_data["reader_id"] = u_id
            w_data["reader_username"] = query.from_user.username or ""
            w_data["reader_name"] = query.from_user.full_name
            db["whispers"][w_id] = w_data
            mark_db_dirty()
            save_db(force=True)

            r_mention = get_user_mention(u_id, query.from_user.full_name)
            edited_text = f'<b><tg-emoji emoji-id="5830245188936670873">🌟</tg-emoji> نجوا با موفقیت توسط کاربر {r_mention} خوانده شد.</b>'

            new_kb = InlineKeyboardMarkup([
                [InlineKeyboardButton("👀 خواندن مجدد", callback_data=f"wh_read:{w_id}", style="primary", icon_custom_emoji_id="5843493805835165294")],
                [
                    InlineKeyboardButton("🏦 ارسال نجوا", switch_inline_query_current_chat="", style="success", icon_custom_emoji_id="5832240029446971049"),
                    InlineKeyboardButton("🤝 پاسخ به نجوا", switch_inline_query_current_chat=f"@{w_data['sender_username']} " if w_data.get('sender_username') else f"{w_data['sender_id']} ", style="success", icon_custom_emoji_id="6294041016261414265")
                ]
            ]) if is_target and not is_sender else InlineKeyboardMarkup([
                [InlineKeyboardButton("👀 خواندن مجدد", callback_data=f"wh_read:{w_id}", style="primary", icon_custom_emoji_id="5843493805835165294")],
                [InlineKeyboardButton("⚠️ حذف نجوا", callback_data=f"wh_del:{w_id}", style="danger", icon_custom_emoji_id="6086969407286808660")],
                [InlineKeyboardButton("🤝 پاسخ به نجوا", switch_inline_query_current_chat=f"@{w_data['sender_username']} " if w_data.get('sender_username') else f"{w_data['sender_id']} ", style="success", icon_custom_emoji_id="6294041016261414265")]
            ])

            try:
                await query.edit_message_text(edited_text, reply_markup=new_kb, parse_mode=ParseMode.HTML)
            except Exception:
                pass
        return

    elif data.startswith("wh_del:"):
        w_id = data.replace("wh_del:", "")
        whispers = db.get("whispers", {})

        if w_id not in whispers:
            await query.answer("❌ این نجوا قبلاً حذف شده است!", show_alert=True)
            return

        w_data = whispers[w_id]
        if query.from_user.id != w_data["sender_id"]:
            await query.answer("شما نمی‌توانید نجوای دیگران را حذف کنید.", show_alert=True)
            return

        del whispers[w_id]
        mark_db_dirty()
        save_db(force=True)

        await query.answer("❗️ نجوای شما با موفقیت حذف شد.", show_alert=True)

        try:
            del_text = '<b><tg-emoji emoji-id="5818716826699307883">❗️</tg-emoji> این نجوا توسط فرستنده حذف گردید.</b>'
            await query.edit_message_text(del_text, reply_markup=None, parse_mode=ParseMode.HTML)
        except Exception:
            pass
        return  

    elif data.startswith("tgl_srv_lock:"):
        parts = data.split(":")
        cid = int(parts[1])
        lock_key = parts[2]

        if not await is_admin_or_owner(context, cid, user_id):
            await query.answer("❌ دسترسی غیرمجاز!", show_alert=True)
            return

        g_data = get_group_data(db, cid)
        locks = g_data.setdefault("locks", get_default_locks_structure())
        locks[lock_key] = not locks.get(lock_key, False)
        
        status_word = "فعال" if locks[lock_key] else "غیرفعال"
        lock_fa_name = ALL_LOCKS.get(lock_key, {}).get("name", lock_key)

        log_admin_action(db, user_id, query.from_user.full_name, g_data.get("title", ""), cid, f"تغییر {lock_fa_name}", f"وضعیت جدید: {status_word}")
        mark_db_dirty()
        save_db(force=True)

        alert_msg = f"{lock_fa_name} با موفقیت {status_word} شد!"
        await query.answer(alert_msg, show_alert=False)
        await render_telegram_service_locks_panel(query, cid)
        return

    elif data.startswith("tgl_lock:"):
        parts = data.split(":")
        cid = int(parts[1])
        lock_key = parts[2]
        page = int(parts[3]) if len(parts) > 3 else 1

        if not await is_admin_or_owner(context, cid, user_id):
            await query.answer("❌ دسترسی غیرمجاز!", show_alert=True)
            return

        g_data = get_group_data(db, cid)
        locks = g_data.setdefault("locks", get_default_locks_structure())
        locks[lock_key] = not locks.get(lock_key, False)
        
        status_word = "فعال" if locks[lock_key] else "غیرفعال"
        lock_fa_name = ALL_LOCKS.get(lock_key, {}).get("name", lock_key)

        log_admin_action(db, user_id, query.from_user.full_name, g_data.get("title", ""), cid, f"تغییر قفل {lock_fa_name}", f"وضعیت جدید: {status_word}")
        mark_db_dirty()
        save_db(force=True)

        alert_msg = f"قفل {lock_fa_name} با موفقیت {status_word} شد!"
        await query.answer(alert_msg, show_alert=False)
        await render_group_locks_panel(query, cid, page)
        return

    # SHUTDOWN MENU
    elif data == "panel_shutdown_menu":
        if int(user_id) != int(OWNER_ID):
            await query.answer("❌ دسترسی غیرمجاز! فقط مالک کل.", show_alert=True)
            return
        await render_shutdown_panel(query, db)
        return

    elif data == "bot_do_turn_on":
        if int(user_id) != int(OWNER_ID):
            await query.answer("❌ دسترسی غیرمجاز! فقط مالک کل.", show_alert=True)
            return
        db["bot_shutdown"] = False
        mark_db_dirty()
        save_db(force=True)
        await query.answer("ربات با موفقیت روشن شد! 🟢", show_alert=True)
        await render_shutdown_panel(query, db)
        return

    elif data == "bot_do_shutdown":
        if int(user_id) != int(OWNER_ID):
            await query.answer("❌ دسترسی غیرمجاز! فقط مالک کل.", show_alert=True)
            return
        db["states"]["waiting_shutdown_msg"] = {str(user_id): current_chat_id}
        mark_db_dirty()
        save_db()
        kb = InlineKeyboardMarkup([[InlineKeyboardButton("❌ لغو", callback_data="cancel_current_flow", style="danger")]])
        await query.message.edit_text("<b>پیام خاموشی را ارسال کنید:</b>\n\n(متن، عکس، گیف، ویدیو، استیکر و... ذخیره می‌شود)", reply_markup=kb, parse_mode=ParseMode.HTML)
        return

    # USER BAN & UNBAN
    elif data == "ban_user_start":
        if int(user_id) != int(OWNER_ID):
            await query.answer("❌ فقط مالک کل.", show_alert=True)
            return
        clear_user_all_states(db, user_id, current_chat_id)
        db["states"].setdefault("ban_flow", {})[session_k] = {"step": "ban_user_id"}
        mark_db_dirty()
        save_db()
        kb = InlineKeyboardMarkup([[InlineKeyboardButton("❌ لغو", callback_data="cancel_current_flow", style="danger")]])
        await query.message.edit_text("لطفاً آیدی عددی کاربر را ارسال کنید:", reply_markup=kb)
        return

    elif data == "unban_user_start":
        if int(user_id) != int(OWNER_ID):
            await query.answer("❌ فقط مالک کل.", show_alert=True)
            return
        clear_user_all_states(db, user_id, current_chat_id)
        db["states"].setdefault("ban_flow", {})[session_k] = {"step": "unban_user_id"}
        mark_db_dirty()
        save_db()
        kb = InlineKeyboardMarkup([[InlineKeyboardButton("❌ لغو", callback_data="cancel_current_flow", style="danger")]])
        await query.message.edit_text("لطفاً آیدی عددی کاربری که می‌خواهید انبن شود را ارسال کنید:", reply_markup=kb)
        return

    elif data.startswith("ban_group_list_"):
        if int(user_id) != int(OWNER_ID):
            await query.answer("❌ فقط مالک کل.", show_alert=True)
            return
        page = int(data.replace("ban_group_list_", ""))
        await render_ban_group_picker(query, page, db)
        return

    elif data.startswith("unban_group_list_"):
        if int(user_id) != int(OWNER_ID):
            await query.answer("❌ فقط مالک کل.", show_alert=True)
            return
        page = int(data.replace("unban_group_list_", ""))
        await render_unban_group_picker(query, page, db)
        return

    elif data.startswith("select_bangrp:"):
        if int(user_id) != int(OWNER_ID):
            await query.answer("❌ دسترسی غیرمجاز!", show_alert=True)
            return
        target_cid = int(data.replace("select_bangrp:", ""))
        clear_user_all_states(db, user_id, current_chat_id)
        db["states"].setdefault("ban_flow", {})[session_k] = {
            "step": "ban_group_reason",
            "target_cid": target_cid
        }
        mark_db_dirty()
        save_db()
        g_data = get_group_data(db, target_cid)
        title = g_data.get("title") or str(target_cid)
        kb = InlineKeyboardMarkup([[InlineKeyboardButton("❌ لغو", callback_data="cancel_current_flow", style="danger")]])
        await query.message.edit_text(f"گروه <b>{html.escape(title)}</b> انتخاب شد.\n\nدلیل بن گروه را وارد کنید:", reply_markup=kb, parse_mode=ParseMode.HTML)
        return

    elif data.startswith("select_unbangrp:"):
        if int(user_id) != int(OWNER_ID):
            await query.answer("❌ دسترسی غیرمجاز!", show_alert=True)
            return
        target_cid_str = data.replace("select_unbangrp:", "")
        if target_cid_str in db.get("global_group_bans", {}):
            del db["global_group_bans"][target_cid_str]
            mark_db_dirty()
            save_db(force=True)
            await send_premium_unban_notification(context.bot, int(target_cid_str), is_group=True)
            await query.answer("بن گروه برداشته شد! 🟢", show_alert=True)
        else:
            await query.answer("این گروه بن نیست.", show_alert=True)
        await render_unban_group_picker(query, 1, db)
        return

    elif data == "owner_fun_named":
        if int(user_id) != int(OWNER_ID):
            await query.answer("❌ دسترسی غیرمجاز!", show_alert=True)
            return
        await render_owner_fun_panel(query, "named", db)
        return

    elif data == "owner_fun_normal":
        if int(user_id) != int(OWNER_ID):
            await query.answer("❌ دسترسی غیرمجاز!", show_alert=True)
            return
        await render_owner_fun_panel(query, "normal", db)
        return

    elif data.startswith("own_fun_add:"):
        if int(user_id) != int(OWNER_ID):
            await query.answer("❌ دسترسی غیرمجاز!", show_alert=True)
            return
        fun_type = data.split(":")[1]
        state_key = "waiting_fun_named_msg" if fun_type == "named" else "waiting_fun_normal_msg"
        db["states"][state_key] = {str(user_id): "global"}
        mark_db_dirty()
        save_db()
        title = "ناموسی" if fun_type == "named" else "عادی"
        kb = InlineKeyboardMarkup([[InlineKeyboardButton("✅ دان", callback_data=f"own_fun_done:{fun_type}", style="success")]])
        await query.message.edit_text(f"➕ لطفاً پاسخ‌های فحش {title} سراسری را بفرستید:\n\nدر پایان «✅ دان» را بزنید.", reply_markup=kb, parse_mode=ParseMode.HTML)
        return

    elif data.startswith("own_fun_done:"):
        fun_type = data.split(":")[1]
        state_key = "waiting_fun_named_msg" if fun_type == "named" else "waiting_fun_normal_msg"
        if str(user_id) in db["states"].get(state_key, {}):
            del db["states"][state_key][str(user_id)]
            mark_db_dirty()
            save_db(force=True)
        await query.answer("تنظیم پاسخ‌ها ذخیره شد.", show_alert=True)
        await render_owner_fun_panel(query, fun_type, db)
        return

    elif data.startswith("own_fun_del_all:"):
        if int(user_id) != int(OWNER_ID):
            await query.answer("❌ دسترسی غیرمجاز!", show_alert=True)
            return
        fun_type = data.split(":")[1]
        key = "global_fun_named" if fun_type == "named" else "global_fun_normal"
        db[key] = []
        mark_db_dirty()
        save_db(force=True)
        await query.answer("تمام پاسخ‌های این بخش حذف شدند.", show_alert=True)
        await render_owner_fun_panel(query, fun_type, db)
        return

    elif data == "cancel_current_flow":
        clear_user_all_states(db, user_id, current_chat_id)
        await query.answer("عملیات به طور کامل لغو شد. ❌", show_alert=True)
        await edit_owner_panel_message(query)
        return

    elif data.startswith("panel_owner_groups_"):
        if int(user_id) != int(OWNER_ID):
            await query.answer("❌ دسترسی غیرمجاز! فقط مالک کل.", show_alert=True)
            return
        page = int(data.split("_")[-1])
        await render_owner_groups_page(query, page, db, context)
        return

    elif data.startswith("ogrp_view:"):
        if int(user_id) != int(OWNER_ID):
            await query.answer("❌ دسترسی غیرمجاز!", show_alert=True)
            return
        target_cid = int(data.replace("ogrp_view:", ""))
        await render_owner_single_group_panel(query, target_cid, db, context)
        return

    elif data.startswith("ogrp_link:"):
        if int(user_id) != int(OWNER_ID):
            await query.answer("❌ دسترسی غیرمجاز!", show_alert=True)
            return
        target_cid = int(data.replace("ogrp_link:", ""))
        invite_link = None
        try:
            bot_member = await context.bot.get_chat_member(target_cid, context.bot.id)
            if bot_member.status == ChatMemberStatus.ADMINISTRATOR:
                invite_link = await context.bot.export_chat_invite_link(target_cid)
        except Exception:
            pass

        if not invite_link:
            g_data = get_group_data(db, target_cid)
            invite_link = g_data.get("invite_link")

        if invite_link:
            await query.message.reply_text(f"🔗 <b>لینک گروه:</b>\n{invite_link}", parse_mode=ParseMode.HTML)
        else:
            await query.message.reply_text(
                f'<b><tg-emoji emoji-id="{CROSS_CUSTOM_EMOJI_ID}">❌</tg-emoji> ربات دسترسی ساخت لینک در گروه را ندارد یا ذخیره نشده است.</b>',
                parse_mode=ParseMode.HTML
            )
        await query.answer()
        return

    elif data.startswith("ogrp_admins:"):
        if int(user_id) != int(OWNER_ID):
            await query.answer("❌ دسترسی غیرمجاز!", show_alert=True)
            return
        target_cid = int(data.replace("ogrp_admins:", ""))
        g_data = get_group_data(db, target_cid)
        title = g_data.get("title", "گروه")

        report_lines = [
            "GROUP ADMINS",
            "============",
            f"Group: {title}",
            f"Chat ID: {target_cid}",
            ""
        ]

        try:
            admins = await context.bot.get_chat_administrators(target_cid)
            for idx, a in enumerate(admins, 1):
                report_lines.append(f"{idx}.")
                report_lines.append(f"Name: {a.user.full_name}")
                report_lines.append(f"Username: @{a.user.username}" if a.user.username else "Username: None")
                report_lines.append(f"ID: {a.user.id}")
                report_lines.append(f"Status: {a.status}")
                report_lines.append(f"Custom Title: {a.custom_title or 'None'}")
                report_lines.append("")
        except Exception as e:
            report_lines.append(f"Error fetching administrators: {e}")

        report_content = "\n".join(report_lines)
        file_bytes = io.BytesIO(report_content.encode("utf-8"))
        file_bytes.name = f"admins_{target_cid}.txt"
        await query.message.reply_document(document=file_bytes, caption=f"👮 گزارش لیست ادمین‌های گروه <code>{target_cid}</code>", parse_mode=ParseMode.HTML)
        await query.answer()
        return

    elif data.startswith("ogrp_members:"):
        if int(user_id) != int(OWNER_ID):
            await query.answer("❌ دسترسی غیرمجاز!", show_alert=True)
            return
        target_cid = int(data.replace("ogrp_members:", ""))
        g_data = get_group_data(db, target_cid)
        title = g_data.get("title", "گروه")

        member_count = "نامشخص"
        try:
            member_count = await context.bot.get_chat_member_count(target_cid)
        except Exception:
            pass

        report_lines = [
            "GROUP INFO",
            "==========",
            f"Title: {title}",
            f"Chat ID: {target_cid}",
            f"Member Count: {member_count}",
            "",
            "MEMBERS (Discovered in Database Cache)",
            "=====================================",
            ""
        ]

        active_users = db.get("recent_active_users", {}).get(str(target_cid), [])
        for idx, (uid_str, info) in enumerate(active_users, 1):
            report_lines.append(f"{idx}.")
            report_lines.append(f"Name: {info.get('fullname')}")
            report_lines.append(f"Username: @{info.get('username')}" if info.get("username") else "Username: None")
            report_lines.append(f"ID: {uid_str}")
            report_lines.append("Status: Active/Member")
            report_lines.append("")

        report_content = "\n".join(report_lines)
        file_bytes = io.BytesIO(report_content.encode("utf-8"))
        file_bytes.name = f"members_{target_cid}.txt"
        await query.message.reply_document(document=file_bytes, caption=f"👥 گزارش اعضای در دسترس گروه <code>{target_cid}</code>", parse_mode=ParseMode.HTML)
        await query.answer()
        return

    elif data.startswith("ogrp_search:"):
        if int(user_id) != int(OWNER_ID):
            await query.answer("❌ دسترسی غیرمجاز!", show_alert=True)
            return
        target_cid = int(data.replace("ogrp_search:", ""))
        db["states"]["waiting_search_query"][str(user_id)] = target_cid
        mark_db_dirty()
        save_db()
        kb = InlineKeyboardMarkup([[InlineKeyboardButton("❌ لغو", callback_data="cancel_current_flow", style="danger")]])
        await query.message.edit_text("🔎 <b>کلمه یا عبارت موردنظر برای جستجو در لاگ‌های این گروه را ارسال کنید:</b>", reply_markup=kb, parse_mode=ParseMode.HTML)
        return

    elif data == "panel_bcast_type_select":
        if int(user_id) != int(OWNER_ID):
            await query.answer("این بخش مخصوص مالک اصلی است.", show_alert=True)
            return
        buttons = [
            [InlineKeyboardButton("📝 پیام متنی یا رسانه", callback_data="bcast_mode:media", style="primary")],
            [InlineKeyboardButton("📊 نظرسنجی معمولی (Poll)", callback_data="bcast_mode:poll", style="primary")],
            [InlineKeyboardButton("🎯 کوئیز (Quiz Poll)", callback_data="bcast_mode:quiz", style="primary")],
            [InlineKeyboardButton("🔙 بازگشت", callback_data="panel_owner_main", style="primary")]
        ]
        await query.message.edit_text("📢 <b>نوع پیام همگانی (Broadcast) را انتخاب کنید:</b>", reply_markup=InlineKeyboardMarkup(buttons), parse_mode=ParseMode.HTML)
        return

    elif data.startswith("bcast_mode:"):
        if int(user_id) != int(OWNER_ID):
            await query.answer("این بخش مخصوص مالک اصلی است.", show_alert=True)
            return
        mode = data.replace("bcast_mode:", "")
        db["states"]["broadcast_builder"][str(user_id)] = {"mode": mode, "step": "dest"}
        mark_db_dirty()
        save_db()

        buttons = [
            [InlineKeyboardButton("👥 تمام گروه‌ها", callback_data="bcast_dest:groups", style="primary")],
            [InlineKeyboardButton("👤 تمام کاربران خصوصی", callback_data="bcast_dest:users", style="primary")],
            [InlineKeyboardButton("🌐 همه (گروه‌ها + کاربران)", callback_data="bcast_dest:all", style="success")],
            [InlineKeyboardButton("🔙 بازگشت", callback_data="panel_bcast_type_select", style="danger")]
        ]
        await query.message.edit_text("🎯 <b>مقصد ارسال پیام همگانی را انتخاب کنید:</b>", reply_markup=InlineKeyboardMarkup(buttons), parse_mode=ParseMode.HTML)
        return

    elif data.startswith("bcast_dest:"):
        if int(user_id) != int(OWNER_ID):
            await query.answer("این بخش مخصوص مالک اصلی است.", show_alert=True)
            return
        dest = data.replace("bcast_dest:", "")
        builder = db["states"]["broadcast_builder"].setdefault(str(user_id), {})
        builder["dest"] = dest
        builder["step"] = "content"
        mark_db_dirty()
        save_db()

        kb = InlineKeyboardMarkup([[InlineKeyboardButton("❌ لغو", callback_data="cancel_current_flow", style="danger")]])
        mode = builder.get("mode", "media")
        if mode == "media":
            await query.message.edit_text("✉️ <b>لطفاً متن، عکس، GIF، ویدیو، استیکر یا فایل موردنظر را بفرستید:</b>", reply_markup=kb, parse_mode=ParseMode.HTML)
        elif mode == "poll":
            await query.message.edit_text("📊 <b>لطفاً نظرسنجی موردنظر را ارسال کنید:</b>\n\n<code>سؤال\nگزینه 1\nگزینه 2</code>", reply_markup=kb, parse_mode=ParseMode.HTML)
        elif mode == "quiz":
            await query.message.edit_text("🎯 <b>لطفاً کوئیز را به صورت زیر ارسال کنید:</b>\n\n<code>سؤال\nگزینه 1\nگزینه 2\nصحیح: 1</code>", reply_markup=kb, parse_mode=ParseMode.HTML)
        return

    elif data == "bcast_confirm_send":
        if int(user_id) != int(OWNER_ID):
            await query.answer("این بخش مخصوص مالک اصلی است.", show_alert=True)
            return
        builder = db["states"]["broadcast_builder"].get(str(user_id))
        if not builder:
            await query.answer("اطلاعات ارسال یافت نشد.", show_alert=True)
            return

        del db["states"]["broadcast_builder"][str(user_id)]
        mark_db_dirty()
        save_db()

        status_msg = await query.message.reply_text("⏳ <b>شروع عملیات ارسال همگانی...</b>", parse_mode=ParseMode.HTML)
        dest = builder.get("dest", "groups")
        targets = []
        if dest in ["groups", "all"]:
            targets.extend(db.get("active_chats", []))
        if dest in ["users", "all"]:
            targets.extend([int(u) for u in db.get("started_users", {}).keys()])

        succ, fail = 0, 0
        b_type = builder.get("type")

        for tid in targets:
            try:
                if b_type == "poll":
                    p_data = builder["poll_data"]
                    await context.bot.send_poll(
                        chat_id=tid,
                        question=p_data["question"],
                        options=p_data["options"],
                        is_anonymous=p_data.get("is_anonymous", True),
                        type=PollType.QUIZ if p_data.get("is_quiz") else PollType.REGULAR,
                        correct_option_id=p_data.get("correct_option_id")
                    )
                elif b_type == "media":
                    await send_media_payload(context.bot, tid, builder["payload"])
                succ += 1
                await asyncio.sleep(0.04)
            except Exception:
                fail += 1

        await status_msg.edit_text(f"📢 <b>عملیات ارسال همگانی به پایان رسید.</b>\n\n✅ ارسال موفق: <code>{succ}</code>\n❌ ناموفق: <code>{fail}</code>", parse_mode=ParseMode.HTML)
        await query.answer()
        return

    elif data == "bcast_cancel":
        if int(user_id) != int(OWNER_ID):
            await query.answer("این بخش مخصوص مالک اصلی است.", show_alert=True)
            return
        clear_user_all_states(db, user_id, current_chat_id)
        await query.message.edit_text(
            f'<b><tg-emoji emoji-id="{CROSS_CUSTOM_EMOJI_ID}">❌</tg-emoji> عملیات ارسال همگانی لغو شد.</b>',
            parse_mode=ParseMode.HTML
        )
        return

    # GROUP ADMIN ADVANCED
    elif data.startswith("panel_group_main:"):
        cid = int(data.replace("panel_group_main:", ""))
        if not await is_admin_or_owner(context, cid, user_id):
            await query.answer("❌ دسترسی غیرمجاز!", show_alert=True)
            return
        await render_group_admin_panel_message(query, cid)
        return

    elif data.startswith("panel_group_advanced:"):
        cid = int(data.replace("panel_group_advanced:", ""))
        if not await is_admin_or_owner(context, cid, user_id):
            await query.answer("❌ دسترسی غیرمجاز!", show_alert=True)
            return
        
        text = get_advanced_status_text(db, cid)
        buttons = [
            [
                InlineKeyboardButton("تایید هویت", callback_data=f"advanced_identity:{cid}", style="primary", icon_custom_emoji_id="5231012545799666522"),
                InlineKeyboardButton("ضد خیانت", callback_data=f"advanced_anti_betrayal:{cid}", style="primary", icon_custom_emoji_id="5872792857252733333")
            ],
            [
                InlineKeyboardButton("عضویت اجباری", callback_data=f"advanced_forced_membership:{cid}", style="primary", icon_custom_emoji_id="6084584811379299518"),
                InlineKeyboardButton("خوش آمد", callback_data=f"advanced_welcome:{cid}", style="primary", icon_custom_emoji_id="5443038326535759644")
            ],
            [
                InlineKeyboardButton("تنظیم اخطار", callback_data=f"advanced_warnings:{cid}", style="primary", icon_custom_emoji_id="5420323339723881652"),
                InlineKeyboardButton("سخت‌گیرانه", callback_data=f"advanced_strict:{cid}", style="primary", icon_custom_emoji_id="5825563515670242868")
            ],
            [
                InlineKeyboardButton("ضد تبچی", callback_data=f"advanced_anti_cheat:{cid}", style="primary", icon_custom_emoji_id="5856986522904959860"),
                InlineKeyboardButton("پیام‌ رگباری", callback_data=f"advanced_burst_messages:{cid}", style="primary", icon_custom_emoji_id="5859215993183674044")
            ],
            [
                InlineKeyboardButton("قفل خودکار", callback_data=f"advanced_auto_lock:{cid}", style="primary", icon_custom_emoji_id="5886328760218688328"),
                InlineKeyboardButton("اختیارات گروه", callback_data=f"advanced_group_permissions:{cid}", style="primary", icon_custom_emoji_id="5901989641204018165")
            ],
            [
                InlineKeyboardButton("پاکسازی گروه", callback_data=f"advanced_cleanup:{cid}", style="primary", icon_custom_emoji_id="5458382591121964689"),
                InlineKeyboardButton("قفل امکانات", callback_data=f"advanced_feature_locks:{cid}", style="primary", icon_custom_emoji_id="5296369303661067030")
            ],
            [
                InlineKeyboardButton("خداحافظی", callback_data=f"advanced_goodbye:{cid}", style="primary", icon_custom_emoji_id="5904279000506704761")
            ],
            [
                InlineKeyboardButton("بازگشت", callback_data=f"panel_group_main:{cid}", style="danger", icon_custom_emoji_id="5983093054842606366")
            ]
        ]
        await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(buttons), parse_mode=ParseMode.HTML)
        return

    elif data.startswith("advanced_"):
        await query.answer("COMING SOON...!", show_alert=True)
        return

    elif data.startswith("panel_group_lists:"):
        cid = int(data.replace("panel_group_lists:", ""))
        if not await is_admin_or_owner(context, cid, user_id):
            await query.answer("❌ دسترسی غیرمجاز!", show_alert=True)
            return
        
        g_data = get_group_data(db, cid)
        text = await build_group_lists_status(context, cid, db, g_data)
        
        buttons = [
            [
                InlineKeyboardButton("مالکین", callback_data=f"list_owners:{cid}", style="primary", icon_custom_emoji_id="6060078591276749279"),
                InlineKeyboardButton("مدیران", callback_data=f"list_admins:{cid}", style="primary", icon_custom_emoji_id="6057831537401925660")
            ],
            [
                InlineKeyboardButton("اعضای ویژه", callback_data=f"list_special:{cid}", style="primary", icon_custom_emoji_id="6294080753298837622"),
                InlineKeyboardButton("کلمات فیلتر", callback_data=f"list_filters:{cid}", style="primary", icon_custom_emoji_id="6086622219310470226")
            ],
            [
                InlineKeyboardButton("سکوت‌ شده‌ها", callback_data=f"list_muted:{cid}", style="primary", icon_custom_emoji_id="5886328760218688328"),
                InlineKeyboardButton("بن‌شده‌ها", callback_data=f"list_banned:{cid}", style="primary", icon_custom_emoji_id="5872823922751185495")
            ],
            [
                InlineKeyboardButton("لیست معاف", callback_data=f"list_exempt:{cid}", style="primary", icon_custom_emoji_id="5884078304729767721"),
                InlineKeyboardButton("لیست اخطار", callback_data=f"list_warns:{cid}", style="primary", icon_custom_emoji_id="5911318301580991657")
            ],
            [
                InlineKeyboardButton("پاسخ‌دهی خودکار", callback_data=f"list_auto_resp:{cid}", style="primary", icon_custom_emoji_id="5859316800361077930"),
                InlineKeyboardButton("کامنت‌گذاری", callback_data=f"list_comments:{cid}", style="primary", icon_custom_emoji_id="5908745251098473369")
            ],
            [
                InlineKeyboardButton("بازگشت", callback_data=f"panel_group_main:{cid}", style="danger", icon_custom_emoji_id="5983093054842606366")
            ]
        ]
        await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(buttons), parse_mode=ParseMode.HTML)
        return

    elif data.startswith(("list_owners:", "list_admins:", "list_special:", "list_filters:", "list_muted:", "list_banned:", "list_exempt:", "list_warns:", "list_auto_resp:", "list_comments:")):
        await query.answer("COMING SOON...!", show_alert=True)
        return    

    elif data.startswith("panel_list_poems:"):
        cid = int(data.replace("panel_list_poems:", ""))
        if not await is_admin_or_owner(context, cid, user_id):
            await query.answer("❌ دسترسی غیرمجاز!", show_alert=True)
            return
        g_data = get_group_data(db, cid)
        poems_list = g_data.get("poems", [])
        if not poems_list:
            text = "📭 <b>هنوز شعری برای این گروه ثبت نشده است.</b>"
        else:
            text = "📢 <b>لیست شعارهای فعال این گروه:</b>\n\n"
            for idx, p in enumerate(poems_list, 1):
                clean_p = html.escape(p).replace("{name}", "نام‌کاربر")
                text += f"{idx}. {clean_p}\n"

        buttons = [[InlineKeyboardButton("🔙 بازگشت", callback_data=f"panel_group_lists:{cid}", style="primary")]]
        await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(buttons), parse_mode=ParseMode.HTML)
        return

    elif data.startswith("panel_list_foods:"):
        cid = int(data.replace("panel_list_foods:", ""))
        if not await is_admin_or_owner(context, cid, user_id):
            await query.answer("❌ دسترسی غیرمجاز!", show_alert=True)
            return
        g_data = get_group_data(db, cid)
        foods = g_data.get("foods", [])
        text = "🍽 <b>لیست غذاهای ذخیره‌شده گروه:</b>\n\n" + ", ".join(foods)
        buttons = [[InlineKeyboardButton("🔙 بازگشت", callback_data=f"panel_group_lists:{cid}", style="primary")]]
        await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(buttons), parse_mode=ParseMode.HTML)
        return

    elif data == "owner_list_poems":
        if int(user_id) != int(OWNER_ID):
            await query.answer("❌ دسترسی غیرمجاز!", show_alert=True)
            return
        poems_list = db.get("global_poems", DEFAULT_POEMS)
        if not poems_list:
            text = "📭 <b>هنوز شعری ثبت نشده است.</b>"
        else:
            text = "📢 <b>لیست شعارهای سراسری ربات:</b>\n\n"
            for idx, p in enumerate(poems_list, 1):
                clean_p = html.escape(p).replace("{name}", "نام‌کاربر")
                text += f"{idx}. {clean_p}\n"
        buttons = [[InlineKeyboardButton("🔙 بازگشت", callback_data="panel_owner_main", style="primary")]]
        await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(buttons), parse_mode=ParseMode.HTML)
        return    

    elif data == "owner_list_foods":
        if int(user_id) != int(OWNER_ID):
            await query.answer("❌ دسترسی غیرمجاز!", show_alert=True)
            return
        foods = db.get("global_foods", DEFAULT_FOODS)
        text = "🍽 <b>لیست غذاهای سراسری ربات:</b>\n\n" + ", ".join(foods)
        buttons = [[InlineKeyboardButton("🔙 بازگشت", callback_data="panel_owner_main", style="primary")]]
        await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(buttons), parse_mode=ParseMode.HTML)
        return

    elif data == "owner_add_poem":
        if int(user_id) != int(OWNER_ID):
            await query.answer("❌ دسترسی غیرمجاز!", show_alert=True)
            return
        db["states"]["waiting_owner_add_poem"] = {str(user_id): current_chat_id}
        mark_db_dirty()
        save_db()
        kb = InlineKeyboardMarkup([[InlineKeyboardButton("❌ لغو", callback_data="cancel_current_flow", style="danger")]])
        await query.message.edit_text("➕ شعر جدید سراسری را با استفاده از <code>{name}</code> یا <code>یوزرنیم</code> بفرستید:", reply_markup=kb, parse_mode=ParseMode.HTML)
        return

    elif data == "owner_add_food":
        if int(user_id) != int(OWNER_ID):
            await query.answer("❌ دسترسی غیرمجاز!", show_alert=True, style="danger")
            return
        db["states"]["waiting_owner_add_food"] = {str(user_id): current_chat_id}
        mark_db_dirty()
        save_db()
        kb = InlineKeyboardMarkup([[InlineKeyboardButton("❌ لغو", callback_data="cancel_current_flow", style="danger")]])
        await query.message.edit_text("➕ نام غذای جدید سراسری که می‌خواهید اضافه شود را بنویسید:", reply_markup=kb, parse_mode=ParseMode.HTML)
        return

    elif data == "panel_group_close":
        try:
            close_text = f'• پنل با موفقیت بسته شد! <tg-emoji emoji-id="{PARTY_CUSTOM_EMOJI_ID}">🎉</tg-emoji>'
            await query.message.edit_text(close_text, reply_markup=None, parse_mode=ParseMode.HTML)
        except Exception:
            try:
                await query.message.delete()
            except Exception:
                pass
        await query.answer()
        return

    elif data == "panel_user_broadcast":
        if int(user_id) != int(OWNER_ID):
            await query.answer("این بخش مخصوص مالک اصلی است.", show_alert=True)
            return
        started_users = db.get("started_users", {})
        user_count = len(started_users)
        text = f"📢 <b>پیام همگانی به تمام کاربران خصوصی ربات</b>\n\n👥 <b>تعداد کاربران دریافت‌کننده:</b> <code>{user_count}</code> نفر"
        buttons = [
            [InlineKeyboardButton("✉️ ارسال پیام همگانی", callback_data="user_broadcast_send", style="success")],
            [InlineKeyboardButton("🔙 بازگشت", callback_data="panel_owner_main", style="primary")]
        ]
        await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(buttons), parse_mode=ParseMode.HTML)
        return

    elif data == "user_broadcast_send":
        if int(user_id) != int(OWNER_ID):
            await query.answer("این بخش مخصوص مالک اصلی است.", show_alert=True)
            return
        db["states"]["waiting_user_broadcast_msg"] = {str(user_id): current_chat_id}
        mark_db_dirty()
        save_db()
        kb = InlineKeyboardMarkup([[InlineKeyboardButton("❌ لغو", callback_data="cancel_current_flow", style="danger")]])
        await query.message.edit_text("<b>✉️ پیام مورد نظر برای ارسال به تمام کاربران خصوصی ربات را بفرستید:</b>", reply_markup=kb, parse_mode=ParseMode.HTML)
        return

    elif data.startswith("panel_comment:"):
        cid = int(data.replace("panel_comment:", ""))
        if not await is_admin_or_owner(context, cid, user_id):
            await query.answer("❌ دسترسی غیرمجاز!", show_alert=True)
            return
        await render_comment_panel_message(query, cid, db)
        return

    elif data.startswith("comment_toggle:"):
        cid = int(data.replace("comment_toggle:", ""))
        if not await is_admin_or_owner(context, cid, user_id):
            await query.answer("❌ دسترسی غیرمجاز!", show_alert=True)
            return
        g_data = get_group_data(db, cid)
        c_set = g_data.setdefault("comment", {"enabled": False, "custom": False})
        c_set["enabled"] = not c_set.get("enabled", False)
        log_admin_action(db, user_id, query.from_user.full_name, g_data.get("title", ""), cid, "تغییر کامنت", f"وضعیت: {c_set['enabled']}")
        mark_db_dirty()
        save_db()
        await render_comment_panel_message(query, cid, db)
        return

    elif data.startswith("comment_set:"):
        cid = int(data.replace("comment_set:", ""))
        if not await is_admin_or_owner(context, cid, user_id):
            await query.answer("❌ دسترسی غیرمجاز!", show_alert=True)
            return
        db["states"]["waiting_comment_msg"][str(user_id)] = cid
        mark_db_dirty()
        save_db()
        kb = InlineKeyboardMarkup([[InlineKeyboardButton("❌ لغو", callback_data="cancel_current_flow", style="danger")]])
        await query.message.edit_text("<b>💬 پیام یا مدیایی که می‌خواهید زیر پست‌های کانال قرار گیرد بفرستید:</b>", reply_markup=kb, parse_mode=ParseMode.HTML)
        return

    elif data.startswith("comment_delete:"):
        cid = int(data.replace("comment_delete:", ""))
        if not await is_admin_or_owner(context, cid, user_id):
            await query.answer("❌ دسترسی غیرمجاز!", show_alert=True)
            return
        g_data = get_group_data(db, cid)
        g_data["comment"] = {"enabled": False, "custom": False}
        mark_db_dirty()
        save_db()
        await query.answer("کامنت ذخیره‌شده این گروه حذف شد.", show_alert=True)
        await render_comment_panel_message(query, cid, db)
        return

    elif data.startswith("panel_welcome:"):
        cid = int(data.replace("panel_welcome:", ""))
        if not await is_admin_or_owner(context, cid, user_id):
            await query.answer("❌ دسترسی غیرمجاز!", show_alert=True)
            return
        await render_welcome_panel_message(query, cid, db)
        return

    elif data.startswith("welcome_toggle:"):
        cid = int(data.replace("welcome_toggle:", ""))
        if not await is_admin_or_owner(context, cid, user_id):
            await query.answer("❌ دسترسی غیرمجاز!", show_alert=True)
            return
        g_data = get_group_data(db, cid)
        w_set = g_data.setdefault("welcome", {"enabled": True, "custom": False})
        w_set["enabled"] = not w_set.get("enabled", True)
        log_admin_action(db, user_id, query.from_user.full_name, g_data.get("title", ""), cid, "تغییر Welcome", f"وضعیت: {w_set['enabled']}")
        mark_db_dirty()
        save_db()
        await render_welcome_panel_message(query, cid, db)
        return

    elif data.startswith("welcome_set:"):
        cid = int(data.replace("welcome_set:", ""))
        if not await is_admin_or_owner(context, cid, user_id):
            await query.answer("❌ دسترسی غیرمجاز!", show_alert=True)
            return
        db["states"]["waiting_welcome_msg"][str(user_id)] = cid
        mark_db_dirty()
        save_db()
        prompt_text = (
            "<b>👋 تنظیم پیام خوش‌آمدگویی اختصاصی گروه:</b>\n\n"
            "لطفاً پیام یا مدیای خوش‌آمدگویی جدید را ارسال کنید.\n"
            "متغیرها: <code>USERNAME</code> | <code>XXXX</code> | <code>TIME</code> | <code>DAY</code>"
        )
        kb = InlineKeyboardMarkup([[InlineKeyboardButton("❌ لغو", callback_data="cancel_current_flow", style="danger")]])
        await query.message.edit_text(prompt_text, reply_markup=kb, parse_mode=ParseMode.HTML)
        return

    elif data.startswith("welcome_delete_confirm:"):
        cid = int(data.replace("welcome_delete_confirm:", ""))
        if not await is_admin_or_owner(context, cid, user_id):
            await query.answer("❌ دسترسی غیرمجاز!", show_alert=True)
            return
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("✅ بله، حذف شود", callback_data=f"welcome_delete_do:{cid}", style="danger"),
             InlineKeyboardButton("❌ لغو", callback_data=f"panel_welcome:{cid}", style="primary")]
        ])
        await query.message.edit_text("<b>آیا از حذف خوش‌آمد اختصاصی اطمینان دارید؟</b>", reply_markup=kb, parse_mode=ParseMode.HTML)
        return

    elif data.startswith("welcome_delete_do:"):
        cid = int(data.replace("welcome_delete_do:", ""))
        if not await is_admin_or_owner(context, cid, user_id):
            await query.answer("❌ دسترسی غیرمجاز!", show_alert=True)
            return
        g_data = get_group_data(db, cid)
        g_data["welcome"] = {"enabled": True, "custom": False}
        mark_db_dirty()
        save_db()
        await query.answer("پیام اختصاصی حذف شد.", show_alert=True)
        await render_welcome_panel_message(query, cid, db)
        return

    elif data.startswith("panel_foods:"):
        cid = int(data.replace("panel_foods:", ""))
        if not await is_admin_or_owner(context, cid, user_id):
            await query.answer("❌ دسترسی غیرمجاز!", show_alert=True)
            return
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("➕ افزودن غذا", callback_data=f"food_add:{cid}", style="success")],
            [InlineKeyboardButton("➖ حذف غذا", callback_data=f"food_del:{cid}", style="danger")],
            [InlineKeyboardButton("📋 لیست غذاها", callback_data=f"panel_list_foods:{cid}", style="primary")],
            [InlineKeyboardButton("🔙 بازگشت", callback_data=f"panel_group_advanced:{cid}", style="primary")]
        ])
        await query.message.edit_text("🍽 <b>مدیریت غذاهای اختصاصی این گروه</b>", reply_markup=keyboard, parse_mode=ParseMode.HTML)
        return

    elif data.startswith("food_add:"):
        cid = int(data.replace("food_add:", ""))
        if not await is_admin_or_owner(context, cid, user_id):
            await query.answer("❌ دسترسی غیرمجاز!", show_alert=True)
            return
        db["states"]["waiting_add_food"][str(user_id)] = cid
        mark_db_dirty()
        save_db()
        kb = InlineKeyboardMarkup([[InlineKeyboardButton("❌ لغو", callback_data="cancel_current_flow", style="danger")]])
        await query.message.edit_text("➕ نام غذایی که می‌خواهید اضافه شود را بنویسید:", reply_markup=kb)
        return

    elif data.startswith("food_del:"):
        cid = int(data.replace("food_del:", ""))
        if not await is_admin_or_owner(context, cid, user_id):
            await query.answer("❌ دسترسی غیرمجاز!", show_alert=True)
            return
        db["states"]["waiting_del_food"][str(user_id)] = cid
        mark_db_dirty()
        save_db()
        kb = InlineKeyboardMarkup([[InlineKeyboardButton("❌ لغو", callback_data="cancel_current_flow", style="danger")]])
        await query.message.edit_text("➖ نام دقیق غذایی که می‌خواهید حذف شود را بنویسید:", reply_markup=kb)
        return

    elif data.startswith("panel_poem_names:"):
        cid = int(data.replace("panel_poem_names:", ""))
        if not await is_admin_or_owner(context, cid, user_id):
            await query.answer("❌ دسترسی غیرمجاز!", show_alert=True)
            return
        db["states"]["waiting_poem_names"][str(user_id)] = cid
        mark_db_dirty()
        save_db()
        g_data = get_group_data(db, cid)
        current_names = ", ".join(g_data.get("custom_names", [])) or "هیچ اسمی ثبت نشده"
        kb = InlineKeyboardMarkup([[InlineKeyboardButton("✅ دان", callback_data=f"poem_names_done:{cid}", style="success")]])
        await query.message.edit_text(f"📜 <b>اسامی فعلی شعرها در این گروه:</b>\n{current_names}\n\nاسامی جدید را یکی‌یکی بفرستید و در پایان «✅ دان» را بزنید.", reply_markup=kb, parse_mode=ParseMode.HTML)
        return

    elif data.startswith("poem_names_done:"):
        cid = int(data.replace("poem_names_done:", ""))
        if str(user_id) in db["states"].get("waiting_poem_names", {}):
            del db["states"]["waiting_poem_names"][str(user_id)]
            mark_db_dirty()
            save_db(force=True)
        await query.answer("اسامی با موفقیت ذخیره شد.", show_alert=True)
        await render_group_admin_panel_message(query, cid)
        return

    elif data.startswith("panel_add_poem:"):
        cid = int(data.replace("panel_add_poem:", ""))
        if not await is_admin_or_owner(context, cid, user_id):
            await query.answer("❌ دسترسی غیرمجاز!", show_alert=True)
            return
        db["states"]["waiting_add_poem"][str(user_id)] = cid
        mark_db_dirty()
        save_db()
        kb = InlineKeyboardMarkup([[InlineKeyboardButton("❌ لغو", callback_data="cancel_current_flow", style="danger")]])
        await query.message.edit_text("➕ شعر جدید را با <code>{name}</code> یا <code>یوزرنیم</code> بفرستید:", reply_markup=kb, parse_mode=ParseMode.HTML)
        return

    # TIC TAC TOE
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
            txt = (
                '<b><tg-emoji emoji-id="5816739230482701944">⚡️</tg-emoji> میبینم به یکم هیجان نیاز دارین! <tg-emoji emoji-id="5818785846823755322">😻</tg-emoji></b>\n\n'
                '<b>آماده بازی دوز هستین بچهااااا؟ <tg-emoji emoji-id="5818984798298841943">⏳</tg-emoji></b>\n\n'
            )
            if m1_txt:
                txt += f'<b>شرکت کنندگان :</b>\n<b>{m1_txt}</b>\n\n<b>- یک نفر دیگه تموممممه! کسی نبودد؟ <tg-emoji emoji-id="5431776939465516694">🔥</tg-emoji></b>\n'
            txt += '<b>با استفاده از دکمه زیر به دوز بپیوندید :</b>'
            
            kb_list = [
                [InlineKeyboardButton("شرکت", callback_data=f"xo_join:{game_id}", style="success", icon_custom_emoji_id="5889002570633977838")]
            ]
            if m1_txt:
                kb_list[0].append(InlineKeyboardButton("انصراف", callback_data=f"xo_leave:{game_id}", style="danger", icon_custom_emoji_id="5888594273862950655"))
            kb_list.append([InlineKeyboardButton("بیخیال", callback_data=f"xo_cancel:{game_id}", style="danger", icon_custom_emoji_id="5848202125078699135")])

            await query.message.edit_text(txt, reply_markup=InlineKeyboardMarkup(kb_list), parse_mode=ParseMode.HTML)
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

    # REPORTS
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
            txt = f'<b><tg-emoji emoji-id="{CHECK_CUSTOM_EMOJI_ID}">✅</tg-emoji> گزارش شما توسط مدیران بررسی شد.</b>'
            await query.message.edit_text(txt, parse_mode=ParseMode.HTML)
            return

    # SIGN ACTIONS
    elif data.startswith("sign_action:"):
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

    elif data.startswith("stat_action:"):
        rec_id = data.replace("stat_action:", "")
        records = db.get("action_records", {})
        if rec_id in records:
            rec = records[rec_id]
            current_count = get_user_stat(db, rec["target_id"], rec["stat_key"])
            alert_msg = f"📊 آمار ثبت‌شده {rec['action_title']} برای {rec['target_name']}: {current_count} بار"
            await query.answer(alert_msg, show_alert=True)
        else:
            await query.answer("اطلاعات یافت نشد!", show_alert=True)
        return

    # COUPLES / SHIPS (VOTING SYSTEM WITH 30 SECONDS TIMEOUT)
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

    # OWNER MAIN PANEL ACTIONS
    elif data == "panel_owner_main":
        if int(user_id) != int(OWNER_ID):
            await query.answer("این بخش مخصوص مالک اصلی است.", show_alert=True)
            return
        await edit_owner_panel_message(query)
        return

    elif data == "panel_admin_logs":
        if int(user_id) != int(OWNER_ID):
            await query.answer("این بخش مخصوص مالک اصلی است.", show_alert=True)
            return
        await render_admin_logs_panel(query, db)
        return

    elif data == "panel_cooldown":
        if int(user_id) != int(OWNER_ID):
            await query.answer("این بخش مخصوص مالک اصلی است.", show_alert=True)
            return
        db["states"]["waiting_cooldown"][str(user_id)] = current_chat_id
        mark_db_dirty()
        save_db()
        kb = InlineKeyboardMarkup([[InlineKeyboardButton("❌ لغو", callback_data="cancel_current_flow", style="danger")]])
        await query.message.edit_text(f"⏱ زمان فعلی محدودیت: <b>{db.get('cooldown_minutes', 10)} دقیقه</b>\n\nزمان جدید را به دقیقه ارسال کنید:", reply_markup=kb, parse_mode=ParseMode.HTML)
        return

    elif data == "panel_features":
        if int(user_id) != int(OWNER_ID):
            await query.answer("این بخش مخصوص مالک اصلی است.", show_alert=True)
            return
        await render_features_panel_message(query, db)
        return

    elif data.startswith("toggle_"):
        if int(user_id) != int(OWNER_ID):
            await query.answer("این بخش مخصوص مالک اصلی است.", show_alert=True)
            return
        fk = data.replace("toggle_", "")
        if fk in db["features"]:
            db["features"][fk] = not db["features"][fk]
            mark_db_dirty()
            save_db()
        await render_features_panel_message(query, db)
        return

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
        save_db(force=True)
    
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

    if int(user_id) != int(OWNER_ID):
        await update.message.reply_text(
            f'<b><tg-emoji emoji-id="{CROSS_CUSTOM_EMOJI_ID}">❌</tg-emoji> این دستور فقط مخصوص مالک اصلی ربات می‌باشد!</b>',
            parse_mode=ParseMode.HTML
        )
        return
    try:
        await send_owner_panel_message(update, context)
    except Exception:
        logger.exception("OWNER PANEL ERROR:")

async def command_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message:
        return
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    db = load_db()
    
    cleared = clear_user_all_states(db, user_id, chat_id)
    if cleared:
        await update.message.reply_text(
            f'<b><tg-emoji emoji-id="{CROSS_CUSTOM_EMOJI_ID}">❌</tg-emoji> تمام عملیات‌های در حال اجرا برای شما به طور کامل لغو گردید.</b>',
            parse_mode=ParseMode.HTML
        )
    else:
        await update.message.reply_text("ℹ️ شما در هیچ حالت انتظاری قرار ندارید.")

async def command_done(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message:
        return
    user_id = str(update.effective_user.id)
    db = load_db()
    states = db.get("states", {})
    done_anything = False

    if user_id in states.get("waiting_poem_names", {}):
        cid = states["waiting_poem_names"][user_id]
        del states["waiting_poem_names"][user_id]
        g_data = get_group_data(db, cid)
        count = len(g_data.get("custom_names", []))
        await update.message.reply_text(f"✅ تنظیم اسامی به پایان رسید. تعداد کل: <b>{count}</b>", parse_mode=ParseMode.HTML)
        done_anything = True

    if user_id in states.get("waiting_fun_named_msg", {}):
        del states["waiting_fun_named_msg"][user_id]
        count = len(db.get("global_fun_named", []))
        await update.message.reply_text(f"✅ ثبت پاسخ‌های فحش ناموسی سراسری پایان یافت. تعداد: <b>{count}</b>", parse_mode=ParseMode.HTML)
        done_anything = True

    if user_id in states.get("waiting_fun_normal_msg", {}):
        del states["waiting_fun_normal_msg"][user_id]
        count = len(db.get("global_fun_normal", []))
        await update.message.reply_text(f"✅ ثبت پاسخ‌های فحش عادی سراسری پایان یافت. تعداد: <b>{count}</b>", parse_mode=ParseMode.HTML)
        done_anything = True

    if done_anything:
        mark_db_dirty()
        save_db(force=True)
    else:
        await update.message.reply_text("ℹ️ شما در هیچ وضعیت انتظاری نیستید.")

# ==========================================
# MESSAGE HANDLER
# ==========================================
async def handle_messages(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message:
        return

    try:
        db = load_db()
        await register_member(update, db)
        
        chat = update.effective_chat
        is_group = chat and chat.type in ["group", "supergroup"]

        if is_group:
            setup_chat_jobs(context.job_queue, [chat.id])

        user_id = update.effective_user.id
        u_str = str(user_id)
        chat_id = chat.id if chat else 0
        session_k = get_session_key(user_id, chat_id)
        raw_text = update.message.text or update.message.caption or ""
        clean_raw = raw_text.strip().lower()
        norm_text = normalize_text(raw_text)
        
        # --------------------------------------
        # LINK COMMAND HANDLER (GROUP ONLY)
        # --------------------------------------
        if is_group and LINK_COMMAND_PATTERN.match(raw_text):
            if not await is_admin_or_owner(context, chat_id, user_id):
                await update.message.reply_text(
                    f'😐 <b>تو که ادمین نیستی! اجازه ندارم بهت لینک بدم.</b> <tg-emoji emoji-id="5276508228128103199">😐</tg-emoji>',
                    parse_mode=ParseMode.HTML
                )
                return

            if not await check_bot_admin_and_link_rights(context, chat_id):
                await update.message.reply_text(
                    f'😔 <b>متاسفم! من ادمین گروه نیستم یا دسترسی به لینک ندارم.</b>\n'
                    f'<b>لطفا به یکی از ادمین‌ها بگو مشکل رو حل کنن!</b> <tg-emoji emoji-id="5274171963487576924">🌟</tg-emoji>',
                    parse_mode=ParseMode.HTML
                )
                return

            cmd_lower = raw_text.strip().lower()

            if any(k in cmd_lower for k in ["عکس", "به صورت عکس", "رو عکس بفرست"]):
                try:
                    chat_obj = await context.bot.get_chat(chat_id)
                    caption_text = await generate_group_link_text_payload(context, chat_id, is_once=False)
                    if chat_obj.photo and chat_obj.photo.big_file_id:
                        await context.bot.send_photo(chat_id=chat_id, photo=chat_obj.photo.big_file_id, caption=caption_text, parse_mode=ParseMode.HTML)
                    else:
                        await update.message.reply_text(caption_text, parse_mode=ParseMode.HTML)
                except Exception:
                    pass
                return

            elif "یک‌بار" in cmd_lower or "یکبار" in cmd_lower:
                text_payload = await generate_group_link_text_payload(context, chat_id, is_once=True)
                await update.message.reply_text(text_payload, reply_markup=build_link_sub_keyboard(chat_id, is_once=True), parse_mode=ParseMode.HTML)
                return

            elif "پیوی" in cmd_lower or "در پیوی" in cmd_lower:
                try:
                    text_payload = await generate_group_link_text_payload(context, chat_id, is_once=False)
                    await context.bot.send_message(chat_id=user_id, text=text_payload, parse_mode=ParseMode.HTML)
                    await update.message.reply_text("✅ لینک گروه با موفقیت در پیوی شما ارسال شد.", parse_mode=ParseMode.HTML)
                except Exception:
                    await update.message.reply_text("❌ خطا در ارسال لینک به پیوی! لطفاً ابتدا ربات را در پیوی استارت کنید.", parse_mode=ParseMode.HTML)
                return

            else:
                panel_text = f'<tg-emoji emoji-id="6044084382174552276">📊</tg-emoji> <b>نوع لینک را انتخاب کنید:</b>'
                await update.message.reply_text(panel_text, reply_markup=build_link_panel_keyboard(chat_id), parse_mode=ParseMode.HTML)
                return 

        # --------------------------------------
        # 1. TEXT LOCK CONTROL COMMANDS (ADMIN ONLY - IN GROUP)
        # --------------------------------------
        if is_group and await is_admin_or_owner(context, chat_id, user_id):
            clean_cmd = re.sub(r"[!/؟?؛\-_]", "", clean_raw).strip()
            clean_cmd = re.sub(r"\s+", " ", clean_cmd)
            
            match_lock = LOCK_COMMAND_PATTERN.match(clean_cmd)
            if match_lock:
                verb1, target1, target2, _, verb2 = match_lock.groups()
                action_text = (verb1 or verb2 or "").strip()
                raw_target = (target1 or target2 or "").strip()

                if raw_target.startswith("قفل "):
                    raw_target = raw_target[4:].strip()

                lock_action = None
                if action_text in ["قفل", "ببند", "قفل کن"]:
                    lock_action = True
                elif action_text in ["باز کن", "بازکن", "حذف قفل", "بازکردن قفل"]:
                    lock_action = False

                if lock_action is not None and raw_target:
                    lock_key = LOCK_TEXT_ALIASES.get(raw_target)
                    if not lock_key:
                        for k, v in ALL_LOCKS.items():
                            if not v.get("is_category") and raw_target == v["name"]:
                                lock_key = k
                                break

                    if lock_key and lock_key in ALL_LOCKS and not ALL_LOCKS[lock_key].get("is_category"):
                        g_data = get_group_data(db, chat_id)
                        locks = g_data.setdefault("locks", get_default_locks_structure())
                        locks[lock_key] = lock_action
                        mark_db_dirty()
                        save_db(force=True)

                        fa_name = ALL_LOCKS[lock_key]["name"]
                        action_word = "فعال" if lock_action else "غیرفعال"
                        log_admin_action(db, user_id, update.effective_user.full_name, chat.title, chat_id, f"دستور متنی {fa_name}", f"وضعیت: {action_word}")

                        if lock_action:
                            reply_text = f'{fa_name} با موفقیت {action_word} شد! <tg-emoji emoji-id="{CHECK_CUSTOM_EMOJI_ID}">✅</tg-emoji>'
                        else:
                            reply_text = f'{fa_name} با موفقیت {action_word} شد! <tg-emoji emoji-id="{CROSS_CUSTOM_EMOJI_ID}">❌</tg-emoji>'

                        await update.message.reply_text(reply_text, parse_mode=ParseMode.HTML)
                        return

        # --------------------------------------
        # OWNER FLOWS IN PV / SPECIFIC SESSIONS
        # --------------------------------------
        if int(user_id) == int(OWNER_ID):
            ban_flows = db.setdefault("states", {}).setdefault("ban_flow", {})
            
            if session_k in ban_flows:
                flow = ban_flows[session_k]
                step = flow.get("step")

                if step == "ban_user_id":
                    target_uid_str = fa_to_en_digits(raw_text.strip())
                    if not target_uid_str.isdigit():
                        kb = InlineKeyboardMarkup([[InlineKeyboardButton("❌ لغو", callback_data="cancel_current_flow", style="danger")]])
                        await update.message.reply_text(
                            f'<b><tg-emoji emoji-id="{CROSS_CUSTOM_EMOJI_ID}">❌</tg-emoji> لطفاً یک آیدی عددی معتبر ارسال کنید:</b>',
                            reply_markup=kb,
                            parse_mode=ParseMode.HTML
                        )
                        return

                    target_uid = int(target_uid_str)
                    if target_uid == int(OWNER_ID):
                        clear_user_all_states(db, user_id, chat_id)
                        await update.message.reply_text(
                            f'<b><tg-emoji emoji-id="{CROSS_CUSTOM_EMOJI_ID}">❌</tg-emoji> شما نمی‌توانید مالک اصلی ربات را بن کنید!</b>',
                            parse_mode=ParseMode.HTML
                        )
                        return

                    flow["step"] = "ban_user_reason"
                    flow["target_uid"] = target_uid
                    mark_db_dirty()
                    save_db()

                    kb = InlineKeyboardMarkup([[InlineKeyboardButton("❌ لغو", callback_data="cancel_current_flow", style="danger")]])
                    await update.message.reply_text("دلیل بن را ارسال کنید:", reply_markup=kb)
                    return

                elif step == "ban_user_reason":
                    flow["reason"] = raw_text.strip()
                    flow["step"] = "ban_user_duration"
                    mark_db_dirty()
                    save_db()

                    kb = InlineKeyboardMarkup([[InlineKeyboardButton("❌ لغو", callback_data="cancel_current_flow", style="danger")]])
                    await update.message.reply_text(
                        "مدت زمان بن را بر حسب دقیقه وارد کنید.\n"
                        "برای بن دائم بنویسید:\n"
                        "دائم / دائمی / همیشه / همیشگی",
                        reply_markup=kb
                    )
                    return

                elif step == "ban_user_duration":
                    target_uid = flow["target_uid"]
                    reason = flow["reason"]
                    dur_clean = raw_text.strip().lower()
                    perm_triggers = ["دائم", "دائمی", "همیشه", "همیشگی", "permanent", "forever"]

                    now_dt = datetime.now()
                    now_str = now_dt.strftime("%Y-%m-%d %H:%M:%S")

                    if dur_clean in perm_triggers:
                        b_type = "permanent"
                        b_until = None
                        dur_display = "دائم"
                    else:
                        min_str = fa_to_en_digits(dur_clean)
                        try:
                            minutes = int(min_str)
                            if minutes <= 0: minutes = 60
                        except ValueError:
                            minutes = 60
                        b_type = "temporary"
                        b_until = now_dt.timestamp() + (minutes * 60)
                        dur_display = f"{minutes} دقیقه"

                    db["global_bans"][str(target_uid)] = {
                        "type": b_type,
                        "banned_at": now_str,
                        "ban_until": b_until,
                        "reason": reason
                    }

                    clear_user_all_states(db, user_id, chat_id)
                    mark_db_dirty()
                    save_db(force=True)

                    pv_sent = await send_premium_ban_notification(
                        context.bot,
                        target_uid,
                        is_group=False,
                        duration_str=dur_display,
                        reason_str=reason
                    )

                    report_status = "✅ پیام به PV کاربر ارسال شد." if pv_sent else "⚠️ کاربر بن شد ولی ارسال پیام به PV ناموفق بود."
                    await update.message.reply_text(
                        f"🚨 <b>کاربر <code>{target_uid}</code> با موفقیت بن شد.</b>\n"
                        f"⏰ مدت: <b>{dur_display}</b>\n"
                        f"⚙️ دلیل: <b>{html.escape(reason)}</b>\n\n{report_status}",
                        parse_mode=ParseMode.HTML
                    )
                    return

                elif step == "unban_user_id":
                    target_uid_str = fa_to_en_digits(raw_text.strip())
                    clear_user_all_states(db, user_id, chat_id)

                    if target_uid_str not in db.get("global_bans", {}):
                        await update.message.reply_text(
                            f'<b><tg-emoji emoji-id="{CROSS_CUSTOM_EMOJI_ID}">❌</tg-emoji> این کاربر بن نیست.</b>',
                            parse_mode=ParseMode.HTML
                        )
                    else:
                        del db["global_bans"][target_uid_str]
                        mark_db_dirty()
                        save_db(force=True)

                        await send_premium_unban_notification(context.bot, int(target_uid_str), is_group=False)
                        await update.message.reply_text(f"✅ بن کاربر <code>{target_uid_str}</code> با موفقیت برداشته شد.", parse_mode=ParseMode.HTML)
                    return

                elif step == "ban_group_reason":
                    flow["reason"] = raw_text.strip()
                    flow["step"] = "ban_group_duration"
                    mark_db_dirty()
                    save_db()

                    kb = InlineKeyboardMarkup([[InlineKeyboardButton("❌ لغو", callback_data="cancel_current_flow", style="danger")]])
                    await update.message.reply_text(
                        "مدت زمان بن گروه را بر حسب دقیقه وارد کنید.\n"
                        "برای بن دائم بنویسید:\n"
                        "دائم / دائمی / همیشه / همیشگی",
                        reply_markup=kb
                    )
                    return

                elif step == "ban_group_duration":
                    target_cid = flow["target_cid"]
                    reason = flow["reason"]
                    dur_clean = raw_text.strip().lower()
                    perm_triggers = ["دائم", "دائمی", "همیشه", "همیشگی", "permanent", "forever"]

                    now_dt = datetime.now()
                    now_str = now_dt.strftime("%Y-%m-%d %H:%M:%S")

                    if dur_clean in perm_triggers:
                        b_type = "permanent"
                        b_until = None
                        dur_display = "دائم"
                    else:
                        min_str = fa_to_en_digits(dur_clean)
                        try:
                            minutes = int(min_str)
                            if minutes <= 0: minutes = 120
                        except ValueError:
                            minutes = 120
                        b_type = "temporary"
                        b_until = now_dt.timestamp() + (minutes * 60)
                        dur_display = f"{minutes} دقیقه"

                    db["global_group_bans"][str(target_cid)] = {
                        "type": b_type,
                        "banned_at": now_str,
                        "ban_until": b_until,
                        "reason": reason
                    }

                    clear_user_all_states(db, user_id, chat_id)
                    mark_db_dirty()
                    save_db(force=True)

                    await send_premium_ban_notification(context.bot, target_cid, is_group=True, duration_str=dur_display, reason_str=reason)
                    await update.message.reply_text(f"🚨 <b>گروه <code>{target_cid}</code> با موفقیت بن شد.</b>\nمدت: <b>{dur_display}</b>", parse_mode=ParseMode.HTML)
                    return

            if u_str in db["states"].get("waiting_fun_named_msg", {}):
                payload = extract_media_payload(update.message)
                if payload:
                    db.setdefault("global_fun_named", []).append(payload)
                    mark_db_dirty()
                    save_db(force=True)
                    kb = InlineKeyboardMarkup([[InlineKeyboardButton("✅ دان", callback_data="own_fun_done:named", style="success")]])
                    await update.message.reply_text(f"✅ پاسخ فحش ناموسی ذخیره شد (کل: {len(db['global_fun_named'])}).", reply_markup=kb, parse_mode=ParseMode.HTML)
                    return

            if u_str in db["states"].get("waiting_fun_normal_msg", {}):
                payload = extract_media_payload(update.message)
                if payload:
                    db.setdefault("global_fun_normal", []).append(payload)
                    mark_db_dirty()
                    save_db(force=True)
                    kb = InlineKeyboardMarkup([[InlineKeyboardButton("✅ دان", callback_data="own_fun_done:normal", style="success")]])
                    await update.message.reply_text(f"✅ پاسخ فحش عادی ذخیره شد (کل: {len(db['global_fun_normal'])}).", reply_markup=kb, parse_mode=ParseMode.HTML)
                    return

            if u_str in db["states"].get("waiting_shutdown_msg", {}):
                del db["states"]["waiting_shutdown_msg"][u_str]
                db["bot_shutdown"] = True
                payload = extract_media_payload(update.message)
                db["shutdown_message"] = {
                    "from_chat_id": update.effective_chat.id,
                    "message_id": update.message.message_id,
                    "payload": payload
                }
                mark_db_dirty()
                save_db(force=True)
                await update.message.reply_text("🔴 <b>ربات با موفقیت خاموش شد و پیام خاموشی ذخیره گردید.</b>", parse_mode=ParseMode.HTML)
                return

            if u_str in db["states"].get("waiting_cooldown", {}):
                del db["states"]["waiting_cooldown"][u_str]
                try:
                    mins = int(fa_to_en_digits(raw_text.strip()))
                    db["cooldown_minutes"] = mins
                    mark_db_dirty()
                    save_db(force=True)
                    await update.message.reply_text(f"✅ زمان محدودیت (Cooldown) به {mins} دقیقه تغییر یافت.")
                except Exception:
                    await update.message.reply_text(
                        f'<b><tg-emoji emoji-id="{CROSS_CUSTOM_EMOJI_ID}">❌</tg-emoji> مقدار وارد شده نامعتبر است.</b>',
                        parse_mode=ParseMode.HTML
                    )
                return
            
            if u_str in db["states"].get("waiting_owner_add_poem", {}):
                del db["states"]["waiting_owner_add_poem"][u_str]
                if raw_text and not raw_text.startswith("/"):
                    poem_item = raw_text.strip().replace("یوزرنیم", "{name}")
                    p_list = db.setdefault("global_poems", list(DEFAULT_POEMS))
                    p_list.append(poem_item)
                    mark_db_dirty()
                    save_db(force=True)
                    await update.message.reply_text("✅ شعر جدید سراسری با موفقیت اضافه شد.")
                    return

            if u_str in db["states"].get("waiting_owner_add_food", {}):
                del db["states"]["waiting_owner_add_food"][u_str]
                if raw_text and not raw_text.startswith("/"):
                    food_item = raw_text.strip()
                    foods = db.setdefault("global_foods", list(DEFAULT_FOODS))
                    if food_item.lower() not in [f.strip().lower() for f in foods]:
                        foods.append(food_item)
                        mark_db_dirty()
                        save_db(force=True)
                        await update.message.reply_text(f"✅ «{food_item}» به منوی سراسری غذاها اضافه شد.")
                    else:
                        await update.message.reply_text("❌ این غذا از قبل در لیست وجود داشته است.")
                    return

            if u_str in db["states"].get("waiting_search_query", {}):
                target_cid = db["states"]["waiting_search_query"][u_str]
                del db["states"]["waiting_search_query"][u_str]
                mark_db_dirty()
                save_db()

                query_word = raw_text.strip().lower()
                g_data = get_group_data(db, target_cid)
                m_logs = g_data.get("message_logs", [])
                matches = [m for m in m_logs if query_word in m.get("text", "").lower()]

                report_lines = [
                    "SEARCH REPORT",
                    "=============",
                    f"Group: {g_data.get('title', 'Unknown')}",
                    f"Chat ID: {target_cid}",
                    f"Query: {query_word}",
                    f"Total Matched: {len(matches)}",
                    "",
                    "RESULTS",
                    "======="
                ]

                for idx, m in enumerate(matches, 1):
                    report_lines.append(f"{idx}.")
                    report_lines.append(f"Message ID: {m['message_id']}")
                    report_lines.append(f"User: {m['user_name']}")
                    report_lines.append(f"User ID: {m['user_id']}")
                    report_lines.append(f"Date: {m['date']}")
                    report_lines.append(f"Text: {m['text']}")
                    if m.get("media_type") != "text":
                        report_lines.append(f"Media Type: {m['media_type']}")
                        report_lines.append(f"File ID: {m.get('file_id')}")
                    report_lines.append("")

                report_content = "\n".join(report_lines)
                file_bytes = io.BytesIO(report_content.encode("utf-8"))
                file_bytes.name = f"search_{target_cid}.txt"
                await update.message.reply_document(document=file_bytes, caption=f"🔎 نتایج جستجوی <code>{query_word}</code>", parse_mode=ParseMode.HTML)
                return

            if u_str in db["states"].get("broadcast_builder", {}):
                builder = db["states"]["broadcast_builder"][u_str]
                mode = builder.get("mode")

                if mode == "media":
                    payload = extract_media_payload(update.message)
                    if payload:
                        builder["type"] = "media"
                        builder["payload"] = payload
                        kb = InlineKeyboardMarkup([
                            [InlineKeyboardButton("✅ تأیید و ارسال همگانی", callback_data="bcast_confirm_send", style="success")],
                            [InlineKeyboardButton("❌ لغو", callback_data="bcast_cancel", style="danger")]
                        ])
                        await update.message.reply_text("📢 <b>پیش‌نمایش مدیا دریافت شد. آیا برای ارسال تأیید می‌کنید؟</b>", reply_markup=kb, parse_mode=ParseMode.HTML)
                        return

                elif mode in ["poll", "quiz"]:
                    lines = [l.strip() for l in raw_text.strip().split("\n") if l.strip()]
                    if len(lines) < 3:
                        await update.message.reply_text(
                            f'<b><tg-emoji emoji-id="{CROSS_CUSTOM_EMOJI_ID}">❌</tg-emoji> حداقل سؤال و ۲ گزینه الزامی است.</b>',
                            parse_mode=ParseMode.HTML
                        )
                        return

                    question = lines[0]
                    correct_id = 0
                    if mode == "quiz":
                        last_line = lines[-1]
                        if "صحیح:" in last_line:
                            try:
                                correct_id = int(fa_to_en_digits(last_line.replace("صحیح:", "").strip())) - 1
                                options = lines[1:-1]
                            except Exception:
                                options = lines[1:]
                        else:
                            options = lines[1:]
                    else:
                        options = lines[1:]

                    builder["type"] = "poll"
                    builder["poll_data"] = {
                        "question": question,
                        "options": options,
                        "is_anonymous": True,
                        "is_quiz": (mode == "quiz"),
                        "correct_option_id": correct_id if mode == "quiz" else None
                    }

                    kb = InlineKeyboardMarkup([
                        [InlineKeyboardButton("✅ تأیید و ارسال به همه", callback_data="bcast_confirm_send", style="success")],
                        [InlineKeyboardButton("❌ لغو", callback_data="bcast_cancel", style="danger")]
                    ])
                    await context.bot.send_poll(
                        chat_id=update.effective_chat.id,
                        question=question,
                        options=options,
                        type=PollType.QUIZ if mode == "quiz" else PollType.REGULAR,
                        correct_option_id=correct_id if mode == "quiz" else None
                    )
                    await update.message.reply_text("📊 <b>پیش‌نمایش نظرسنجی بالا را مشاهده می‌کنید. تأیید برای ارسال همگانی؟</b>", reply_markup=kb, parse_mode=ParseMode.HTML)
                    return

            if u_str in db["states"].get("waiting_user_broadcast_msg", {}):
                del db["states"]["waiting_user_broadcast_msg"][u_str]
                payload = extract_media_payload(update.message)
                if not payload:
                    await update.message.reply_text(
                        f'<b><tg-emoji emoji-id="{CROSS_CUSTOM_EMOJI_ID}">❌</tg-emoji> پیامی دریافت نشد.</b>',
                        parse_mode=ParseMode.HTML
                    )
                    return

                started_users = db.get("started_users", {})
                succ, fail = 0, 0
                status_msg = await update.message.reply_text("⏳ در حال ارسال همگانی...")
                for uid_k in started_users.keys():
                    try:
                        await send_media_payload(context.bot, int(uid_k), payload)
                        succ += 1
                        await asyncio.sleep(0.04)
                    except Exception:
                        fail += 1

                await status_msg.edit_text(f"✅ ارسال به اتمام رسید.\n\nموفق: {succ}\nناموفق: {fail}")
                return

        # --------------------------------------
        # HANDLER CLEANUP (GROUP ONLY)
        # --------------------------------------
        match_cleanup = CLEANUP_PATTERN.match(raw_text)
        if match_cleanup:
            if not is_group:
                return
            if not await is_admin_or_owner(context, chat_id, user_id):
                await update.message.reply_text(
                    f'<b><tg-emoji emoji-id="{CROSS_CUSTOM_EMOJI_ID}">❌</tg-emoji> فقط مدیران گروه دسترسی اجرای این دستور را دارند.</b>',
                    parse_mode=ParseMode.HTML
                )
                return

            count_str = match_cleanup.group("count")
            if not count_str or not count_str.isdigit() or int(count_str) <= 0:
                await update.message.reply_text("<b>فرمت دستور پاکسازی اشتباه است!\nمثال: <code>حذف 20</code></b>", parse_mode=ParseMode.HTML)
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
                            await update.message.reply_text(
                                f'<b><tg-emoji emoji-id="{CROSS_CUSTOM_EMOJI_ID}">❌</tg-emoji> ربات دسترسی حذف پیام‌ها را ندارد.</b>',
                                parse_mode=ParseMode.HTML
                            )
                            return
                        break

                log_admin_action(db, user_id, update.effective_user.full_name, update.effective_chat.title, chat_id, "پاکسازی", f"پاکسازی {deleted_count} پیام اخیر")
                confirm_msg = await context.bot.send_message(
                    chat_id=chat_id,
                    text=f'<b>پاکسازی {deleted_count} پیام اخیر انجام شد! <tg-emoji emoji-id="{CLEANUP_CUSTOM_EMOJI_ID}">📝</tg-emoji></b>',
                    parse_mode=ParseMode.HTML
                )
                await asyncio.sleep(5)
                try:
                    await context.bot.delete_message(chat_id=chat_id, message_id=confirm_msg.message_id)
                except Exception:
                    pass
            except Exception as e:
                logger.error(f"Cleanup Error: {e}")
            return

        # --------------------------------------
        # HANDLER FUN COMMANDS: «ناموسی بده» & «فحش بده» (GROUP ONLY)
        # --------------------------------------
        match_fun_named = FUN_NAMED_PATTERN.match(raw_text)
        match_fun_normal = FUN_NORMAL_PATTERN.match(raw_text)

        if match_fun_named or match_fun_normal:
            if not is_group:
                return

            is_named = bool(match_fun_named)
            match_obj = match_fun_named if is_named else match_fun_normal
            cnt_str = match_obj.group("count")
            req_cnt = int(cnt_str) if cnt_str else 1
            req_cnt = min(req_cnt, MAX_FUN_MESSAGES)

            if update.message.reply_to_message and update.message.reply_to_message.from_user and update.message.reply_to_message.from_user.id == context.bot.id:
                await update.message.reply_text('<b>منظورت چیه؟ <tg-emoji emoji-id="5829923384217050622">❓</tg-emoji></b>', parse_mode=ParseMode.HTML)
                return

            g_data = get_group_data(db, chat_id)
            key_grp = "fun_named_responses" if is_named else "fun_normal_responses"
            key_glob = "global_fun_named" if is_named else "global_fun_normal"
            responses_list = g_data.get(key_grp, []) or db.get(key_glob, [])

            if not responses_list:
                title = "ناموسی" if is_named else "عادی"
                await update.message.reply_text(f"<b>هنوز هیچ پاسخ فحش {title} برای ربات ثبت نشده است!</b>", parse_mode=ParseMode.HTML)
                return

            target_msg_id = update.message.reply_to_message.message_id if update.message.reply_to_message else None
            try:
                await context.bot.delete_message(chat_id=chat_id, message_id=update.message.message_id)
            except Exception:
                pass

            for _ in range(req_cnt):
                resp_payload = random.choice(responses_list)
                await send_media_payload(context.bot, chat_id, resp_payload, reply_to_message_id=target_msg_id)
                await asyncio.sleep(0.3)
            return

        # --------------------------------------
        # HANDLER PIN / UNPIN COMMANDS (GROUP ONLY)
        # --------------------------------------
        if clean_raw in PIN_PATTERNS or clean_raw in UNPIN_PATTERNS:
            if not is_group:
                return
            if not await is_admin_or_owner(context, chat_id, user_id):
                await update.message.reply_text(
                    f'<b><tg-emoji emoji-id="{CROSS_CUSTOM_EMOJI_ID}">❌</tg-emoji> فقط مدیران گروه دسترسی اجرای این دستور را دارند.</b>',
                    parse_mode=ParseMode.HTML
                )
                return

            if not update.message.reply_to_message:
                await update.message.reply_text("<b>برای استفاده از این دستور باید روی پیام مورد نظر ریپلای کنید!</b>", parse_mode=ParseMode.HTML)
                return

            target_msg_id = update.message.reply_to_message.message_id
            if clean_raw in PIN_PATTERNS:
                try:
                    await context.bot.pin_chat_message(chat_id=chat_id, message_id=target_msg_id)
                    log_admin_action(db, user_id, update.effective_user.full_name, update.effective_chat.title, chat_id, "پین پیام", f"Message ID: {target_msg_id}")
                    await update.message.reply_text('<b>پیامتو پین کردم عزیزم! <tg-emoji emoji-id="5870593825407243361">👋</tg-emoji></b>', parse_mode=ParseMode.HTML)
                except Exception:
                    await update.message.reply_text(
                        f'<b><tg-emoji emoji-id="{CROSS_CUSTOM_EMOJI_ID}">❌</tg-emoji> ربات دسترسی سنجاق کردن پیام‌ها را ندارد.</b>',
                        parse_mode=ParseMode.HTML
                    )
                return
            elif clean_raw in UNPIN_PATTERNS:
                try:
                    await context.bot.unpin_chat_message(chat_id=chat_id, message_id=target_msg_id)
                    log_admin_action(db, user_id, update.effective_user.full_name, update.effective_chat.title, chat_id, "آن‌پین پیام", f"Message ID: {target_msg_id}")
                    await update.message.reply_text('<b>پیامو از پین دراوردم رفیق! <tg-emoji emoji-id="5870593825407243361">👋</tg-emoji></b>', parse_mode=ParseMode.HTML)
                except Exception:
                    await update.message.reply_text(
                        f'<b><tg-emoji emoji-id="{CROSS_CUSTOM_EMOJI_ID}">❌</tg-emoji> ربات دسترسی تغییر پیام‌های سنجاق‌شده را ندارد.</b>',
                        parse_mode=ParseMode.HTML
                    )
                return

        # --------------------------------------
        # COMMAND 'کامنت روشن' & 'پنل' (GROUP ONLY)
        # --------------------------------------
        if is_group and clean_raw in ["کامنت روشن", "گودی کامنت روشن"]:
            if not await is_admin_or_owner(context, chat_id, user_id):
                await update.message.reply_text(
                    f'<b><tg-emoji emoji-id="{CROSS_CUSTOM_EMOJI_ID}">❌</tg-emoji> فقط مدیران گروه دسترسی به این دستور را دارند.</b>',
                    parse_mode=ParseMode.HTML
                )
                return
            g_data = get_group_data(db, chat_id)
            c_set = g_data.setdefault("comment", {"enabled": False, "custom": False})
            c_set["enabled"] = True
            mark_db_dirty()
            save_db(force=True)
            await update.message.reply_text("✅ <b>سیستم کامنت اتوماتیک برای این گروه فعال شد.</b>", parse_mode=ParseMode.HTML)
            return

        if is_group and clean_raw in ["پنل", "admin", "/admin"] and await is_admin_or_owner(context, chat_id, user_id):
            await command_admin_panel(update, context)
            return

        if u_str in db["states"].get("waiting_welcome_msg", {}):
            target_cid = db["states"]["waiting_welcome_msg"][u_str]
            if await is_admin_or_owner(context, target_cid, user_id):
                del db["states"]["waiting_welcome_msg"][u_str]
                payload = extract_media_payload(update.message)
                if payload:
                    g_data = get_group_data(db, target_cid)
                    g_data["welcome"] = {"enabled": True, "custom": True, "payload": payload}
                    mark_db_dirty()
                    save_db(force=True)
                    await update.message.reply_text("✅ <b>پیام و مدیای خوش‌آمدگویی اختصاصی این گروه ذخیره شد!</b>", parse_mode=ParseMode.HTML)
                    return

        if u_str in db["states"].get("waiting_comment_msg", {}):
            target_cid = db["states"]["waiting_comment_msg"][u_str]
            if await is_admin_or_owner(context, target_cid, user_id):
                del db["states"]["waiting_comment_msg"][u_str]
                payload = extract_media_payload(update.message)
                if payload:
                    g_data = get_group_data(db, target_cid)
                    g_data["comment"] = {"enabled": True, "custom": True, "payload": payload}
                    mark_db_dirty()
                    save_db(force=True)
                    await update.message.reply_text("✅ <b>کامنت اتوماتیک اختصاصی این گروه با مدیا ذخیره شد!</b>", parse_mode=ParseMode.HTML)
                    return

        if u_str in db["states"].get("waiting_add_food", {}):
            target_cid = db["states"]["waiting_add_food"][u_str]
            del db["states"]["waiting_add_food"][u_str]
            if raw_text:
                g_data = get_group_data(db, target_cid)
                foods = g_data.setdefault("foods", list(DEFAULT_FOODS))
                food_item = raw_text.strip()
                if food_item.lower() not in [f.strip().lower() for f in foods]:
                    foods.append(food_item)
                    await update.message.reply_text(f"✅ «{food_item}» به منوی این گروه اضافه شد.")
                else:
                    await update.message.reply_text(
                        f'<b><tg-emoji emoji-id="{CROSS_CUSTOM_EMOJI_ID}">❌</tg-emoji> این غذا قبلاً وجود داشته!</b>',
                        parse_mode=ParseMode.HTML
                    )
                mark_db_dirty()
                save_db(force=True)
                return

        if u_str in db["states"].get("waiting_del_food", {}):
            target_cid = db["states"]["waiting_del_food"][u_str]
            del db["states"]["waiting_del_food"][u_str]
            if raw_text:
                g_data = get_group_data(db, target_cid)
                foods = g_data.setdefault("foods", list(DEFAULT_FOODS))
                food_item = raw_text.strip()
                target_idx = next((i for i, f in enumerate(foods) if f.strip().lower() == food_item.lower()), None)
                if target_idx is not None:
                    rm = foods.pop(target_idx)
                    await update.message.reply_text(f"✅ «{rm}» از لیست این گروه حذف شد.")
                else:
                    await update.message.reply_text(
                        f'<b><tg-emoji emoji-id="{CROSS_CUSTOM_EMOJI_ID}">❌</tg-emoji> این غذا یافت نشد!</b>',
                        parse_mode=ParseMode.HTML
                    )
                mark_db_dirty()
                save_db(force=True)
                return

        if u_str in db["states"].get("waiting_poem_names", {}):
            target_cid = db["states"]["waiting_poem_names"][u_str]
            if raw_text and not raw_text.startswith("/"):
                g_data = get_group_data(db, target_cid)
                c_names = g_data.setdefault("custom_names", [])
                c_names.append(raw_text.strip())
                mark_db_dirty()
                save_db(force=True)
                await update.message.reply_text(f"✅ اسم «{raw_text.strip()}» برای این گروه ثبت شد. بعدی را بفرستید یا «✅ دان» را بزنید.")
                return

        if u_str in db["states"].get("waiting_add_poem", {}):
            target_cid = db["states"]["waiting_add_poem"][u_str]
            del db["states"]["waiting_add_poem"][u_str]
            if raw_text and not raw_text.startswith("/"):
                poem_item = raw_text.strip().replace("یوزرنیم", "{name}")
                g_data = get_group_data(db, target_cid)
                p_list = g_data.setdefault("poems", list(DEFAULT_POEMS))
                p_list.append(poem_item)
                mark_db_dirty()
                save_db(force=True)
                await update.message.reply_text("✅ شعر جدید برای این گروه اضافه شد.")
                return

        features = db.get("features", {})

        # --------------------------------------
        # HELP / راهنما PANEL
        # --------------------------------------
        help_triggers = ["راهنما", "/help", "گودی راهنما", "گودی معرفی کن", "گودی چیا بلدی؟", "چیا بلدی؟", "چیا بلدی", "گودی چیا بلدی"]
        if clean_raw in help_triggers:
            txt = (
                '<b>سلام عزیزم به ربات من خوش اومدی! <tg-emoji emoji-id="5352750090974929602">😍</tg-emoji></b>\n\n'
                '<b>از طریق دکمه‌های زیر میتونی کاملا با گودی که یه اژدها کوچولو هست آشنا بشی! <tg-emoji emoji-id="5884128023271182329">🐉</tg-emoji></b>'
            )
            kb = InlineKeyboardMarkup([
                [InlineKeyboardButton("راهنمای سرگرمی", callback_data="help_fun", style="primary", icon_custom_emoji_id="5415940089375106928"),
                 InlineKeyboardButton("راهنمای بی ادبی", callback_data="help_rude", style="primary", icon_custom_emoji_id="5832633418386513259")],
                [InlineKeyboardButton("راهنمای کاربردی", callback_data="help_useful", style="primary", icon_custom_emoji_id="5830338333892418460"),
                 InlineKeyboardButton("راهنمای مدیریتی", callback_data="help_admin", style="primary", icon_custom_emoji_id="5803348359972393936")]
            ])
            await update.message.reply_text(txt, reply_markup=kb, parse_mode=ParseMode.HTML)
            return
        # --------------------------------------
        # REPORT SYSTEM (GROUP ONLY)
        # --------------------------------------
        if is_group and clean_raw in ["گزارش", "report"] and update.message.reply_to_message:
            target_msg = update.message.reply_to_message
            if target_msg.from_user and target_msg.from_user.id == context.bot.id:
                await update.message.reply_text('<b>منو گزارش میدی؟! <tg-emoji emoji-id="5818704981179505821">🕹</tg-emoji></b>', parse_mode=ParseMode.HTML)
                return

            rep_id = f"{chat_id}_{update.message.message_id}"
            reports = db.setdefault("reports", {})
            reports[rep_id] = {"reporter_id": user_id, "target_msg_id": target_msg.message_id}
            mark_db_dirty()
            save_db()

            txt = '<b><tg-emoji emoji-id="5819051035284479206">🚨</tg-emoji> گزارش شما برای مدیران گروه ارسال شد!</b>'
            kb = InlineKeyboardMarkup([
                [InlineKeyboardButton("بررسی شد", callback_data=f"report_resolve:{rep_id}", style="success", icon_custom_emoji_id="5206607081334906820"),
                 InlineKeyboardButton("حذف", callback_data=f"report_cancel:{rep_id}", style="danger", icon_custom_emoji_id="5819154526816444042")]
            ])
            await update.message.reply_text(txt, reply_markup=kb, parse_mode=ParseMode.HTML)
            return

        # --------------------------------------
        # DODOL / FUN RESPONSE (GROUP ONLY)
        # --------------------------------------
        if is_group and DODOL_PATTERN.search(raw_text):
            ascii_penis = (
                "⣿⣿⣿⣿⣿⣿⣿⣿⣿⠟⠛⢉⢉⢉⢉⠻⣿⣿⣿⣿⣿⣿\n"
                "⣿⣿⣿⣿⣿⣿⣿⠟⠠⡰⣕⣗⣷⣧⣝⣅⠘⣿⣿⣿⣿⣿\n"
                "⣿⣿⣿⣿⣿⣿⠃⣠⣳⣟⣿⣿⣷⣿⡿⣜⠄⣿⣿⣿⣿⣿\n"
                "⣿⣿⣿⣿⠁⠄⣳⢷⣿⣿⣿⣿⡿⣿⣿⣿ ⣿⣿\n"
                "⣿⣿⣿⣿⠃⠄⢢⡹⣿⢷⣯⢿⢷⡫⣗⠍⢰⣿⣿⣿⣿⣿\n"
                "⣿⣿⣿⡏⢀⢄⠤⣁⠋⠿⣗⣟⡯⡏⢎⠁⢸⣿⣿⣿⣿⣿\n"
                "⣿⣿⣿⠄⢔⢕⣯⣿⣿⡲⡤⡄⡤⠄⡀⢠⣿⣿⣿⣿⣿⣿\n"
                "⣿⣿⠇⠠⡳⣯⣿⣿⣾⢵⣫⢎⢎⠆⢀⣿⣿⣿⣿⣿⣿⣿\n"
                "⣿⣿⠄⢨⣫⣿⣿⡿⣿⣻⢎⡗⡕⡅⢸⣿⣿⣿⣿⣿⣿⣿\n"
                "⣿⣿⠄ ⢾⣾⣿⣿⣟⣗⡪⡳⡀⢸⣿⣿⣿⣿⣿⣿⣿\n"
                "⣿⣿⠄⢸⢽⣿⣷⣿⣻⡮⡧⡳⡱⡁⢸⣿⣿⣿⣿⣿⣿⣿\n"
                "⣿⣿⡄⢨⣻⣽⣿⣟⣿⣞⣗⡽⡸⡐⢸⣿⣿⣿⣿⣿⣿⣿\n"
                "⣿⣿⡇⢀⢗⣿⣿⣿⣿⡿⣞⡵⡣⣊⢸⣿⣿⣿⣿⣿⣿⣿\n"
                "⣿⣿⣿⡀⡣⣗⣿⣿⣿⣿⣯⡯⡺⣼⠎⣿⣿⣿⣿⣿⣿⣿\n"
                "⣿⣿⣿⣧⠐⡵⣻⣟⣯⣿⣷⣟⣝⢞⡿⢹⣿⣿⣿⣿⣿⣿\n"
                "⣿⣿⣿⣿⡆⢘⡺⣽⢿⣻⣿⣗⡷⣹⢩⢃⢿⣿⣿⣿⣿⣿\n"
                "⣿⣿⣿⣿⣷⠄⠪⣯⣟⣿⢯⣿⣻⣜⢎⢆⠜⣿⣿⣿⣿⣿\n"
                "⣿⣿⣿⣿⡆⠄⢣⣻⣽⣿⣿⣟⣾⡮⡺⡸⠸⣿⣿⣿⣿⣿\n"
                "⣿⣿⠛⠉⠁⠄⢕⡳⣽⡾⣿⢽⣯⡿⣮⢚⣅⠹⣿⣿⣿\n"
                "⡿⠋⠄⠄⠄⠄⢀⠒⠝⣞⢿⡿⣿⣽⢿⡽⣧⣳⡅⠌⠻⣿\n"
                "⠁⠄⠄⠄⠄⠄⠐⡐⠱⡱⣻⡻⣝⣮⣟⣿⣿⣿⣿⣿⣿⣿"
            )
            clean_ascii = re.sub(r"[a-zA-Z]+", "", ascii_penis)
            msg1 = await update.message.reply_text(f"<code>{clean_ascii}</code>", parse_mode=ParseMode.HTML)
            await msg1.reply_text('<b>میخوریش برام؟؟ <tg-emoji emoji-id="5431423351987916271">👅</tg-emoji></b>', parse_mode=ParseMode.HTML)
            return

        # --------------------------------------
        # BOT NAME RESPONSES (GROUP ONLY)
        # --------------------------------------
        is_reply_to_bot = (
            update.message.reply_to_message and 
            update.message.reply_to_message.from_user and 
            update.message.reply_to_message.from_user.id == context.bot.id
        )

        if is_group and is_reply_to_bot and (clean_raw.startswith("درصد ") or clean_raw.startswith("این چقدر ") or clean_raw.startswith("این چقد ")):
            topic = clean_raw.replace("درصد ", "").replace("این چقدر ", "").replace("این چقد ", "").replace(" بودن", "").replace("ش", "").replace("ه", "").strip()
            await update.message.reply_text(f'<b>{html.escape(topic)} خودتی! <tg-emoji emoji-id="5886539179256450622">🤪</tg-emoji></b>', parse_mode=ParseMode.HTML)
            return

        if is_group and (is_reply_to_bot and clean_raw in ["تو کی هستی", "تو کی هستی؟"]):
            await update.message.reply_text('<b>من گودی هستم خوشگله! <tg-emoji emoji-id="5321415182109401472">😽</tg-emoji></b>', parse_mode=ParseMode.HTML)
            return

        elif is_group and (clean_raw == "گودی" or (is_reply_to_bot and clean_raw in ["گودی", "گودی؟"])):
            await update.message.reply_text('<b>بله خودم هستم چیکارم دارین؟ <tg-emoji emoji-id="5276088141671846201">🌟</tg-emoji></b>', parse_mode=ParseMode.HTML)
            return

        # --------------------------------------
        # ACTION REGISTRATION (GROUP ONLY)
        # --------------------------------------
        action_type = None
        if any(k in clean_raw for k in ["ثبت گوه خوری", "ثبت گوهخوری"]): action_type = "goh_khori"
        elif any(k in clean_raw for k in ["ثبت کصلیسی", "ثبت کص لیسی"]): action_type = "kos_lisi"
        elif any(k in clean_raw for k in ["ثبت خایمالی", "ثبت خایه مالی"]): action_type = "khaymali"
        elif any(k in clean_raw for k in ["ثبت کصخلی", "ثبت کص خلی"]): action_type = "kos_khali"
        elif any(k in clean_raw for k in ["ثبت جندگی", "ثبت جنده گی"]): action_type = "jendegi"

        if action_type:
            if not is_group:
                return
            if not update.message.reply_to_message:
                await update.message.reply_text(
                    f'<b><tg-emoji emoji-id="{CROSS_CUSTOM_EMOJI_ID}">❌</tg-emoji> برای ثبت باید روی پیام یک نفر ریپلای کنی!</b>',
                    parse_mode=ParseMode.HTML
                )
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
                    "goh_khori": {"title": "گوه‌خوری", "stat_key": "goh_khori", "icon_id": "5819051035284479206", "funny_text": "گوه‌خوری نوین مشاهده شد!"},
                    "kos_lisi": {"title": "کصلیسی", "stat_key": "kos_lisi", "icon_id": "5832692422647226240", "funny_text": "مدال شجاعت کصلیسی تعلق گرفت!"},
                    "khaymali": {"title": "خایمالی", "stat_key": "khaymali", "icon_id": "5920300405341820405", "funny_text": "خایمال‌نامه جدید صادر شد!"},
                    "kos_khali": {"title": "کصخلی", "stat_key": "kos_khali", "icon_id": "5443038326535759644", "funny_text": "پرونده پزشکی کصخلی تنظیم شد!"},
                    "jendegi": {"title": "جندگی", "stat_key": "jendegi", "icon_id": "4974615079971455718", "funny_text": "ثبت جندگی جدید در سیستم با موفقیت ثبت شد!"}
                }
                cfg = action_configs[action_type]
                rec_id = f"{chat_id}_{update.message.message_id}"
                
                increment_user_stat(db, target_uid, cfg["stat_key"])
                records = db.setdefault("action_records", {})
                records[rec_id] = {
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
        # STATS & OVERALL USER STATUS (GROUP ONLY)
        # --------------------------------------
        is_asking_own_stats = clean_raw in ["آمارم", "آمار من", "وضعیت من"]
        is_asking_other_stats = clean_raw in ["اوضاع این", "اوضاعش", "آمار این", "وضعیت این", "وضعیت"] and update.message.reply_to_message

        if is_group and (is_asking_own_stats or is_asking_other_stats):
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
        # GENERAL PERCENTAGE (GROUP ONLY)
        # --------------------------------------
        if is_group and (clean_raw.startswith("درصد ") or clean_raw.startswith("این چقدر ") or clean_raw.startswith("این چقد ")):
            target_uid, target_fname, target_uname, target_mention = resolve_target_user(update, context)
            topic = clean_raw.replace("درصد ", "").replace("این چقدر ", "").replace("این چقد ", "").replace(" بودن", "").strip()
            val = random.randint(0, 100)
            rand_emoji_id = random.choice(["5886539179256450622", "5922483378304586599", "5195297917048462460", "5983342699816685361"])
            await update.message.reply_text(f"{target_mention}\n\n<tg-emoji emoji-id=\"{rand_emoji_id}\">🎲</tg-emoji> <b>{val}٪ {html.escape(topic)}ه</b>", parse_mode=ParseMode.HTML)
            return

        # --------------------------------------
        # WORLD TIME (GROUP ONLY)
        # --------------------------------------
        if is_group and features.get("world_time", True):
            selected_country = None
            if norm_text.startswith("ساعت "):
                target_name = norm_text.replace("ساعت ", "").strip()
                for c_name, c_data in WORLD_COUNTRIES.items():
                    if target_name == c_name or target_name in c_data.get("aliases", []):
                        selected_country = (c_name, c_data)
                        break

            if selected_country:
                c_name, c_data = selected_country
                c_time = datetime.now(ZoneInfo(c_data["tz"])).strftime("%H:%M:%S")
                msg = f'<b>{c_data["emoji"]} ساعت {c_name}: {c_time}</b>'
                await update.message.reply_text(msg, parse_mode=ParseMode.HTML)
                return

            elif norm_text in ["ساعت", "ساعت جهانی"]:
                lines = ['<b><tg-emoji emoji-id="5399898266265475100">🌍</tg-emoji> ساعت جهانی برخی از کشورها :</b>\n']
                for c_name, c_data in WORLD_COUNTRIES.items():
                    c_time = datetime.now(ZoneInfo(c_data["tz"])).strftime("%H:%M:%S")
                    lines.append(f'<b>{c_data["emoji"]} {c_name}: {c_time}</b>')
                
                await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.HTML)
                return
# --------------------------------------
        # FUN FEATURES WITH PREMIUM EMOJIS & COOLDOWN
        # --------------------------------------
        # ۲. خوشتیپ / خوژتیپ
        if is_group and norm_text in ["خوشتیپ کیه", "خوشتیپ کی", "خوژتیپ کیه", "خوژتیپ کی", "خوشتیپ", "خوژتیپ"] and features.get("handsome", True):
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
                else:
                    await update.message.reply_text('<b>❌ کاربری در حافظه گروه پیدا نشد!</b>', parse_mode=ParseMode.HTML)
            return

        # ۳. جنده
        elif is_group and norm_text in ["جنده کیه", "جنده کی", "جنده"] and features.get("jende", True):
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
                else:
                    await update.message.reply_text('<b>❌ کاربری در حافظه گروه پیدا نشد!</b>', parse_mode=ParseMode.HTML)
            return

        # ۴. کونی
        elif is_group and norm_text in ["کونی کیه", "کونی کی", "کونی"] and features.get("koni", True):
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
                else:
                    await update.message.reply_text('<b>❌ کاربری در حافظه گروه پیدا نشد!</b>', parse_mode=ParseMode.HTML)
            return

        # ۵. جقی
        elif is_group and norm_text in ["جقی", "جقی کیه", "جقی گروه"] and features.get("jaghi", True):
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
                else:
                    await update.message.reply_text('<b>❌ کاربری در حافظه گروه پیدا نشد!</b>', parse_mode=ParseMode.HTML)
            return

        # ۶. کصخل / کسخل
        elif is_group and norm_text in ["کصخل", "کسخل", "کصخل گروه", "کسخل گروه"] and features.get("koskhal", True):
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
                else:
                    await update.message.reply_text('<b>❌ کاربری در حافظه گروه پیدا نشد!</b>', parse_mode=ParseMode.HTML)
            return

        # ۷. سکسی
        elif is_group and norm_text in ["سکسی", "سکسی گروه"] and features.get("sexy", True):
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
                else:
                    await update.message.reply_text('<b>❌ کاربری در حافظه گروه پیدا نشد!</b>', parse_mode=ParseMode.HTML)
            return

        # ۸. جذاب
        elif is_group and norm_text in ["جذاب", "جذاب گروه"] and features.get("jazab", True):
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
                else:
                    await update.message.reply_text('<b>❌ کاربری در حافظه گروه پیدا نشد!</b>', parse_mode=ParseMode.HTML)
            return

        # ۹. شیپ / کاپل
        elif is_group and norm_text in ["شیپ کن", "شیپ", "کاپل", "کاپل کن"] and features.get("ship", True):
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

                    if "couples" not in db:
                        db["couples"] = {}
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
                        '<b> اعضای کافی موجود نیست! <tg-emoji emoji-id="5857415006022278161">❌</tg-emoji></b>',
                        parse_mode=ParseMode.HTML
                    )
            return

        # غذا
        elif is_group and any(w in norm_text.split() for w in ["غذا", "غدا", "نهار", "شام"]) and features.get("food", True):
            g_data = get_group_data(db, chat_id)
            fl = g_data.get("foods", DEFAULT_FOODS)
            if fl:
                selected_food = random.choice(fl)
                msg = (
                    f'<b><tg-emoji emoji-id="5418248505447698083">🧽</tg-emoji> دنبال غذایی؟ بنظرم بهترین ایده غذا برای تو اینه :</b>\n\n'
                    f'<b><tg-emoji emoji-id="5357066069250948384">🐱</tg-emoji> | {html.escape(selected_food)}</b>'
                )
                await update.message.reply_text(msg, parse_mode=ParseMode.HTML)
            return

        # شعر
        elif is_group and norm_text in ["شعر", "شعر بگو", "شاعر شو"] and features.get("poems", True):
            g_data = get_group_data(db, chat_id)
            custom_names = g_data.get("custom_names", [])
            if custom_names:
                target_name = random.choice(custom_names)
            else:
                m_tuple = await get_fast_random_member(context, chat_id, db)
                target_name = get_user_mention(int(m_tuple[0]), m_tuple[1]["fullname"]) if m_tuple else "رفیق"

            all_poems = g_data.get("poems", DEFAULT_POEMS)
            poem_template = random.choice(all_poems)
            final_poem = poem_template.format(name=target_name)
            await update.message.reply_text(f'<tg-emoji emoji-id="5859527571586161695">✍️</tg-emoji> <b>{final_poem}</b>', parse_mode=ParseMode.HTML)
            return

        # لف
        elif is_group and LEF_PATTERN.search(raw_text) and features.get("lef", True):
            g_data = get_group_data(db, chat_id)
            ml = g_data.get("media_lef") or db.get("media_lef")
            if ml:
                await send_media_payload(context.bot, chat_id, ml)
            return

    except Exception:
        logger.exception("Error in handle_messages:")

# ==========================================
# GLOBAL ERROR HANDLER & MAIN
# ==========================================
async def global_error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    logger.error(f"Global Error: {context.error}", exc_info=context.error)

def main():
    if not BOT_TOKEN or BOT_TOKEN == "YOUR_BOT_TOKEN_HERE":
        logger.critical("FATAL: BOT_TOKEN is missing!")
        sys.exit(1)

    load_db()
    threading.Thread(target=run_health_check_server, daemon=True).start()

    app = Application.builder().token(BOT_TOKEN).post_init(post_init).build()

    # 0. Global Security Guard (Group -10)
    app.add_handler(MessageHandler(filters.ALL, global_security_guard), group=-10)
    app.add_handler(CallbackQueryHandler(global_security_guard), group=-10)

    # 1. Group Lock Enforcer (Group -5)
    app.add_handler(MessageHandler(filters.ChatType.GROUPS & filters.ALL, enforce_group_locks), group=-5)
    app.add_handler(MessageHandler(filters.ChatType.GROUPS & filters.UpdateType.EDITED_MESSAGE, enforce_group_locks), group=-5)

    # 2. Text Welcome Toggle Command (Group -4) - Admin only
    app.add_handler(
        MessageHandler(
            filters.ChatType.GROUPS & filters.TEXT & (~filters.COMMAND),
            handle_welcome_text_command
        ),
        group=-4
    )

    # 3. Automatic comment for channel connected discussion group
    app.add_handler(MessageHandler(filters.ChatType.GROUPS & filters.IS_AUTOMATIC_FORWARD, handle_automatic_channel_comments), group=-3)

    # 4. Welcome system (ChatMember event + Service Message fallback)
    app.add_handler(ChatMemberHandler(handle_chat_member_welcome, ChatMemberHandler.CHAT_MEMBER), group=-2)
    app.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, handle_new_chat_members), group=-2)

    # Chat Member Tracking for bot itself
    app.add_handler(ChatMemberHandler(track_chats, ChatMemberHandler.MY_CHAT_MEMBER))

    # --- این بخش را دقیقاً اینجا قرار بده ---
    # Inline Query Handler for Whisper
    app.add_handler(InlineQueryHandler(handle_inline_whisper))
    # --------------------------------------

    # General callback & command handlers
    app.add_handler(CallbackQueryHandler(handle_callback_query))
    app.add_handler(CommandHandler("start", command_start))
    app.add_handler(CommandHandler("panel", command_owner_panel))
    app.add_handler(CommandHandler("cancel", command_cancel))
    app.add_handler(CommandHandler("done", command_done))

    # 5. Dwoz game
    app.add_handler(
        MessageHandler(filters.TEXT & (~filters.COMMAND), dwoz_message_handler),
        group=-1
    )

    # 6. General message handler
    app.add_handler(
        MessageHandler(filters.ALL & (~filters.COMMAND), handle_messages)
    )

    app.add_error_handler(global_error_handler)

    logger.info("Bot is running with full per-group lock & enhanced welcome system...")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()        
