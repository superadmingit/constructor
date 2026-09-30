# Веб-сервис «Конструктор штампов». Подходит для Hugging Face Spaces (Docker), Render, любого VPS.
FROM python:3.12-slim

# Системные библиотеки для OpenCascade (cadquery) и шрифты с кириллицей для чертежей
RUN apt-get update && apt-get install -y --no-install-recommends \
        libgl1 libglib2.0-0 libxrender1 libxext6 libx11-6 libfontconfig1 fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/*

RUN useradd -m -u 1000 app
WORKDIR /home/app/constructor
COPY --chown=app:app requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY --chown=app:app . .
USER app
ENV PORT=7860 MPLCONFIGDIR=/tmp/mpl
EXPOSE 7860
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT}"]
