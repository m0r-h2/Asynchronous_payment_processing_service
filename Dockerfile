FROM python:3.12-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY alembic.ini pytest.ini requirements-dev.txt ./
COPY alembic ./alembic
COPY app ./app
COPY tests ./tests

EXPOSE 8000
