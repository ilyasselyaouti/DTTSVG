FROM python:3.11-slim

# Installation de FFmpeg
RUN apt-get update && rm -rf /var/lib/apt/lists/*
# Récupération de l'exécutable FFmpeg complet
COPY --from=mwader/static-ffmpeg:7.1 /ffmpeg /usr/local/bin/
COPY --from=mwader/static-ffmpeg:7.1 /ffprobe /usr/local/bin/

WORKDIR /app

# Installation des dépendances Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copie du script
COPY app.py .

EXPOSE 5000

CMD ["python", "app.py"]