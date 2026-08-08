import html
import json
import logging
import os
import random
import re
import shutil
import sys
import threading
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
    filters,
)

# ==========================================
# CONFIGURATION & LOGGING
# ==========================================
BOT_TOKEN = "8618205537:AAFCjx1_PkdC43ezimZgp-z5PAx0JKEmJqI"  # توکن ربات[cite: 2]
OWNER_ID = 6749949992[cite: 2]
DB_FILE = "db.json"[cite: 2]
TEMP_DB_FILE = "db.json.tmp"[cite: 2]
BROKEN_DB_FILE = "db.json.broken"[cite: 2]

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)[cite: 2]
logger = logging.getLogger(__name__)[cite: 2]

# ==========================================
# DUMMY HTTP SERVER FOR RENDER WEB SERVICE
# ==========================================
class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)[cite: 2]
        self.end_headers()[cite: 2]
        self.wfile.write(b"Bot is alive!")[cite: 2]

    def log_message(self, format, *args):
        return[cite: 2]

def run_health_check_server():
    port = int(os.environ.get("PORT", 8080))[cite: 2]
    server = HTTPServer(("0.0.0.0", port), HealthCheckHandler)[cite: 2]
    logger.info(f"Dummy HTTP server running on port {port}")[cite: 2]
    server.serve_forever()[cite: 2]

# ==========================================
# ADVANCED REGEX PATTERNS & TEXT NORMALIZER
# ==========================================
LEF_PATTERN = re.compile(
    r"(?:\b|(?<=\s))ل+[فف]*[عع]*[هه]*(?:\s*(?:داد|بده|میده|میدم|میخوام))?(?=\s|[.,!?؛؟]|$)",
    re.IGNORECASE
)[cite: 2]

def normalize_text(text: str) -> str:
    if not text:
        return ""[cite: 2]
    text = re.sub(r"[؟?\.,!؛\-_]", " ", text)[cite: 2]
    text = text.replace("\u200c", " ")[cite: 2]
    text = re.sub(r"(.)\1{2,}", r"\1", text)[cite: 2]
    text = re.sub(r"ه{2,}", "ه", text)[cite: 2]
    text = re.sub(r"و{2,}", "و", text)[cite: 2]
    text = re.sub(r"ی{2,}", "ی", text)[cite: 2]
    words = text.strip().split()[cite: 2]
    return " ".join(words)[cite: 2]

# ==========================================
# GLOBAL DB CACHE & DIRTY FLAG
# ==========================================
_DB_CACHE = None[cite: 2]
_DB_DIRTY = False[cite: 2]

# ==========================================
# DEFAULT FOODS DATABASE (150+ ITEMS)
# ==========================================
DEFAULT_FOODS = [
    "قرمه سبزی", "قیمه سیب‌زمینی", "قیمه نثار", "فسنجان", "دیزی / آبگوشت",
    "کباب کوبیده", "جوجه کباب", "شیشلیک", "کباب برگ", "کباب سلطانی",
    "کباب بختیاری", "کباب تابه ای", "ماهی کباب", "چلو گوشت", "زرشک پلو با مرغ",
    "باقالی پلو با گوشت", "باقالی پلو با مرغ", "آلبالو پلو", "شیرین پلو", "کلم پلو شیرازی",
    "عدس پلو با گوشت", "لوبیا پلو", "رشته پلو", "استامبولی", "دمپختک",
    "ته‌چین مرغ", "ته‌چین گوشت", "ته‌چین بادمجان", "کوفته تبریزی", "کوفته ریزه",
    "دلمه برگ مو", "دلمه بادمجان", "دلمه فلفل دلمه‌ای", "دلمه کدو", "میرزا قاسمی",
    "کشک بادمجان", "حلیم بادمجون", "خورشت بادمجان", "خورشت کدو", "خورشت کرفس",
    "خورشت به آلو", "خورشت ریواس", "خورشت کنگر", "خورشت داوود پاشا", "خورشت خلال",
    "خورشت ماسه", "باقلا قاتوق", "ترش تره", "اناربیج", "ماهی سفید سرخ شده",
    "سبزی پلو با ماهی", "قلیه ماهی", "قلیه میگو", "میگو پلو", "پلو مخلوط ماهی",
    "آش رشته", "آش دوغ", "آش شله قلمکار", "آش جو", "آش میوه",
    "آش گوجه", "آش انار", "آبگوشت بزباش", "سیرابی", "کله پاچه",
    "حلیم گندم", "شله مشهدی", "یتیمچه", "کوکو سبزی", "کوکو سیب‌زمینی",
    "کوکو شیرین", "کتلت گوشت", "کتلت مرغ", "شامی کباب", "شامی پوک",
    "فلافل", "سمبوسه", "پیراشکی گوشت", "سوسیس بندری", "الویه",
    "سالاد ماکارونی", "پیتزا مخلوط", "پیتزا پپرونی", "پیتزا مرغ و قارچ", "پیتزا گوشت و قارچ",
    "پیتزا سبزیجات", "پیتزا سیر و steak", "پیتزا مارگاریتا", "برگر مخصوص", "چیزبرگر",
    "قارچ برگر", "دوبل برگر", "زاپاتا", "ساندویچ هایدا", "ساندویچ رست بیف",
    "ساندویچ مرغ", "ساندویچ زبان", "ساندویچ مغز", "ساندویچ کباب ترکی", "اسنک کباب",
    "اسنک مرغ", "پاستا آلفردو", "پاستا پستو", "پاستا بلونز", "لازانیا",
    "اسپاگتی با گوشت", "گراتن بادمجان", "نودل مرغ", "نودل سبزیجات", "استیک گوشت",
    "استیک مرغ", "شنتسل مرغ", "کورن داگ", "مرغ سوخاری (KFC)", "فیله سوخاری",
    "قارچ سوخاری", "سیب‌زمینی سرخ کرده", "پوتین", "سیب سرخ کرده با پنیر", "تاکو گوشت",
    "بوریتو", "سوشی", "شاورما مرغ", "شاورما گوشت", "کپک کباب",
    "حمص با نان", "فاهیتا مرغ", "چیلی کن کارنه", "کیسادیا", "راتاتویی",
    "سوفله قارچ", "پای گوشت", "پای مرغ و قارچ", "امپانادا", "پلاو",
    "بریانی اصفهان", "بریانی هندی", "چکن تیکا ماسالا", "باتر چکن", "کاری مرغ",
    "سالمون گریل شده", "استیک تن ماهی", "سویچیکول", "کیک گوشت", "رولت گوشت",
    "رولت مرغ", "بورانی بادمجان", "نرگسی اسفناج", "اشکنه", "کله جوش",
    "شامی لپه", "پاکورا", "پای چوپان", "گراتن سیب‌زمینی", "کانلونی",
    "پاستا کربونارا", "میت‌بال اسپاگتی", "چیکن پارمیجانا", "سالاد سزار با مرغ", "سالاد یونانی"
][cite: 2]

# ==========================================
# DEFAULT POEMS DATABASE
# ==========================================
DEFAULT_POEMS = [
    "{name} خواست منو خراب کنه، بردن تو خرابه کردنش!",
    "در ناامیدی بسی امید است، زیر لباس {name} کصی سفید است!",
    "از دیشب تا حالا شبیه‌خون زدن، {name} رو بردن و جف‌کون زدن!",
    "ای که از کوچه معشوقه ما می‌گذری، بی‌خبر از دل ما {name} رو یواشکی می‌بری!",
    "نه جانی ماند و نه دلداری ماند، {name} ماند و یک کونِ بادکرده!",
    "سعدیا مرد نکونام نمیرد هرگز، {name} ار دادن کون خسته شود حرفی نیست!",
    "روزها فکر من این است و همه‌شب سخنم، که چرا {name} این‌قدر بی‌هوا می‌ده به من!",
    "ز اندازه بیرون تشنه‌ام، مهر {name} در دل افکنده‌ام!",
    "گر بدین سان زیست باید پاک، {name} رو باید گذاشت روی خاک!",
    "به صحرا نگرم صحرا تو بینم، به دریا نگرم {name} رو تو زیرم بینم!"
]

# ==========================================
# DATABASE HELPER
# ==========================================
def get_default_db_structure() -> dict:
    return {
        "members": {},[cite: 2]
        "hourly_messages": {},[cite: 2]
        "last_job_reset": 0,[cite: 2]
        "active_chats": [],[cite: 2]
        "foods": list(DEFAULT_FOODS),[cite: 2]
        "custom_names": [],     # اسامی سفارشی برای شعرها[cite: 1]
        "media_lef": None,[cite: 2]
        "cooldown_minutes": 10,  # مدت زمان کول‌داون پیش‌فرض (۱۰ دقیقه)[cite: 2]
        "cooldowns": {},         # {chat_id: {feature_name: {"timestamp": float, "data": dict}}}[cite: 2]
        "couples": {},           # {message_id: {"u1": dict, "u2": dict, "agrees": [], "disagrees": []}}[cite: 2]
        "features": {
            "world_time": True,[cite: 2]
            "handsome": True,[cite: 2]
            "jende": True,[cite: 2]
            "koni": True,[cite: 2]
            "ship": True,[cite: 2]
            "food": True,[cite: 2]
            "lef": True,[cite: 2]
            "goh_khor": True,[cite: 2]
            "koni_percent": True,[cite: 2]
            "poems": True,
        },
        "states": {
            "waiting_lef_media": [],[cite: 2]
            "waiting_add_food": [],[cite: 2]
            "waiting_del_food": [],[cite: 2]
            "waiting_cooldown": [],[cite: 2]
            "waiting_poem_names": []
        }
    }

def load_db() -> dict:
    global _DB_CACHE
    if _DB_CACHE is not None:
        return _DB_CACHE[cite: 2]

    default_struct = get_default_db_structure()

    if not os.path.exists(DB_FILE):
        _DB_CACHE = default_struct
        save_db(force=True)
        return _DB_CACHE[cite: 2]

    try:
        with open(DB_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)[cite: 2]
            for key, val in default_struct.items():
                if key not in data:
                    data[key] = val[cite: 2]
            _DB_CACHE = data
            return _DB_CACHE[cite: 2]
    except (json.JSONDecodeError, Exception) as e:
        logger.error(f"Database corrupted! Backing up to {BROKEN_DB_FILE}. Error: {e}")[cite: 2]
        try:
            shutil.copy(DB_FILE, BROKEN_DB_FILE)[cite: 2]
        except Exception as copy_err:
            logger.error(f"Backup failed: {copy_err}")[cite: 2]
        
        _DB_CACHE = default_struct
        save_db(force=True)
        return _DB_CACHE[cite: 2]

def mark_db_dirty():
    global _DB_DIRTY
    _DB_DIRTY = True[cite: 2]

def save_db(force: bool = False):
    global _DB_DIRTY, _DB_CACHE
    if not force and not _DB_DIRTY:
        return[cite: 2]
    if _DB_CACHE is None:
        return[cite: 2]

    try:
        with open(TEMP_DB_FILE, "w", encoding="utf-8") as f:
            json.dump(_DB_CACHE, f, ensure_ascii=False, indent=4)[cite: 2]
        os.replace(TEMP_DB_FILE, DB_FILE)[cite: 2]
        _DB_DIRTY = False[cite: 2]
    except Exception as e:
        logger.error(f"Error saving DB: {e}")[cite: 2]

# ==========================================
# HELPER FUNCTIONS
# ==========================================
def get_user_mention(user_id: int, fullname: str) -> str:
    clean_name = html.escape(fullname)[cite: 2]
    return f'<a href="tg://user?id={user_id}">{clean_name}</a>'[cite: 2]

async def is_user_in_chat(context: ContextTypes.DEFAULT_TYPE, chat_id: int, user_id: int) -> bool:
    try:
        member = await context.bot.get_chat_member(chat_id, user_id)[cite: 2]
        return member.status in [
            ChatMemberStatus.MEMBER,
            ChatMemberStatus.ADMINISTRATOR,
            ChatMemberStatus.OWNER
        ][cite: 2]
    except Exception:
        return False[cite: 2]

async def get_valid_group_members(context: ContextTypes.DEFAULT_TYPE, chat_id: int, db: dict) -> list:
    members = db.get("members", {})[cite: 2]
    valid_members = []
    for uid_str, info in members.items():
        uid = int(uid_str)[cite: 2]
        if await is_user_in_chat(context, chat_id, uid):
            valid_members.append((uid_str, info))[cite: 2]
    return valid_members[cite: 2]

async def is_admin_or_owner(context: ContextTypes.DEFAULT_TYPE, chat_id: int, user_id: int) -> bool:
    if user_id == OWNER_ID:
        return True[cite: 2]
    try:
        member = await context.bot.get_chat_member(chat_id, user_id)[cite: 2]
        return member.status in [ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER][cite: 2]
    except Exception as e:
        logger.error(f"Error checking admin status: {e}")[cite: 2]
        return False[cite: 2]

async def register_member(update: Update, db: dict):
    user = update.effective_user[cite: 2]
    chat = update.effective_chat[cite: 2]
    if not user or user.is_bot:
        return[cite: 2]
        
    user_id = str(user.id)[cite: 2]
    fullname = user.full_name or "کاربر"[cite: 2]
    username = user.username or ""[cite: 2]
    
    if user_id not in db["members"] or db["members"][user_id].get("fullname") != fullname:
        db["members"][user_id] = {"username": username, "fullname": fullname}[cite: 2]
        mark_db_dirty()[cite: 2]
    
    if chat and chat.type in ["group", "supergroup"]:
        if chat.id not in db["active_chats"]:
            db["active_chats"].append(chat.id)[cite: 2]
            mark_db_dirty()[cite: 2]
            
        current_count = db["hourly_messages"].get(user_id, 0)[cite: 2]
        db["hourly_messages"][user_id] = current_count + 1[cite: 2]
        mark_db_dirty()[cite: 2]
        
    save_db()[cite: 2]

# ==========================================
# COOLDOWN & TIMER SYSTEM
# ==========================================
def get_cooldown_remaining(db: dict, chat_id: int, feature: str) -> tuple[bool, int, dict]:
    chat_str = str(chat_id)[cite: 2]
    cooldowns = db.get("cooldowns", {}).get(chat_str, {})[cite: 2]
    if feature not in cooldowns:
        return False, 0, {}[cite: 2]
    
    last_time = cooldowns[feature].get("timestamp", 0)[cite: 2]
    cooldown_limit = db.get("cooldown_minutes", 10) * 60[cite: 2]
    elapsed = datetime.now().timestamp() - last_time[cite: 2]
    
    if elapsed < cooldown_limit:
        remaining_seconds = int(cooldown_limit - elapsed)[cite: 2]
        return True, remaining_seconds, cooldowns[feature].get("data", {})[cite: 2]
    return False, 0, {}[cite: 2]

def set_cooldown_data(db: dict, chat_id: int, feature: str, data: dict):
    chat_str = str(chat_id)[cite: 2]
    if "cooldowns" not in db:
        db["cooldowns"] = {}[cite: 2]
    if chat_str not in db["cooldowns"]:
        db["cooldowns"][chat_str] = {}[cite: 2]
        
    db["cooldowns"][chat_str][feature] = {
        "timestamp": datetime.now().timestamp(),
        "data": data
    }[cite: 2]
    mark_db_dirty()[cite: 2]
    save_db()[cite: 2]

# ==========================================
# WELCOME HANDLER (BOT ADDED TO GROUP)
# ==========================================
async def track_chats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    result = update.my_chat_member[cite: 2]
    if not result:
        return[cite: 2]

    new_status = result.new_chat_member.status[cite: 2]
    if new_status in [ChatMemberStatus.MEMBER, ChatMemberStatus.ADMINISTRATOR]:
        welcome_msg = (
            "<b>سلام نینیا ، یه ربات سرگرمی اینجاست...! </b>"
            '<tg-emoji emoji-id="5276251363313996750">😊</tg-emoji>\n\n'
            "<b>شروع کنید به مسخره بازی که حال کنیم! </b>"
            '<tg-emoji emoji-id="5274211661870295868">😌</tg-emoji>'
        )[cite: 1, 2]
        try:
            await context.bot.send_message(
                chat_id=result.chat.id,
                text=welcome_msg,
                parse_mode=ParseMode.HTML
            )[cite: 2]
        except Exception as e:
            logger.error(f"Failed to send welcome message: {e}")[cite: 2]

# ==========================================
# JOB QUEUE SYSTEM
# ==========================================
async def hourly_goh_khor_job(context: ContextTypes.DEFAULT_TYPE):
    db = load_db()[cite: 2]
    if not db["features"].get("goh_khor", True):
        return[cite: 2]
        
    messages_data = db.get("hourly_messages", {})[cite: 2]
    if not messages_data:
        return[cite: 2]
        
    top_user_id = max(messages_data, key=lambda k: messages_data[k])[cite: 2]
    max_msgs = messages_data[top_user_id][cite: 2]
    
    if max_msgs > 0:
        member_info = db["members"].get(top_user_id, {})[cite: 2]
        fullname = member_info.get("fullname", "کاربر")[cite: 2]
        mention = get_user_mention(int(top_user_id), fullname)[cite: 2]
        
        text = f"🏆 <b>گوه خور این ساعت</b>\n\n{mention}\n\nتو این یک ساعت خیلی حرف زدی 😂"[cite: 2]
        
        target_chat_id = context.job.chat_id[cite: 2]
        if target_chat_id:
            try:
                await context.bot.send_message(
                    chat_id=target_chat_id,
                    text=text,
                    parse_mode=ParseMode.HTML
                )[cite: 2]
            except Exception as e:
                logger.error(f"Job send error to {target_chat_id}: {e}")[cite: 2]

    db["hourly_messages"] = {}[cite: 2]
    db["last_job_reset"] = int(datetime.now().timestamp())[cite: 2]
    mark_db_dirty()[cite: 2]
    save_db(force=True)[cite: 2]

def setup_chat_jobs(job_queue, active_chats: list):
    if not job_queue:
        return[cite: 2]
    for chat_id in active_chats:
        job_name = f"goh_khor_{chat_id}"[cite: 2]
        existing_jobs = job_queue.get_jobs_by_name(job_name)[cite: 2]
        if not existing_jobs:
            job_queue.run_repeating(
                hourly_goh_khor_job,
                interval=3600,
                first=3600,
                chat_id=chat_id,
                name=job_name
            )[cite: 2]

async def post_init(application: Application):
    db = load_db()[cite: 2]
    setup_chat_jobs(application.job_queue, db.get("active_chats", []))[cite: 2]

# ==========================================
# ADMIN PANEL RENDERING & PAGINATION
# ==========================================
async def render_main_panel_message(query):
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🖼 رسانه لف", callback_data="panel_media_lef")],[cite: 2]
        [InlineKeyboardButton("🍽 مدیریت غذاها", callback_data="panel_foods")],[cite: 2]
        [InlineKeyboardButton("📜 اسامی شعرها", callback_data="panel_poem_names")],
        [InlineKeyboardButton("⏱ زمان محدودیت (Cooldown)", callback_data="panel_cooldown")],[cite: 2]
        [InlineKeyboardButton("⚙ مدیریت قابلیت ها", callback_data="panel_features")][cite: 2]
    ])
    await query.message.edit_text("مدیر عزیز\n\nچه چیزی را تغییر می‌دهید؟", reply_markup=keyboard)[cite: 2]

async def render_features_panel_message(query, db: dict):
    feats = db.get("features", {})[cite: 2]
    def status(key):
        return "✅" if feats.get(key, True) else "❌"[cite: 2]

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton(f"{status('world_time')} 🌍 ساعت جهانی", callback_data="toggle_world_time")],[cite: 2]
        [InlineKeyboardButton(f"{status('handsome')} 😎 خوشتیپ", callback_data="toggle_handsome")],[cite: 2]
        [InlineKeyboardButton(f"{status('jende')} 😂 جنده", callback_data="toggle_jende")],[cite: 2]
        [InlineKeyboardButton(f"{status('koni')} 🤣 کونی", callback_data="toggle_koni")],[cite: 2]
        [InlineKeyboardButton(f"{status('ship')} ❤️ شیپ", callback_data="toggle_ship")],[cite: 2]
        [InlineKeyboardButton(f"{status('food')} 🍽 غذا", callback_data="toggle_food")],[cite: 2]
        [InlineKeyboardButton(f"{status('lef')} 🖼 لف", callback_data="toggle_lef")],[cite: 2]
        [InlineKeyboardButton(f"{status('goh_khor')} 🏆 گوه خور", callback_data="toggle_goh_khor")],[cite: 2]
        [InlineKeyboardButton(f"{status('koni_percent')} 📊 درصد", callback_data="toggle_koni_percent")],[cite: 2]
        [InlineKeyboardButton("🔙 بازگشت", callback_data="panel_main")][cite: 2]
    ])
    await query.message.edit_text(
        "⚙ <b>مدیریت قابلیت‌ها</b>\n\nبا کلیک روی هر دکمه، وضعیت آن را روشن یا خاموش کنید:",
        reply_markup=keyboard,
        parse_mode=ParseMode.HTML
    )[cite: 2]

async def render_food_list_page(query, db: dict, page: int = 1):
    foods = db.get("foods", [])[cite: 2]
    per_page = 15[cite: 2]
    total_pages = max(1, (len(foods) + per_page - 1) // per_page)[cite: 2]
    page = max(1, min(page, total_pages))[cite: 2]
    
    current_foods = foods[(page - 1) * per_page : page * per_page][cite: 2]
    food_str = "\n".join([f"• {html.escape(f)}" for f in current_foods])[cite: 2]
    
    nav_buttons = [][cite: 2]
    if page > 1:
        nav_buttons.append(InlineKeyboardButton("◀️ قبلی", callback_data=f"food_page_{page - 1}"))[cite: 2]
    nav_buttons.append(InlineKeyboardButton(f"صفحه {page} از {total_pages}", callback_data="noop"))[cite: 2]
    if page < total_pages:
        nav_buttons.append(InlineKeyboardButton("بعدی ▶️", callback_data=f"food_page_{page + 1}"))[cite: 2]
        
    keyboard = InlineKeyboardMarkup([nav_buttons, [InlineKeyboardButton("🔙 بازگشت", callback_data="panel_foods")]])[cite: 2]
    await query.message.edit_text(
        f"📋 <b>لیست غذاها (تعداد کل: {len(foods)})</b>\n\n{food_str}",
        reply_markup=keyboard,
        parse_mode=ParseMode.HTML
    )[cite: 2]

# ==========================================
# CALLBACK QUERY HANDLER
# ==========================================
async def handle_callback_query(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query[cite: 2]
    data = query.data[cite: 2]
    user_id = query.from_user.id[cite: 2]
    chat_id = update.effective_chat.id if update.effective_chat else 0[cite: 2]
    db = load_db()[cite: 2]

    # مدیریت دکمه‌های موافقم / افتضاح برای سیستم کاپل[cite: 2]
    if data in ["couple_agree", "couple_disagree"]:
        msg_id = str(query.message.message_id)[cite: 2]
        couples = db.get("couples", {})[cite: 2]
        
        if msg_id not in couples:
            await query.answer("❌ اطلاعات این شیپ منقضی شده است!", show_alert=True)[cite: 2]
            return[cite: 2]

        couple_data = couples[msg_id][cite: 2]
        agrees = couple_data["agrees"][cite: 2]
        disagrees = couple_data["disagrees"][cite: 2]
        user_info = {"id": user_id, "name": query.from_user.full_name}[cite: 2]

        if data == "couple_agree":
            disagrees = [u for u in disagrees if u["id"] != user_id][cite: 2]
            if not any(u["id"] == user_id for u in agrees):
                agrees.append(user_info)[cite: 2]
                await query.answer("موافقت شما ثبت شد! 👍")[cite: 2]
            else:
                await query.answer("شما قبلاً موافقت کرده‌اید!")[cite: 2]
        else:
            agrees = [u for u in agrees if u["id"] != user_id][cite: 2]
            if not any(u["id"] == user_id for u in disagrees):
                disagrees.append(user_info)[cite: 2]
                await query.answer("مخالفت شما ثبت شد! 👎")[cite: 2]
            else:
                await query.answer("شما قبلاً مخالفت کرده‌اید!")[cite: 2]

        couple_data["agrees"] = agrees[cite: 2]
        couple_data["disagrees"] = disagrees[cite: 2]
        db["couples"][msg_id] = couple_data[cite: 2]
        mark_db_dirty()[cite: 2]
        save_db()[cite: 2]

        u1, u2 = couple_data["u1"], couple_data["u2"][cite: 2]
        name1 = get_user_mention(u1["id"], u1["name"])[cite: 2]
        name2 = get_user_mention(u2["id"], u2["name"])[cite: 2]

        agrees_text = ", ".join([get_user_mention(u["id"], u["name"]) for u in agrees]) if agrees else "هیچکس"[cite: 2]
        disagrees_text = ", ".join([get_user_mention(u["id"], u["name"]) for u in disagrees]) if disagrees else "هیچکس"[cite: 2]

        new_text = (
            f"❤️ <b>کاپل امروز</b>\n\n"
            f"{name1} ❤️ {name2}\n\n"
            f"👍 <b>موافقان:</b> {agrees_text}\n"
            f"👎 <b>مخالفان:</b> {disagrees_text}"
        )[cite: 2]

        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("🟢 موافقم", callback_data="couple_agree"),
                InlineKeyboardButton("🔴 افتضاح", callback_data="couple_disagree")
            ]
        ])

        try:
            await query.message.edit_text(new_text, reply_markup=keyboard, parse_mode=ParseMode.HTML)[cite: 2]
        except Exception:
            pass[cite: 2]
        return[cite: 2]

    if data == "noop":
        await query.answer()[cite: 2]
        return[cite: 2]

    if not await is_admin_or_owner(context, chat_id, user_id):
        await query.answer("❌ دسترسی غیرمجاز!", show_alert=True)[cite: 2]
        return[cite: 2]

    if data == "panel_main":
        await render_main_panel_message(query)[cite: 2]
    elif data == "panel_media_lef":
        if user_id not in db["states"]["waiting_lef_media"]:
            db["states"]["waiting_lef_media"].append(user_id)[cite: 2]
            mark_db_dirty()[cite: 2]
            save_db()[cite: 2]
        await query.message.edit_text("🖼 لطفاً رسانه مورد نظر را ارسال کنید.\n\nبرای لغو /cancel را بزنید.")[cite: 2]
    elif data == "panel_foods":
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("➕ افزودن غذا", callback_data="food_add")],[cite: 2]
            [InlineKeyboardButton("➖ حذف غذا", callback_data="food_del")],[cite: 2]
            [InlineKeyboardButton("📋 لیست غذاها", callback_data="food_page_1")],[cite: 2]
            [InlineKeyboardButton("🔙 بازگشت", callback_data="panel_main")][cite: 2]
        ])
        await query.message.edit_text("🍽 <b>مدیریت غذاها</b>\n\nگزینه مورد نظر را انتخاب کنید:", reply_markup=keyboard, parse_mode=ParseMode.HTML)[cite: 2]
    elif data == "food_add":
        if user_id not in db["states"]["waiting_add_food"]:
            db["states"]["waiting_add_food"].append(user_id)[cite: 2]
            mark_db_dirty()[cite: 2]
            save_db()[cite: 2]
        await query.message.edit_text("➕ نام غذایی که می‌خواهید اضافه شود را بنویسید:\n\nبرای لغو /cancel را بزنید.")[cite: 2]
    elif data == "food_del":
        if user_id not in db["states"]["waiting_del_food"]:
            db["states"]["waiting_del_food"].append(user_id)[cite: 2]
            mark_db_dirty()[cite: 2]
            save_db()[cite: 2]
        await query.message.edit_text("➖ نام دقیق غذایی که می‌خواهید حذف شود را بنویسید:\n\nبرای لغو /cancel را بزنید.")[cite: 2]
    elif data == "panel_cooldown":
        if user_id not in db["states"]["waiting_cooldown"]:
            db["states"]["waiting_cooldown"].append(user_id)[cite: 2]
            mark_db_dirty()[cite: 2]
            save_db()[cite: 2]
        await query.message.edit_text(f"⏱ زمان فعلی محدودیت (Cooldown): <b>{db.get('cooldown_minutes', 10)} دقیقه</b>\n\nلطفاً زمان جدید را به دقیقه (عدد انگلیسی) وارد کنید:\n\nبرای لغو /cancel را بزنید.", parse_mode=ParseMode.HTML)[cite: 2]
    elif data == "panel_poem_names":
        if user_id not in db["states"]["waiting_poem_names"]:
            db["states"]["waiting_poem_names"].append(user_id)
            mark_db_dirty()
            save_db()
        current_names = ", ".join(db.get("custom_names", [])) or "هیچ اسمی ثبت نشده"
        await query.message.edit_text(f"📜 <b>اسامی فعلی برای شعرها:</b>\n{current_names}\n\nلطفاً اسامی جدید را یکی‌یکی بفرستید. وقتی تمام شد دستور <code>/done</code> را ارسال کنید.\nبرای لغو دستور /cancel را بزنید.", parse_mode=ParseMode.HTML)
    elif data.startswith("food_page_"):
        await render_food_list_page(query, db, page=int(data.replace("food_page_", "")))[cite: 2]
    elif data == "panel_features":
        await render_features_panel_message(query, db)[cite: 2]
    elif data.startswith("toggle_"):
        fk = data.replace("toggle_", "")[cite: 2]
        if fk in db["features"]:
            db["features"][fk] = not db["features"][fk][cite: 2]
            mark_db_dirty()[cite: 2]
            save_db()[cite: 2]
        await render_features_panel_message(query, db)[cite: 2]

    await query.answer()[cite: 2]

# ==========================================
# COMMAND HANDLERS
# ==========================================
async def command_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message:
        return[cite: 2]
    user_id = update.effective_user.id[cite: 2]
    chat_id = update.effective_chat.id[cite: 2]
    
    if not await is_admin_or_owner(context, chat_id, user_id):
        await update.message.reply_text("❌ شما دسترسی به پنل مدیریت را ندارید!")[cite: 2]
        return[cite: 2]

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🖼 رسانه لف", callback_data="panel_media_lef")],[cite: 2]
        [InlineKeyboardButton("🍽 مدیریت غذاها", callback_data="panel_foods")],[cite: 2]
        [InlineKeyboardButton("📜 اسامی شعرها", callback_data="panel_poem_names")],
        [InlineKeyboardButton("⏱ زمان محدودیت (Cooldown)", callback_data="panel_cooldown")],[cite: 2]
        [InlineKeyboardButton("⚙ مدیریت قابلیت ها", callback_data="panel_features")][cite: 2]
    ])
    await update.message.reply_text("مدیر عزیز\n\nچه چیزی را تغییر می‌دهید؟", reply_markup=keyboard)[cite: 2]

async def command_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message:
        return[cite: 2]
    user_id = update.effective_user.id[cite: 2]
    db = load_db()[cite: 2]
    
    cancelled = False[cite: 2]
    states = db.get("states", {})[cite: 2]
    for k in ["waiting_lef_media", "waiting_add_food", "waiting_del_food", "waiting_cooldown", "waiting_poem_names"]:
        if user_id in states.get(k, []):
            states[k].remove(user_id)[cite: 2]
            cancelled = True[cite: 2]
            
    if cancelled:
        mark_db_dirty()[cite: 2]
        save_db(force=True)[cite: 2]
        await update.message.reply_text("🚫 عملیات لغو شد.")[cite: 2]
    else:
        await update.message.reply_text("ℹ️ شما در هیچ حالت انتظاری قرار ندارید.")[cite: 2]

async def command_done(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message:
        return
    user_id = update.effective_user.id
    db = load_db()
    
    states = db.get("states", {})
    if user_id in states.get("waiting_poem_names", []):
        states["waiting_poem_names"].remove(user_id)
        mark_db_dirty()
        save_db(force=True)
        count = len(db.get("custom_names", []))
        await update.message.reply_text(f"✅ تنظیم اسامی به پایان رسید. تعداد کل اسامی ثبت‌شده: <b>{count}</b>", parse_mode=ParseMode.HTML)
    else:
        await update.message.reply_text("ℹ️ شما در حالت تنظیم اسامی قرار ندارید.")

# ==========================================
# MESSAGE HANDLER
# ==========================================
async def handle_messages(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message:
        return[cite: 2]

    db = load_db()[cite: 2]
    await register_member(update, db)[cite: 2]
    
    if update.effective_chat and update.effective_chat.type in ["group", "supergroup"]:
        setup_chat_jobs(context.job_queue, [update.effective_chat.id])[cite: 2]

    user_id = update.effective_user.id[cite: 2]
    chat_id = update.effective_chat.id[cite: 2]
    raw_text = update.message.text or ""[cite: 2]
    
    # --------------------------------------
    # ADMIN WAITING STATES
    # --------------------------------------
    if await is_admin_or_owner(context, chat_id, user_id):
        if user_id in db["states"].get("waiting_lef_media", []):
            media = None[cite: 2]
            if update.message.sticker:
                media = {"type": "sticker", "file_id": update.message.sticker.file_id}[cite: 2]
            elif update.message.photo:
                media = {"type": "photo", "file_id": update.message.photo[-1].file_id}[cite: 2]
            elif update.message.animation:
                media = {"type": "animation", "file_id": update.message.animation.file_id}[cite: 2]
            elif update.message.video:
                media = {"type": "video", "file_id": update.message.video.file_id}[cite: 2]
                
            if media:
                db["media_lef"] = media[cite: 2]
                db["states"]["waiting_lef_media"].remove(user_id)[cite: 2]
                mark_db_dirty()[cite: 2]
                save_db(force=True)[cite: 2]
                await update.message.reply_text("✅ رسانه لف ذخیره شد.")[cite: 2]
                return[cite: 2]
            else:
                await update.message.reply_text("❌ لطفاً یک رسانه ارسال کنید (یا /cancel را بزنید).")[cite: 2]
                return[cite: 2]

        if user_id in db["states"].get("waiting_add_food", []):
            if raw_text:
                food_item = raw_text.strip()[cite: 2]
                if food_item.lower() in [f.strip().lower() for f in db["foods"]]:
                    await update.message.reply_text("❌ این غذا قبلاً وجود داشته!")[cite: 2]
                else:
                    db["foods"].append(food_item)[cite: 2]
                    await update.message.reply_text(f"✅ «{food_item}» اضافه شد.")[cite: 2]
                db["states"]["waiting_add_food"].remove(user_id)[cite: 2]
                mark_db_dirty()[cite: 2]
                save_db(force=True)[cite: 2]
                return[cite: 2]

        if user_id in db["states"].get("waiting_del_food", []):
            if raw_text:
                food_item = raw_text.strip()[cite: 2]
                target_idx = next((i for i, f in enumerate(db["foods"]) if f.strip().lower() == food_item.lower()), None)[cite: 2]
                if target_idx is not None:
                    rm = db["foods"].pop(target_idx)[cite: 2]
                    await update.message.reply_text(f"✅ «{rm}» حذف شد.")[cite: 2]
                else:
                    await update.message.reply_text("❌ این غذا یافت نشد!")[cite: 2]
                db["states"]["waiting_del_food"].remove(user_id)[cite: 2]
                mark_db_dirty()[cite: 2]
                save_db(force=True)[cite: 2]
                return[cite: 2]

        if user_id in db["states"].get("waiting_cooldown", []):
            if raw_text and raw_text.isdigit():
                val = int(raw_text)[cite: 2]
                if val > 0:
                    db["cooldown_minutes"] = val[cite: 2]
                    await update.message.reply_text(f"✅ زمان محدودیت با موفقیت روی <b>{val} دقیقه</b> تنظیم شد.", parse_mode=ParseMode.HTML)[cite: 2]
                else:
                    await update.message.reply_text("❌ عدد باید بزرگتر از صفر باشد.")[cite: 2]
                db["states"]["waiting_cooldown"].remove(user_id)[cite: 2]
                mark_db_dirty()[cite: 2]
                save_db(force=True)[cite: 2]
                return[cite: 2]
            else:
                await update.message.reply_text("❌ لطفاً فقط یک عدد صحیح وارد کنید.")[cite: 2]
                return[cite: 2]

        if user_id in db["states"].get("waiting_poem_names", []):
            if raw_text and not raw_text.startswith("/"):
                name_item = raw_text.strip()
                if "custom_names" not in db:
                    db["custom_names"] = []
                db["custom_names"].append(name_item)
                mark_db_dirty()
                save_db(force=True)
                await update.message.reply_text(f"✅ اسم «{name_item}» ثبت شد. اسم بعدی را بفرستید یا /done را بزنید.")
                return

    features = db.get("features", {})[cite: 2]
    norm_text = normalize_text(raw_text)[cite: 2]

    # --------------------------------------
    # SPECIAL NAME RESPONSES (موسوی / خانم ادیبی)
    # --------------------------------------
    is_reply_to_bot = (
        update.message.reply_to_message and 
        update.message.reply_to_message.from_user and 
        update.message.reply_to_message.from_user.id == context.bot.id
    )

    if norm_text == "موسوی" or (is_reply_to_bot and "موسوی" in raw_text):
        await update.message.reply_text(
            '<b>چیکارم شوهرم داری بی‌حیا ! </b><tg-emoji emoji-id="5424906801931002013">🥹</tg-emoji>',
            parse_mode=ParseMode.HTML
        )
        return

    elif norm_text in ["ادیبی", "خانم ادیبی", "تو کی هستی"] or (is_reply_to_bot and any(k in raw_text for k in ["ادیبی", "خانم ادیبی", "تو کی هستی"])):
        await update.message.reply_text(
            '<b>بله خودم هستم چیکارم دارین؟ </b><tg-emoji emoji-id="5427008713266472251">🌟</tg-emoji>',
            parse_mode=ParseMode.HTML
        )
        return

    # ۱. ساعت جهانی پریمیوم (۱۴ کشور)
    if norm_text in ["ساعت جهانی", "ساعت"] and features.get("world_time", True):
        now_tehran = datetime.now(ZoneInfo("Asia/Tehran")).strftime("%H:%M:%S")[cite: 2]
        now_ny = datetime.now(ZoneInfo("America/New_York")).strftime("%H:%M:%S")[cite: 2]
        now_germany = datetime.now(ZoneInfo("Europe/Berlin")).strftime("%H:%M:%S")
        now_london = datetime.now(ZoneInfo("Europe/London")).strftime("%H:%M:%S")
        now_istanbul = datetime.now(ZoneInfo("Europe/Istanbul")).strftime("%H:%M:%S")[cite: 2]
        now_mumbai = datetime.now(ZoneInfo("Asia/Kolkata")).strftime("%H:%M:%S")[cite: 2]
        now_riyadh = datetime.now(ZoneInfo("Asia/Riyadh")).strftime("%H:%M:%S")[cite: 2]
        now_paris = datetime.now(ZoneInfo("Europe/Paris")).strftime("%H:%M:%S")[cite: 2]
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
            f'<b><tg-emoji emoji-id="6136551252781172945">🇹🇷</tg-emoji> ترکیه: {now_istanbul}</b>\n'
            f'<b><tg-emoji emoji-id="5202079966761590204">🇮🇳</tg-emoji> هندوستان: {now_mumbai}</b>\n'
            f'<b><tg-emoji emoji-id="5931269906434624310">🇸🇦</tg-emoji> عربستان: {now_riyadh}</b>\n'
            f'<b><tg-emoji emoji-id="5431782733376399004">🇫🇷</tg-emoji> فرانسه: {now_paris}</b>\n'
            f'<b><tg-emoji emoji-id="5226948110873278599">🇨🇳</tg-emoji> چین: {now_beijing}</b>\n'
            f'<b><tg-emoji emoji-id="5474542319673812606">🇻🇳</tg-emoji> ویتنام: {now_hanoi}</b>\n'
            f'<b><tg-emoji emoji-id="5228799250367788944">🇶🇦</tg-emoji> قطر: {now_doha}</b>\n'
            f'<b><tg-emoji emoji-id="5456531898304047227">🇰🇷</tg-emoji> کره جنوبی: {now_seoul}</b>\n'
            f'<b><tg-emoji emoji-id="5456261908069885892">🇯🇵</tg-emoji> ژاپن: {now_tokyo}</b>\n'
            f'<b><tg-emoji emoji-id="5382151560182642075">🇫🇮</tg-emoji> فنلاند: {now_helsinki}</b>'
        )
        await update.message.reply_text(msg, parse_mode=ParseMode.HTML)

    # ۲. خوشتیپ / خوژتیپ (با استایل اختصاصی پریمیوم و تگ مستقیم)
    elif norm_text in ["خوشتیپ کیه", "خوشتیپ کی", "خوژتیپ کیه", "خوژتیپ کی", "خوشتیپ", "خوژتیپ"] and features.get("handsome", True):
        word_label = "خوژتیپ" if "خوژ" in norm_text else "خوشتیپ"
        is_cd, rem_sec, cd_data = get_cooldown_remaining(db, chat_id, "handsome")[cite: 2]
        
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
            vm = await get_valid_group_members(context, chat_id, db)[cite: 2]
            if vm:
                tid, info = random.choice(vm)[cite: 2]
                target_mention = get_user_mention(int(tid), info["fullname"])
                set_cooldown_data(db, chat_id, "handsome", {"id": int(tid), "fullname": info["fullname"]})[cite: 2]
                
                msg = (
                    f'<b><tg-emoji emoji-id="5332699109168013117">🌟</tg-emoji> {word_label} گروه اینه :</b>\n\n'
                    f'<b><tg-emoji emoji-id="5321484996802797866">😎</tg-emoji> | {target_mention}</b>'
                )
                await update.message.reply_text(msg, parse_mode=ParseMode.HTML)

    # ۳. جنده (با تایمر و تک‌کلمه)
    elif norm_text in ["جنده کیه", "جنده کی", "جنده"] and features.get("jende", True):
        is_cd, rem_sec, cd_data = get_cooldown_remaining(db, chat_id, "jende")[cite: 2]
        if is_cd:
            m_rem, s_rem = divmod(rem_sec, 60)[cite: 2]
            target_mention = get_user_mention(cd_data["id"], cd_data["fullname"])[cite: 2]
            msg = (
                f"👑 <b>جنده گروه اینه:</b>\n\n{target_mention}\n\n"
                f"⏳ ولی <b>{m_rem} دقیقه و {s_rem} ثانیه</b> دیگه یکی دیگه مشخص میشه."
            )
            await update.message.reply_text(msg, parse_mode=ParseMode.HTML)[cite: 2]
        else:
            vm = await get_valid_group_members(context, chat_id, db)[cite: 2]
            if vm:
                tid, info = random.choice(vm)[cite: 2]
                set_cooldown_data(db, chat_id, "jende", {"id": int(tid), "fullname": info["fullname"]})[cite: 2]
                await update.message.reply_text(f"👑 <b>جنده گروه اینه</b>\n\n{get_user_mention(int(tid), info['fullname'])}", parse_mode=ParseMode.HTML)[cite: 2]

    # ۴. کونی (با تایمر و تک‌کلمه)
    elif norm_text in ["کونی کیه", "کونی کی", "کونی"] and features.get("koni", True):
        is_cd, rem_sec, cd_data = get_cooldown_remaining(db, chat_id, "koni")[cite: 2]
        if is_cd:
            m_rem, s_rem = divmod(rem_sec, 60)[cite: 2]
            target_mention = get_user_mention(cd_data["id"], cd_data["fullname"])[cite: 2]
            msg = (
                f"🍑 <b>کونی گروه اینه:</b>\n\n{target_mention}\n\n"
                f"⏳ ولی <b>{m_rem} دقیقه و {s_rem} ثانیه</b> دیگه یکی دیگه مشخص میشه."
            )
            await update.message.reply_text(msg, parse_mode=ParseMode.HTML)[cite: 2]
        else:
            vm = await get_valid_group_members(context, chat_id, db)[cite: 2]
            if vm:
                tid, info = random.choice(vm)[cite: 2]
                set_cooldown_data(db, chat_id, "koni", {"id": int(tid), "fullname": info["fullname"]})[cite: 2]
                await update.message.reply_text(f"🍑 <b>کونی گروه اینه</b>\n\n{get_user_mention(int(tid), info['fullname'])}", parse_mode=ParseMode.HTML)[cite: 2]

    # ۵. شیپ / کاپل (با دکمه‌های رنگی و تگ)
    elif norm_text in ["شیپ کن", "شیپ", "کاپل", "کاپل کن"] and features.get("ship", True):
        is_cd, rem_sec, cd_data = get_cooldown_remaining(db, chat_id, "ship")[cite: 2]
        if is_cd:
            m_rem, s_rem = divmod(rem_sec, 60)[cite: 2]
            name1 = get_user_mention(cd_data["u1"]["id"], cd_data["u1"]["name"])[cite: 2]
            name2 = get_user_mention(cd_data["u2"]["id"], cd_data["u2"]["name"])[cite: 2]
            msg = (
                f"❤️ <b>کاپل این دوره:</b>\n\n{name1} ❤️ {name2}\n\n"
                f"⏳ ولی <b>{m_rem} دقیقه و {s_rem} ثانیه</b> دیگه کاپل جدید مشخص میشه."
            )
            await update.message.reply_text(msg, parse_mode=ParseMode.HTML)[cite: 2]
        else:
            vm = await get_valid_group_members(context, chat_id, db)[cite: 2]
            if len(vm) >= 2:
                s = random.sample(vm, 2)[cite: 2]
                u1_dict = {"id": int(s[0][0]), "name": s[0][1]['fullname']}[cite: 2]
                u2_dict = {"id": int(s[1][0]), "name": s[1][1]['fullname']}[cite: 2]
                
                name1 = get_user_mention(u1_dict["id"], u1_dict["name"])[cite: 2]
                name2 = get_user_mention(u2_dict["id"], u2_dict["name"])[cite: 2]

                kb = InlineKeyboardMarkup([
                    [
                        InlineKeyboardButton("🟢 موافقم", callback_data="couple_agree"),
                        InlineKeyboardButton("🔴 افتضاح", callback_data="couple_disagree")
                    ]
                ])

                sent_msg = await update.message.reply_text(
                    f"❤️ <b>کاپل امروز</b>\n\n{name1} ❤️ {name2}\n\n👍 <b>موافقان:</b> هیچکس\n👎 <b>مخالفان:</b> هیچکس",
                    reply_markup=kb,
                    parse_mode=ParseMode.HTML
                )[cite: 2]

                if "couples" not in db:
                    db["couples"] = {}[cite: 2]
                db["couples"][str(sent_msg.message_id)] = {
                    "u1": u1_dict,
                    "u2": u2_dict,
                    "agrees": [],
                    "disagrees": []
                }[cite: 2]
                
                set_cooldown_data(db, chat_id, "ship", {"u1": u1_dict, "u2": u2_dict})[cite: 2]
            else:
                await update.message.reply_text("❌ اعضای کافی موجود نیست!")[cite: 2]

    # ۶. سیستم شعرخوانی
    elif norm_text in ["شعر", "شعر بگو", "شاعر شو"] and features.get("poems", True):
        custom_names = db.get("custom_names", [])
        if custom_names:
            target_name = random.choice(custom_names)
        else:
            vm = await get_valid_group_members(context, chat_id, db)
            if vm:
                tid, info = random.choice(vm)
                target_name = get_user_mention(int(tid), info["fullname"])
            else:
                target_name = "رفیق"

        poem_template = random.choice(DEFAULT_POEMS)
        final_poem = poem_template.format(name=target_name)
        await update.message.reply_text(f"📜 <b>{final_poem}</b>", parse_mode=ParseMode.HTML)

    # ۷. پیشنهاد غذا
    elif norm_text in ["غذا چی بخورم", "غذا چی بپزم", "غذا چی بخوریم", "غذا چی بپزیم"] and features.get("food", True):
        fl = db.get("foods", [])[cite: 2]
        if fl:
            await update.message.reply_text(f"😋 پیشنهاد من به تو:\n\n🍔 <b>{html.escape(random.choice(fl))}</b>", parse_mode=ParseMode.HTML)[cite: 2]

    # ۸. درصد کونی بودن
    elif norm_text == "این چقد کونیه" and features.get("koni_percent", True):
        if update.message.reply_to_message:
            tu = update.message.reply_to_message.from_user[cite: 2]
            await update.message.reply_text(f"{get_user_mention(tu.id, tu.full_name)}\n\n🤣 {random.randint(0, 100)}٪ کونیه", parse_mode=ParseMode.HTML)[cite: 2]

    # ۹. تشخیص «لف»
    elif LEF_PATTERN.search(raw_text) and features.get("lef", True):
        ml = db.get("media_lef")[cite: 2]
        if ml:
            mt, fi = ml["type"], ml["file_id"][cite: 2]
            if mt == "sticker": await update.message.reply_sticker(fi)[cite: 2]
            elif mt == "photo": await update.message.reply_photo(fi)[cite: 2]
            elif mt == "animation": await update.message.reply_animation(fi)[cite: 2]
            elif mt == "video": await update.message.reply_video(fi)[cite: 2]

# ==========================================
# GLOBAL ERROR HANDLER & MAIN
# ==========================================
async def global_error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    logger.error(f"Error: {context.error}", exc_info=context.error)[cite: 2]

def main():
    if not BOT_TOKEN or BOT_TOKEN == "YOUR_BOT_TOKEN_HERE":
        logger.critical("FATAL: BOT_TOKEN is missing!")[cite: 2]
        sys.exit(1)[cite: 2]

    load_db()[cite: 2]

    threading.Thread(target=run_health_check_server, daemon=True).start()[cite: 2]

    app = Application.builder().token(BOT_TOKEN).post_init(post_init).build()[cite: 2]

    app.add_handler(ChatMemberHandler(track_chats, ChatMemberHandler.MY_CHAT_MEMBER))[cite: 2]

    app.add_handler(CallbackQueryHandler(handle_callback_query))[cite: 2]
    app.add_handler(CommandHandler("panel", command_panel))[cite: 2]
    app.add_handler(CommandHandler("cancel", command_cancel))[cite: 2]
    app.add_handler(CommandHandler("done", command_done))
    app.add_handler(MessageHandler(filters.ALL & (~filters.COMMAND), handle_messages))[cite: 2]
    app.add_error_handler(global_error_handler)[cite: 2]

    logger.info("Bot is running...")[cite: 2]
    app.run_polling(drop_pending_updates=True)[cite: 2]

if __name__ == "__main__":
    main()[cite: 2]
