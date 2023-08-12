FROM python:3.12.0b3-alpine3.18
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
# COPY app.py .
# COPY chat/ .
COPY . .
CMD ["python", "app.py"]
