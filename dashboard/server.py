#!/usr/bin/env python3
"""
Jio Sniper Dashboard — Backend Server v2.0
FastAPI + Socket.IO + Playwright + Multi-Provider SMS APIs
Features: Resource Monitor, Settings, Analytics, Order Detail
"""
import asyncio
import aiohttp
import os
import re
import time
import json
import uuid
import sys
import shutil
import psutil
import random
import csv
import base64
from urllib.parse import urlparse, parse_qs

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import socketio
import uvicorn

# ─── Paths ────────────────────────────────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(BASE_DIR)
PROFILES_DIR = os.path.join(PROJECT_DIR, "profiles")
CONFIG_FILE = os.path.join(BASE_DIR, "config.json")
ANALYTICS_FILE = os.path.join(BASE_DIR, "analytics.json")
SPEED_MAP = {"slow": 2.0, "normal": 1.0, "fast": 0.3}
ANALYTICS_MAX_AGE_DAYS = 7

# ─── AnneBella panel URL helpers ─────────────────────────────────────────────
def decode_panel_accounts(panel_url):
    """Decode ?m=<base64-json> from an AnneBella panel URL into Firebase accounts."""
    panel_url = (panel_url or "").strip()
    if not panel_url:
        return []

    try:
        encoded = parse_qs(urlparse(panel_url).query).get("m", [""])[0]
        if not encoded:
            return []

        # tolerate missing Base64 padding
        encoded += "=" * (-len(encoded) % 4)
        decoded = base64.b64decode(encoded).decode("utf-8")
        raw_items = json.loads(decoded)

        accounts = []
        for item in raw_items if isinstance(raw_items, list) else []:
            if not isinstance(item, dict):
                continue
            url = str(item.get("url", "")).strip().rstrip("/")
            key = str(item.get("key", "")).strip()
            if url.startswith(("http://", "https://")):
                accounts.append({"url": url, "key": key})
        return accounts
    except Exception as exc:
        print(f"Failed to decode PANEL_URL: {exc}")
        return []

PANEL_URL = os.environ.get("PANEL_URL", "").strip()
PANEL_ACCOUNTS = decode_panel_accounts(PANEL_URL)

# ─── Default Configuration ───────────────────────────────────────────────────
DEFAULT_CONFIG = {
    "providers": {
        "OTPSMS": {
            "url": "https://www.otpsms.in/stubs/handler_api.php",
            "key": os.environ.get("OTPSMS_API_KEY", ""),
            "service": "jio",
            "country": "",
            "delay": 3
        },
        "UOTP": {
            "url": "https://uotp.store/api/stubs/handler_api.php",
            "key": os.environ.get("UOTP_API_KEY", ""),
            "service": "jio", "country": "22", "delay": 2
        },
        "Grizzly": {
            "url": "https://api.grizzlysms.com/stubs/handler_api.php",
            "key": os.environ.get("GRIZZLY_API_KEY", ""),
            "service": "jio", "country": "22", "delay": 3
        },
        "Tiger": {
            "url": "https://api.tiger-sms.com/stubs/handler_api.php",
            "key": os.environ.get("TIGER_API_KEY", ""),
            "service": "mjo", "country": "22", "delay": 5
        },
        "MeowSMS": {
            "url": "https://meowsms.shop/stubs/handler_api.php",
            "key": os.environ.get("MEOWSMS_API_KEY", ""),
            "service": "myjio", "country": "22", "delay": 3
        },
        "OTPDoctor": {
            "url": "https://www.otpdoctor.in/stubs/handler_api.php",
            "key": os.environ.get("OTPDOCTOR_API_KEY", ""),
            "service": "13318", "country": "in", "delay": 3
        },
        "FirebaseDirect": {
            "url": "",
            "key": "",
            "service": "jio", "country": "in", "delay": 0
        }
    },
    "firebase_urls": [
        a["url"] for a in PANEL_ACCOUNTS
    ] or [u.strip() for u in os.environ.get("FIREBASE_URLS", "").split(",") if u.strip()],
    "firebase_accounts": PANEL_ACCOUNTS,  # auto-populated from PANEL_URL when present
    "otpsms_servers": ["1", "2", "5", "6", "7", "8", "9", "11", "12", "13", "33", "36", "71", "234", "458", "2344", "4566", "64653"],
    "uotp_servers": ["5", "3", "4", "2", "1", "8"],
    "otpdoctor_services": ["13318", "13273"],
    "omkar_keys": [k.strip() for k in os.environ.get("OMKAR_API_KEYS", "").split(",") if k.strip()],
    "omkar_usage": {},
    "timing": {
        "otp_poll_interval": 3,
        "cancel_wait_seconds": 120,
        "max_otp_attempts": 60
    }
}

JIO_LOGIN_URL = "https://www.jio.com/selfcare//"

# ─── Proxies ─────────────────────────────────────────────────────────────────


# ─── Load / Save Config ──────────────────────────────────────────────────────
def load_config():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r') as f:
                saved = json.load(f)
                # Deep merge providers so new ones (like FirebaseDirect) appear
                if "providers" in saved:
                    for p_name, p_data in DEFAULT_CONFIG["providers"].items():
                        if p_name not in saved["providers"]:
                            saved["providers"][p_name] = p_data
                
                # Merge with defaults for any missing keys
                merged = DEFAULT_CONFIG.copy()
                merged.update(saved)
                # Force dynamic keys from env to override saved static keys
                for p_name, p_data in merged.get("providers", {}).items():
                    default_key = DEFAULT_CONFIG["providers"].get(p_name, {}).get("key")
                    if default_key:
                        p_data["key"] = default_key
                merged["omkar_keys"] = DEFAULT_CONFIG["omkar_keys"]
                if "firebase_urls" not in merged:
                    merged["firebase_urls"] = DEFAULT_CONFIG["firebase_urls"]
                if "firebase_accounts" not in merged:
                    # Migrate: wrap existing firebase_urls as accounts with no key
                    merged["firebase_accounts"] = [{"url": u, "key": ""} for u in merged["firebase_urls"]]

                # PANEL_URL always overrides stale config.json panel/Firebase entries.
                if PANEL_ACCOUNTS:
                    merged["firebase_accounts"] = PANEL_ACCOUNTS
                    merged["firebase_urls"] = [a["url"] for a in PANEL_ACCOUNTS]
                return merged
        except:
            pass
    return DEFAULT_CONFIG.copy()

def save_config(cfg):
    with open(CONFIG_FILE, 'w') as f:
        json.dump(cfg, f, indent=2)

config = load_config()

# ─── Analytics Persistence ────────────────────────────────────────────────────
def load_analytics():
    if os.path.exists(ANALYTICS_FILE):
        try:
            with open(ANALYTICS_FILE, 'r') as f:
                data = json.load(f)
                # Purge entries older than 7 days
                cutoff = time.time() - (ANALYTICS_MAX_AGE_DAYS * 86400)
                data["events"] = [e for e in data.get("events", []) if e.get("t", 0) > cutoff]
                return data
        except:
            pass
    return {"events": [], "sessions": []}

def save_analytics():
    # Purge old entries before saving
    cutoff = time.time() - (ANALYTICS_MAX_AGE_DAYS * 86400)
    analytics["events"] = [e for e in analytics.get("events", []) if e.get("t", 0) > cutoff]
    with open(ANALYTICS_FILE, 'w') as f:
        json.dump(analytics, f)

def record_analytics_event(provider, event_type, extra=None):
    """Record a timestamped analytics event."""
    entry = {"t": time.time(), "p": provider, "e": event_type}
    if extra:
        entry.update(extra)
    analytics["events"].append(entry)
    # Periodic save (every 10 events)
    if len(analytics["events"]) % 10 == 0:
        save_analytics()

analytics = load_analytics()

# ─── App Setup ────────────────────────────────────────────────────────────────
sio = socketio.AsyncServer(async_mode='asgi', cors_allowed_origins='*')
app = FastAPI()
sio_app = socketio.ASGIApp(sio, app)

static_dir = os.path.join(BASE_DIR, "static")
app.mount("/static", StaticFiles(directory=static_dir), name="static")

@app.get("/")
async def index():
    return FileResponse(os.path.join(static_dir, "index.html"))

# ─── Global State ─────────────────────────────────────────────────────────────
class State:
    orders = {}
    sniper_tasks = []
    is_sniping = False
    stop_event = None
    http_session = None
    browser = None
    pw = None
    omkar_index = 0
    dead_omkar_keys = set()
    active_browsers = 0
    jio_count = 0
    target_count = 5
    stats = {"fetched": 0, "jio": 0, "otp": 0, "login": 0}
    system_monitor_task = None
    omkar_gen_stop = False
    
    # Firebase State
    firebase_otp_queues = {}
    firebase_listener_task = None

state = State()

# ─── System Resource Monitor ─────────────────────────────────────────────────
async def system_monitor_loop():
    """Emit CPU/RAM stats every 2 seconds."""
    while True:
        try:
            cpu = psutil.cpu_percent(interval=1)
            mem = psutil.virtual_memory()
            omkar_usage_dict = config.get("omkar_usage", {})
            omkar_keys_list = config.get("omkar_keys", [])
            
            omkar_data = []
            for i, key in enumerate(omkar_keys_list):
                usage = omkar_usage_dict.get(key, 0)
                omkar_data.append({
                    "label": f"Key {i+1} (..{key[-4:]})",
                    "usage": usage,
                    "max": 200
                })
            
            browser_count = sum(1 for o in state.orders.values() if o.get("_context") is not None)
            
            await sio.emit("system_stats", {
                "cpu": round(cpu, 1),
                "ram_used": round(mem.used / (1024**3), 1),
                "ram_total": round(mem.total / (1024**3), 1),
                "ram_percent": mem.percent,
                "browsers_open": browser_count,
                "omkar_data": omkar_data
            })
        except:
            pass
        await asyncio.sleep(2)

# ─── SMS API Functions ────────────────────────────────────────────────────────
async def get_balance(p_name):
    cfg = config["providers"].get(p_name, {})
    if not cfg:
        return None
    try:
        async with state.http_session.get(cfg["url"], params={"action": "getBalance", "api_key": cfg["key"]}) as resp:
            text = (await resp.text()).strip()
            if text.startswith("ACCESS_BALANCE:"):
                return float(text.split(":", 1)[1])
    except:
        pass
    return None

async def buy_grizzly_number():
    """Attempt to buy a Grizzly SMS number for Chile or Indonesia for 'ot' service."""
    cfg = config["providers"].get("Grizzly", {})
    if not cfg:
        return None, None, None, None
        
    api_key = cfg["key"]
    base_url = cfg["url"]
    
    # Try Chile first (151), then Indonesia (6)
    for country_id, country_name, prefix in [("151", "Chile", "56"), ("6", "Indonesia", "62")]:
        try:
            params = {
                "api_key": api_key,
                "action": "getNumber",
                "service": "ot",  # Any other
                "country": country_id
            }
            async with state.http_session.get(base_url, params=params) as resp:
                text = (await resp.text()).strip()
                if text.startswith("ACCESS_NUMBER:"):
                    parts = text.split(":")
                    tzid = parts[1]
                    full_number = parts[2]
                    
                    # Ensure prefix is stripped properly
                    local_number = full_number
                    if local_number.startswith(prefix):
                        local_number = local_number[len(prefix):]
                    
                    return tzid, local_number, country_name, full_number
        except Exception:
            pass
            
    return None, None, None, None

async def poll_grizzly_otp(tzid, timeout=65):
    """Poll for OTP for a given transaction ID."""
    cfg = config["providers"].get("Grizzly", {})
    if not cfg:
        return None
        
    api_key = cfg["key"]
    base_url = cfg["url"]
    
    start_time = time.time()
    while time.time() - start_time < timeout:
        try:
            params = {
                "api_key": api_key,
                "action": "getStatus",
                "id": tzid
            }
            async with state.http_session.get(base_url, params=params) as resp:
                text = (await resp.text()).strip()
                if text.startswith("STATUS_OK:"):
                    return text.split(":")[1]
        except Exception:
            pass
        await asyncio.sleep(3)
    return None

async def cancel_grizzly_number(tzid):
    """Cancel number to get refund if OTP never arrived."""
    cfg = config["providers"].get("Grizzly", {})
    if not cfg:
        return False
        
    api_key = cfg["key"]
    base_url = cfg["url"]
    
    try:
        params = {
            "api_key": api_key,
            "action": "setStatus",
            "status": "8", # Cancel code for Grizzly
            "id": tzid
        }
        async with state.http_session.get(base_url, params=params) as resp:
            text = (await resp.text()).strip()
            return "ACCESS_CANCEL" in text
    except Exception:
        pass
    return False

async def get_carrier(number_str):
    if not number_str.startswith('+'): number_str = '+' + number_str
    url = "https://carrier-lookup-api.omkar.cloud/lookup"
    omkar_keys = config.get("omkar_keys", [])
    
    if "omkar_usage" not in config:
        config["omkar_usage"] = {}
        
    for _ in range(len(omkar_keys)):
        key = omkar_keys[state.omkar_index % len(omkar_keys)]
        if key not in config["omkar_usage"]:
            config["omkar_usage"][key] = 0
            
        try:
            async with state.http_session.get(url, params={"phone": number_str}, headers={"API-Key": key}) as resp:
                if resp.status in [429, 400, 403]:
                    data = await resp.json()
                    msg = data.get("message", "").lower()
                    if "exceeded" in msg or "verify your phone number" in msg:
                        config["omkar_usage"][key] = 200
                        save_config(config)
                        state.omkar_index = (state.omkar_index + 1) % len(omkar_keys)
                        continue
                if resp.status == 200:
                    config["omkar_usage"][key] += 1
                    save_config(config)
                    return (await resp.json()).get("carrier", "Unknown")
        except:
            pass
    return "Unknown"

async def buy_number(p_name):
    cfg = config["providers"].get(p_name, {})
    if not cfg:
        return {"status": "error"}
    
    # Base parameters
    params = {"action": "getNumber", "api_key": cfg["key"]}
    if cfg.get("country"):
        params["country"] = cfg["country"]
    
    # Handle provider-specific rotations (servers or services)
    rotations = [None]
    if p_name == "OTPSMS":
        rotations = config.get("otpsms_servers", [])
        params["service"] = cfg["service"]
    elif p_name == "UOTP":
        rotations = config.get("uotp_servers", [])
        params["service"] = cfg["service"]
    elif p_name == "OTPDoctor":
        rotations = config.get("otpdoctor_services", [])
    else:
        params["service"] = cfg["service"]
        
    for rot in rotations:
        if p_name == "OTPSMS" and rot:
            params["server"] = rot
        elif p_name == "UOTP" and rot:
            params["operator"] = rot
        elif p_name == "OTPDoctor" and rot:
            params["service"] = rot
            
        try:
            async with state.http_session.get(cfg["url"], params=params) as resp:
                text = (await resp.text()).strip()
                if text.startswith("ACCESS_NUMBER:"):
                    parts = text.split(":")
                    return {"status": "success", "aid": parts[1], "phone": parts[2]}
        except:
            pass
    return {"status": "error"}

async def get_otp_status(p_name, aid):
    cfg = config["providers"].get(p_name, {})
    if not cfg:
        return "ERROR"
    try:
        async with state.http_session.get(cfg["url"], params={"action": "getStatus", "api_key": cfg["key"], "id": aid}) as resp:
            return (await resp.text()).strip()
    except:
        return "ERROR"

async def cancel_api_number(p_name, aid):
    cfg = config["providers"].get(p_name, {})
    if not cfg:
        return "ERROR"
    try:
        async with state.http_session.get(cfg["url"], params={"action": "setStatus", "api_key": cfg["key"], "status": "8", "id": aid}) as resp:
            return (await resp.text()).strip()
    except:
        return "ERROR"

# ─── Order Helpers ────────────────────────────────────────────────────────────
def order_event(order, msg):
    """Add a timestamped event to an order's lifecycle log."""
    if "events" not in order:
        order["events"] = []
    order["events"].append({"t": time.time(), "msg": msg})

def safe_order(order):
    """Return order dict without internal references for JSON serialization."""
    return {k: v for k, v in order.items() if not k.startswith('_')}

async def emit_order(order):
    state.orders[order["id"]] = order
    await sio.emit("number_update", safe_order(order))

async def emit_stats():
    await sio.emit("stats_update", state.stats)

async def emit_log(msg, level="info"):
    await sio.emit("log", {"message": msg, "level": level})

# ─── Number Processing Pipeline ──────────────────────────────────────────────
async def process_number(p_name, aid, phone):
    order_id = str(uuid.uuid4())[:8]
    order = {
        "id": order_id, "aid": aid, "phone": phone, "provider": p_name,
        "status": "checking_carrier", "carrier": None, "otp": None,
        "timestamp": time.time(), "events": []
    }
    order_event(order, f"Number purchased from {p_name}")
    await emit_order(order)
    state.stats["fetched"] += 1
    record_analytics_event(p_name, "fetched")
    await emit_stats()
    
    # Check carrier
    order_event(order, "Checking carrier via MNP lookup...")
    carrier = await get_carrier(phone)
    order["carrier"] = carrier
    order_event(order, f"Carrier identified: {carrier}")
    
    if "jio" in carrier.lower() or "reliance" in carrier.lower():
        state.stats["jio"] += 1
        record_analytics_event(p_name, "jio")
        await emit_stats()
        order["status"] = "waiting_otp"
        await emit_order(order)
        await emit_log(f"✓ [{p_name}] {phone}: {carrier} — TRUE JIO!", "success")
        
        state.jio_count += 1
        asyncio.create_task(handle_jio_number(order))
    else:
        order["status"] = "non_jio"
        await emit_order(order)
        await emit_log(f"✗ [{p_name}] {phone}: {carrier}", "warn")
        asyncio.create_task(cancel_order(order))

async def handle_jio_number(order):
    try:
        await _handle_jio_number_impl(order)
    finally:
        state.jio_count = max(0, state.jio_count - 1)

async def _handle_jio_number_impl(order):
    aid = order["aid"]
    phone = order["phone"]
    p_name = order["provider"]
    timing = config.get("timing", {})
    poll_interval = timing.get("otp_poll_interval", 3)
    max_attempts = timing.get("max_otp_attempts", 60)
    
    clean_phone = phone[2:] if phone.startswith("91") and len(phone) > 10 else phone
    
    # Browser automation: Open immediately to trigger OTP
    context = None
    page = None
    if state.browser:
        try:
            order["status"] = "logging_in"
            order_event(order, "Opening browser and navigating to jio.com...")
            await emit_order(order)
            
            profile_path = os.path.join(PROFILES_DIR, f"session_{order['id']}")
            os.makedirs(profile_path, exist_ok=True)
            
            context = await state.browser.new_context(
                user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            )
            page = await context.new_page()
            
            order["_context"] = context
            order["_page"] = page
            
            await page.goto(JIO_LOGIN_URL, wait_until="domcontentloaded", timeout=60000)
            await asyncio.sleep(2)
            
            order_event(order, f"Typing phone number: {clean_phone}")
            await page.locator('[data-testid="numberField"]').fill(clean_phone)
            await asyncio.sleep(1)
            
            order_event(order, "Clicking Generate OTP...")
            await page.locator('[data-testid="generateOTPButton"]').click()
            await emit_log(f"[{phone}] Clicked Generate OTP on jio.com", "info")
            await asyncio.sleep(2)
            
            # Detect Jio IP Rate Limits
            if await page.locator('text="exceeded the maximum attempts"').count() > 0:
                raise Exception("Jio IP Rate Limited: Exceeded max attempts!")
            if await page.locator('text="try again after some time"').count() > 0:
                raise Exception("Jio IP Rate Limited: Try again later!")

            
        except Exception as e:
            err_msg = str(e)
            order_event(order, f"Browser setup failed: {err_msg}")
            
            if "Rate Limited" in err_msg:
                await emit_log(f"🚨 [{phone}] Jio Rate Limit hit! Cancelling number.", "error")
                asyncio.create_task(cancel_order(order, instant=True))
            else:
                order["status"] = "cancelled"
                await emit_log(f"[{phone}] Browser error: {err_msg[:80]}", "error")
                # Immediate refund attempt but maybe not instant if we want to be safe
                asyncio.create_task(cancel_order(order, instant=True))
            
            await emit_order(order)
            if context:
                await context.close()
            return
    
    order["status"] = "waiting_otp"
    order_event(order, "Waiting for OTP from SMS provider...")
    await emit_order(order)
    
    max_attempts = 80  # Override to 4 minutes (80 attempts * 3s) for the Resend OTP flow
    
    # Poll for OTP
    otp_code = None
    start_time = time.time()
    resend_clicked = False
    
    for attempt in range(max_attempts):
        elapsed = time.time() - start_time
        if elapsed > 121 and page and not resend_clicked:
            resend_clicked = True
            try:
                order_event(order, "2 mins passed. Clicking Resend OTP on jio.com...")
                await emit_order(order)
                await emit_log(f"[{phone}] Clicking Resend OTP...", "warn")
                await page.locator('button[aria-label="Resend OTP"]').click(timeout=5000)
                await asyncio.sleep(1)
            except Exception as e:
                order_event(order, f"Could not click Resend OTP: {str(e)[:50]}")
                await emit_log(f"[{phone}] Failed to click Resend OTP", "error")

        # Graceful stop: removed early return so active Jio logins finish processing
        status = await get_otp_status(p_name, aid)
        if status.startswith("STATUS_OK:"):
            otp_text = status.split(":", 1)[1]
            match = re.search(r'\b(\d{6})\b', otp_text)
            otp_code = match.group(1) if match else otp_text.strip()
            state.stats["otp"] += 1
            record_analytics_event(p_name, "otp")
            await emit_stats()
            order["otp"] = otp_code
            order["status"] = "otp_received"
            order_event(order, f"OTP received: {otp_code}")
            os.system("afplay /System/Library/Sounds/Glass.aiff &")
            await emit_order(order)
            await emit_log(f"✅ [{p_name}] {phone} OTP: {otp_code}", "success")
            break
        elif "CANCEL" in status:
            order["status"] = "cancelled"
            order_event(order, "Cancelled by SMS provider (no OTP delivered)")
            await emit_order(order)
            await emit_log(f"[{p_name}] {phone} cancelled by server", "error")
            if context:
                await context.close()
            return
        await asyncio.sleep(poll_interval)
    
    if not otp_code:
        order["status"] = "cancelling"
        order_event(order, "Timed out waiting for OTP. Cancelling number...")
        await emit_order(order)
        await emit_log(f"[{p_name}] {phone} no OTP received", "error")
        asyncio.create_task(cancel_order(order, instant=True))
        if context:
            await context.close()
        return
        
    # If we have browser, type OTP and submit
    if page:
        try:
            order["status"] = "logging_in"
            await emit_order(order)
            
            order_event(order, f"Typing OTP: {otp_code}")
            for i, digit in enumerate(otp_code[:6]):
                await page.locator(f'#basic-input-testInput-code-block-{i}').fill(digit)
                await asyncio.sleep(0.1)
            await asyncio.sleep(1)
            
            order_event(order, "Clicking Submit...")
            await page.locator('button:has-text("Submit")').click()
            await asyncio.sleep(3)
            
            state.stats["login"] += 1
            record_analytics_event(p_name, "login")
            await emit_stats()
            # --- AUTO EXTRACTION LOGIC ---
            order["status"] = "logging_in"
            order_event(order, "Looking for Gemini offer banner...")
            await emit_order(order)
            
            captured_url = []
            async def handle_route(route):
                req_url = route.request.url
                if "serviceactivation.google.com" in req_url or "accounts.google.com" in req_url or "oauth2" in req_url.lower():
                    captured_url.append(req_url)
                    try:
                        await route.abort()
                    except: pass
                else:
                    try:
                        await route.continue_()
                    except: pass
            
            await context.route("**/*", handle_route)
            
            try:
                # Wait for the banner to appear (increased timeout for slow Jio loading)
                await page.wait_for_selector('#imageNotification', timeout=60000)
                order_event(order, "Found Gemini banner! Clicking...")
                await emit_order(order)
                
                # We expect the click to open a new tab/redirect
                await page.click('#imageNotification')
                
                # Wait for the redirect to be caught
                for _ in range(15):
                    if captured_url:
                        break
                    await asyncio.sleep(1)
                    
                if captured_url:
                    # Prioritize serviceactivation.google.com if found, otherwise use the first caught URL
                    target_link = next((url for url in captured_url if "serviceactivation.google.com" in url), captured_url[0])
                    
                    # Save to links.txt
                    with open(os.path.join(PROJECT_DIR, "links.txt"), "a") as f:
                        f.write(f"{phone} | {target_link}\n")
                        
                    order["status"] = "logged_in"
                    order_event(order, "✅ Link automatically extracted & saved to links.txt!")
                    await emit_order(order)
                    await emit_log(f"🎉 [{phone}] Gemini Link Saved!", "success")
                    await asyncio.sleep(2)
                    
                    # Successfully done, close browser
                    await context.close()
                    order["_context"] = None
                    return
                else:
                    order_event(order, "⚠️ Clicked banner but redirect not caught.")
            except Exception as e:
                order_event(order, f"⚠️ Banner not found or error: {str(e)[:40]}")

            # Fallback to manual mode if automation failed or timed out
            order["status"] = "extract_link"
            order_event(order, "✅ Login successful! Banner not found, do manual extraction.")
            await emit_order(order)
            await emit_log(f"🎉 [{p_name}] {phone} LOGGED IN! Extract link now.", "success")
            
            # 20-minute timeout for manual extraction
            await asyncio.sleep(1200)
            if order.get("status") == "extract_link":
                order["status"] = "completed"
                order_event(order, "⏰ 20 minutes passed. Closing tab to free RAM.")
                await emit_order(order)
                await emit_log(f"🧹 [{phone}] Auto-closed after 20 mins of inactivity", "warn")
                if context:
                    try:
                        await context.close()
                    except:
                        pass
                if order["id"] in state.orders:
                    del state.orders[order["id"]]
                    await sio.emit("number_remove", {"id": order["id"]})
            
        except Exception as e:
            order["status"] = "cancelled"
            order_event(order, f"Browser error typing OTP: {str(e)}")
            await emit_order(order)
            await emit_log(f"[{phone}] Browser error: {str(e)[:80]}", "error")
            await context.close()

async def cancel_order(order, instant=False):
    order["status"] = "cancelling"
    if instant:
        cancel_wait = 0
    else:
        cancel_wait = config.get("timing", {}).get("cancel_wait_seconds", 120)
        
        # OTPDoctor requires 5 minutes (300 seconds) before cancellation
        if order["provider"] == "OTPDoctor":
            cancel_wait = max(cancel_wait, 300)
            
    if cancel_wait > 0:
        order_event(order, f"Waiting {cancel_wait}s before cancelling...")
        await emit_order(order)
        await asyncio.sleep(cancel_wait)
    else:
        order_event(order, "Cancelling number immediately...")
        await emit_order(order)
    
    while True:
        status = await cancel_api_number(order["provider"], order["aid"])
        if "EARLY_CANCEL_DENIED" in status:
            order_event(order, "Early cancel denied, retrying in 10s...")
            await asyncio.sleep(10)
        elif "CANCEL" in status or "ACTIVATION" in status:
            order["status"] = "cancelled"
            order_event(order, "Successfully cancelled & refunded")
            await emit_order(order)
            await emit_log(f"[{order['phone']}] Cancelled & refunded", "info")
            await asyncio.sleep(5)
            if order["id"] in state.orders:
                del state.orders[order["id"]]
                await sio.emit("number_remove", {"id": order["id"]})
            break
        else:
            order["status"] = "cancelled"
            order_event(order, f"Cancel response: {status}")
            await emit_order(order)
            break

# ─── Firebase Direct Architecture ────────────────────────────────────────────
SUCCESS_CSV = os.path.join(PROJECT_DIR, "extracted_links.csv")
FAILED_CSV = os.path.join(PROJECT_DIR, "failed_links.csv")

def init_csvs():
    if not os.path.exists(SUCCESS_CSV):
        with open(SUCCESS_CSV, "w", newline="") as f:
            csv.writer(f).writerow(["Firebase URL", "Device ID", "Phone Number", "Extracted Link"])
    if not os.path.exists(FAILED_CSV):
        with open(FAILED_CSV, "w", newline="") as f:
            csv.writer(f).writerow(["Firebase URL", "Device ID", "Phone Number", "Failed Step"])

# Regional digit maps for normalization
REGIONAL_DIGITS = str.maketrans(
    "०१२३४५६७८९"  # Hindi/Devanagari
    "০১২৩৪৫৬৭৮৯"  # Bengali
    "੦੧੨੩੪੫੬੭੮੯"  # Punjabi
    "૦૧૨૩૪૫૬૭૮૯"  # Gujarati
    "୦୧୨୩୪୫୬୭୮୯"  # Odia
    "౦౧౨౩౪౫౬౭౮౯"  # Telugu
    "೦೧೨೩೪೫೬೭೮೯"  # Kannada
    "൦൧൨൩൪൫൬൭൮൯"  # Malayalam
    "௦௧௨௩௪௫௬௭௮௯",  # Tamil
    "0123456789" * 9
)

def normalize_digits(text):
    """Convert regional script digits to Latin digits."""
    return text.translate(REGIONAL_DIGITS)

def extract_phone_from_text(text):
    """Extract any 10-digit Indian mobile number, normalizing regional digits."""
    normalized = normalize_digits(text)
    match = re.search(r'(?<!\d)([6-9]\d{9})(?!\d)', normalized)
    return match.group(1) if match else None

def is_jio_message(msg_data):
    """Check if a message is Jio-related by checking both message body and sender."""
    text = msg_data.get("message", "").lower()
    sender = msg_data.get("sender", "").lower()
    return "jio" in text or "jio" in sender

def parse_firebase_datetime(dt_str):
    """Parse Firebase dateTime like '22-07-2025 | 01:12 pm' to a timestamp."""
    try:
        from datetime import datetime
        clean = dt_str.replace(" | ", " ").strip()
        for fmt in ["%d-%m-%Y %I:%M %p", "%d-%m-%Y %I:%M:%S %p", "%d-%m-%Y %H:%M"]:
            try:
                return datetime.strptime(clean, fmt).timestamp()
            except ValueError:
                continue
    except Exception:
        pass
    return 0

async def fetch_initial_mapping():
    device_map = {}

    # Use firebase_accounts (with optional auth key) — fallback to firebase_urls
    raw_accounts = config.get("firebase_accounts") or []
    if not raw_accounts:
        raw_accounts = [{"url": u, "key": ""} for u in config.get("firebase_urls", []) if u.strip()]
    accounts = [a for a in raw_accounts if isinstance(a, dict) and a.get("url", "").strip()]

    if not accounts:
        await emit_log("No Firebase accounts configured! Set PANEL_URL or FIREBASE_URLS.", "error")
        return device_map

    for acc in accounts:
        fb_url = acc["url"].strip().rstrip("/")
        fb_key = acc.get("key", "").strip()
        auth_param = f"?auth={fb_key}" if fb_key else ""
        try:
            # 1. Fetch the online status of clients
            online_devices = set()
            for attempt in range(3):
                try:
                    async with state.http_session.get(f"{fb_url}/clients.json{auth_param}", timeout=15) as resp:
                        if resp.status == 200:
                            clients_data = await resp.json()
                            if clients_data:
                                for dev_id, dev_info in clients_data.items():
                                    if isinstance(dev_info, dict) and dev_info.get("status") is True:
                                        online_devices.add(dev_id)
                            break
                except Exception as req_err:
                    if attempt == 2: raise req_err
                    await asyncio.sleep(2)
            
            # 2. Fetch the messages (with auth if key present)
            data = None
            for attempt in range(3):
                try:
                    async with state.http_session.get(f"{fb_url}/messages.json{auth_param}", timeout=15) as resp:
                        if resp.status == 200:
                            data = await resp.json()
                            break
                except Exception as req_err:
                    if attempt == 2: raise req_err
                    await asyncio.sleep(2)
            if not data: continue
            
            online_count = 0
            offline_count = 0
            jio_tagged = 0
            fallback_found = 0
            
            for device_id, msgs in data.items():
                if not isinstance(msgs, dict): continue
                
                if device_id not in online_devices:
                    offline_count += 1
                    continue
                    
                sorted_msgs = sorted(msgs.items(), key=lambda x: int(x[0]) if str(x[0]).isdigit() else 0, reverse=True)
                if not sorted_msgs:
                    offline_count += 1
                    continue
                
                online_count += 1
                found = False
                
                # Pass 1: Look for messages that mention Jio (sender or body) and contain a phone
                for msg_id, msg_data in sorted_msgs:
                    if not isinstance(msg_data, dict): continue
                    if is_jio_message(msg_data):
                        phone = extract_phone_from_text(msg_data.get("message", ""))
                        if phone:
                            device_map[device_id] = { "phone": phone, "url": fb_url }
                            jio_tagged += 1
                            found = True
                            break
                
                # Pass 2: Fallback — scan ALL messages for any Indian mobile number
                if not found:
                    for msg_id, msg_data in sorted_msgs:
                        if not isinstance(msg_data, dict): continue
                        phone = extract_phone_from_text(msg_data.get("message", ""))
                        if phone:
                            device_map[device_id] = { "phone": phone, "url": fb_url }
                            fallback_found += 1
                            break
                            
            await emit_log(f"[{fb_url.split('/')[2].split('.')[0]}] Online: {online_count}, Offline: {offline_count} | Jio-tagged: {jio_tagged}, Fallback: {fallback_found}", "info")
        except Exception as e:
            await emit_log(f"Error fetching from {fb_url}: {e}", "error")
            
    await emit_log(f"Mapped {len(device_map)} phone numbers from ONLINE Firebase devices!", "success")
    return device_map

async def listen_for_otps(fb_url):
    url = f"{fb_url}/messages.json"
    headers = {"Accept": "text/event-stream"}
    try:
        async with state.http_session.get(url, headers=headers) as resp:
            event_type = None
            buffer = ""
            async for chunk in resp.content.iter_any():
                if state.stop_event and state.stop_event.is_set(): break
                buffer += chunk.decode('utf-8', errors='ignore')
                while '\n' in buffer:
                    line, buffer = buffer.split('\n', 1)
                    line = line.strip()
                    if not line: continue
                    if line.startswith("event: "):
                        event_type = line[7:]
                    elif line.startswith("data: "):
                        data_str = line[6:]
                        if data_str == "null" or event_type not in ["put", "patch"]: continue
                        try:
                            event_data = json.loads(data_str)
                            path, data = event_data.get("path", ""), event_data.get("data")
                            if not data or path == "/": continue
                            parts = [p for p in path.split("/") if p]
                            device_id = None
                            if len(parts) >= 2:
                                device_id = parts[0]
                                messages_to_check = [data]
                            elif len(parts) == 1:
                                device_id = parts[0]
                                if isinstance(data, dict):
                                    messages_to_check = list(data.values())
                                else:
                                    messages_to_check = []
                            else:
                                messages_to_check = []
                                    
                            if device_id and device_id in state.firebase_otp_queues:
                                for msg_dict in messages_to_check:
                                    if isinstance(msg_dict, dict):
                                        text = msg_dict.get("message", "")
                                        normalized = normalize_digits(text)
                                        # Extract ANY 6-digit number — queue is flushed before OTP request,
                                        # so any 6-digit code arriving now IS the OTP
                                        otp_match = re.search(r'\b(\d{6})\b', normalized)
                                        if otp_match:
                                            otp = otp_match.group(1)
                                            await state.firebase_otp_queues[device_id].put(otp)
                        except Exception: pass
    except asyncio.CancelledError: pass
    except Exception as e: await emit_log(f"SSE Listener error for {fb_url}: {e}", "error")

async def process_firebase_number(device_id, phone, fb_url, speed_delay):
    order_id = str(uuid.uuid4())[:8]
    clean_phone = phone[2:] if (phone.startswith("91") and len(phone) > 10) else phone
    order = {
        "id": order_id, "aid": device_id, "phone": "+91" + clean_phone, "provider": "FirebaseDirect",
        "status": "checking_carrier", "carrier": "Jio", "otp": None,
        "timestamp": time.time(), "events": []
    }
    
    order_event(order, f"Discovered on Firebase Device: {device_id}")
    await emit_order(order)
    
    state.stats["fetched"] += 1
    state.stats["jio"] += 1
    await emit_stats()
    
    order["status"] = "waiting_otp"
    await emit_order(order)
    
    state.jio_count += 1
    context = None
    page = None
    
    try:
        if not state.browser: raise Exception("Browser not initialized")
        order["status"] = "logging_in"
        order_event(order, "Opening browser and navigating to jio.com...")
        await emit_order(order)
        
        profile_path = os.path.join(PROFILES_DIR, f"session_{order_id}")
        os.makedirs(profile_path, exist_ok=True)
        
        context = await state.browser.new_context(user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
        page = await context.new_page()
        order["_context"] = context
        order["_page"] = page
        
        await page.goto("https://www.jio.com/selfcare/login/", wait_until="domcontentloaded", timeout=60000)
        await asyncio.sleep(2)
        
        order_event(order, f"Typing phone number: {clean_phone}")
        await page.locator('[data-testid="numberField"]').fill(clean_phone)
        await asyncio.sleep(1)
        
        order_event(order, "Clicking Generate OTP...")
        
        # Flush the queue to prevent old OTP race conditions
        while not state.firebase_otp_queues[device_id].empty():
            state.firebase_otp_queues[device_id].get_nowait()
            
        await page.locator('[data-testid="generateOTPButton"]').click()
        await emit_log(f"[{phone}] Clicked Generate OTP on jio.com", "info")
        await asyncio.sleep(2)
        
        # Fast termination checks
        page_text = await page.content()
        if "non-Jio number" in page_text or "non-jio number" in page_text.lower():
            raise Exception("Non-Jio number detected")
        if "exceeded the maximum attempts" in page_text:
            raise Exception("Jio IP Rate Limited")
        
        order["status"] = "waiting_otp"
        order_event(order, "Waiting for Firebase SSE OTP...")
        await emit_order(order)
        
        try:
            otp_code = await asyncio.wait_for(state.firebase_otp_queues[device_id].get(), timeout=60.0)
        except asyncio.TimeoutError:
            raise Exception("Firebase OTP timeout")
            
        order["otp"] = otp_code
        order["status"] = "otp_received"
        order_event(order, f"OTP received: {otp_code}")
        await emit_order(order)
        await emit_log(f"OTP received from Firebase!", "success")
        
        order["status"] = "logging_in"
        for i, digit in enumerate(otp_code[:6]):
            await page.locator(f'#basic-input-testInput-code-block-{i}').fill(digit)
            await asyncio.sleep(0.1)
        await asyncio.sleep(1)
        await page.locator('button:has-text("Submit")').click()
        await asyncio.sleep(3)
        
        state.stats["login"] += 1
        await emit_stats()
        
        # Extraction
        order_event(order, "Looking for Gemini offer banner...")
        await emit_order(order)
        
        captured_url = []
        async def handle_route(route):
            req_url = route.request.url
            if "serviceactivation.google.com" in req_url or "accounts.google.com" in req_url or "oauth2" in req_url.lower():
                captured_url.append(req_url)
                try: await route.abort()
                except: pass
            else:
                try: await route.continue_()
                except: pass
                
        await context.route("**/*", handle_route)
        
        await page.wait_for_selector('#imageNotification', timeout=60000)
        order_event(order, "Found Gemini banner! Clicking...")
        await page.click('#imageNotification')
        
        for _ in range(15):
            if captured_url: break
            await asyncio.sleep(1)
            
        if captured_url:
            target_link = next((url for url in captured_url if "serviceactivation.google.com" in url), captured_url[0])
            with open(SUCCESS_CSV, "a", newline="") as f:
                csv.writer(f).writerow([fb_url, device_id, phone, target_link])
            
            with open(os.path.join(PROJECT_DIR, "links.txt"), "a") as f:
                f.write(f"{phone} | {target_link}\n")
                
            order["status"] = "logged_in"
            order_event(order, "✅ Link extracted & saved to CSV/links.txt!")
            await emit_order(order)
            await emit_log(f"🎉 [{phone}] Gemini Link Saved!", "success")
            await asyncio.sleep(2)
            await context.close()
            order["_context"] = None
            return
        else:
            raise Exception("Clicked banner but redirect not caught")
            
    except Exception as e:
        err_msg = str(e).split('\n')[0]
        order["status"] = "cancelled"
        order_event(order, f"Firebase Error: {err_msg}")
        await emit_order(order)
        await emit_log(f"[{phone}] Error: {err_msg}", "error")
        with open(FAILED_CSV, "a", newline="") as f:
            csv.writer(f).writerow([fb_url, device_id, phone, err_msg])
        if context: await context.close()
    finally:
        state.jio_count = max(0, state.jio_count - 1)

async def firebase_sniper_worker(speed_delay):
    init_csvs()
    device_map = await fetch_initial_mapping()
    if not device_map: return
    
    used_file = "used_firebase_devices.txt"
    used_devices = set()
    if os.path.exists(used_file):
        with open(used_file, "r") as f:
            used_devices = set(line.strip() for line in f if line.strip())
            
    available_devices = [k for k in device_map.keys() if k not in used_devices]
    state.firebase_otp_queues = {k: asyncio.Queue() for k in available_devices}
    
    # Spawn a listener for each active Firebase URL (use firebase_accounts if available)
    if state.firebase_listener_task is None or state.firebase_listener_task.done():
        raw_accs = config.get("firebase_accounts") or [{"url": u, "key": ""} for u in config.get("firebase_urls", []) if u.strip()]
        listener_urls = [a["url"].strip() for a in raw_accs if isinstance(a, dict) and a.get("url", "").strip()]
        if listener_urls:
            async def run_listeners():
                await asyncio.gather(*(listen_for_otps(url) for url in listener_urls))
            state.firebase_listener_task = asyncio.create_task(run_listeners())
        
    while not state.stop_event.is_set() and available_devices:
        if state.jio_count >= state.target_count:
            await asyncio.sleep(2)
            continue
            
        device_id = available_devices.pop(0)
        with open(used_file, "a") as f:
            f.write(device_id + "\n")
            
        phone = device_map[device_id]["phone"]
        fb_url = device_map[device_id]["url"]
        asyncio.create_task(process_firebase_number(device_id, phone, fb_url, speed_delay))
        await asyncio.sleep(1)
    
    # All devices dispatched — wait for in-flight tasks to finish
    await emit_log(f"All {len(device_map)} Firebase devices dispatched. Waiting for in-flight tasks...", "info")
    while state.jio_count > 0 and not state.stop_event.is_set():
        await asyncio.sleep(2)
    
    # Clean up listener
    if state.firebase_listener_task and not state.firebase_listener_task.done():
        state.firebase_listener_task.cancel()
    await emit_log("✅ Firebase Direct completed — all devices processed!", "success")

# ─── Sniper Workers ──────────────────────────────────────────────────────────
async def sniper_worker(p_name, speed_delay):
    delay = config["providers"].get(p_name, {}).get("delay", 3) * speed_delay
    
    while not state.stop_event.is_set():
        if state.jio_count >= state.target_count:
            await asyncio.sleep(delay)
            continue
        try:
            result = await buy_number(p_name)
            if result["status"] == "success":
                asyncio.create_task(process_number(p_name, result["aid"], result["phone"]))
        except:
            pass
        await asyncio.sleep(delay)

# ─── Socket.IO Events ────────────────────────────────────────────────────────
@sio.on('connect')
async def on_connect(sid, environ):
    await emit_log("Dashboard connected", "info")
    # Start system monitor if not running
    if state.system_monitor_task is None or state.system_monitor_task.done():
        state.system_monitor_task = asyncio.create_task(system_monitor_loop())

@sio.on('get_balances')
async def on_get_balances(sid):
    if not state.http_session:
        state.http_session = aiohttp.ClientSession()
    balances = {}
    for p in config["providers"]:
        if p == "FirebaseDirect":
            # Firebase has no balance API — count total/online/offline
            total = online = 0
            try:
                accounts = config.get("firebase_accounts") or [{"url": u, "key": ""} for u in config.get("firebase_urls", [])]
                for acc in accounts:
                    fb_url = (acc.get("url") if isinstance(acc, dict) else acc or "").strip()
                    fb_key = (acc.get("key") if isinstance(acc, dict) else "") or ""
                    if not fb_url: continue
                    params = {"auth": fb_key} if fb_key else {}
                    async with state.http_session.get(
                        f"{fb_url.rstrip('/')}/clients.json",
                        params=params,
                        timeout=aiohttp.ClientTimeout(total=8)
                    ) as resp:
                        if resp.status == 200:
                            data = await resp.json()
                            if isinstance(data, dict):
                                total += len(data)
                                online += sum(1 for d in data.values() if isinstance(d, dict) and d.get("status"))
            except:
                pass
            balances[p] = f"fb:{total}:{online}:{total - online}"
        else:
            bal = await get_balance(p)
            balances[p] = bal
    await sio.emit("balance_update", balances, to=sid)

@sio.on('start_sniping')
async def on_start_sniping(sid, data):
    if state.is_sniping:
        await emit_log("Already sniping!", "warn")
        return
    
    providers = data.get("providers", list(config["providers"].keys()))
    state.target_count = data.get("batch_size", 5)
    speed = data.get("speed", "normal")
    speed_delay = SPEED_MAP.get(speed, 1.0)
    
    state.is_sniping = True
    state.stop_event = asyncio.Event()
    state.jio_count = 0
    state.stats = {"fetched": 0, "jio": 0, "otp": 0, "login": 0}
    
    # Record session start
    analytics.setdefault("sessions", []).append({
        "start": time.time(), "providers": providers, "target": state.target_count
    })
    
    if not state.http_session:
        state.http_session = aiohttp.ClientSession()
    
    os.makedirs(PROFILES_DIR, exist_ok=True)
    try:
        from playwright.async_api import async_playwright
        if not state.pw:
            state.pw = await async_playwright().start()

        chromium_path = shutil.which("chromium")
        print("Chromium:", chromium_path)
        print("Google Chrome:", shutil.which("google-chrome"))
        print("Chrome:", shutil.which("chrome"))

        if not state.browser or not state.browser.is_connected():
            if not chromium_path:
                raise RuntimeError("Chromium executable was not found")

            state.browser = await state.pw.chromium.launch(
                executable_path=chromium_path,
                headless=True,
                args=[
                    "--no-sandbox",
                    "--disable-setuid-sandbox",
                    "--disable-dev-shm-usage",
                    "--disable-gpu",
                    "--disable-extensions",
                    "--disable-background-networking",
                    "--disable-default-apps",
                    "--disable-sync",
                    "--no-first-run",
                ],
            )

        await emit_log("Browser launched", "info")
    except Exception as e:
        await emit_log(f"Browser launch failed: {e}. OTP-only mode.", "warn")
    
    await sio.emit("sniping_started")
    await emit_log(f"🚀 Sniping started! Providers: {', '.join(providers)} | Target: {state.target_count}", "success")
    state.sniper_tasks = []
    for p in providers:
        if p == "FirebaseDirect":
            state.sniper_tasks.append(asyncio.create_task(firebase_sniper_worker(speed_delay)))
        elif p in config["providers"]:
            state.sniper_tasks.append(asyncio.create_task(sniper_worker(p, speed_delay)))

@sio.on('stop_sniping')
async def on_stop_sniping(sid):
    if state.stop_event:
        state.stop_event.set()
    await emit_log("⏳ Gracefully stopping... letting active tasks finish.", "warn")
    
    # Wait for tasks to finish in background
    async def monitor_tasks():
        if state.sniper_tasks:
            await asyncio.gather(*state.sniper_tasks, return_exceptions=True)
        state.sniper_tasks = []
        state.is_sniping = False
        save_analytics()
        await sio.emit("sniping_stopped")
        await emit_log("⏹ All tasks completed. Sniping stopped.", "warn")
        
    asyncio.create_task(monitor_tasks())

@sio.on('force_stop_sniping')
async def on_force_stop_sniping(sid):
    if state.stop_event:
        state.stop_event.set()
    for task in state.sniper_tasks:
        task.cancel()
    state.sniper_tasks = []
    state.is_sniping = False
    save_analytics()
    await sio.emit("sniping_stopped")
    await emit_log("✖ FORCE STOPPED. All tasks killed instantly.", "error")

@sio.on('kill_zombie_browsers')
async def on_kill_zombie_browsers(sid):
    await emit_log("🧹 Killing zombie Google Chrome for Testing processes...", "warn")
    os.system('pkill -f "Google Chrome for Testing" >/dev/null 2>&1 || true')
    await emit_log("✅ Zombie browsers cleared!", "success")

@sio.on('cancel_number')
async def on_cancel_number(sid, data):
    order_id = data.get("id")
    order = state.orders.get(order_id)
    if not order:
        return
    ctx = order.get("_context")
    if ctx:
        try:
            await ctx.close()
        except:
            pass
        order["_context"] = None
    order_event(order, "Manually cancelled by user")
    asyncio.create_task(cancel_order(order))
    await emit_log(f"Cancelling {order['phone']}...", "warn")

@sio.on('request_new_otp')
async def on_request_new_otp(sid, data):
    order_id = data.get("id")
    order = state.orders.get(order_id)
    if not order:
        return
    order["status"] = "waiting_otp"
    order["otp"] = None
    order_event(order, "Re-polling for new OTP...")
    await emit_order(order)
    await emit_log(f"Re-polling OTP for {order['phone']}...", "info")
    asyncio.create_task(handle_jio_number(order))

@sio.on('force_cancel')
async def on_force_cancel(sid, data):
    order_id = data.get("id")
    order = state.orders.get(order_id)
    if not order:
        return
    ctx = order.get("_context")
    if ctx:
        try:
            await ctx.close()
        except:
            pass
        order["_context"] = None
    order_event(order, "Force cancelled — skipping wait timer")
    order["status"] = "cancelling"
    await emit_order(order)
    # Force cancel immediately (no 120s wait)
    status = await cancel_api_number(order["provider"], order["aid"])
    order["status"] = "cancelled"
    order_event(order, f"Force cancel result: {status}")
    await emit_order(order)
    await emit_log(f"[{order['phone']}] Force cancelled: {status}", "warn")
    await asyncio.sleep(3)
    if order_id in state.orders:
        del state.orders[order_id]
        await sio.emit("number_remove", {"id": order_id})

@sio.on('get_orders')
async def on_get_orders(sid):
    for order in state.orders.values():
        await sio.emit("number_update", safe_order(order), to=sid)

@sio.on('get_settings')
async def on_get_settings(sid):
    await sio.emit("settings_data", config, to=sid)

@sio.on('save_settings')
async def on_save_settings(sid, data):
    global config
    config.update(data)
    save_config(config)
    await emit_log("⚙️ Settings saved!", "success")
    await sio.emit("settings_saved")

@sio.on('get_analytics')
async def on_get_analytics(sid):
    await sio.emit("analytics_data", analytics, to=sid)

@sio.on('get_order_detail')
async def on_get_order_detail(sid, data):
    order_id = data.get("id")
    order = state.orders.get(order_id)
    if order:
        await sio.emit("order_detail", safe_order(order), to=sid)

@sio.on('stop_omkar_generation')
async def on_stop_omkar_generation(sid):
    state.omkar_gen_stop = True
    await sio.emit('omkar_gen_log', {'msg': 'Stopping generation after current step...', 'level': 'warn'}, to=sid)

@sio.on('generate_omkar_keys')
async def on_generate_omkar_keys(sid, data):
    accounts = data.get('accounts', [])
    if not accounts:
        return
    state.omkar_gen_stop = False
    await sio.emit('omkar_gen_log', {'msg': f'Starting automation for {len(accounts)} accounts...', 'level': 'info'}, to=sid)
    asyncio.create_task(process_omkar_generation(sid, accounts))


async def _process_single_omkar_account(sid, account_line, omkar_txt_path, sem, stagger_delay=0):
    # Stagger launches so we don't slam Omkar's servers all at once
    if stagger_delay > 0:
        await asyncio.sleep(stagger_delay)
    async with sem:

        if state.omkar_gen_stop:
            await sio.emit('omkar_gen_log', {'msg': 'Generation stopped by user.', 'level': 'warn'}, to=sid)
            return
            
        parts = account_line.split('|')
        if len(parts) < 4:
            await sio.emit('omkar_gen_log', {'msg': f'Invalid format: {account_line}', 'level': 'error'}, to=sid)
            return
            
        raw_email, password, refresh_token, client_id = [p.strip() for p in parts[:4]]
        # Strip numbering like "237. " from the beginning of the email string
        email = re.sub(r'^\d+\.\s*', '', raw_email)
        
        name_part = email.split('@')[0]
        # Make name nicely spaced and capitalized if mixed case (e.g., RandirMaeqi -> Randir Maeqi)
        name = re.sub(r'([a-z])([A-Z])', r'\1 \2', name_part).title()
        
        # Use the Outlook password as the Omkar password, but ensure it meets Omkar's special character requirement!
        omkar_pass = password
        if not re.search(r'[!@#$%^&*]', omkar_pass):
            omkar_pass += "!"
            
        await sio.emit('omkar_gen_log', {'msg': f'Processing {email}...', 'level': 'info'}, to=sid)
        
        context = None
        try:
            if not state.pw:
                from playwright.async_api import async_playwright
                state.pw = await async_playwright().start()
                state.browser = await state.pw.chromium.launch(headless=True)
            
            context = await state.browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            )
            page = await context.new_page()
            
            # Step 1: Sign up
            await sio.emit('omkar_gen_log', {'msg': f'[{email}] Navigating to Omkar signup...', 'level': 'info'}, to=sid)
            await page.goto("https://www.omkar.cloud/auth/sign-up", wait_until="networkidle")
            await asyncio.sleep(2) # Give React time to hydrate
            
            await page.locator('input[name="name"]').press_sequentially(name, delay=30)
            await page.locator('input[type="email"]').press_sequentially(email, delay=30)
            await page.locator('input[type="password"]').press_sequentially(omkar_pass, delay=30)
            
            await sio.emit('omkar_gen_log', {'msg': f'[{email}] Submitting signup form...', 'level': 'info'}, to=sid)
            await page.locator('button:has-text("Submit")').click(force=True)
            await asyncio.sleep(5)
            
            # Step 2: Graph API Email Fetch
            await sio.emit('omkar_gen_log', {'msg': f'[{email}] Requesting Graph API access token...', 'level': 'info'}, to=sid)
            
            token_url = "https://login.microsoftonline.com/common/oauth2/v2.0/token"
            token_data = {
                "client_id": client_id,
                "grant_type": "refresh_token",
                "refresh_token": refresh_token,
                "scope": "Mail.Read"
            }
            
            access_token = None
            async with state.http_session.post(token_url, data=token_data) as resp:
                if resp.status != 200:
                    err = await resp.text()
                    await sio.emit('omkar_gen_log', {'msg': f'[{email}] Failed to get access token: {err[:100]}', 'level': 'error'}, to=sid)
                    raise Exception("Graph API Token Error")
                res_data = await resp.json()
                access_token = res_data.get("access_token")
                
            if not access_token:
                raise Exception("No access token returned")
                
            # Poll for the verification email (up to 2 minutes)
            await sio.emit('omkar_gen_log', {'msg': f'[{email}] Polling Inbox for Omkar verification email...', 'level': 'info'}, to=sid)
            verification_link = None
            for _ in range(24):
                async with state.http_session.get(
                    "https://graph.microsoft.com/v1.0/me/messages?$top=5",
                    headers={"Authorization": f"Bearer {access_token}"}
                ) as resp:
                    if resp.status == 200:
                        msgs = await resp.json()
                        for msg in msgs.get("value", []):
                            subject = msg.get("subject", "").lower()
                            if "verification" in subject or "verify" in subject or "omkar" in subject:
                                body = msg.get("body", {}).get("content", "")
                                # Look for the brevo tracking link (domain changes frequently, e.g. sendibt2.com, sendibt3.com)
                                match = re.search(r'(https://[a-zA-Z0-9.-]+sendibt[0-9]\.com/tr/cl/[^\s"\'<>]+)', body)
                                if match:
                                    verification_link = match.group(1)
                                    break
                                # Fallback if /tr/cl/ isn't used
                                match_any = re.search(r'(https://[a-zA-Z0-9.-]+sendibt[0-9]\.com/[^\s"\'<>]+)', body)
                                if match_any:
                                    verification_link = match_any.group(1)
                                    break
                    if verification_link:
                        break
                await asyncio.sleep(5)
                
            if not verification_link:
                await sio.emit('omkar_gen_log', {'msg': f'[{email}] Verification email not found after 2 mins.', 'level': 'error'}, to=sid)
                raise Exception("Email timeout")
                
            # Step 3: Verify and Extract Key
            await sio.emit('omkar_gen_log', {'msg': f'[{email}] Found link! Verifying...', 'level': 'info'}, to=sid)
            try:
                await page.goto(verification_link, wait_until="domcontentloaded", timeout=30000)
            except Exception as e:
                await sio.emit('omkar_gen_log', {'msg': f'[{email}] Redirect took too long, proceeding anyway...', 'level': 'warn'}, to=sid)
                
            await asyncio.sleep(3)
            
            await sio.emit('omkar_gen_log', {'msg': f'[{email}] Fetching API Key...', 'level': 'info'}, to=sid)
            await page.goto("https://www.omkar.cloud/api-key", wait_until="domcontentloaded", timeout=30000)
            await asyncio.sleep(2)
            
            # Check if we were redirected to sign-in page
            if "sign-in" in page.url:
                await sio.emit('omkar_gen_log', {'msg': f'[{email}] Redirected to sign-in, manually logging in...', 'level': 'warn'}, to=sid)
                try:
                    await page.locator('input[type="email"]').press_sequentially(email, delay=30)
                    await page.locator('input[type="password"]').press_sequentially(omkar_pass, delay=30)
                    await page.locator('button[type="submit"]').click(force=True)
                    await asyncio.sleep(4)
                    
                    # Ensure we go to the API key page after login
                    await page.goto("https://www.omkar.cloud/api-key", wait_until="domcontentloaded", timeout=30000)
                    await asyncio.sleep(2)
                except Exception as e:
                    await sio.emit('omkar_gen_log', {'msg': f'[{email}] Manual login failed: {str(e)[:100]}', 'level': 'error'}, to=sid)
            
            # The key is typically in an input field or a code block. We'll look for ok_...
            content = await page.content()
            match = re.search(r'(ok_[a-f0-9]{32})', content)
            
            if match:
                api_key = match.group(1)
                await sio.emit('omkar_gen_log', {'msg': f'[{email}] 🎉 Extracted Key: {api_key}', 'level': 'success'}, to=sid)
                
                # Append to file
                with open(omkar_txt_path, "a") as f:
                    f.write(f"{api_key}\n")
                    
                # --- NEW LOGIC: Automate Phone Verification with Grizzly SMS ---
                await sio.emit('omkar_gen_log', {'msg': f'[{email}] Navigating to Phone Verification...', 'level': 'info'}, to=sid)
                await page.goto("https://www.omkar.cloud/account/verify-phone", wait_until="domcontentloaded", timeout=30000)
                await asyncio.sleep(2)
                
                await sio.emit('omkar_gen_log', {'msg': f'[{email}] Buying number from Grizzly SMS (Chile/Indonesia)...', 'level': 'info'}, to=sid)
                tzid, local_number, country_name, full_number = await buy_grizzly_number()
                
                if not tzid:
                    await sio.emit('omkar_gen_log', {'msg': f'[{email}] Failed to buy Grizzly number! Leaving browser OPEN for you. Key: {api_key}', 'level': 'warn'}, to=sid)
                    context = None
                else:
                    await sio.emit('omkar_gen_log', {'msg': f'[{email}] Bought {country_name} number: {full_number}. Filling form...', 'level': 'success'}, to=sid)
                    try:
                        # 1. Select Country
                        await page.locator('[data-test-subj="comboBoxSearchInput"]').fill(country_name)
                        await asyncio.sleep(1)
                        # Press ArrowDown to highlight the option, then Enter
                        await page.keyboard.press("ArrowDown")
                        await asyncio.sleep(0.5)
                        await page.keyboard.press("Enter")
                        await asyncio.sleep(1)
                        # Fallback: try to explicitly click it if the dropdown is still open
                        try:
                            await page.locator(f'button[role="option"]:has-text("{country_name}")').click(timeout=2000)
                        except:
                            pass
                        await asyncio.sleep(1)
                        
                        # 2. Enter Phone Number
                        await page.locator('input[name="phone"]').fill(local_number)
                        await asyncio.sleep(1)
                        await page.keyboard.press("Enter")
                        
                        # Wait for OTP input to appear
                        try:
                            await page.wait_for_selector('input[name="code"]', timeout=20000)
                            await sio.emit('omkar_gen_log', {'msg': f'[{email}] Waiting up to 65s for OTP...', 'level': 'info'}, to=sid)
                            
                            otp = await poll_grizzly_otp(tzid, timeout=65)
                            
                            if not otp:
                                await sio.emit('omkar_gen_log', {'msg': f'[{email}] No OTP yet. Clicking "Resend code" and waiting 60s more...', 'level': 'warn'}, to=sid)
                                await page.locator('span:has-text("Resend code")').click()
                                otp = await poll_grizzly_otp(tzid, timeout=60)
                                
                            if otp:
                                await sio.emit('omkar_gen_log', {'msg': f'[{email}] 🎉 OTP Received: {otp}! Submitting...', 'level': 'success'}, to=sid)
                                os.system("afplay /System/Library/Sounds/Glass.aiff &")
                                await page.locator('input[name="code"]').fill(otp)
                                await asyncio.sleep(1)
                                await page.keyboard.press("Enter")
                                await asyncio.sleep(5) # Wait for success redirect or message
                                
                                # Mark as VERIFIED in omkar.txt
                                lines = []
                                with open(omkar_txt_path, "r") as f:
                                    lines = f.readlines()
                                with open(omkar_txt_path, "w") as f:
                                    for line in lines:
                                        if api_key in line and "VERIFIED" not in line:
                                            f.write(f"{line.strip()} - VERIFIED\n")
                                        else:
                                            f.write(line)
                                            
                                await sio.emit('omkar_gen_log', {'msg': f'[{email}] Phone verification COMPLETE! Account ready.', 'level': 'success'}, to=sid)
                                # Let context close naturally
                            else:
                                await sio.emit('omkar_gen_log', {'msg': f'[{email}] OTP never arrived. Cancelling number for refund.', 'level': 'error'}, to=sid)
                                await cancel_grizzly_number(tzid)
                                context = None # Leave browser open for manual debug
                        except Exception as e:
                            await sio.emit('omkar_gen_log', {'msg': f'[{email}] Error during OTP submission: {str(e)[:100]}. Cancelling number.', 'level': 'error'}, to=sid)
                            await cancel_grizzly_number(tzid)
                            context = None
                    except Exception as e:
                        await sio.emit('omkar_gen_log', {'msg': f'[{email}] UI Error filling phone form: {str(e)[:100]}. Cancelling number.', 'level': 'error'}, to=sid)
                        await cancel_grizzly_number(tzid)
                        context = None
                # -----------------------------------------------------------------
            else:
                await sio.emit('omkar_gen_log', {'msg': f'[{email}] Could not find ok_ key! Browser kept open. Password: {omkar_pass}', 'level': 'error'}, to=sid)
                context = None # Prevent finally block from closing it
                
        except Exception as e:
            await sio.emit('omkar_gen_log', {'msg': f'[{email}] Error: {str(e)[:150]}', 'level': 'error'}, to=sid)
            # If there's an error, maybe keep it open too?
            # Let's keep it open for debugging
            await sio.emit('omkar_gen_log', {'msg': f'[{email}] Browser kept open for debugging. Password: {omkar_pass}', 'level': 'warn'}, to=sid)
            context = None
        finally:
            if context:
                await context.close()

async def process_omkar_generation(sid, accounts):
    omkar_txt_path = os.path.join(PROJECT_DIR, "omkar.txt")
    
    if not state.pw:
        from playwright.async_api import async_playwright
        state.pw = await async_playwright().start()
        state.browser = await state.pw.chromium.launch(headless=True)
        
    # Limit concurrency: max 3 accounts doing Grizzly phone verification at once
    sem = asyncio.Semaphore(3)
    
    tasks = []
    for i, account_line in enumerate(accounts):
        tasks.append(asyncio.create_task(_process_single_omkar_account(sid, account_line, omkar_txt_path, sem, stagger_delay=i * 8)))
        
    await asyncio.gather(*tasks)
    
    await sio.emit('omkar_gen_log', {'msg': 'Automation sequence completed.', 'level': 'success'}, to=sid)
    await sio.emit('omkar_gen_done', {}, to=sid)

@sio.on('stop_chatgpt_login')
async def on_stop_chatgpt_login(sid):
    state.chatgpt_login_stop = True
    await sio.emit('chatgpt_log', {'msg': 'Stopping login process...', 'level': 'warn'}, to=sid)

@sio.on('start_chatgpt_login')
async def on_start_chatgpt_login(sid, data):
    num_tabs = data.get('num_tabs', 3)
    state.chatgpt_login_stop = False
    await sio.emit('chatgpt_log', {'msg': f'Starting automation for {num_tabs} tabs...', 'level': 'info'}, to=sid)
    asyncio.create_task(process_chatgpt_login(sid, num_tabs))

async def process_chatgpt_login(sid, num_tabs):
    script_path = os.path.join(PROJECT_DIR, "outlook-chatgpt-auto-login", "chatgpt_web_login.py")
    
    if getattr(state, "chatgpt_login_stop", False):
        await sio.emit('chatgpt_log', {'msg': 'Generation stopped by user.', 'level': 'warn'}, to=sid)
        return
        
    await sio.emit('chatgpt_log', {'msg': f'Launching chatgpt_web_login.py for {num_tabs} tabs...', 'level': 'info'}, to=sid)
    
    try:
        # We launch the python script asynchronously using sys.executable to stay inside the venv
        process = await asyncio.create_subprocess_exec(
            sys.executable, script_path,
            env={**os.environ, "NUM_TABS": str(num_tabs)},
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        
        await sio.emit('chatgpt_log', {'msg': f'Script launched (PID: {process.pid}). Please wait for it to complete.', 'level': 'success'}, to=sid)
        
    except Exception as e:
        await sio.emit('chatgpt_log', {'msg': f'Error launching script: {e}', 'level': 'error'}, to=sid)
        
    await sio.emit('chatgpt_log', {'msg': 'Automation sequence completed.', 'level': 'success'}, to=sid)
    await sio.emit('chatgpt_login_done', {}, to=sid)

# ─── Main ─────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("🚀 Jio Sniper Dashboard v2.0 — http://localhost:8000")
    uvicorn.run(sio_app, host="0.0.0.0", port=8000, log_level="warning")
