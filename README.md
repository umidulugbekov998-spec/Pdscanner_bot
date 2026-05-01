# 📄 AI Document Scanner Bot — Deployment Guide

## Project Structure

```
scanner_bot/
├── main.py          ← Entry point; starts polling
├── config.py        ← Bot token, admin ID, API keys
├── database.py      ← aiosqlite async DB layer
├── handlers.py      ← All aiogram 3.x handlers & FSM
├── utils.py         ← OpenCV / Pillow pipeline + OpenAI helper
├── requirements.txt ← Python dependencies
└── scanner_bot.db   ← SQLite DB (auto-created on first run)
```

---

## ⚙️ Setup on Linux (Myxvest.ru)

### 1. Install system dependencies
```bash
sudo apt update
sudo apt install -y python3 python3-pip python3-venv libgl1-mesa-glx libglib2.0-0 fonts-dejavu
```

### 2. Clone / upload the project files
```bash
mkdir ~/scanner_bot && cd ~/scanner_bot
# Upload all .py files and requirements.txt here
```

### 3. Create a virtual environment
```bash
python3 -m venv venv
source venv/bin/activate
```

### 4. Install Python dependencies
```bash
pip install -r requirements.txt
```

### 5. Edit config.py
Open `config.py` and fill in:
- `BOT_TOKEN`       — your bot token from @BotFather
- `ADMIN_ID`        — your Telegram numeric user ID
- `OPENAI_API_KEY`  — your OpenAI API key (https://platform.openai.com/api-keys)
- `BOT_USERNAME`    — your bot's @username (without @)

### 6. Run the bot
```bash
python main.py
```

---

## 🔄 Run as a systemd service (auto-start on reboot)

```bash
sudo nano /etc/systemd/system/scanner_bot.service
```

Paste:
```ini
[Unit]
Description=AI Document Scanner Telegram Bot
After=network.target

[Service]
User=YOUR_LINUX_USERNAME
WorkingDirectory=/home/YOUR_LINUX_USERNAME/scanner_bot
ExecStart=/home/YOUR_LINUX_USERNAME/scanner_bot/venv/bin/python main.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

Enable & start:
```bash
sudo systemctl daemon-reload
sudo systemctl enable scanner_bot
sudo systemctl start scanner_bot
sudo systemctl status scanner_bot
```

View logs:
```bash
sudo journalctl -u scanner_bot -f
```

---

## 💳 Admin Commands

| Action | How |
|--------|-----|
| Open Admin Panel | Send `/admin` to the bot |
| Set payment card | Admin Panel → 💳 Set Card Number |
| Approve premium | Forward receipt from admin notification → ✅ Approve |
| Broadcast message | Admin Panel → 📢 Broadcast |
| View statistics | Admin Panel → 📊 Statistics |

---

## 🆙 Upgrading Plans

1. User taps **💎 Get Premium** → sees the card number.
2. User pays and uploads a payment receipt screenshot.
3. Bot forwards the screenshot to the Admin with **Approve / Decline** buttons.
4. Admin taps **Approve** → user is instantly upgraded to Premium in the DB.

---

## 📝 Notes

- The SQLite database (`scanner_bot.db`) is created automatically on first run.
- OpenAI Vision (GPT-4o) requires a funded OpenAI account. If you don't have one,
  the AI Assistant feature will return a graceful error message.
- For very high traffic, consider replacing `MemoryStorage()` in `main.py` with
  `RedisStorage` from `aiogram.fsm.storage.redis`.
