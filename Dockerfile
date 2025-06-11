FROM python:3.13-slim-buster

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD black . && python -m unittest discover -s tests -p "*_test.py"
