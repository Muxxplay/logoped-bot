# 🚀 Bepul serverga joylash qo'llanmasi

Bu bot **aiogram + SQLite**. Uni to'liq bepul, doim ishlaydigan joyga qo'yishning
3 ta yo'li bor. Birinchisini tavsiya qilaman.

| # | Yo'l | Narx | 24/7 ishlaydimi? | Bank kartasi | Bazа qayerda |
|---|------|------|------------------|--------------|--------------|
| **1** | **GitHub Actions** | $0 | ~5 soat + 10 daqiqa tanaffus | ❌ kerak emas | ✅ repo'da saqlanadi |
| 2 | Oracle Cloud Free VM | $0 | ✅ doim | ✅ kerak (vaqtincha) | ✅ diskda |
| 3 | Docker (o'z VPS/ucingiz) | o'zingizcha | ✅ doim | ❌ | ✅ diskda |

> **30 kunlik bepul variantlar bormi?** Ha, Railway ($5 credit), Render (30 kunlik free
> Postgres) — lekin 30 kundan keyin to'xtaydi. Yuqoridagilar esa **umr bo'yi bepul**.

---

## ✅ YO'L 1 — GitHub Actions (eng oson, karta kerak emas)

Ishlatilgan resurs: **0 soat** (repo ochiq bo'lsa). Bank kartasi **kerak emas**.

### Qadam 1 — 3 ta secret qo'shing

Repo da ochiladigan `Settings` → `Secrets and variables` → `Actions` →
`New repository secret` (3 marta):

| Secret nomi | Qiymati |
|---|---|
| `BOT_TOKEN` | @BotFather dan olgan token, masalan `7123456789:AAH...` |
| `ADMIN_IDS` | Sizning Telegram ID. Uni @userinfobot orqali olasiz |
| `ADMIN_PASSWORD` | /admin uchun parol — kuchli qiling |

### Qadam 2 — Botni ishga tushiring

`Actions` tab → `Logoped Bot` → `Run workflow` → `Run workflow` tugmasi.

30 soniya ichida `Setup Python` → `Botni ishga tushirish` paydo bo'ladi.
Loglarda `Baza tayyor` va `Start polling` yozuvi chiqishi kerak.

### Qadam 3 — Telegram'da sinab ko'ring

Botga `/start` yuboring. Ishlayapti ✅

### Qanday ishlaydi?

* Har 5 soatda workflow avtomatik ishga tushadi va bot ~5 soat ishlaydi.
* To'xtaganda Telegram'dagi xabarlar **yo'qolmaydi** — ular navbatda turadi va
  keyingi ishga tushganda yetkazib beriladi. Faqat javob berish 5 daqiqa kechikadi.
* Har ishga tushishda `logoped.db` avtomatik GitHub'ga commit qilinadi →
  foydalanuvchilar, mashqlar, fikr-mulohazalar **doim saqlanib qoladi**.

### Muhim

* `DROP_PENDING_UPDATES` workflow'da `false` qiling (allaqachon shunday).
  Agar `true` bo'lsa, bot to'xtagan paytdagi xabarlar o'chib ketadi.
* Repo **ochiq** bo'lishi kerak — ochiq repoda Actions to'liq bepul.
  Yopiq repoda oyiga ~33 soatlik limit bor (2000 daqiqa).
* Yangi mashq qo'shdingizmi? Ishga tushirish tugmasini bosing — 5 soat kutmasangiz.

---

## ✅ YO'L 2 — Oracle Cloud "Always Free" (haqiqiy 24/7 server)

**4 yadru / 24 GB RAM / 200 GB disk**, doim ishlaydi, hech qachon to'xtamaydi.

> ⚠️ Ro'yxatdan o'tganda bank kartasi so'raladi: ~1$ vaqtincha ushlanadi va
> qaytariladi. Bu Oracle'ning standart tekshiruvi — pul yechilmaydi.

### Qadam 1 — VM yarating

1. <https://cloud.oracle.com> → ro'yxatdan o'ting
2. **Create a VM instance** →
   - Image: **Canonical Ubuntu 24.04**
   - Shape: **VM.Standard.A1.Flex**, **4 OCPU**, **24 GB RAM** (Always Free)
   - **Create** → "Save private key" tugmasi bilan `.key` faylini yuklab oling
3. Bo'sh joylarni to'ldiring. VM yaratildi.

### Qadam 2 — SSH bilan kiring

```bash
chmod 400 ~/ssh-key-ocx.key
ssh -i ~/ssh-key-ocx.key ubuntu@<VM-IP-manzili>
```

### Qadam 3 — Botni o'rnating

Serverga kirgach, bitta buyruq:

```bash
git clone https://github.com/Muxxplay/logoped-bot.git
cd logoped-bot
bash deploy/oracle-setup.sh
```

Skript `.env` faylini ochadi — u yerga token, admin ID va parolni yozing
(kiritish, `Ctrl+O`, Enter, `Ctrl+X`).

Tayyor bo'ldi — bot darhol ishlaydi va server qayta ishga tushsa ham
o'zi qayta ishga tushadi (systemd).

### Foydali buyruqlar

```bash
journalctl -u logoped-bot -f          # loglarni real-time ko'rish
sudo systemctl restart logoped-bot    # qayta ishga tushirish
sudo systemctl stop logoped-bot       # to'xtatish
```

### Xavfsizlik (majburiy emas, lekin tavsiya qilinadi)

```bash
sudo ufw allow OpenSSH && sudo ufw enable
```

---

## ✅ YO'L 3 — Docker (o'z serveringiz bo'lsa)

```bash
git clone https://github.com/Muxxplay/logoped-bot.git
cd logoped-bot
cp .env.example .env && nano .env      # token / admin ID / parol
docker build -t logoped-bot .
docker volume create logoped-data
docker run -d --name logoped-bot --restart always \
  -p 8080:8080 --env-file .env \
  -v logoped-data:/data \
  logoped-bot
```

Loglar: `docker logs -f logoped-bot`

---

## 🧪 Kompyuteringizda sinab ko'rish

```bash
python -m venv venv
venv\Scripts\activate          # Windows
pip install -r requirements.txt
copy .env.example .env         # Windows  (Linux/Mac: cp)
notepad .env                   # to'ldiring
python logoped_bot.py
```

---

## ⚙️ Muhit o'zgaruvchilari (`.env`)

| O'zgaruvchi | Kerakmi | Izoh |
|---|---|---|
| `BOT_TOKEN` | ✅ | @BotFather tokeni |
| `ADMIN_IDS` | ✅ | vergul bilan ajratilgan Telegram ID lar |
| `ADMIN_PASSWORD` | ✅ | /admin paroli |
| `DB_PATH` | ixtiyoriy | bazа fayli (Docker/Oracle da `/data/logoped.db`) |
| `PORT` | ixtiyoriy | health-check porti, `0` = o'chirilgan |
| `DROP_PENDING_UPDATES` | ixtiyoriy | faqat birinchi o'rnatishda `true` |

### Health-check

`PORT` belgilansa, bot `GET /health` so'roviga `200 logoped-bot: ok` javobini
beradi — Render, Fly.io, HF Spaces shunday platformalar buni talab qiladi.
