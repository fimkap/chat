FROM python:3.9-slim-buster
WORKDIR /app
RUN apt-get update \
  && apt-get -y install netcat gcc \
  && apt-get clean
COPY requirements.txt .
RUN pip install --upgrade pip
RUN pip install --no-cache-dir -r requirements.txt
COPY app.py .
COPY chat/. ./chat/
RUN mkdir /logs
CMD exec gunicorn --bind :5002 --worker-class eventlet -w 1 app:app
