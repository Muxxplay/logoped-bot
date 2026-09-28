# ==========================================================
#  Oracle Cloud "Always Free" VM ga o'rnatish (24/7, to'liq bepul)
#  4 yadru / 24 GB RAM / 200 GB disk — karta talab qilinadi
#  (ro'yxatdan o'tganda ~1$ vaqtincha ushlanadi, keyin qaytariladi)
# ==========================================================
#  SERVERGA SSH bilan kirgach, ushbu faylni bajarish:
#      bash deploy/oracle-setup.sh
# ==========================================================
set -e

APP_DIR="$HOME/logoped-bot"

echo "1/5  Python va paketlar tayyorlanmoqda..."
sudo apt update -y
sudo apt install -y python3 python3-venv python3-pip git

echo "2/5  Loyiha yuklanmoqda..."
if [ -d "$APP_DIR" ]; then
    cd "$APP_DIR" && git pull
else
    git clone https://github.com/Muxxplay/logoped-bot.git "$APP_DIR"
fi
cd "$APP_DIR"

echo "3/5  Virtual muhit yaratilmoqda..."
python3 -m venv venv
./venv/bin/pip install --upgrade pip
./venv/bin/pip install -r requirements.txt

echo "4/5  .env sozlash..."
if [ ! -f .env ]; then
    cp .env.example .env
    chmod 600 .env
    echo ">>> .env fayli yaratildi. Uni tahrirlang va keyin qayta ishga tushiring!"
    nano .env
fi

# Bazа doimiy diskda turishi uchun
mkdir -p "$HOME/data"
grep -q "DB_PATH" .env || echo "DB_PATH=$HOME/data/logoped.db" >> .env

echo "5/5  systemd xizmati yoqilmoqda..."
sudo cp deploy/logoped.service /etc/systemd/system/logoped.service
sudo sed -i "s|ExecStart=.*|ExecStart=$APP_DIR/venv/bin/python $APP_DIR/logoped_bot.py|" /etc/systemd/system/logoped.service
sudo sed -i "s|WorkingDirectory=.*|WorkingDirectory=$APP_DIR|" /etc/systemd/system/logoped.service
sudo sed -i "s|EnvironmentFile=.*|EnvironmentFile=$APP_DIR/.env|" /etc/systemd/system/logoped.service
sudo sed -i "s|^User=.*|User=$(whoami)|" /etc/systemd/system/logoped.service
sudo systemctl daemon-reload
sudo systemctl enable --now logoped-bot

echo ""
echo "=============================================="
echo " TAYYOR! Bot ishlayapti."
echo " Loglar:    journalctl -u logoped-bot -f"
echo " Qayta ishga tushirish: sudo systemctl restart logoped-bot"
echo "=============================================="
