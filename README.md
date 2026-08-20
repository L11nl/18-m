# AnneBella Jio-ChatGPT Portal

An automated dashboard and sniping toolkit for registering and verifying ChatGPT accounts using various SMS provider APIs and Microsoft Graph API for Outlook verification.

[![Deploy on Railway](https://railway.com/button.svg)](https://railway.com/new/template?template=https://github.com/annebella165040-png/Gemini-autoextractorbot)

---

## Project Structure

| File / Folder | Purpose |
|---|---|
| `dashboard/` | Web UI — monitor snipers, check balances, manage API keys, launch ChatGPT login |
| `auto_sniper.py` | Master sniper that delegates to individual providers |
| `grizzly_sniper.py` / `grizzly_auto_buyer.py` | Grizzly SMS provider scripts |
| `tiger_sniper.py` / `tiger_adb_sniper.py` | Tiger SMS provider scripts |
| `meowsms_sniper.py` / `meowsms_adb_sniper.py` | MeowSMS provider scripts |
| `uotp_sniper.py` / `uotp_adb_sniper.py` / `uotp_auto_buyer.py` | UOTP provider scripts |
| `omni_sniper.py` | Omni provider sniper |
| `outlook-chatgpt-auto-login/` | Playwright automation to create & verify ChatGPT accounts via Outlook |
| `.env.example` | Template for all required API keys |
| `requirements.txt` | Python dependencies |

---

## Getting Started

### 1. Clone the repo

```bash
git clone https://github.com/annebella165040-png/Gemini-autoextractorbot.git
cd Gemini-autoextractorbot
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
playwright install
```

### 3. Set up environment variables

```bash
cp .env.example .env
# Edit .env and fill in your API keys
```

See `.env.example` for the full list of required keys.

### 4. Run the Dashboard

```bash
python dashboard/server.py
```

Open your browser at `http://localhost:8000`.

---

## Deploy on Railway

Click the button above or follow these steps:

1. **Fork** this repo to your GitHub account
2. Go to [railway.com](https://railway.com) → **New Project** → **Deploy from GitHub repo**
3. Select your fork
4. Add all environment variables from `.env.example` in the Railway **Variables** tab
5. Set the **Start Command** to:
   ```
   python dashboard/server.py
   ```
6. Deploy — Railway will install `requirements.txt` automatically

---

## Usage

- **Start Snipers** — Use the dashboard UI to start polling your chosen SMS provider
- **Login ChatGPT** — Click the `Login ChatGPT` button, provide emails/credentials; the automation handles the rest
- **API Keys** — All keys live in `.env` (see `.env.example`). Never hardcode keys in Python files

---

## Features

- **Multi-provider support** — Grizzly, Tiger, MeowSMS, UOTP, Omni, ADB-based snipers
- **Auto-Retry & Timers** — Cleans up zombie browsers and handles sluggish UI loads automatically
- **Direct UI Login** — Navigates the ChatGPT pricing page to trigger Outlook verifications without getting stuck in settings
- **In-Memory Sessions** — Runs Playwright instances asynchronously without retaining tracking cookies across fresh account creations
- **Microsoft Graph OTP** — Fetches verification codes from Outlook via Graph API automatically
