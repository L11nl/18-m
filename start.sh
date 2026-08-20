#!/bin/bash
# ᴀɴɴᴇʙᴇʟʟᴀ ᴊɪᴏ-ᴄʜᴀᴛɢᴘᴛ ᴘᴏʀᴛᴀʟ — Railway Startup Script

# DO NOT use set -e — we want both services to run independently
export PORT="${PORT:-8000}"
export DASHBOARD_URL="http://localhost:${PORT}"

echo "🚀 AnneBella Portal starting on port $PORT"

# ── Dashboard via uvicorn CLI (most reliable, handles PORT correctly) ────────
python3 -m uvicorn dashboard.server:sio_app \
  --host 0.0.0.0 \
  --port "$PORT" \
  --log-level warning &

DASH_PID=$!
echo "📡 Dashboard PID $DASH_PID"

# Wait for dashboard to be ready before bot connects
sleep 5

# ── Telegram Bot ─────────────────────────────────────────────────────────────
echo "🤖 Starting Telegram bot..."
python3 telegram_bot.py &
BOT_PID=$!
echo "✅ Bot PID $BOT_PID"

# ── Keep container alive; auto-restart crashed services ──────────────────────
while true; do
  sleep 30

  # Restart dashboard if it died
  if ! kill -0 $DASH_PID 2>/dev/null; then
    echo "⚠️  Dashboard died — restarting..."
    python3 -m uvicorn dashboard.server:sio_app \
      --host 0.0.0.0 \
      --port "$PORT" \
      --log-level warning &
    DASH_PID=$!
    echo "📡 Dashboard restarted PID $DASH_PID"
    sleep 5
  fi

  # Restart bot if it died
  if ! kill -0 $BOT_PID 2>/dev/null; then
    echo "⚠️  Bot died — restarting..."
    python3 telegram_bot.py &
    BOT_PID=$!
    echo "🤖 Bot restarted PID $BOT_PID"
  fi
done
