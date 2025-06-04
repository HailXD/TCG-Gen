# syntax=docker/dockerfile:1
FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
        git libjpeg-dev zlib1g-dev build-essential \
    && rm -rf /var/lib/apt/lists/*
    
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

COPY . .

RUN git clone https://github.com/PokemonTCG/pokemon-tcg-data
RUN chmod -R a+rwX /app

EXPOSE 7860

RUN python ext.py && python short.py

CMD ["python", "app.py"]