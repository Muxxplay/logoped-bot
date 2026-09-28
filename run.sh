#!/bin/sh
# Bot ishlab ketganda avtomatik qayta ishga tushirish (Docker uchun)
set -e

while true; do
    echo "=== Logoped bot ishga tushmoqda: $(date -u) ==="
    python logoped_bot.py
    echo "=== Bot to'xtadi. 5 soniyadan keyin qayta urinish ==="
    sleep 5
done
