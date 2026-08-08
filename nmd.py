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
BOT_TOKEN = "8618205537:AAFCjx1_PkdC43ezimZgp-z5PAx0JKEmJqI"  # توکن ربات
OWNER_ID = 6749949992
DB_FILE = "db.json"
TEMP_DB_FILE = "db.json.tmp"
BROKEN_DB_FILE = "db.json.broken"

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

# ==========================================
# GLOBAL DB CACHE & DIRTY FLAG
# ==========================================
_DB_CACHE = None
_DB_DIRTY = False

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
]

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
        "members": {},
        "hourly_messages": {},
        "last_job_reset": 0,
        "active_chats": [],
        "foods": list(DEFAULT_FOODS),
        "custom_names": [],
        "media_lef": None,
        "cooldown_minutes": 10,
        "cooldowns": {},
        "couples": {},
        "features": {
            "world_time": True,
            "handsome": True,
            "jende": True,
            "koni": True,
            "ship": True,
            "food": True,
            "lef": True,
            "goh_khor": True,
            "koni_percent": True,
            "poems": True,
        },
        "states": {
            "waiting_lef_media": [],
            "waiting_add_food": [],
            "waiting_del_food": [],
            "waiting_cooldown": [],
            "waiting_poem_names": []
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
        logger.error(f"Database corrupted! Backing up to {BROKEN_DB_FILE}. Error: {e}")
        try:
            shutil.copy(DB_FILE, BROKEN_DB_FILE)
        except Exception as copy_err:
            logger.error(f"Backup failed: {copy_err}")
        
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
# HELPER FUNCTIONS
# ==========================================
def get_user_mention(user_id: int, fullname: str) -> str:
    clean_name = html.escape(fullname)
    return f'<a href="tg://user?id={user_id}">{clean_name}</a>'

async def is_user_in_chat(context: ContextTypes.DEFAULT_TYPE, chat_id: int, user_id: int) -> bool:
    try:
        member = await context.bot.get_chat_member(chat_id, user_id)
        return member.status in [
            ChatMemberStatus.MEMBER,
            ChatMemberStatus.ADMINISTRATOR,
            ChatMemberStatus.OWNER
        ]
    except Exception:
        return False

async def get_valid_group_members(context: ContextTypes.DEFAULT_TYPE, chat_id: int, db: dict) -> list:
    members = db.get("members", {})
    valid_members = []
    for uid_str, info in members.items():
        uid = int(uid_str)
        if await is_user_in_chat(context, chat_id, uid):
            valid_members.append((uid_str, info))
    return valid_members

async def is_admin_or_owner(context: ContextTypes.DEFAULT_TYPE, chat_id: int, user_id: int) -> bool:
    if user_id == OWNER_ID:
        return True
    try:
        member = await context.bot.get_chat_member(chat_id, user_id)
        return member.status in [ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER]
    except Exception as e:
        logger.error(f"Error checking admin status: {e}")
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
        if chat.id not in db["active_chats"]:
            db["active_chats"].append(chat.id)
            mark_db_dirty()
            
        current_count = db["hourly_messages"].get(user_id, 0)
        db["hourly_messages"][user_id] = current_count + 1
        mark_db_dirty()
        
    save_db()

# ==========================================
# COOLDOWN & TIMER SYSTEM
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
    if "cooldowns" not in db:
        db["cooldowns"] = {}
    if chat_str not in db["cooldowns"]:
        db["cooldowns"][chat_str] = {}
        
    db["cooldowns"][chat_str][feature] = {
        "timestamp": datetime.now().timestamp(),
        "data": data
    }
    mark_db_dirty()
    save_db()

# ==========================================
# WELCOME HANDLER (BOT ADDED TO GROUP)
# ==========================================
async def track_chats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    result = update.my_chat_member
    if not result:
        return

    new_status = result.new_chat_member.status
    if new_status in [ChatMemberStatus.MEMBER, ChatMemberStatus.ADMINISTRATOR]:
        welcome_msg = (
            "<b>سلام نینیا ، یه ربات سرگرمی اینجاست...! </b>"
            '<tg-emoji emoji-id="5276251363313996750">😊</tg-emoji>\n\n'
            "<b>شروع کنید به مسخره بازی که حال کنیم! </b>"
            '<tg-emoji emoji-id="5274211661870295868">😌</tg-emoji>'
        )
        try:
            await context.bot.send_message(
                chat_id=result.chat.id,
                text=welcome_msg,
                parse_mode=ParseMode.HTML
            )
        except Exception as e:
            logger.error(f"Failed to send welcome message: {e}")

# ==========================================
# JOB QUEUE SYSTEM
# ==========================================
async def hourly_goh_khor_job(context: ContextTypes.DEFAULT_TYPE):
    db = load_db()
    if not db["features"].get("goh_khor", True):
        return
        
    messages_data = db.get("hourly_messages", {})
    if not messages_data:
        return
        
    top_user_id = max(messages_data, key=lambda k: messages_data[k])
    max_msgs = messages_data[top_user_id]
    
    if max_msgs > 0:
        member_info = db["members"].get(top_user_id, {})
        fullname = member_info.get("fullname", "کاربر")
        mention = get_user_mention(int(top_user_id), fullname)
        
        text = f"🏆 <b>گوه خور این ساعت</b>\n\n{mention}\n\nتو این یک ساعت خیلی حرف زدی 😂"
        
        target_chat_id = context.job.chat_id
        if target_chat_id:
            try:
                await context.bot.send_message(
                    chat_id=target_chat_id,
                    text=text,
                    parse_mode=ParseMode.HTML
                )
            except Exception as e:
                logger.error(f"Job send error to {target_chat_id}: {e}")

    db["hourly_messages"] = {}
    db["last_job_reset"] = int(datetime.now().timestamp())
    mark_db_dirty()
    save_db(force=True)

def setup_chat_jobs(job_queue, active_chats: list):
    if not job_queue:
        return
    for chat_id in active_chats:
        job_name = f"goh_khor_{chat_id}"
        existing_jobs = job_queue.get_jobs_by_name(job_name)
        if not existing_jobs:
            job_queue.run_repeating(
                hourly_goh_khor_job,
                interval=3600,
                first=3600,
                chat_id=chat_id,
                name=job_name
            )

async def post_init(application: Application):
    db = load_db()
    setup_chat_jobs(application.job_queue, db.get("active_chats", []))

# ==========================================
# ADMIN PANEL RENDERING & PAGINATION
# ==========================================
async def render_main_panel_message(query):
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🖼 رسانه لف", callback_data="panel_media_lef")],
        [InlineKeyboardButton("🍽 مدیریت غذاها", callback_data="panel_foods")],
        [InlineKeyboardButton("📜 اسامی شعرها", callback_data="panel_poem_names")],
        [InlineKeyboardButton("⏱ زمان محدودیت (Cooldown)", callback_data="panel_cooldown")],
        [InlineKeyboardButton("⚙ مدیریت قابلیت ها", callback_data="panel_features")]
    ])
    await query.message.edit_text("مدیر عزیز\n\nچه چیزی را تغییر می‌دهید؟", reply_markup=keyboard)

async def render_features_panel_message(query, db: dict):
    feats = db.get("features", {})
    def status(key):
        return "✅" if feats.get(key, True) else "❌"

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton(f"{status('world_time')} 🌍 ساعت جهانی", callback_data="toggle_world_time")],
        [InlineKeyboardButton(f"{status('handsome')} 😎 خوشتیپ", callback_data="toggle_handsome")],
        [InlineKeyboardButton(f"{status('jende')} 😂 جنده", callback_data="toggle_jende")],
        [InlineKeyboardButton(f"{status('koni')} 🤣 کونی", callback_data="toggle_koni")],
        [InlineKeyboardButton(f"{status('ship')} ❤️ شیپ", callback_data="toggle_ship")],
        [InlineKeyboardButton(f"{status('food')} 🍽 غذا", callback_data="toggle_food")],
        [InlineKeyboardButton(f"{status('lef')} 🖼 لف", callback_data="toggle_lef")],
        [InlineKeyboardButton(f"{status('goh_khor')} 🏆 گوه خور", callback_data="toggle_goh_khor")],
        [InlineKeyboardButton(f"{status('koni_percent')} 📊 درصد", callback_data="toggle_koni_percent")],
        [InlineKeyboardButton("🔙 بازگشت", callback_data="panel_main")]
    ])
    await query.message.edit_text(
        "⚙ <b>مدیریت قابلیت‌ها</b>\n\nبا کلیک روی هر دکمه، وضعیت آن را روشن یا خاموش کنید:",
        reply_markup=keyboard,
        parse_mode=ParseMode.HTML
    )

async def render_food_list_page(query, db: dict, page: int = 1):
    foods = db.get("foods", [])
    per_page = 15
    total_pages = max(1, (len(foods) + per_page - 1) // per_page)
    page = max(1, min(page, total_pages))
    
    current_foods = foods[(page - 1) * per_page : page * per_page]
    food_str = "\n".join([f"• {html.escape(f)}" for f in current_foods])
    
    nav_buttons = []
    if page > 1:
        nav_buttons.append(InlineKeyboardButton("◀️ قبلی", callback_data=f"food_page_{page - 1}"))
    nav_buttons.append(InlineKeyboardButton(f"صفحه {page} از {total_pages}", callback_data="noop"))
    if page < total_pages:
        nav_buttons.append(InlineKeyboardButton("بعدی ▶️", callback_data=f"food_page_{page + 1}"))
        
    keyboard = InlineKeyboardMarkup([nav_buttons, [InlineKeyboardButton("🔙 بازگشت", callback_data="panel_foods")]])
    await query.message.edit_text(
        f"📋 <b>لیست غذاها (تعداد کل: {len(foods)})</b>\n\n{food_str}",
        reply_markup=keyboard,
        parse_mode=ParseMode.HTML
    )

# ==========================================
# CALLBACK QUERY HANDLER
# ==========================================
async def handle_callback_query(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data
    user_id = query.from_user.id
    chat_id = update.effective_chat.id if update.effective_chat else 0
    db = load_db()

    if data in ["couple_agree", "couple_disagree"]:
        msg_id = str(query.message.message_id)
        couples = db.get("couples", {})
        
        if msg_id not in couples:
            await query.answer("❌ اطلاعات این شیپ منقضی شده است!", show_alert=True)
            return

        couple_data = couples[msg_id]
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
            f"❤️ <b>کاپل امروز</b>\n\n"
            f"{name1} ❤️ {name2}\n\n"
            f"👍 <b>موافقان:</b> {agrees_text}\n"
            f"👎 <b>مخالفان:</b> {disagrees_text}"
        )

        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("🟢 موافقم", callback_data="couple_agree"),
                InlineKeyboardButton("🔴 افتضاح", callback_data="couple_disagree")
            ]
        ])

        try:
            await query.message.edit_text(new_text, reply_markup=keyboard, parse_mode=ParseMode.HTML)
        except Exception:
            pass
        return

    if data == "noop":
        await query.answer()
        return

    if not await is_admin_or_owner(context, chat_id, user_id):
        await query.answer("❌ دسترسی غیرمجاز!", show_alert=True)
        return

    if data == "panel_main":
        await render_main_panel_message(query)
    elif data == "panel_media_lef":
        if user_id not in db["states"]["waiting_lef_media"]:
            db["states"]["waiting_lef_media"].append(user_id)
            mark_db_dirty()
            save_db()
        await query.message.edit_text("🖼 لطفاً رسانه مورد نظر را ارسال کنید.\n\nبرای لغو /cancel را بزنید.")
    elif data == "panel_foods":
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("➕ افزودن غذا", callback_data="food_add")],
            [InlineKeyboardButton("➖ حذف غذا", callback_data="food_del")],
            [InlineKeyboardButton("📋 لیست غذاها", callback_data="food_page_1")],
            [InlineKeyboardButton("🔙 بازگشت", callback_data="panel_main")]
        ])
        await query.message.edit_text("🍽 <b>مدیریت غذاها</b>\n\nگزینه مورد نظر را انتخاب کنید:", reply_markup=keyboard, parse_mode=ParseMode.HTML)
    elif data == "food_add":
        if user_id not in db["states"]["waiting_add_food"]:
            db["states"]["waiting_add_food"].append(user_id)
            mark_db_dirty()
            save_db()
        await query.message.edit_text("➕ نام غذایی که می‌خواهید اضافه شود را بنویسید:\n\nبرای لغو /cancel را بزنید.")
    elif data == "food_del":
        if user_id not in db["states"]["waiting_del_food"]:
            db["states"]["waiting_del_food"].append(user_id)
            mark_db_dirty()
            save_db()
        await query.message.edit_text("➖ نام دقیق غذایی که می‌خواهید حذف شود را بنویسید:\n\nبرای لغو /cancel را بزنید.")
    elif data == "panel_cooldown":
        if user_id not in db["states"]["waiting_cooldown"]:
            db["states"]["waiting_cooldown"].append(user_id)
            mark_db_dirty()
            save_db()
        await query.message.edit_text(f"⏱ زمان فعلی محدودیت (Cooldown): <b>{db.get('cooldown_minutes', 10)} دقیقه</b>\n\nلطفاً زمان جدید را به دقیقه (عدد انگلیسی) وارد کنید:\n\nبرای لغو /cancel را بزنید.", parse_mode=ParseMode.HTML)
    elif data == "panel_poem_names":
        if user_id not in db["states"]["waiting_poem_names"]:
            db["states"]["waiting_poem_names"].append(user_id)
            mark_db_dirty()
            save_db()
        current_names = ", ".join(db.get("custom_names", [])) or "هیچ اسمی ثبت نشده"
        await query.message.edit_text(f"📜 <b>اسامی فعلی برای شعرها:</b>\n{current_names}\n\nلطفاً اسامی جدید را یکی‌یکی بفرستید. وقتی تمام شد دستور <code>/done</code> را ارسال کنید.\nبرای لغو دستور /cancel را بزنید.", parse_mode=ParseMode.HTML)
    elif data.startswith("food_page_"):
        await render_food_list_page(query, db, page=int(data.replace("food_page_", "")))
    elif data == "panel_features":
        await render_features_panel_message(query, db)
    elif data.startswith("toggle_"):
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
async def command_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message:
        return
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    
    if not await is_admin_or_owner(context, chat_id, user_id):
        await update.message.reply_text("❌ شما دسترسی به پنل مدیریت را ندارید!")
        return

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🖼 رسانه لف", callback_data="panel_media_lef")],
        [InlineKeyboardButton("🍽 مدیریت غذاها", callback_data="panel_foods")],
        [InlineKeyboardButton("📜 اسامی شعرها", callback_data="panel_poem_names")],
        [InlineKeyboardButton("⏱ زمان محدودیت (Cooldown)", callback_data="panel_cooldown")],
        [InlineKeyboardButton("⚙ مدیریت قابلیت ها", callback_data="panel_features")]
    ])
    await update.message.reply_text("مدیر عزیز\n\nچه چیزی را تغییر می‌دهید؟", reply_markup=keyboard)

async def command_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message:
        return
    user_id = update.effective_user.id
    db = load_db()
    
    cancelled = False
    states = db.get("states", {})
    for k in ["waiting_lef_media", "waiting_add_food", "waiting_del_food", "waiting_cooldown", "waiting_poem_names"]:
        if user_id in states.get(k, []):
            states[k].remove(user_id)
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
        return

    db = load_db()
    await register_member(update, db)
    
    if update.effective_chat and update.effective_chat.type in ["group", "supergroup"]:
        setup_chat_jobs(context.job_queue, [update.effective_chat.id])

    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    raw_text = update.message.text or ""
    
    # --------------------------------------
    # ADMIN WAITING STATES
    # --------------------------------------
    if await is_admin_or_owner(context, chat_id, user_id):
        if user_id in db["states"].get("waiting_lef_media", []):
            media = None
            if update.message.sticker:
                media = {"type": "sticker", "file_id": update.message.sticker.file_id}
            elif update.message.photo:
                media = {"type": "photo", "file_id": update.message.photo[-1].file_id}
            elif update.message.animation:
                media = {"type": "animation", "file_id": update.message.animation.file_id}
            elif update.message.video:
                media = {"type": "video", "file_id": update.message.video.file_id}
                
            if media:
                db["media_lef"] = media
                db["states"]["waiting_lef_media"].remove(user_id)
                mark_db_dirty()
                save_db(force=True)
                await update.message.reply_text("✅ رسانه لف ذخیره شد.")
                return
            else:
                await update.message.reply_text("❌ لطفاً یک رسانه ارسال کنید (یا /cancel را بزنید).")
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

        if user_id in db["states"].get("waiting_cooldown", []):
            if raw_text and raw_text.isdigit():
                val = int(raw_text)
                if val > 0:
                    db["cooldown_minutes"] = val
                    await update.message.reply_text(f"✅ زمان محدودیت با موفقیت روی <b>{val} دقیقه</b> تنظیم شد.", parse_mode=ParseMode.HTML)
                else:
                    await update.message.reply_text("❌ عدد باید بزرگتر از صفر باشد.")
                db["states"]["waiting_cooldown"].remove(user_id)
                mark_db_dirty()
                save_db(force=True)
                return
            else:
                await update.message.reply_text("❌ لطفاً فقط یک عدد صحیح وارد کنید.")
                return

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

    features = db.get("features", {})
    norm_text = normalize_text(raw_text)

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
            vm = await get_valid_group_members(context, chat_id, db)
            if vm:
                tid, info = random.choice(vm)
                target_mention = get_user_mention(int(tid), info["fullname"])
                set_cooldown_data(db, chat_id, "handsome", {"id": int(tid), "fullname": info["fullname"]})
                
                msg = (
                    f'<b><tg-emoji emoji-id="5332699109168013117">🌟</tg-emoji> {word_label} گروه اینه :</b>\n\n'
                    f'<b><tg-emoji emoji-id="5321484996802797866">😎</tg-emoji> | {target_mention}</b>'
                )
                await update.message.reply_text(msg, parse_mode=ParseMode.HTML)

    # ۳. جنده (با تایمر و تک‌کلمه)
    elif norm_text in ["جنده کیه", "جنده کی", "جنده"] and features.get("jende", True):
        is_cd, rem_sec, cd_data = get_cooldown_remaining(db, chat_id, "jende")
        if is_cd:
            m_rem, s_rem = divmod(rem_sec, 60)
            target_mention = get_user_mention(cd_data["id"], cd_data["fullname"])
            msg = (
                f"👑 <b>جنده گروه اینه:</b>\n\n{target_mention}\n\n"
                f"⏳ ولی <b>{m_rem} دقیقه و {s_rem} ثانیه</b> دیگه یکی دیگه مشخص میشه."
            )
            await update.message.reply_text(msg, parse_mode=ParseMode.HTML)
        else:
            vm = await get_valid_group_members(context, chat_id, db)
            if vm:
                tid, info = random.choice(vm)
                set_cooldown_data(db, chat_id, "jende", {"id": int(tid), "fullname": info["fullname"]})
                await update.message.reply_text(f"👑 <b>جنده گروه اینه</b>\n\n{get_user_mention(int(tid), info['fullname'])}", parse_mode=ParseMode.HTML)

    # ۴. کونی (با تایمر و تک‌کلمه)
    elif norm_text in ["کونی کیه", "کونی کی", "کونی"] and features.get("koni", True):
        is_cd, rem_sec, cd_data = get_cooldown_remaining(db, chat_id, "koni")
        if is_cd:
            m_rem, s_rem = divmod(rem_sec, 60)
            target_mention = get_user_mention(cd_data["id"], cd_data["fullname"])
            msg = (
                f"🍑 <b>کونی گروه اینه:</b>\n\n{target_mention}\n\n"
                f"⏳ ولی <b>{m_rem} دقیقه و {s_rem} ثانیه</b> دیگه یکی دیگه مشخص میشه."
            )
            await update.message.reply_text(msg, parse_mode=ParseMode.HTML)
        else:
            vm = await get_valid_group_members(context, chat_id, db)
            if vm:
                tid, info = random.choice(vm)
                set_cooldown_data(db, chat_id, "koni", {"id": int(tid), "fullname": info["fullname"]})
                await update.message.reply_text(f"🍑 <b>کونی گروه اینه</b>\n\n{get_user_mention(int(tid), info['fullname'])}", parse_mode=ParseMode.HTML)

    # ۵. شیپ / کاپل (با دکمه‌های رنگی و تگ)
    elif norm_text in ["شیپ کن", "شیپ", "کاپل", "کاپل کن"] and features.get("ship", True):
        is_cd, rem_sec, cd_data = get_cooldown_remaining(db, chat_id, "ship")
        if is_cd:
            m_rem, s_rem = divmod(rem_sec, 60)
            name1 = get_user_mention(cd_data["u1"]["id"], cd_data["u1"]["name"])
            name2 = get_user_mention(cd_data["u2"]["id"], cd_data["u2"]["name"])
            msg = (
                f"❤️ <b>کاپل این دوره:</b>\n\n{name1} ❤️ {name2}\n\n"
                f"⏳ ولی <b>{m_rem} دقیقه و {s_rem} ثانیه</b> دیگه کاپل جدید مشخص میشه."
            )
            await update.message.reply_text(msg, parse_mode=ParseMode.HTML)
        else:
            vm = await get_valid_group_members(context, chat_id, db)
            if len(vm) >= 2:
                s = random.sample(vm, 2)
                u1_dict = {"id": int(s[0][0]), "name": s[0][1]['fullname']}
                u2_dict = {"id": int(s[1][0]), "name": s[1][1]['fullname']}
                
                name1 = get_user_mention(u1_dict["id"], u1_dict["name"])
                name2 = get_user_mention(u2_dict["id"], u2_dict["name"])

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
                )

                if "couples" not in db:
                    db["couples"] = {}
                db["couples"][str(sent_msg.message_id)] = {
                    "u1": u1_dict,
                    "u2": u2_dict,
                    "agrees": [],
                    "disagrees": []
                }
                
                set_cooldown_data(db, chat_id, "ship", {"u1": u1_dict, "u2": u2_dict})
            else:
                await update.message.reply_text("❌ اعضای کافی موجود نیست!")

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
        fl = db.get("foods", [])
        if fl:
            await update.message.reply_text(f"😋 پیشنهاد من به تو:\n\n🍔 <b>{html.escape(random.choice(fl))}</b>", parse_mode=ParseMode.HTML)

    # ۸. درصد کونی بودن
    elif norm_text == "این چقد کونیه" and features.get("koni_percent", True):
        if update.message.reply_to_message:
            tu = update.message.reply_to_message.from_user
            await update.message.reply_text(f"{get_user_mention(tu.id, tu.full_name)}\n\n🤣 {random.randint(0, 100)}٪ کونیه", parse_mode=ParseMode.HTML)

    # ۹. تشخیص «لف»
    elif LEF_PATTERN.search(raw_text) and features.get("lef", True):
        ml = db.get("media_lef")
        if ml:
            mt, fi = ml["type"], ml["file_id"]
            if mt == "sticker": await update.message.reply_sticker(fi)
            elif mt == "photo": await update.message.reply_photo(fi)
            elif mt == "animation": await update.message.reply_animation(fi)
            elif mt == "video": await update.message.reply_video(fi)

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
    app.add_handler(CommandHandler("panel", command_panel))
    app.add_handler(CommandHandler("cancel", command_cancel))
    app.add_handler(CommandHandler("done", command_done))
    app.add_handler(MessageHandler(filters.ALL & (~filters.COMMAND), handle_messages))
    app.add_error_handler(global_error_handler)

    logger.info("Bot is running...")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
