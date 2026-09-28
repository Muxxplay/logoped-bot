FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PORT=8080 \
    DB_PATH=/data/logoped.db

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN mkdir -p /data
VOLUME ["/data"]

EXPOSE 8080

# Bot ishlab ketganda (kutilmagan xato) avtomatik qayta ishga tushadi
CMD ["sh", "run.sh"]
