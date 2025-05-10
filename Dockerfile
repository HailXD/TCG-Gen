# syntax=docker/dockerfile:1
FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
        git libjpeg-dev zlib1g-dev build-essential \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

COPY . .

RUN git clone https://github.com/type-null/PTCG-database
RUN chmod -R a+rwX /app

EXPOSE 7860

CMD ["sh", "-c", "python ext.py && python short.py && app.py"]