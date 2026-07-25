FROM python:3.11-slim

# 🔥 INSTALLA TUTTE LE DIPENDENZE
RUN apt-get update && apt-get install -y \
    libgl1 \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    libgomp1 \
    libnspr4 \
    libnss3 \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --upgrade pip && \
    pip install playwright Pillow imagehash requests

# 🔥 INSTALLA BROWSER E DIPENDENZE
RUN playwright install-deps && playwright install chromium

WORKDIR /app
COPY bot.py .
COPY hash_phash_db.json .

CMD ["python", "-u", "bot.py"]
