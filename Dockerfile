FROM python:3.13-slim
WORKDIR /app
ENV PYTHONUNBUFFERED=1
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app.py .
COPY chat/. ./chat/
RUN mkdir -p /logs
ENV CHAT_LOG_DIR=/logs
EXPOSE 5002
# gthread worker: long-lived connections + simple-websocket upgrades.
# Socket.IO needs a single worker unless a message queue is configured.
CMD exec gunicorn --bind :5002 --worker-class gthread --threads 100 -w 1 app:app
