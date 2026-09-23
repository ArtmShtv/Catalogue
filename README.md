# Quoter — Цитатник

Тестовое задание: сервис цитатника.

Проект настроен для локального запуска через Docker.

## Стек

- Python 3.12
- Django / Django REST Framework
- Docker

## Требования

- Docker
- Docker Compose

## Запуск

### 1. Клонируйте репозиторий
```bash
git clone <repository-url>
cd Quoter
```

### 2. Создайте файл окружения
```bash
cp .env.example .env
```

Значения по умолчанию подходят для локального запуска.

### 3. Соберите и запустите контейнер
```bash
docker build -t quote-store .
docker run --rm \
  --name quote-store \
  --env-file .env \
  -p 8000:8000 \
  --memory=256m \
  --cpus=0.5 \
  --pids-limit=64 \
  quote-store
```

API доступен по адресу:

http://localhost:8000/

### 4. Примените миграции
В отдельном терминале:

```bash
docker exec quote-store python manage.py migrate
```

## Переменные окружения

| Переменная | Описание | Пример |
|---|---|---|
| `DEBUG` | Режим отладки Django | `True` |
| `SECRET_KEY` | Секретный ключ Django | `change-me` |

`.env` не добавляется в репозиторий. Шаблон находится в `.env.example`.

## API

Базовый URL:
```text
http://localhost:8000/
```