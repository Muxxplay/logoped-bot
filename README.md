# Logoped Yordamchisi — Telegram bot

Nutq terapiyasi (logopediya) mashqlari, foydalanuvchi progressi, fikr-mulohaza
tizimi, admin panel va 3 tilli interfeys (🇺🇿 o'zbekcha, 🇷🇺 ruscha, 🇬🇧 inglizcha).

* **Kutubxona:** aiogram 3.x
* **Baza:** SQLite
* **Ishga tushirish:** `python logoped_bot.py`

## Tez ishga tushirish

```bash
pip install -r requirements.txt
copy .env.example .env      # Linux/Mac: cp .env.example .env
notepad .env                # BOT_TOKEN, ADMIN_IDS, ADMIN_PASSWORD ni to'ldiring
python logoped_bot.py
```

## Serverga joylash

**➡️ [DEPLOY.md](DEPLOY.md) — bepul hosting qo'llanmasi**

| Yo'l | Narx | 24/7 | Karta |
|---|---|---|---|
| GitHub Actions | $0 | ~5 soat + 10 daq | ❌ |
| Oracle Cloud Free | $0 | ✅ doim | ✅ |
| Docker (o'z VPS) | — | ✅ doim | ❌ |

## Admin panel

`/admin` buyrug'i + `.env` dagi `ADMIN_PASSWORD` bilan kiriladi:
statistika, mashq/kategoriya qo'shish va o'chirish, fikr-mulohazalar, broadcast.

> `/admin` faqat `ADMIN_IDS` da ko'rsatilgan ID'lar uchun ochiq.
