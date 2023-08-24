FROM python:3.11-alpine
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app.py .
COPY chat/. ./chat/
RUN mkdir /logs
CMD exec gunicorn --bind :5002 --worker-class eventlet -w 1 app:app
