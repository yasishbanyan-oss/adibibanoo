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
    ContextTypes,
    filters,
)

# ==========================================
# CONFIGURATION & LOGGING
# ==========================================
BOT_TOKEN = "8618205537:AAGXWSVJc3YhDT07aMRFwkPCl05mUVlPsso"  # توکن ربات خود را اینجا وارد کنید
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
        # خاموش کردن لاگ‌های تکراری HTTP
        return

def run_health_check_server():
    port = int(os.environ.get("PORT", 8080))
    server = HTTPServer(("0.0.0.0", port), HealthCheckHandler)
    logger.info(f"Dummy HTTP server running on port {port}")
    server.serve_forever()

# ==========================================
# ADVANCED REGEX PATTERNS & TEXT NORMALIZER
# ==========================================
# Regex دقیق برای تشخیص حالت‌های مختلف «لف» بدون تداخل با کلمات نامرتبط
LEF_PATTERN = re.compile(
    r"(?:\b|(?<=\s))ل+[فف]*[عع]*[هه]*(?:\s*(?:داد|بده|میده|میدم|میخوام))?(?=\s|[.,!?؛؟]|$)",
    re.IGNORECASE
)

def normalize_text(text: str) -> str:
    """
    نرمال‌سازی پیشرفته متن:
    - حذف علامت سؤال و علائم نگارشی
    - حذف فاصله‌های اضافی و نیم‌فاصله‌ها
    - حذف تکرار حروف کشیده شده (مثلاً 'خووووشتیپ' -> 'خوشتیپ')
    """
    if not text:
        return ""
    
    # حذف علائم نگارشی و علامت سؤال
    text = re.sub(r"[؟?\.,!؛\-_]", " ", text)
    # جایگزینی نیم‌فاصله با فاصله عادی
    text = text.replace("\u200c", " ")
    
    # استانداردسازی حروف کشیده شده (کاهش ۳ یا چند حرف تکراری به ۲ حرف برای تحلیل بهینه)
    text = re.sub(r"(.)\1{2,}", r"\1", text)
    
    # اصلاح تکرارهای رایج مانند "کیههه" -> "کیه"، "خوووشتیپ" -> "خوشتیپ"
    text = re.sub(r"ه{2,}", "ه", text)
    text = re.sub(r"و{2,}", "و", text)
    text = re.sub(r"ی{2,}", "ی", text)
    
    # حذف فاصله‌های اضافی بین کلمات
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
# DATABASE HELPER
# ==========================================
def get_default_db_structure() -> dict:
    return {
        "members": {},          # {user_id: {"username": ..., "fullname": ...}}
        "hourly_messages": {}, # {user_id: count}
        "last_job_reset": 0,    # timestamp
        "active_chats": [],     # لیست chat_id گروه‌های فعال
        "foods": list(DEFAULT_FOODS),
        "media_lef": None,      # {"type": ..., "file_id": ...}
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
        },
        "states": {
            "waiting_lef_media": [],
            "waiting_add_food": [],
            "waiting_del_food": []
        }
    }

def load_db() -> dict:
    """بارگیری دیتابیس JSON با حافظه کش (In-Memory) و پشتیبان‌گیری در صورت خرابی"""
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
        logger.error(f"Database file is corrupted! Backing up to {BROKEN_DB_FILE}. Error: {e}")
        try:
            shutil.copy(DB_FILE, BROKEN_DB_FILE)
        except Exception as copy_err:
            logger.error(f"Could not backup broken DB file: {copy_err}")
        
        _DB_CACHE = default_struct
        save_db(force=True)
        return _DB_CACHE

def mark_db_dirty():
    """علامت‌گذاری دیتابیس جهت بازنویسی روی دیسک در صورت وجود تغییرات"""
    global _DB_DIRTY
    _DB_DIRTY = True

def save_db(force: bool = False):
    """ذخیره اتمی (Atomic Write) دیتابیس فقط در صورت بروز تغییرات (Dirty Flag)"""
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
        logger.error(f"Error saving DB safely: {e}")

# ==========================================
# HELPER FUNCTIONS
# ==========================================
def get_user_mention(user_id: int, fullname: str) -> str:
    """ایجاد منشن اختصاصی HTML با فرار ایمن کاراکترها (html.escape)"""
    clean_name = html.escape(fullname)
    return f'<a href="tg://user?id={user_id}">{clean_name}</a>'

async def is_user_in_chat(context: ContextTypes.DEFAULT_TYPE, chat_id: int, user_id: int) -> bool:
    """بررسی عضویت فعلی کاربر در گروه جهت حذف اعضای خارج شده"""
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
    """استخراج اعضای معتبر موجود در گروه"""
    members = db.get("members", {})
    valid_members = []
    
    for uid_str, info in members.items():
        uid = int(uid_str)
        if await is_user_in_chat(context, chat_id, uid):
            valid_members.append((uid_str, info))
            
    return valid_members

async def is_admin_or_owner(context: ContextTypes.DEFAULT_TYPE, chat_id: int, user_id: int) -> bool:
    """بررسی دسترسی ادمین گروه یا Owner سیستم"""
    if user_id == OWNER_ID:
        return True
    try:
        member = await context.bot.get_chat_member(chat_id, user_id)
        return member.status in [ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER]
    except Exception as e:
        logger.error(f"Error checking admin status: {e}")
        return False

async def register_member(update: Update, db: dict):
    """ثبت اطلاعات کاربر، آمار همه‌جانبه تمام پیام‌ها و لیست چت‌های فعال"""
    user = update.effective_user
    chat = update.effective_chat
    
    if not user or user.is_bot:
        return
        
    user_id = str(user.id)
    fullname = user.full_name or "کاربر"
    username = user.username or ""
    
    if user_id not in db["members"] or db["members"][user_id].get("fullname") != fullname:
        db["members"][user_id] = {
            "username": username,
            "fullname": fullname
        }
        mark_db_dirty()
    
    # شمارش تمام پیام‌ها (متن، عکس، استیکر، ویس، گیف، ویدیو، فایل و...)
    if chat and chat.type in ["group", "supergroup"]:
        if chat.id not in db["active_chats"]:
            db["active_chats"].append(chat.id)
            mark_db_dirty()
            
        current_count = db["hourly_messages"].get(user_id, 0)
        db["hourly_messages"][user_id] = current_count + 1
        mark_db_dirty()
        
    save_db()

# ==========================================
# JOB QUEUE SYSTEM
# ==========================================
async def hourly_goh_khor_job(context: ContextTypes.DEFAULT_TYPE):
    """جوب زمان‌بندی شده برای تعیین پرپیام‌ترین کاربر در هر گروه"""
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
        
        text = (
            f"🏆 <b>گووه خور این ساعت</b>\n\n"
            f"{mention}\n\n"
            f"تو این یک ساعت خیلی حرف زدی 😂"
        )
        
        target_chat_id = context.job.chat_id
        if target_chat_id:
            try:
                await context.bot.send_message(
                    chat_id=target_chat_id,
                    text=text,
                    parse_mode=ParseMode.HTML
                )
            except Exception as e:
                logger.error(f"Failed to send hourly job message to {target_chat_id}: {e}")

    db["hourly_messages"] = {}
    db["last_job_reset"] = int(datetime.now().timestamp())
    mark_db_dirty()
    save_db(force=True)

def setup_chat_jobs(job_queue, active_chats: list):
    """ثبت یا راه‌اندازی مجدد بدون تکرار Job برای تمامی گروه‌های ثبت شده"""
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
    """راه‌اندازی JobQueue پس از شروع به‌کار ربات"""
    db = load_db()
    setup_chat_jobs(application.job_queue, db.get("active_chats", []))

# ==========================================
# ADMIN PANEL RENDERING & PAGINATION
# ==========================================
async def render_main_panel_message(query):
    """ویرایش پیام به منوی اصلی پنل"""
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🖼 رسانه لف", callback_data="panel_media_lef")],
        [InlineKeyboardButton("🍽 مدیریت غذاها", callback_data="panel_foods")],
        [InlineKeyboardButton("⚙ مدیریت قابلیت ها", callback_data="panel_features")]
    ])
    await query.message.edit_text(
        "مدیر عزیز\n\nچه چیزی را تغییر می‌دهید؟",
        reply_markup=keyboard
    )

async def render_features_panel_message(query, db: dict):
    """ویرایش پیام به منوی مدیریت قابلیت‌ها بدون ارسال پیام جدید"""
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
        [InlineKeyboardButton(f"{status('goh_khor')} 🏆 گووه خور", callback_data="toggle_goh_khor")],
        [InlineKeyboardButton(f"{status('koni_percent')} 📊 درصد", callback_data="toggle_koni_percent")],
        [InlineKeyboardButton("🔙 بازگشت", callback_data="panel_main")]
    ])
    
    await query.message.edit_text(
        "⚙ <b>مدیریت قابلیت‌ها</b>\n\nبا کلیک روی هر دکمه، وضعیت آن را روشن یا خاموش کنید:",
        reply_markup=keyboard,
        parse_mode=ParseMode.HTML
    )

async def render_food_list_page(query, db: dict, page: int = 1):
    """نمایش لیست غذاها به همراه صفحه‌بندی (Pagination)"""
    foods = db.get("foods", [])
    per_page = 15
    total_pages = max(1, (len(foods) + per_page - 1) // per_page)
    
    page = max(1, min(page, total_pages))
    start_idx = (page - 1) * per_page
    end_idx = start_idx + per_page
    
    current_foods = foods[start_idx:end_idx]
    food_str = "\n".join([f"• {html.escape(f)}" for f in current_foods])
    
    nav_buttons = []
    if page > 1:
        nav_buttons.append(InlineKeyboardButton("◀️ قبلی", callback_data=f"food_page_{page - 1}"))
    nav_buttons.append(InlineKeyboardButton(f"صفحه {page} از {total_pages}", callback_data="noop"))
    if page < total_pages:
        nav_buttons.append(InlineKeyboardButton("بعدی ▶️", callback_data=f"food_page_{page + 1}"))
        
    keyboard = InlineKeyboardMarkup([
        nav_buttons,
        [InlineKeyboardButton("🔙 بازگشت", callback_data="panel_foods")]
    ])
    
    await query.message.edit_text(
        f"📋 <b>لیست غذاها (تعداد کل: {len(foods)})</b>\n\n{food_str}",
        reply_markup=keyboard,
        parse_mode=ParseMode.HTML
    )

# ==========================================
# CALLBACK QUERY HANDLER
# ==========================================
async def handle_callback_query(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """هندلر مرکزی تمامی دکمه‌های شیشه‌ای با پاسخ قطعی به همه queryها"""
    query = update.callback_query
    data = query.data
    user_id = query.from_user.id
    chat_id = update.effective_chat.id if update.effective_chat else 0
    db = load_db()

    # ۱. دکمه‌های عمومی شیپ
    if data == "ship_yes":
        await query.answer("خایمالی نکن 😂", show_alert=True)
        return
    elif data == "ship_no":
        await query.answer("بکیرم 😂", show_alert=True)
        return
    elif data == "noop":
        await query.answer()
        return

    # ۲. بررسی احراز هویت ادمین/مالک
    if not await is_admin_or_owner(context, chat_id, user_id):
        await query.answer("❌ دسترسی غیرمجاز! فقط مدیران گروه و Owner دسترسی دارند.", show_alert=True)
        return

    # ۳. پیمایش پنل
    if data == "panel_main":
        await render_main_panel_message(query)
        await query.answer()
        return

    elif data == "panel_media_lef":
        if user_id not in db["states"]["waiting_lef_media"]:
            db["states"]["waiting_lef_media"].append(user_id)
            mark_db_dirty()
            save_db()
        await query.message.edit_text("🖼 لطفاً رسانه مورد نظر (عکس، استیکر، گیف یا ویدیو) را ارسال کنید.\n\nبرای لغو دستور /cancel را بزنید.")
        await query.answer()
        return

    elif data == "panel_foods":
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("➕ افزودن غذا", callback_data="food_add")],
            [InlineKeyboardButton("➖ حذف غذا", callback_data="food_del")],
            [InlineKeyboardButton("📋 لیست غذاها", callback_data="food_page_1")],
            [InlineKeyboardButton("🔙 بازگشت", callback_data="panel_main")]
        ])
        await query.message.edit_text("🍽 <b>مدیریت غذاها</b>\n\nگزینه مورد نظر را انتخاب کنید:", reply_markup=keyboard, parse_mode=ParseMode.HTML)
        await query.answer()
        return

    elif data == "food_add":
        if user_id not in db["states"]["waiting_add_food"]:
            db["states"]["waiting_add_food"].append(user_id)
            mark_db_dirty()
            save_db()
        await query.message.edit_text("➕ نام غذایی که می‌خواهید اضافه شود را بنویسید:\n\nبرای لغو دستور /cancel را بزنید.")
        await query.answer()
        return

    elif data == "food_del":
        if user_id not in db["states"]["waiting_del_food"]:
            db["states"]["waiting_del_food"].append(user_id)
            mark_db_dirty()
            save_db()
        await query.message.edit_text("➖ نام دقیق غذایی که می‌خواهید حذف شود را بنویسید:\n\nبرای لغو دستور /cancel را بزنید.")
        await query.answer()
        return

    elif data.startswith("food_page_"):
        page_num = int(data.replace("food_page_", ""))
        await render_food_list_page(query, db, page=page_num)
        await query.answer()
        return

    elif data == "panel_features":
        await render_features_panel_message(query, db)
        await query.answer()
        return

    elif data.startswith("toggle_"):
        feature_key = data.replace("toggle_", "")
        if feature_key in db["features"]:
            db["features"][feature_key] = not db["features"][feature_key]
            mark_db_dirty()
            save_db()
        await render_features_panel_message(query, db)
        await query.answer()
        return

    await query.answer()

# ==========================================
# COMMAND HANDLERS
# ==========================================
async def command_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """هندلر دستور /panel"""
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
        [InlineKeyboardButton("⚙ مدیریت قابلیت ها", callback_data="panel_features")]
    ])
    
    await update.message.reply_text(
        "مدیر عزیز\n\nچه چیزی را تغییر می‌دهید؟",
        reply_markup=keyboard
    )

async def command_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """هندلر دستور /cancel جهت خروج از تمامی حالت‌های انتظار بدون ذخیره اطلاعات"""
    if not update.message:
        return
        
    user_id = update.effective_user.id
    db = load_db()
    
    cancelled = False
    states = db.get("states", {})
    
    for key in ["waiting_lef_media", "waiting_add_food", "waiting_del_food"]:
        if user_id in states.get(key, []):
            states[key].remove(user_id)
            cancelled = True
            
    if cancelled:
        mark_db_dirty()
        save_db(force=True)
        await update.message.reply_text("🚫 عملیات لغو شد و از حالت انتظار خارج شدید.")
    else:
        await update.message.reply_text("ℹ️ شما در هیچ حالت انتظاری قرار ندارید.")

# ==========================================
# MESSAGE HANDLER
# ==========================================
async def handle_messages(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """هندلر مرکزی پیام‌ها، پردازش استیت‌های مدیریت و قابلیت‌ها"""
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
    # PROCESS WAITING ADMIN STATES
    # --------------------------------------
    if await is_admin_or_owner(context, chat_id, user_id):
        # دریافت رسانه لف
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
                await update.message.reply_text("✅ رسانه لف با موفقیت ذخیره شد.")
                return
            else:
                await update.message.reply_text("❌ لطفاً یک عکس، استیکر، گیف یا ویدیو ارسال کنید.\n(برای لغو /cancel را بزنید)")
                return

        # افزودن غذا (جلوگیری از افزودن تکراری)
        if user_id in db["states"].get("waiting_add_food", []):
            if raw_text:
                food_item = raw_text.strip()
                normalized_foods = [f.strip().lower() for f in db["foods"]]
                
                if food_item.lower() in normalized_foods:
                    await update.message.reply_text("❌ این غذا قبلاً در لیست وجود داشته است!")
                else:
                    db["foods"].append(food_item)
                    await update.message.reply_text(f"✅ غذای «{food_item}» به لیست اضافه شد.")
                
                db["states"]["waiting_add_food"].remove(user_id)
                mark_db_dirty()
                save_db(force=True)
                return

        # حذف غذا
        if user_id in db["states"].get("waiting_del_food", []):
            if raw_text:
                food_item = raw_text.strip()
                target_idx = None
                for idx, f in enumerate(db["foods"]):
                    if f.strip().lower() == food_item.lower():
                        target_idx = idx
                        break
                        
                if target_idx is not None:
                    removed_food = db["foods"].pop(target_idx)
                    await update.message.reply_text(f"✅ غذای «{removed_food}» از لیست حذف شد.")
                else:
                    await update.message.reply_text("❌ این غذا در لیست یافت نشد!")
                
                db["states"]["waiting_del_food"].remove(user_id)
                mark_db_dirty()
                save_db(force=True)
                return

    features = db.get("features", {})
    norm_text = normalize_text(raw_text)

    # ۱. ساعت جهانی
    if norm_text in ["ساعت جهانی", "ساعت"] and features.get("world_time", True):
        tehran_tz = ZoneInfo("Asia/Tehran")
        ny_tz = ZoneInfo("America/New_York")
        
        now_tehran = datetime.now(tehran_tz).strftime("%H:%M:%S")
        now_ny = datetime.now(ny_tz).strftime("%H:%M:%S")
        
        msg = (
            "🌍 <b>ساعت جهانی</b>\n\n"
            f"🇮🇷 تهران\n<code>{now_tehran}</code>\n\n"
            f"🇺🇸 نیویورک\n<code>{now_ny}</code>"
        )
        await update.message.reply_text(msg, parse_mode=ParseMode.HTML)

    # ۲. خوشتیپ کیه؟
    elif norm_text in ["خوشتیپ کیه", "خوشتیپ کی"] and features.get("handsome", True):
        valid_members = await get_valid_group_members(context, chat_id, db)
        if valid_members:
            target_id, info = random.choice(valid_members)
            mention = get_user_mention(int(target_id), info["fullname"])
            await update.message.reply_text(
                f"😎 خوشتیپ گروه اینه\n\n{mention}",
                parse_mode=ParseMode.HTML
            )

    # ۳. جنده کیه؟
    elif norm_text in ["جنده کیه", "جنده کی"] and features.get("jende", True):
        valid_members = await get_valid_group_members(context, chat_id, db)
        if valid_members:
            target_id, info = random.choice(valid_members)
            mention = get_user_mention(int(target_id), info["fullname"])
            await update.message.reply_text(
                f"👑 جنده گروه اینه\n\n{mention}",
                parse_mode=ParseMode.HTML
            )

    # ۴. کونی کیه؟
    elif norm_text in ["کونی کیه", "کونی کی"] and features.get("koni", True):
        valid_members = await get_valid_group_members(context, chat_id, db)
        if valid_members:
            target_id, info = random.choice(valid_members)
            mention = get_user_mention(int(target_id), info["fullname"])
            await update.message.reply_text(
                f"🍑 کونی گروه اینه\n\n{mention}",
                parse_mode=ParseMode.HTML
            )

    # ۵. شیپ کن
    elif norm_text in ["شیپ کن", "شیپ"] and features.get("ship", True):
        valid_members = await get_valid_group_members(context, chat_id, db)
        if len(valid_members) >= 2:
            sampled = random.sample(valid_members, 2)
            (u1_id, u1_info), (u2_id, u2_info) = sampled[0], sampled[1]
            
            name1 = get_user_mention(int(u1_id), u1_info["fullname"])
            name2 = get_user_mention(int(u2_id), u2_info["fullname"])
            
            keyboard = InlineKeyboardMarkup([
                [
                    InlineKeyboardButton("👍 آره", callback_data="ship_yes"),
                    InlineKeyboardButton("👎 نه", callback_data="ship_no")
                ]
            ])
            
            await update.message.reply_text(
                f"❤️ <b>کاپل امروز</b>\n\n{name1} ❤️ {name2}",
                reply_markup=keyboard,
                parse_mode=ParseMode.HTML
            )
        else:
            await update.message.reply_text("❌ تعداد اعضای حاضر و فعال گروه برای شیپ کافی نیست!")

    # ۶. غذا چی بخورم / غذا چی بپزم
    elif norm_text in ["غذا چی بخورم", "غذا چی بپزم", "غذا چی بخوریم", "غذا چی بپزیم"] and features.get("food", True):
        foods_list = db.get("foods", [])
        if foods_list:
            selected_food = random.choice(foods_list)
            await update.message.reply_text(
                f"😋 پیشنهاد من به تو:\n\n🍔 <b>{html.escape(selected_food)}</b>",
                parse_mode=ParseMode.HTML
            )

    # ۸. درصد کونی بودن
    elif norm_text == "این چقد کونیه" and features.get("koni_percent", True):
        if update.message.reply_to_message:
            target_user = update.message.reply_to_message.from_user
            mention = get_user_mention(target_user.id, target_user.full_name)
            percent = random.randint(0, 100)
            await update.message.reply_text(
                f"{mention}\n\n🤣 {percent}٪ کونیه",
                parse_mode=ParseMode.HTML
            )

    # ۹. تشخیص «لف» با Regex پیشرفته
    elif LEF_PATTERN.search(raw_text) and features.get("lef", True):
        media_lef = db.get("media_lef")
        if media_lef:
            m_type = media_lef["type"]
            f_id = media_lef["file_id"]
            
            if m_type == "sticker":
                await update.message.reply_sticker(f_id)
            elif m_type == "photo":
                await update.message.reply_photo(f_id)
            elif m_type == "animation":
                await update.message.reply_animation(f_id)
            elif m_type == "video":
                await update.message.reply_video(f_id)

# ==========================================
# GLOBAL ERROR HANDLER
# ==========================================
async def global_error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    """مدیریت خطاهای غیرمنتظره و ثبت آن‌ها در لاگ سیستم بدون کرش ربات"""
    logger.error(f"Exception while handling an update: {context.error}", exc_info=context.error)

# ==========================================
# MAIN APPLICATION
# ==========================================
def main():
    """شروع به کار ربات با بررسی اعتبار توکن و تنظیم هندلرها"""
    if not BOT_TOKEN or BOT_TOKEN == "YOUR_BOT_TOKEN_HERE":
        logger.critical("FATAL: BOT_TOKEN is missing or set to default! Please update BOT_TOKEN in nmd.py.")
        sys.exit(1)

    load_db()

    app = Application.builder().token(BOT_TOKEN).post_init(post_init).build()

    # ۱. ثبت CallbackQueryHandler (بالاترین اولویت)
    app.add_handler(CallbackQueryHandler(handle_callback_query))
    
    # ۲. ثبت CommandHandlerها
    app.add_handler(CommandHandler("panel", command_panel))
    app.add_handler(CommandHandler("cancel", command_cancel))
    
    # ۳. ثبت MessageHandler برای تمامی پیام‌ها (متن و رسانه)
    app.add_handler(MessageHandler(filters.ALL & (~filters.COMMAND), handle_messages))

    # ۴. ثبت Error Handler سراسری
    app.add_error_handler(global_error_handler)

    threading.Thread(target=run_health_check_server, daemon=True).start()

    logger.info("Bot is running cleanly...")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
