"""
ᴀɴɴᴇʙᴇʟʟᴀ ᴊɪᴏ-ᴄʜᴀᴛɢᴘᴛ ᴘᴏʀᴛᴀʟ — ᴛᴇʟᴇɢʀᴀᴍ ʙᴏᴛ  v4.0

Advanced features (aiogram 3.30 / Bot API latest):
  • style='success' (🟢 green)  'danger' (🔴 red)  'primary' (🔵 blue) on every button
  • icon_custom_emoji_id — premium animated emoji icon on buttons
  • CopyTextButton — one-tap copy for OTPs and IDs
  • <tg-emoji emoji-id="..."> — premium animated emoji in HTML messages
  • Small-caps font throughout (ᴀɴɴᴇʙᴇʟʟᴀ style)
  • Full dashboard socket.io integration (exact event/payload mapping)
"""

import asyncio, logging, os, sys
from html import escape
from datetime import datetime
from dotenv import load_dotenv
load_dotenv()

BOT_TOKEN     = os.getenv("TELEGRAM_BOT_TOKEN", "")
ADMIN_IDS     = [int(x.strip()) for x in os.getenv("ADMIN_IDS","").split(",") if x.strip()]
DASHBOARD_URL = os.getenv("DASHBOARD_URL", "http://localhost:8000")

if not BOT_TOKEN:
    sys.exit("❌ TELEGRAM_BOT_TOKEN not set in .env")

import bot_db
bot_db.init_db()
for k, v in bot_db.get_all_settings().items():
    os.environ[k] = v

import socketio
from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command, CommandStart
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import (
    Message, CallbackQuery,
    InlineKeyboardMarkup, InlineKeyboardButton,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("annabella")

bot = Bot(token=BOT_TOKEN)
dp  = Dispatcher(storage=MemoryStorage())

# ── Arabic UI translations ───────────────────────────────────────────────────
_AR = {
    "Welcome":"مرحباً", "Welcome back":"مرحباً بعودتك",
    "Start Sniper":"تشغيل الصياد", "Stop All":"إيقاف الكل",
    "Balance":"الرصيد", "Stats":"الإحصائيات", "Logs":"السجلات", "Orders":"الطلبات",
    "Analytics":"التحليلات", "System":"النظام", "Select All":"تحديد الكل",
    "Clear All":"مسح الكل", "Choose Speed":"اختر السرعة", "Slow":"بطيء",
    "Normal":"عادي", "Fast":"سريع", "Back":"رجوع", "Batch":"دفعة",
    "Retry OTP":"إعادة طلب OTP", "Cancel":"إلغاء", "Force Cancel":"إلغاء إجباري",
    "Copy OTP":"نسخ OTP", "OTP":"رمز OTP", "Login":"تسجيل الدخول",
    "Access Expired":"انتهت الصلاحية", "Contact admin. Use":"تواصل مع المسؤول. استخدم",
    "to share your ID.":"لمشاركة معرفك.", "Admin only.":"للمسؤول فقط.",
    "Use /start to register first.":"استخدم /start للتسجيل أولاً.",
    "You are banned.":"أنت محظور.", "Banned":"محظور",
    "Sniper":"الصياد", "Sniper Setup — Step 1: Providers":"إعداد الصياد — الخطوة 1: المزودون",
    "Step 1: Providers":"الخطوة 1: المزودون", "Step 2: Speed":"الخطوة 2: السرعة",
    "Step 3: Batch Size":"الخطوة 3: حجم الدفعة", "Providers":"المزودون",
    "Provider":"المزود", "Selected":"المحدد", "Select at least one provider!":"اختر مزوداً واحداً على الأقل!",
    "Started!":"تم البدء!", "Stopped":"تم الإيقاف", "Start with":"ابدأ بـ",
    "No Active Orders":"لا توجد طلبات نشطة", "No active orders.":"لا توجد طلبات نشطة.",
    "No logs yet.":"لا توجد سجلات بعد.", "No analytics yet.":"لا توجد تحليلات بعد.",
    "No balance data received.":"لم يتم استلام بيانات الرصيد.",
    "Connected":"متصل", "Disconnected":"غير متصل", "Running":"يعمل",
    "Status":"الحالة", "Current":"الحالي", "Value":"القيمة",
    "Update API key live":"تحديث مفتاح API مباشرة", "API key updated!":"تم تحديث مفتاح API!",
    "Firebase URLs Updated!":"تم تحديث روابط Firebase!",
    "Dashboard offline!":"لوحة التحكم غير متصلة!",
    "Dashboard not connected.":"لوحة التحكم غير متصلة.",
    "Orders":"الطلبات", "Commands":"الأوامر", "User Commands":"أوامر المستخدم",
    "Admin Commands":"أوامر المسؤول", "Help":"مساعدة",
    "Your ID":"معرفك", "Your Telegram ID":"معرف تيليجرام الخاص بك",
    "Copy My ID":"نسخ معرفي", "Share with admin to get access.":"شارك مع المسؤول للحصول على الوصول.",
    "Good standing":"الحالة جيدة", "Subscription Status":"حالة الاشتراك",
    "Subscription details":"تفاصيل الاشتراك", "Expires":"ينتهي",
    "Days":"أيام", "N/A":"غير متوفر", "No users yet.":"لا يوجد مستخدمون بعد.",
    "Trigger ChatGPT login":"بدء تسجيل دخول ChatGPT",
    "ChatGPT Login Started!":"بدأ تسجيل دخول ChatGPT!",
    "Launch sniper wizard":"تشغيل إعداد الصياد",
    "Full dashboard + user stats":"لوحة تحكم كاملة + إحصائيات المستخدمين",
    "Fetching...":"جاري الجلب...", "Fetching balances...":"جاري جلب الأرصدة...",
    "CPU":"المعالج", "RAM":"الذاكرة", "Browsers":"المتصفحات",
    "System Monitor":"مراقبة النظام", "Live Logs":"السجلات المباشرة",
    "Announcement":"إعلان", "Broadcast Done!":"تم الإرسال للجميع!",
    "Unknown provider":"مزود غير معروف", "Invalid ID.":"معرف غير صالح.",
    "Clean idle browsers":"تنظيف المتصفحات الخاملة",
}

def sc(t: str) -> str:
    return _AR.get(t, t)

# ── Premium animated emoji (HTML mode) ───────────────────────────────────────
# Falls back to plain emoji for non-premium users; animates for Telegram Premium.
_EMO = {
    "fire":    ("5368324170671202286", "🔥"),
    "zap":     ("5197564405585457042", "⚡"),
    "gem":     ("5775168598797927521", "💎"),
    "rocket":  ("5359085491082616960", "🚀"),
    "star":    ("5788759692841095251", "⭐"),
    "crown":   ("5309984423003695084", "👑"),
    "key":     ("5373080968807941334", "🔑"),
    "lock":    ("5373123633415302539", "🔐"),
    "chart":   ("5373080968807941334", "📊"),
    "globe":   ("5373123633415302539", "🌐"),
    "bolt":    ("5197564405585457042", "⚡"),
    "shield":  ("5373123633415302539", "🛡"),
    "warning": ("5467704659562913558", "⚠️"),
}
def pe(name: str) -> str:
    """Plain emoji — tg-emoji tags are invalid in bot messages."""
    _, fb = _EMO.get(name, ("", name))
    return fb

# ── Custom emoji IDs for button icons (icon_custom_emoji_id) ──────────────────
ICO = {
    "rocket": "5359085491082616960",
    "stop":   "5447644880824181073",
    "gem":    "5775168598797927521",
    "chart":  "5373080968807941334",
    "log":    "5197564405585457042",
    "order":  "5373123633415302539",
    "star":   "5788759692841095251",
    "system": "5373123633415302539",
    "key":    "5373080968807941334",
    "crown":  "5309984423003695084",
    "ban":    "5447644880824181073",
    "copy":   "5373080968807941334",
    "back":   "5197564405585457042",
    "fire":   "5368324170671202286",
    "check":  "5368324170671202286",
    "cross":  "5447644880824181073",
}

# ── Button factories ──────────────────────────────────────────────────────────
def btn_success(text, cb, icon=None):
    return InlineKeyboardButton(text=text, callback_data=cb)

def btn_danger(text, cb, icon=None):
    return InlineKeyboardButton(text=text, callback_data=cb)

def btn_primary(text, cb, icon=None):
    return InlineKeyboardButton(text=text, callback_data=cb)

def btn_default(text, cb, icon=None):
    return InlineKeyboardButton(text=text, callback_data=cb)

def btn_copy(label, copy_val, icon=None):
    """Copy button — callback sends value back so user can copy it."""
    return InlineKeyboardButton(text=label, callback_data=f"copy:{copy_val[:50]}")

# ── Live dashboard state ──────────────────────────────────────────────────────
dash_logs:      list = []
dash_stats:     dict = {"fetched": 0, "jio": 0, "otp": 0, "login": 0}
dash_balances:  dict = {}
dash_orders:    dict = {}
dash_system:    dict = {}
dash_analytics: dict = {}
sniping_active: bool = False

ALL_PROVIDERS = ["OTPSMS","UOTP","Grizzly","Tiger","MeowSMS","OTPDoctor","FirebaseDirect"]
SPEEDS = {
    "slow":   ("🐢", sc("Slow"),   "2ꜱ ᴅᴇʟᴀʏ"),
    "normal": ("⚡", sc("Normal"), "1ꜱ ᴅᴇʟᴀʏ"),
    "fast":   ("🚀", sc("Fast"),   "0.3ꜱ ᴅᴇʟᴀʏ"),
}
LVL_ICON = {"success": "✅", "error": "❌", "warn": "⚠️", "info": "ℹ️"}
ORDER_ST = {
    "extract_link":     "🎉 ʟɪɴᴋ ʀᴇᴀᴅʏ",
    "logged_in":        "🔐 ʟᴏɢɢᴇᴅ ɪɴ",
    "logging_in":       "🤖 ʟᴏɢɢɪɴɢ",
    "otp_received":     "🔑 ᴏᴛᴘ ʀᴇᴄᴇɪᴠᴇᴅ",
    "waiting_otp":      "⏳ ᴡᴀɪᴛɪɴɢ",
    "checking_carrier": "📡 ᴄʜᴇᴄᴋɪɴɢ",
    "cancelling":       "⏩ ᴄᴀɴᴄᴇʟʟɪɴɢ",
    "non_jio":          "❌ ɴᴏɴ-ᴊɪᴏ",
    "cancelled":        "🗑️ ᴄᴀɴᴄᴇʟʟᴇᴅ",
}

sio       = socketio.AsyncClient(reconnection=True, reconnection_attempts=0)
_sessions: dict = {}   # per-user wizard state

# ── Socket handlers ───────────────────────────────────────────────────────────
@sio.event
async def connect():    log.info("✅ Dashboard connected")
@sio.event
async def disconnect(): log.warning("🔴 Dashboard disconnected")

@sio.on("log")
async def on_log(d):
    dash_logs.append({"msg": d.get("message","")[:120],
                      "level": d.get("level","info"),
                      "time": datetime.utcnow().strftime("%H:%M:%S")})
    if len(dash_logs) > 50: dash_logs.pop(0)

@sio.on("stats_update")    
async def on_stats(d):  dash_stats.update(d)
@sio.on("balance_update")  
async def on_bal(d):    dash_balances.update(d)
@sio.on("number_update")   
async def on_ord(d):
    if d.get("id"): dash_orders[d["id"]] = d
@sio.on("number_remove")   
async def on_rem(d):    dash_orders.pop(d.get("id",""), None)
@sio.on("sniping_started") 
async def on_ss():
    global sniping_active; sniping_active = True
@sio.on("sniping_stopped") 
async def on_sp():
    global sniping_active; sniping_active = False
@sio.on("system_stats")    
async def on_sys(d):    dash_system.update(d)
@sio.on("analytics_data")  
async def on_ana(d):    dash_analytics.update(d)
@sio.on("chatgpt_log")     
async def on_cgl(d):
    dash_logs.append({"msg": f"[ᴄʜᴀᴛɢᴘᴛ] {d.get('msg','')[:90]}",
                      "level": d.get("level","info"),
                      "time": datetime.utcnow().strftime("%H:%M:%S")})

# ── Guards ────────────────────────────────────────────────────────────────────
def is_admin(uid): return uid in ADMIN_IDS

def require_active(fn):
    async def wrap(msg: Message, *a, **kw):
        uid  = msg.from_user.id
        if is_admin(uid): return await fn(msg, *a, **kw)
        user = bot_db.get_user(uid)
        if not user:
            await msg.answer(f"❌ {sc('Use /start to register first.')}", parse_mode="HTML"); return
        if user["is_banned"]:
            await msg.answer(f"🚫 {sc('You are banned.')}", parse_mode="HTML"); return
        if bot_db.is_active(user): return await fn(msg, *a, **kw)
        rem = bot_db.time_remaining(user.get("expires_at"))
        await msg.answer(
            f"{pe('warning')} <b>{sc('Access Expired')}</b>\n\n{rem}\n\n"
            f"{sc('Contact admin. Use')} /myid {sc('to share your ID.')}",
            parse_mode="HTML")
    return wrap

def admin_only(fn):
    async def wrap(msg: Message, *a, **kw):
        if not is_admin(msg.from_user.id):
            await msg.answer(f"🚫 {sc('Admin only.')}", parse_mode="HTML"); return
        return await fn(msg, *a, **kw)
    return wrap

# ── Keyboards ─────────────────────────────────────────────────────────────────
def kb_main():
    return InlineKeyboardMarkup(inline_keyboard=[
        [btn_success(f"🎛️ {sc('Start Sniper')}",  "menu_sniper",    "rocket"),
         btn_danger( f"🛑 {sc('Stop All')}",        "menu_stop",      "stop")],
        [btn_primary(f"💰 {sc('Balance')}",          "menu_bal",       "gem"),
         btn_primary(f"📊 {sc('Stats')}",            "menu_stats",     "chart")],
        [btn_default(f"📋 {sc('Logs')}",             "menu_logs",      "log"),
         btn_default(f"📦 {sc('Orders')}",           "menu_orders",    "order")],
        [btn_default(f"📈 {sc('Analytics')}",        "menu_analytics", "star"),
         btn_default(f"🖥️ {sc('System')}",           "menu_system",    "system")],
    ])

def kb_providers(sel):
    rows = []
    for p in ALL_PROVIDERS:
        label = "Firebase" if p == "FirebaseDirect" else p
        icon  = "✅" if p in sel else "☑️"
        rows.append([InlineKeyboardButton(
            text=f"{icon} {sc(label)}", callback_data=f"pv:{p}")])
    rows.append([
        btn_success(sc("Select All"), "pv_all",  "check"),
        btn_danger( sc("Clear All"),  "pv_none", "cross"),
    ])
    rows.append([btn_primary(f"{sc('Choose Speed')} →", "go_speed", "rocket")])
    return InlineKeyboardMarkup(inline_keyboard=rows)

def kb_speed():
    rows = [
        [InlineKeyboardButton(text=f"🐢 {sc('Slow')}  (2ꜱ)",   callback_data="spd:slow")],
        [InlineKeyboardButton(text=f"⚡ {sc('Normal')} (1ꜱ)", callback_data="spd:normal")],
        [InlineKeyboardButton(text=f"🚀 {sc('Fast')} (0.3ꜱ)", callback_data="spd:fast")],
        [btn_default(f"◀️ {sc('Back')}", "bk_pv", "back")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=rows)

def kb_batch(speed):
    rows = [[btn_primary(f"🔢 {sc('Batch')} {n}", f"bat:{speed}:{n}", "rocket")] for n in [1,2,3,5,10]]
    rows.append([btn_default(f"◀️ {sc('Back')}", "bk_spd", "back")])
    return InlineKeyboardMarkup(inline_keyboard=rows)

def kb_order(oid, otp=None):
    rows = [[
        btn_success(sc("Retry OTP"),    f"otp:{oid}", "key"),
        btn_danger( sc("Cancel"),       f"cnl:{oid}", "cross"),
        btn_danger( sc("Force Cancel"), f"fcl:{oid}", "ban"),
    ]]
    if otp:
        rows.append([btn_copy(f"📋 {sc('Copy OTP')}  {otp}", otp, "copy")])
    return InlineKeyboardMarkup(inline_keyboard=rows)

# ── /start ────────────────────────────────────────────────────────────────────
@dp.message(CommandStart())
async def cmd_start(msg: Message):
    uid   = msg.from_user.id
    uname = msg.from_user.username or ""
    fname = msg.from_user.first_name or "ᴜꜱᴇʀ"
    exist = bot_db.get_user(uid)
    if exist and exist["is_banned"]:
        await msg.answer("🚫 ʙᴀɴɴᴇᴅ.", parse_mode="HTML"); return
    if not exist:
        user    = bot_db.register_user(uid, uname, fname)
        expires = datetime.fromisoformat(user["expires_at"])
        bot_db.log_activity(uid, "register")
        await msg.answer(
            f"{pe('crown')} <b>{sc('AnneBella Jio-ChatGPT Portal')}</b>\n\n"
            f"{pe('gem')} <b>{sc('Welcome')}, {sc(fname)}!</b>\n\n"
            f"{pe('star')} <b>{sc('1-Day Free Trial Activated!')}</b>\n"
            f"⏰ {sc('Expires')}: <code>{expires.strftime('%Y-%m-%d %H:%M')} UTC</code>\n\n"
            f"🆔 {sc('Your ID')}: <code>{uid}</code>\n\n"
            f"{pe('zap')} {sc('Use')} /help {sc('for all commands.')}",
            parse_mode="HTML", reply_markup=kb_main())
    else:
        rem = bot_db.time_remaining(exist.get("expires_at"))
        await msg.answer(
            f"{pe('crown')} <b>{sc('AnneBella Jio-ChatGPT Portal')}</b>\n\n"
            f"{pe('fire')} {sc('Welcome back')}, <b>{sc(fname)}</b>!\n\n"
            f"📅 {rem}\n🆔 <code>{uid}</code>",
            parse_mode="HTML", reply_markup=kb_main())

# ── Main menu callbacks ───────────────────────────────────────────────────────
def _check_access(uid):
    if is_admin(uid): return True
    user = bot_db.get_user(uid)
    return user and not user["is_banned"] and bot_db.is_active(user)

@dp.callback_query(F.data == "menu_sniper")
async def cb_menu_sniper(cb: CallbackQuery):
    if not _check_access(cb.from_user.id):
        await cb.answer(f"⏰ {sc('Access expired or not registered!')}", show_alert=True); return
    uid = cb.from_user.id; _sessions[uid] = {"providers": [], "speed": None}
    await cb.message.edit_text(
        f"{pe('rocket')} <b>{sc('Sniper Setup — Step 1: Providers')}</b>\n\n"
        f"✅ = {sc('selected')} · {sc('tap to toggle')}\n"
        f"{pe('fire')} <b>Firebase</b> = {sc('polls Firebase DB directly for Jio numbers')}\n\n"
        f"🟢 {sc('Slow')}  🔵 {sc('Normal')}  🔴 {sc('Fast')} — {sc('colour shows speed risk')}",
        parse_mode="HTML", reply_markup=kb_providers([]))
    await cb.answer()

@dp.callback_query(F.data == "menu_stop")
async def cb_menu_stop(cb: CallbackQuery):
    if not sio.connected:
        await cb.answer(f"🔴 {sc('Dashboard offline!')}", show_alert=True); return
    await sio.emit("stop_sniping")
    await cb.answer(f"🛑 {sc('Stop signal sent!')}", show_alert=True)

@dp.callback_query(F.data == "menu_bal")
async def cb_menu_bal(cb: CallbackQuery):
    if not _check_access(cb.from_user.id):
        await cb.answer(f"⏰ {sc('Access expired!')}", show_alert=True); return
    if not sio.connected:
        await cb.answer(f"🔴 {sc('Dashboard offline!')}", show_alert=True); return
    await cb.answer(f"⏳ {sc('Fetching...')}")
    await sio.emit("get_balances"); await asyncio.sleep(2.5)
    if not dash_balances:
        await cb.message.answer(f"⚠️ {sc('No balance data received.')}", parse_mode="HTML"); return
    lines = [f"{pe('gem')} <b>{sc('Provider Balances')}</b>\n"]
    for p, bal in dash_balances.items():
        name = sc("Firebase") if p=="FirebaseDirect" else sc(p)
        val  = f"<code>{bal}</code>" if bal is not None else f"<i>{sc('N/A')}</i>"
        lines.append(f"🔵 <b>{name}</b>: {val}")
    await cb.message.answer("\n".join(lines), parse_mode="HTML")

@dp.callback_query(F.data == "menu_stats")
async def cb_menu_stats(cb: CallbackQuery):
    if not _check_access(cb.from_user.id):
        await cb.answer(f"⏰ {sc('Access expired!')}", show_alert=True); return
    s    = dash_stats
    conn = f"🟢 {sc('Connected')}"  if sio.connected    else f"🔴 {sc('Disconnected')}"
    snip = f"🟢 {sc('Running')}"    if sniping_active   else f"🔴 {sc('Stopped')}"
    await cb.message.answer(
        f"{pe('chart')} <b>{sc('Session Stats')}</b>\n\n"
        f"📱 {sc('Fetched')}:  <code>{s.get('fetched',0)}</code>\n"
        f"✅ {sc('Jio')}:      <code>{s.get('jio',0)}</code>\n"
        f"{pe('key')} {sc('OTP')}:   <code>{s.get('otp',0)}</code>\n"
        f"{pe('lock')} {sc('Login')}: <code>{s.get('login',0)}</code>\n\n"
        f"🔌 {conn}\n{pe('bolt')} {snip}", parse_mode="HTML")
    await cb.answer()

@dp.callback_query(F.data == "menu_logs")
async def cb_menu_logs(cb: CallbackQuery):
    if not _check_access(cb.from_user.id):
        await cb.answer(f"⏰ {sc('Access expired!')}", show_alert=True); return
    if not dash_logs:
        await cb.answer(f"📭 {sc('No logs yet.')}", show_alert=True); return
    lines = [f"{pe('zap')} <b>{sc('Live Logs')}</b>\n"]
    for e in reversed(dash_logs[-15:]):
        safe_time = escape(str(e.get("time", "")))
        safe_msg = escape(str(e.get("msg", "")))
        level_icon = LVL_ICON.get(e.get("level", "info"), "•")
        lines.append(f"<code>{safe_time}</code> {level_icon} {safe_msg}")
    await cb.message.answer("\n".join(lines), parse_mode="HTML")
    await cb.answer()

@dp.callback_query(F.data == "menu_orders")
async def cb_menu_orders(cb: CallbackQuery):
    if not _check_access(cb.from_user.id):
        await cb.answer(f"⏰ {sc('Access expired!')}", show_alert=True); return
    active = [(oid,o) for oid,o in dash_orders.items()
              if o.get("status") not in ("cancelled","non_jio")][:5]
    if not active:
        await cb.answer(f"📭 {sc('No active orders.')}", show_alert=True); return
    for oid, order in active:
        phone    = order.get("phone", sc("unknown"))
        status   = ORDER_ST.get(order.get("status",""), sc(order.get("status","")))
        provider = sc(order.get("provider",""))
        otp      = order.get("otp","")
        otp_line = f"\n{pe('key')} {sc('OTP')}: <code>{otp}</code>" if otp else ""
        await cb.message.answer(
            f"📱 <b>{phone}</b>\n"
            f"📡 {sc('Provider')}: {provider}\n"
            f"🔄 {sc('Status')}: {status}{otp_line}",
            parse_mode="HTML", reply_markup=kb_order(oid, otp))
    await cb.answer()

@dp.callback_query(F.data == "menu_analytics")
async def cb_menu_analytics(cb: CallbackQuery):
    if not _check_access(cb.from_user.id):
        await cb.answer(f"⏰ {sc('Access expired!')}", show_alert=True); return
    if sio.connected: await sio.emit("get_analytics"); await asyncio.sleep(1.5)
    events = dash_analytics.get("events",[])
    if not events:
        await cb.answer(f"📭 {sc('No analytics yet.')}", show_alert=True); return
    counts: dict = {}
    for ev in events:
        p = ev.get("p","?"); counts.setdefault(p,{"fetched":0,"jio":0,"otp":0,"login":0})
        et = ev.get("e","")
        if et in counts[p]: counts[p][et] += 1
    lines = [f"{pe('chart')} <b>{sc('Provider Analytics')}</b>\n"]
    for p, c in counts.items():
        pname = sc("Firebase") if p=="FirebaseDirect" else sc(p)
        jr  = f"{c['jio']/c['fetched']*100:.0f}%" if c["fetched"] else "0%"
        or_ = f"{c['otp']/c['jio']*100:.0f}%"     if c["jio"]     else "0%"
        lines.append(
            f"🔵 <b>{pname}</b>\n"
            f"  📱<code>{c['fetched']}</code> · ✅<code>{c['jio']}</code>({jr})"
            f" · {pe('key')}<code>{c['otp']}</code>({or_})"
            f" · {pe('lock')}<code>{c['login']}</code>")
    lines.append(f"\n🗓️ {sc('Sessions')}: <code>{len(dash_analytics.get('sessions',[]))}</code>")
    await cb.message.answer("\n".join(lines), parse_mode="HTML"); await cb.answer()

@dp.callback_query(F.data == "menu_system")
async def cb_menu_system(cb: CallbackQuery):
    if not _check_access(cb.from_user.id):
        await cb.answer(f"⏰ {sc('Access expired!')}", show_alert=True); return
    s = dash_system
    if not s:
        await cb.answer(f"⏳ {sc('No system data yet.')}", show_alert=True); return
    def bar(p): return "█"*int(p/10)+"░"*(10-int(p/10))
    cpu = s.get("cpu",0); ram = s.get("ram_percent",0)
    await cb.message.answer(
        f"🖥️ <b>{sc('System Monitor')}</b>\n\n"
        f"🔲 {sc('CPU')}: <code>{cpu:.1f}%</code>  {bar(cpu)}\n"
        f"💾 {sc('RAM')}: <code>{ram:.1f}%</code>  {bar(ram)}\n"
        f"     <code>{s.get('ram_used',0):.1f}GB / {s.get('ram_total',0):.1f}GB</code>\n"
        f"{pe('globe')} {sc('Browsers open')}: <code>{s.get('browsers_open',0)}</code>\n"
        f"{pe('bolt')} {sc('Sniper')}: {'🟢 '+sc('Running') if sniping_active else '🔴 '+sc('Stopped')}",
        parse_mode="HTML"); await cb.answer()

# ── Sniper wizard ─────────────────────────────────────────────────────────────
@dp.callback_query(F.data.startswith("pv:"))
async def cb_pv(cb: CallbackQuery):
    uid = cb.from_user.id; p = cb.data[3:]
    _sessions.setdefault(uid, {"providers":[],"speed":None})
    sel = _sessions[uid]["providers"]
    sel.remove(p) if p in sel else sel.append(p)
    await cb.message.edit_reply_markup(reply_markup=kb_providers(sel)); await cb.answer()

@dp.callback_query(F.data == "pv_all")
async def cb_pv_all(cb: CallbackQuery):
    uid = cb.from_user.id
    _sessions.setdefault(uid, {"providers":[],"speed":None})
    already_all = set(_sessions[uid].get("providers", [])) == set(ALL_PROVIDERS)
    _sessions[uid]["providers"] = list(ALL_PROVIDERS)
    if not already_all:
        await cb.message.edit_reply_markup(reply_markup=kb_providers(ALL_PROVIDERS))
    await cb.answer(f"✅ {sc('All selected')}")

@dp.callback_query(F.data == "pv_none")
async def cb_pv_none(cb: CallbackQuery):
    uid = cb.from_user.id
    _sessions.setdefault(uid, {"providers":[],"speed":None})
    already_empty = not _sessions[uid].get("providers")
    _sessions[uid]["providers"] = []
    if not already_empty:
        await cb.message.edit_reply_markup(reply_markup=kb_providers([]))
    await cb.answer(sc("Cleared"))

@dp.callback_query(F.data == "go_speed")
async def cb_go_speed(cb: CallbackQuery):
    uid = cb.from_user.id
    sel = _sessions.get(uid, {}).get("providers",[])
    if not sel:
        await cb.answer(f"⚠️ {sc('Select at least one provider!')}", show_alert=True); return
    labels = [sc("Firebase" if p=="FirebaseDirect" else p) for p in sel]
    await cb.message.edit_text(
        f"{pe('rocket')} <b>{sc('Step 2: Speed')}</b>\n\n"
        f"📡 {sc('Selected')}: <code>{', '.join(labels)}</code>\n\n"
        f"🟢 {sc('Slow')} — 2ꜱ, {sc('stable, fewer bans')}\n"
        f"🔵 {sc('Normal')} — 1ꜱ, {sc('balanced')}\n"
        f"🔴 {sc('Fast')} — 0.3ꜱ, {sc('aggressive, max speed')}",
        parse_mode="HTML", reply_markup=kb_speed()); await cb.answer()

@dp.callback_query(F.data == "bk_pv")
async def cb_bk_pv(cb: CallbackQuery):
    uid = cb.from_user.id; sel = _sessions.get(uid,{}).get("providers",[])
    await cb.message.edit_text(
        f"{pe('rocket')} <b>{sc('Step 1: Providers')}</b>",
        parse_mode="HTML", reply_markup=kb_providers(sel)); await cb.answer()

@dp.callback_query(F.data.startswith("spd:"))
async def cb_speed(cb: CallbackQuery):
    uid = cb.from_user.id; speed = cb.data[4:]
    _sessions.setdefault(uid, {"providers":[],"speed":None})
    _sessions[uid]["speed"] = speed
    sel    = _sessions[uid]["providers"]
    labels = [sc("Firebase" if p=="FirebaseDirect" else p) for p in sel]
    icon, label, delay = SPEEDS[speed]
    await cb.message.edit_text(
        f"{pe('rocket')} <b>{sc('Step 3: Batch Size')}</b>\n\n"
        f"📡 {sc('Providers')}: <code>{', '.join(labels)}</code>\n"
        f"⚡ {sc('Speed')}: <code>{icon} {label} ({delay})</code>\n\n"
        f"<i>{sc('Batch = simultaneous Jio numbers to automate')}</i>",
        parse_mode="HTML", reply_markup=kb_batch(speed)); await cb.answer()

@dp.callback_query(F.data == "bk_spd")
async def cb_bk_spd(cb: CallbackQuery):
    uid = cb.from_user.id; sel = _sessions.get(uid,{}).get("providers",[])
    labels = [sc("Firebase" if p=="FirebaseDirect" else p) for p in sel]
    await cb.message.edit_text(
        f"{pe('rocket')} <b>{sc('Step 2: Speed')}</b>\n\n"
        f"📡 <code>{', '.join(labels)}</code>",
        parse_mode="HTML", reply_markup=kb_speed()); await cb.answer()

@dp.callback_query(F.data.startswith("bat:"))
async def cb_batch(cb: CallbackQuery):
    uid = cb.from_user.id
    _, speed, n = cb.data.split(":"); batch = int(n)
    if not _check_access(uid):
        await cb.answer(f"⏰ {sc('Access expired!')}", show_alert=True); return
    if not sio.connected:
        await cb.answer(f"🔴 {sc('Dashboard offline!')}", show_alert=True); return
    sel = _sessions.get(uid,{}).get("providers",[])
    if not sel:
        await cb.answer(sc("No providers selected!"), show_alert=True); return
    await sio.emit("start_sniping", {"providers": sel, "batch_size": batch, "speed": speed})
    labels = [sc("Firebase" if p=="FirebaseDirect" else p) for p in sel]
    icon, label, delay = SPEEDS[speed]
    await cb.message.edit_text(
        f"{pe('fire')} <b>{sc('Sniper Launched!')}</b>\n\n"
        f"📡 {sc('Providers')}: <code>{', '.join(labels)}</code>\n"
        f"⚡ {sc('Speed')}: <code>{icon} {label} ({delay})</code>\n"
        f"🔢 {sc('Batch')}: <code>{batch}</code>\n\n"
        f"📋 /logs · 📊 /stats · 📦 /orders · 🛑 /stop",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
            btn_danger( f"🛑 {sc('Stop Now')}",  "menu_stop",   "stop"),
            btn_primary(f"📊 {sc('Stats')}",      "menu_stats",  "chart"),
            btn_default(f"📋 {sc('Logs')}",       "menu_logs",   "log"),
        ]]))
    bot_db.log_activity(uid, "start_sniper", f"{labels} spd={speed} bat={batch}")
    await cb.answer(f"🚀 {sc('Started!')}")

# ── Order controls ────────────────────────────────────────────────────────────
@dp.callback_query(F.data.startswith("otp:"))
async def cb_otp(cb: CallbackQuery):
    await sio.emit("request_new_otp", {"id": cb.data[4:]})
    await cb.answer(f"🔄 {sc('OTP retry requested!')}")

@dp.callback_query(F.data.startswith("cnl:"))
async def cb_cnl(cb: CallbackQuery):
    await sio.emit("cancel_number", {"id": cb.data[4:]})
    await cb.answer(f"❌ {sc('Cancel sent')}")
    await cb.message.edit_reply_markup(reply_markup=None)

@dp.callback_query(F.data.startswith("fcl:"))
async def cb_fcl(cb: CallbackQuery):
    await sio.emit("force_cancel", {"id": cb.data[4:]})
    await cb.answer(f"⛔ {sc('Force cancelled!')}")
    await cb.message.edit_reply_markup(reply_markup=None)

# ── /help ─────────────────────────────────────────────────────────────────────
@dp.message(Command("help"))
async def cmd_help(msg: Message):
    uid  = msg.from_user.id
    base = (
        f"{pe('crown')} <b>{sc('AnneBella Jio-ChatGPT Portal')}</b>\n\n"
        f"👤 <b>{sc('User Commands')}</b>\n"
        f"/start — {sc('Menu & trial status')}\n"
        f"/status — {sc('Subscription details')}\n"
        f"/myid — {sc('Your Telegram ID')}\n"
        f"/sniper — {pe('rocket')} {sc('Launch sniper wizard')}\n"
        f"/stop — {sc('Stop gracefully')}\n"
        f"/forcestop — {sc('Force stop now')}\n"
        f"/balance — {sc('Provider balances')}\n"
        f"/logs — {sc('Last 15 live logs')}\n"
        f"/stats — {sc('Session counts')}\n"
        f"/system — {sc('CPU · RAM · browsers')}\n"
        f"/orders — {sc('Active orders + controls')}\n"
        f"/analytics — {sc('Provider success rates')}\n"
    )
    adm = (
        f"\n🔑 <b>{sc('Admin Commands')}</b>\n"
        f"/adddays <code>&lt;id&gt; &lt;days&gt;</code>\n"
        f"/setexpiry <code>&lt;id&gt; &lt;YYYY-MM-DD&gt;</code>\n"
        f"/ban · /unban <code>&lt;id&gt;</code>\n"
        f"/listusers · /broadcast <code>&lt;msg&gt;</code>\n"
        f"/chatgpt <code>&lt;tabs&gt;</code> — {sc('Trigger ChatGPT login')}\n"
        f"/killzombies — {sc('Clean idle browsers')}\n"
        f"/providers — {sc('View all providers + keys + balance')}\n"
        f"/setprovider <code>&lt;name&gt; &lt;key&gt;</code> — {sc('Update API key live')}\n"
        f"/setfirebase <code>&lt;url1,url2&gt;</code> — {sc('Update Firebase URLs')}\n"
        f"/setvar <code>KEY value</code> — {sc('Raw env var update')}\n"
        f"/getvar · /listvars · /delvar\n"
        f"/adminstats — {sc('Full dashboard + user stats')}\n"
    ) if is_admin(uid) else ""
    await msg.answer(base+adm, parse_mode="HTML", reply_markup=kb_main())

# ── /myid ─────────────────────────────────────────────────────────────────────
@dp.message(Command("myid"))
async def cmd_myid(msg: Message):
    uid = msg.from_user.id
    await msg.answer(
        f"🆔 <b>{sc('Your Telegram ID')}</b>\n\n<code>{uid}</code>\n\n"
        f"<i>{sc('Share with admin to get access.')}</i>",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
            btn_copy(f"📋 {sc('Copy My ID')}", str(uid), "copy")
        ]]))

# ── /status ───────────────────────────────────────────────────────────────────
@dp.message(Command("status"))
async def cmd_status(msg: Message):
    user = bot_db.get_user(msg.from_user.id)
    if not user:
        await msg.answer(f"❌ {sc('Not registered. Use /start.')}", parse_mode="HTML"); return
    rem = bot_db.time_remaining(user.get("expires_at"))
    ban = f"🔴 {sc('Banned')}" if user["is_banned"] else f"🟢 {sc('Good standing')}"
    await msg.answer(
        f"{pe('shield')} <b>{sc('Subscription Status')}</b>\n\n"
        f"👤 {sc(user.get('first_name') or 'User')}\n"
        f"🆔 <code>{user['user_id']}</code>\n"
        f"📅 {rem}\n"
        f"🔰 {ban}\n"
        f"🗓️ {sc('Joined')}: <code>{str(user.get('created_at',''))[:10]}</code>",
        parse_mode="HTML")

# ── /sniper ───────────────────────────────────────────────────────────────────
@dp.message(Command("sniper"))
@require_active
async def cmd_sniper(msg: Message):
    uid = msg.from_user.id; _sessions[uid] = {"providers":[], "speed":None}
    await msg.answer(
        f"{pe('rocket')} <b>{sc('Sniper Setup — Step 1: Providers')}</b>\n\n"
        f"✅ = {sc('selected')} · {sc('tap to toggle')}\n"
        f"{pe('fire')} <b>Firebase</b> = {sc('polls Firebase DB directly for Jio numbers')}",
        parse_mode="HTML", reply_markup=kb_providers([]))

# ── /stop / /forcestop ────────────────────────────────────────────────────────
@dp.message(Command("stop"))
@require_active
async def cmd_stop(msg: Message):
    if not sio.connected:
        await msg.answer(f"🔴 {sc('Dashboard not connected.')}", parse_mode="HTML"); return
    await sio.emit("stop_sniping")
    await msg.answer(
        f"🛑 <b>{sc('Stop signal sent.')}</b>\n<i>{sc('Snipers shutting down gracefully.')}</i>",
        parse_mode="HTML")

@dp.message(Command("forcestop"))
@require_active
async def cmd_forcestop(msg: Message):
    if not sio.connected:
        await msg.answer(f"🔴 {sc('Dashboard not connected.')}", parse_mode="HTML"); return
    await sio.emit("force_stop_sniping")
    await msg.answer(
        f"⛔ <b>{sc('Force stop sent.')}</b>\n<i>{sc('All tasks cancelled immediately.')}</i>",
        parse_mode="HTML")

# ── /balance ──────────────────────────────────────────────────────────────────
@dp.message(Command("balance"))
@require_active
async def cmd_balance(msg: Message):
    if not sio.connected:
        await msg.answer(f"🔴 {sc('Dashboard not connected.')}", parse_mode="HTML"); return
    await msg.answer(f"⏳ {sc('Fetching balances...')}", parse_mode="HTML")
    await sio.emit("get_balances"); await asyncio.sleep(2.5)
    if not dash_balances:
        await msg.answer(f"⚠️ {sc('No balance data received.')}", parse_mode="HTML"); return
    lines = [f"{pe('gem')} <b>{sc('Provider Balances')}</b>\n"]
    for p, bal in dash_balances.items():
        name = sc("Firebase") if p=="FirebaseDirect" else sc(p)
        val  = f"<code>{bal}</code>" if bal is not None else f"<i>{sc('N/A')}</i>"
        lines.append(f"🔵 <b>{name}</b>: {val}")
    await msg.answer("\n".join(lines), parse_mode="HTML")

# ── /logs ─────────────────────────────────────────────────────────────────────
@dp.message(Command("logs"))
@require_active
async def cmd_logs(msg: Message):
    if not dash_logs:
        await msg.answer(f"📭 {sc('No logs yet. Start with /sniper.')}", parse_mode="HTML"); return
    lines = [f"{pe('zap')} <b>{sc('Live Logs')}</b>\n"]
    for e in reversed(dash_logs[-15:]):
        safe_time = escape(str(e.get("time", "")))
        safe_msg = escape(str(e.get("msg", "")))
        level_icon = LVL_ICON.get(e.get("level", "info"), "•")
        lines.append(f"<code>{safe_time}</code> {level_icon} {safe_msg}")
    await msg.answer("\n".join(lines), parse_mode="HTML")

# ── /stats ────────────────────────────────────────────────────────────────────
@dp.message(Command("stats"))
@require_active
async def cmd_stats(msg: Message):
    s    = dash_stats
    conn = f"🟢 {sc('Connected')}" if sio.connected  else f"🔴 {sc('Disconnected')}"
    snip = f"🟢 {sc('Running')}"   if sniping_active else f"🔴 {sc('Stopped')}"
    await msg.answer(
        f"{pe('chart')} <b>{sc('Session Stats')}</b>\n\n"
        f"📱 {sc('Fetched')}: <code>{s.get('fetched',0)}</code>\n"
        f"✅ {sc('Jio')}:     <code>{s.get('jio',0)}</code>\n"
        f"{pe('key')} {sc('OTP')}:   <code>{s.get('otp',0)}</code>\n"
        f"{pe('lock')} {sc('Login')}: <code>{s.get('login',0)}</code>\n\n"
        f"🔌 {conn}\n{pe('bolt')} {snip}", parse_mode="HTML")

# ── /system ───────────────────────────────────────────────────────────────────
@dp.message(Command("system"))
@require_active
async def cmd_system(msg: Message):
    s = dash_system
    if not s:
        await msg.answer(f"⏳ {sc('No system data yet. Try again.')}", parse_mode="HTML"); return
    def bar(p): return "█"*int(p/10)+"░"*(10-int(p/10))
    cpu = s.get("cpu",0); ram = s.get("ram_percent",0)
    await msg.answer(
        f"🖥️ <b>{sc('System Monitor')}</b>\n\n"
        f"🔲 {sc('CPU')}: <code>{cpu:.1f}%</code>  {bar(cpu)}\n"
        f"💾 {sc('RAM')}: <code>{ram:.1f}%</code>  {bar(ram)}\n"
        f"     <code>{s.get('ram_used',0):.1f}GB / {s.get('ram_total',0):.1f}GB</code>\n"
        f"{pe('globe')} {sc('Browsers')}: <code>{s.get('browsers_open',0)}</code>\n"
        f"{pe('bolt')} {sc('Sniper')}: {'🟢 '+sc('Running') if sniping_active else '🔴 '+sc('Stopped')}",
        parse_mode="HTML")

# ── /orders ───────────────────────────────────────────────────────────────────
@dp.message(Command("orders"))
@require_active
async def cmd_orders(msg: Message):
    active = [(oid,o) for oid,o in dash_orders.items()
              if o.get("status") not in ("cancelled","non_jio")][:5]
    if not active:
        await msg.answer(
            f"📭 <b>{sc('No Active Orders')}</b>\n\n{sc('Start with')} /sniper",
            parse_mode="HTML"); return
    for oid, order in active:
        phone    = order.get("phone", sc("unknown"))
        status   = ORDER_ST.get(order.get("status",""), sc(order.get("status","")))
        provider = sc(order.get("provider",""))
        otp      = order.get("otp","")
        otp_line = f"\n{pe('key')} {sc('OTP')}: <code>{otp}</code>" if otp else ""
        await msg.answer(
            f"📱 <b>{phone}</b>\n"
            f"📡 {sc('Provider')}: {provider}\n"
            f"🔄 {sc('Status')}: {status}{otp_line}",
            parse_mode="HTML", reply_markup=kb_order(oid, otp))

# ── /analytics ────────────────────────────────────────────────────────────────
@dp.message(Command("analytics"))
@require_active
async def cmd_analytics(msg: Message):
    if sio.connected: await sio.emit("get_analytics"); await asyncio.sleep(1.5)
    events = dash_analytics.get("events",[])
    if not events:
        await msg.answer(f"📭 {sc('No analytics yet.')}", parse_mode="HTML"); return
    counts: dict = {}
    for ev in events:
        p = ev.get("p","?"); counts.setdefault(p,{"fetched":0,"jio":0,"otp":0,"login":0})
        et = ev.get("e","")
        if et in counts[p]: counts[p][et] += 1
    lines = [f"{pe('chart')} <b>{sc('Provider Analytics')}</b>\n"]
    for p, c in counts.items():
        pname = sc("Firebase") if p=="FirebaseDirect" else sc(p)
        jr  = f"{c['jio']/c['fetched']*100:.0f}%" if c["fetched"] else "0%"
        or_ = f"{c['otp']/c['jio']*100:.0f}%"     if c["jio"]     else "0%"
        lines.append(
            f"🔵 <b>{pname}</b>\n"
            f"  📱<code>{c['fetched']}</code> · ✅<code>{c['jio']}</code>({jr})"
            f" · {pe('key')}<code>{c['otp']}</code>({or_})"
            f" · {pe('lock')}<code>{c['login']}</code>")
    await msg.answer("\n".join(lines), parse_mode="HTML")

# ── Admin: user management ────────────────────────────────────────────────────
@dp.message(Command("adddays"))
@admin_only
async def cmd_adddays(msg: Message):
    parts = msg.text.strip().split()
    if len(parts)<3:
        await msg.answer("❌ /adddays <code>&lt;id&gt; &lt;days&gt;</code>",parse_mode="HTML"); return
    try: tid=int(parts[1]); days=int(parts[2]); assert days>0
    except: await msg.answer(f"❌ {sc('Must be positive integers.')}",parse_mode="HTML"); return
    new_exp = bot_db.add_days(tid, days)
    await msg.answer(
        f"🟢 <b>+{days} {sc('days')}</b> {sc('for')} <code>{tid}</code>\n"
        f"📅 {sc('New expiry')}: <code>{new_exp.strftime('%Y-%m-%d %H:%M')} UTC</code>",
        parse_mode="HTML")
    try:
        await bot.send_message(tid,
            f"{pe('star')} <b>{sc(f'{days} day(s) added to your access!')}</b>\n"
            f"📅 {sc('Expires')}: <code>{new_exp.strftime('%Y-%m-%d %H:%M')} UTC</code>\n\n"
            f"{sc('Use')} /sniper {sc('to start.')}",
            parse_mode="HTML", reply_markup=kb_main())
    except: pass
    bot_db.log_activity(msg.from_user.id,"add_days",f"{tid} +{days}d")

@dp.message(Command("setexpiry"))
@admin_only
async def cmd_setexpiry(msg: Message):
    parts = msg.text.strip().split()
    if len(parts)<3:
        await msg.answer("❌ /setexpiry <code>&lt;id&gt; &lt;YYYY-MM-DD&gt;</code>",parse_mode="HTML"); return
    try: tid=int(parts[1]); exp=datetime.strptime(parts[2],"%Y-%m-%d")
    except: await msg.answer(f"❌ {sc('Example: /setexpiry 123456 2025-12-31')}",parse_mode="HTML"); return
    if not bot_db.get_user(tid): bot_db.register_user(tid,"","")
    bot_db.set_expiry(tid, exp)
    await msg.answer(f"🟢 <code>{tid}</code> → <code>{exp.strftime('%Y-%m-%d')}</code>",parse_mode="HTML")

@dp.message(Command("ban"))
@admin_only
async def cmd_ban(msg: Message):
    parts = msg.text.strip().split()
    if len(parts)<2: await msg.answer("❌ /ban <code>&lt;id&gt;</code>",parse_mode="HTML"); return
    try: tid=int(parts[1])
    except: await msg.answer(f"❌ {sc('Invalid ID.')}",parse_mode="HTML"); return
    bot_db.ban_user(tid)
    await msg.answer(f"🔴 <code>{tid}</code> {sc('banned.')}",parse_mode="HTML")

@dp.message(Command("unban"))
@admin_only
async def cmd_unban(msg: Message):
    parts = msg.text.strip().split()
    if len(parts)<2: await msg.answer("❌ /unban <code>&lt;id&gt;</code>",parse_mode="HTML"); return
    try: tid=int(parts[1])
    except: await msg.answer(f"❌ {sc('Invalid ID.')}",parse_mode="HTML"); return
    bot_db.unban_user(tid)
    await msg.answer(f"🟢 <code>{tid}</code> {sc('unbanned.')}",parse_mode="HTML")

@dp.message(Command("listusers"))
@admin_only
async def cmd_listusers(msg: Message):
    users = bot_db.get_all_users()
    if not users: await msg.answer(f"{sc('No users yet.')}",parse_mode="HTML"); return
    active_n = sum(1 for u in users if bot_db.is_active(u))
    lines = [f"👥 <b>{sc(f'Users — {len(users)} total, {active_n} active')}</b>\n"]
    for u in users[:40]:
        rem  = bot_db.time_remaining(u.get("expires_at"))
        ban  = " 🔴" if u["is_banned"] else ""
        name = sc(u.get("first_name") or u.get("username") or "Unknown")
        lines.append(f"• <code>{u['user_id']}</code> {name}{ban}\n  └ {rem}")
    if len(users)>40: lines.append(f"\n<i>+{len(users)-40} more</i>")
    await msg.answer("\n".join(lines),parse_mode="HTML")

@dp.message(Command("broadcast"))
@admin_only
async def cmd_broadcast(msg: Message):
    parts = msg.text.strip().split(None,1)
    if len(parts)<2: await msg.answer("❌ /broadcast <code>&lt;message&gt;</code>",parse_mode="HTML"); return
    text  = parts[1]; users = bot_db.get_all_users(); sent = failed = 0
    for u in users:
        if u["is_banned"]: continue
        try:
            await bot.send_message(u["user_id"],
                f"📢 <b>{sc('Announcement')}</b>\n\n{text}",parse_mode="HTML")
            sent += 1
        except: failed += 1
        await asyncio.sleep(0.05)
    await msg.answer(
        f"📢 <b>{sc('Broadcast Done!')}</b>\n🟢 {sent} · 🔴 {failed}",parse_mode="HTML")

@dp.message(Command("chatgpt"))
@admin_only
async def cmd_chatgpt(msg: Message):
    parts = msg.text.strip().split()
    tabs  = int(parts[1]) if len(parts)>1 and parts[1].isdigit() else 1
    if not sio.connected: await msg.answer(f"🔴 {sc('Dashboard offline.')}",parse_mode="HTML"); return
    await sio.emit("start_chatgpt_login",{"num_tabs": tabs})
    await msg.answer(
        f"🤖 <b>{sc('ChatGPT Login Started!')}</b>\n"
        f"🖥️ {sc('Tabs')}: <code>{tabs}</code>\n\n"
        f"{sc('Watch')} /logs {sc('for')} <code>[ᴄʜᴀᴛɢᴘᴛ]</code> {sc('entries.')}",
        parse_mode="HTML")

@dp.message(Command("killzombies"))
@admin_only
async def cmd_killzombies(msg: Message):
    if not sio.connected: await msg.answer(f"🔴 {sc('Dashboard offline.')}",parse_mode="HTML"); return
    await sio.emit("kill_zombie_browsers")
    await msg.answer(f"🧹 <b>{sc('Zombie browsers killed.')}</b>",parse_mode="HTML")

@dp.message(Command("setvar"))
@admin_only
async def cmd_setvar(msg: Message):
    parts = msg.text.strip().split(None,2)
    if len(parts)<3:
        await msg.answer(
            f"❌ /setvar <code>KEY value</code>\n\n<b>{sc('Examples')}:</b>\n"
            f"<code>/setvar FIREBASE_URLS https://a.firebaseio.com</code>\n"
            f"<code>/setvar GRIZZLY_API_KEY abc123</code>",parse_mode="HTML"); return
    key = parts[1].upper(); val = parts[2].strip()
    bot_db.set_setting(key, val); os.environ[key] = val
    preview = val[:60]+"..." if len(val)>60 else val
    await msg.answer(
        f"🟢 <b><code>{key}</code></b> {sc('updated!')}\n"
        f"{sc('Value')}: <code>{preview}</code>\n\n"
        f"<i>⚠️ {sc('Restart dashboard for new sessions.')}</i>",parse_mode="HTML")

@dp.message(Command("getvar"))
@admin_only
async def cmd_getvar(msg: Message):
    parts = msg.text.strip().split()
    if len(parts)<2: await msg.answer("❌ /getvar <code>KEY</code>",parse_mode="HTML"); return
    key = parts[1].upper()
    val = bot_db.get_setting(key) or os.environ.get(key, f"<i>{sc('not set')}</i>")
    if any(s in key for s in ("KEY","TOKEN","SECRET","PASSWORD")):
        val = str(val)[:4]+"****"+str(val)[-3:] if len(str(val))>7 else "****"
    await msg.answer(f"🔑 <code>{key}</code> =\n<code>{val}</code>",parse_mode="HTML")

@dp.message(Command("listvars"))
@admin_only
async def cmd_listvars(msg: Message):
    settings = bot_db.get_all_settings()
    if not settings: await msg.answer(f"{sc('No custom vars set.')}",parse_mode="HTML"); return
    lines = [f"⚙️ <b>{sc('Overridden Variables')}</b>\n"]
    for k,v in settings.items():
        masked = v[:4]+"****" if any(s in k for s in ("KEY","TOKEN","SECRET")) else v[:60]
        lines.append(f"• <code>{k}</code> = <code>{masked}</code>")
    await msg.answer("\n".join(lines),parse_mode="HTML")

@dp.message(Command("delvar"))
@admin_only
async def cmd_delvar(msg: Message):
    parts = msg.text.strip().split()
    if len(parts)<2: await msg.answer("❌ /delvar <code>KEY</code>",parse_mode="HTML"); return
    bot_db.delete_setting(parts[1].upper())
    await msg.answer(f"🗑️ <code>{parts[1].upper()}</code> {sc('removed.')}",parse_mode="HTML")

@dp.message(Command("adminstats"))
@admin_only
async def cmd_adminstats(msg: Message):
    users  = bot_db.get_all_users()
    active = sum(1 for u in users if bot_db.is_active(u))
    banned = sum(1 for u in users if u["is_banned"])
    s      = dash_stats; sy = dash_system
    conn   = f"🟢 {sc('Connected')}" if sio.connected  else f"🔴 {sc('Disconnected')}"
    snip   = f"🟢 {sc('Running')}"   if sniping_active else f"🔴 {sc('Stopped')}"
    await msg.answer(
        f"{pe('crown')} <b>{sc('Admin — Full Stats')}</b>\n\n"
        f"👥 {sc('Total users')}: <code>{len(users)}</code>\n"
        f"🟢 {sc('Active subs')}: <code>{active}</code>\n"
        f"🔴 {sc('Banned')}: <code>{banned}</code>\n"
        f"⚙️ {sc('Custom vars')}: <code>{len(bot_db.get_all_settings())}</code>\n\n"
        f"📱 {sc('Fetched')}: <code>{s.get('fetched',0)}</code>\n"
        f"✅ {sc('Jio')}: <code>{s.get('jio',0)}</code>\n"
        f"{pe('key')} {sc('OTP')}: <code>{s.get('otp',0)}</code>\n"
        f"{pe('lock')} {sc('Login')}: <code>{s.get('login',0)}</code>\n\n"
        f"🔲 {sc('CPU')}: <code>{sy.get('cpu',0):.1f}%</code> · "
        f"{pe('globe')} {sc('Browsers')}: <code>{sy.get('browsers_open',0)}</code>\n"
        f"🔌 {conn} · {pe('bolt')} {snip}", parse_mode="HTML")

# ── Provider management ───────────────────────────────────────────────────────
# Maps exact dashboard provider names → their env var keys
PROVIDER_ENV_MAP = {
    "OTPSMS":       "OTPSMS_API_KEY",
    "UOTP":         "UOTP_API_KEY",
    "Grizzly":      "GRIZZLY_API_KEY",
    "Tiger":        "TIGER_API_KEY",
    "MeowSMS":      "MEOWSMS_API_KEY",
    "OTPDoctor":    "OTPDOCTOR_API_KEY",
    "FirebaseDirect": None,   # uses FIREBASE_URLS (comma-separated), not a key
}
PROVIDER_ALIASES = {
    "otpsms":"OTPSMS","uotp":"UOTP","grizzly":"Grizzly","tiger":"Tiger",
    "meow":"MeowSMS","meowsms":"MeowSMS","otpdoctor":"OTPDoctor",
    "firebase":"FirebaseDirect","firebasedirect":"FirebaseDirect","fb":"FirebaseDirect",
}

def _provider_key_status(pname):
    """Return masked key value or status string for a provider."""
    env_key = PROVIDER_ENV_MAP.get(pname)
    if pname == "FirebaseDirect":
        urls = os.environ.get("FIREBASE_URLS","")
        if not urls: return f"<i>{sc('not set')}</i>"
        count = len([u for u in urls.split(",") if u.strip()])
        return f"<code>{count} URL(s) set</code>"
    if not env_key: return f"<i>{sc('N/A')}</i>"
    val = bot_db.get_setting(env_key) or os.environ.get(env_key,"")
    if not val: return f"🔴 <i>{sc('not set')}</i>"
    masked = val[:4]+"****"+val[-3:] if len(val)>7 else "****"
    return f"🟢 <code>{masked}</code>"

def kb_provider_select(action="setkey"):
    """Inline keyboard — tap a provider to manage it."""
    rows = []
    for p in ALL_PROVIDERS:
        label = "Firebase" if p=="FirebaseDirect" else p
        env_key = PROVIDER_ENV_MAP.get(p)
        val = os.environ.get(env_key,"") if env_key else os.environ.get("FIREBASE_URLS","")
        icon = "🟢" if val else "🔴"
        rows.append([btn_primary(f"{icon} {sc(label)}", f"prov_{action}:{p}", "key")])
    rows.append([btn_default(f"◀️ {sc('Back')}", "prov_close", "back")])
    return InlineKeyboardMarkup(inline_keyboard=rows)

# /providers — show all providers with key status + live balance
@dp.message(Command("providers"))
@admin_only
async def cmd_providers(msg: Message):
    if sio.connected:
        await sio.emit("get_balances"); await asyncio.sleep(2)
    lines = [f"{pe('gem')} <b>{sc('Provider Config & Balance')}</b>\n"]
    for p in ALL_PROVIDERS:
        label   = "Firebase" if p=="FirebaseDirect" else p
        key_st  = _provider_key_status(p)
        bal     = dash_balances.get(p)
        bal_txt = f" · 💰<code>{bal}</code>" if bal is not None else ""
        lines.append(f"📡 <b>{sc(label)}</b>: {key_st}{bal_txt}")
    lines.append(
        f"\n{pe('zap')} <b>{sc('Commands')}:</b>\n"
        f"/setprovider <code>&lt;name&gt; &lt;api_key&gt;</code>\n"
        f"/setfirebase <code>&lt;url1,url2,...&gt;</code>\n\n"
        f"<i>{sc('Names')}: otpsms · uotp · grizzly · tiger · meowsms · otpdoctor · firebase</i>"
    )
    await msg.answer("\n".join(lines), parse_mode="HTML",
                     reply_markup=kb_provider_select("setkey"))

# Inline: tap a provider → show what to send
@dp.callback_query(F.data.startswith("prov_setkey:"))
async def cb_prov_setkey(cb: CallbackQuery):
    pname = cb.data.split(":",1)[1]
    label = "Firebase" if pname=="FirebaseDirect" else pname
    if pname == "FirebaseDirect":
        await cb.message.answer(
            f"{pe('fire')} <b>{sc('Update Firebase URLs')}</b>\n\n"
            f"{sc('Send this command')}:\n"
            f"<code>/setfirebase https://url1.firebaseio.com,https://url2.firebaseio.com</code>\n\n"
            f"<i>{sc('Comma-separated. Changes take effect immediately.')}</i>",
            parse_mode="HTML")
    else:
        env_key = PROVIDER_ENV_MAP[pname]
        await cb.message.answer(
            f"{pe('key')} <b>{sc(f'Update {label} API Key')}</b>\n\n"
            f"{sc('Current')}: {_provider_key_status(pname)}\n\n"
            f"{sc('Send this command')}:\n"
            f"<code>/setprovider {label.lower()} YOUR_NEW_KEY</code>\n\n"
            f"<i>({sc('env var')}: <code>{env_key}</code>)</i>",
            parse_mode="HTML")
    await cb.answer()

@dp.callback_query(F.data == "prov_close")
async def cb_prov_close(cb: CallbackQuery):
    await cb.message.edit_reply_markup(reply_markup=None); await cb.answer()

# /setprovider <name> <api_key>  — update key live + push to dashboard config
@dp.message(Command("setprovider"))
@admin_only
async def cmd_setprovider(msg: Message):
    parts = msg.text.strip().split(None, 2)
    if len(parts) < 3:
        await msg.answer(
            f"❌ <b>{sc('Usage')}:</b> /setprovider <code>&lt;name&gt; &lt;api_key&gt;</code>\n\n"
            f"<b>{sc('Valid names')}:</b>\n"
            f"<code>otpsms · uotp · grizzly · tiger · meowsms · otpdoctor</code>\n\n"
            f"<b>{sc('Examples')}:</b>\n"
            f"<code>/setprovider grizzly abc123xyz</code>\n"
            f"<code>/setprovider uotp myapikey456</code>",
            parse_mode="HTML"); return

    alias  = parts[1].lower().strip()
    api_key = parts[2].strip()
    pname  = PROVIDER_ALIASES.get(alias)

    if not pname:
        await msg.answer(
            f"❌ {sc('Unknown provider')} <code>{alias}</code>\n"
            f"<i>{sc('Valid')}: otpsms · uotp · grizzly · tiger · meowsms · otpdoctor · firebase</i>",
            parse_mode="HTML"); return

    if pname == "FirebaseDirect":
        await msg.answer(
            f"⚠️ {sc('Firebase uses URLs, not an API key.')}\n"
            f"{sc('Use')} /setfirebase {sc('instead.')}",
            parse_mode="HTML"); return

    env_key = PROVIDER_ENV_MAP[pname]
    label   = pname

    # 1. Save to persistent DB + current process env
    bot_db.set_setting(env_key, api_key)
    os.environ[env_key] = api_key

    # 2. Push live to dashboard via save_settings if connected
    dash_pushed = False
    if sio.connected:
        try:
            await sio.emit("get_settings"); await asyncio.sleep(0.5)
            # Update just this provider's key in dashboard config
            update_payload = {
                "providers": {
                    pname: {"key": api_key}
                }
            }
            await sio.emit("save_settings", update_payload)
            dash_pushed = True
        except Exception as e:
            log.warning(f"Dashboard push failed: {e}")

    masked = api_key[:4]+"****"+api_key[-3:] if len(api_key)>7 else "****"
    live_txt = (f"🟢 {sc('Pushed to dashboard live!')}" if dash_pushed
                else f"⚠️ {sc('Dashboard offline — takes effect on next restart.')}")
    await msg.answer(
        f"✅ <b>{sc(label)}</b> {sc('API key updated!')}\n\n"
        f"{pe('key')} {sc('Key')}: <code>{masked}</code>\n"
        f"⚙️ {sc('Env var')}: <code>{env_key}</code>\n"
        f"📡 {live_txt}",
        parse_mode="HTML")
    bot_db.log_activity(msg.from_user.id, "set_provider", f"{pname} key updated")

# /setfirebase <url1,url2,...>  — update Firebase URLs live
@dp.message(Command("setfirebase"))
@admin_only
async def cmd_setfirebase(msg: Message):
    parts = msg.text.strip().split(None, 1)
    if len(parts) < 2:
        await msg.answer(
            f"❌ <b>{sc('Usage')}:</b>\n"
            f"<code>/setfirebase https://a.firebaseio.com,https://b.firebaseio.com</code>\n\n"
            f"<i>{sc('Comma-separated list of Firebase Realtime DB URLs.')}</i>",
            parse_mode="HTML"); return

    raw  = parts[1].strip()
    urls = [u.strip() for u in raw.split(",") if u.strip()]

    if not urls:
        await msg.answer(f"❌ {sc('No valid URLs found.')}", parse_mode="HTML"); return

    # Validate basic format
    bad = [u for u in urls if not u.startswith("http")]
    if bad:
        await msg.answer(
            f"❌ {sc('These do not look like valid URLs')}:\n"
            + "\n".join(f"<code>{b}</code>" for b in bad),
            parse_mode="HTML"); return

    joined = ",".join(urls)
    bot_db.set_setting("FIREBASE_URLS", joined)
    os.environ["FIREBASE_URLS"] = joined

    # Push live to dashboard
    dash_pushed = False
    if sio.connected:
        try:
            await sio.emit("save_settings", {"firebase_urls": urls})
            dash_pushed = True
        except Exception as e:
            log.warning(f"Dashboard push failed: {e}")

    live_txt = (f"🟢 {sc('Pushed to dashboard live!')}" if dash_pushed
                else f"⚠️ {sc('Dashboard offline — takes effect on next restart.')}")
    lines = [f"{pe('fire')} <b>{sc('Firebase URLs Updated!')}</b>\n"]
    for i, u in enumerate(urls, 1):
        lines.append(f"{i}. <code>{u}</code>")
    lines.append(f"\n📡 {live_txt}")
    await msg.answer("\n".join(lines), parse_mode="HTML")
    bot_db.log_activity(msg.from_user.id, "set_firebase", f"{len(urls)} URLs")

# ── Background socket connector ───────────────────────────────────────────────
async def dashboard_connector():
    while True:
        try:
            if not sio.connected:
                log.info(f"Connecting to dashboard @ {DASHBOARD_URL}")
                await sio.connect(DASHBOARD_URL, transports=["websocket","polling"])
        except Exception as e:
            log.warning(f"Dashboard unreachable ({e}). Retry in 15s.")
        await asyncio.sleep(15)

async def main():
    log.info(f"🤖 {sc('AnneBella Jio-ChatGPT Bot')} v4.0 starting (aiogram 3.30)")
    if not ADMIN_IDS: log.warning("⚠️ No ADMIN_IDS set in .env!")
    asyncio.create_task(dashboard_connector())
    await dp.start_polling(bot, skip_updates=True)

if __name__ == "__main__":
    asyncio.run(main())
