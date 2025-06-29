FROM python:3.10-slim

WORKDIR /code

COPY requirements.txt .

RUN pip install -r requirements.txt

COPY . .

CMD uvicorn app.main:app --reload --host 0.0.0.0 --port 80
