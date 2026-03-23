# CloudBox

Личное облачное хранилище с SRE-стеком. Проект построен для практики инфраструктурной инженерии: контейнеризация, мониторинг, агрегация логов, управление инцидентами.

![Python](https://img.shields.io/badge/Python-3.12-3776AB?style=flat&logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688?style=flat&logo=fastapi&logoColor=white)
![Docker](https://img.shields.io/badge/Docker-Compose-2496ED?style=flat&logo=docker&logoColor=white)
![Elasticsearch](https://img.shields.io/badge/Elasticsearch-8.12-005571?style=flat&logo=elasticsearch&logoColor=white)
![Prometheus](https://img.shields.io/badge/Prometheus-мониторинг-E6522C?style=flat&logo=prometheus&logoColor=white)
![Grafana](https://img.shields.io/badge/Grafana-дашборды-F46800?style=flat&logo=grafana&logoColor=white)

---

## Скриншоты

**Веб-интерфейс**

<img width="1908" height="922" alt="image" src="https://github.com/user-attachments/assets/aed85dac-b6e7-42a8-aed1-13263ac22f40" />
<img width="1901" height="914" alt="image" src="https://github.com/user-attachments/assets/95e426ab-d12a-4ffe-8e63-c49101bb9003" />
<img width="1900" height="912" alt="image" src="https://github.com/user-attachments/assets/fb6a3f45-1568-43ab-a015-278f8ff280c7" />
<img width="1907" height="917" alt="image" src="https://github.com/user-attachments/assets/aaf6ce0a-1605-46f7-8277-c8b9882931f2" />

**Kibana — дашборд активности**

<img width="1901" height="921" alt="image" src="https://github.com/user-attachments/assets/5ffafe55-dac5-4394-b30d-af7636df22d4" />

**Grafana — node exporter**

<img width="1881" height="923" alt="image" src="https://github.com/user-attachments/assets/f063d49e-112b-4726-b221-928cc7738ee1" />

---

## Архитектура

```
Браузер / Телефон
        |
        | HTTP :8080
        v
 ┌──────────────┐
 │  FastAPI App  │  ←── JWT Auth, REST API, Static SPA
 └──────┬───────┘
        │
   ┌────┴────┬──────────┬──────────┐
   v         v          v          v
PostgreSQL  Redis     MinIO    Prometheus
 (файлы)  (токены)  (объекты)  (метрики)
                                   │
                               Grafana
                            (визуализация)

Логи Docker
      │
   Filebeat
      │
Elasticsearch ──→ Kibana
  (applogs-*)   (анализ логов)
```

---

## Возможности

### Приложение
- JWT-авторизация с ротацией refresh-токенов
- Загрузка / скачивание / переименование / удаление файлов (до 500 МБ)
- Управление папками с вложенностью
- Общий доступ к файлам по временной ссылке
- Квота на хранилище (1 ГБ по умолчанию)

### SRE-стек

| Слой | Инструмент | Назначение |
|---|---|---|
| Контейнеризация | Docker Compose | Все сервисы в изолированных контейнерах |
| Объектное хранилище | MinIO | S3-совместимое хранилище файлов |
| Метрики | Prometheus + node_exporter | Количество запросов, latency, error rate, системные метрики |
| Дашборды | Grafana | Обзор приложения и состояния сервера |
| Сбор логов | Filebeat | Сборка логов Docker-контейнеров |
| Хранение логов | Elasticsearch | Индексация и хранение структурированных логов |
| Анализ логов | Kibana | Поиск, визуализация, алерты по логам |
| Reverse proxy | Nginx | Rate limiting, SSL termination |

---

## Быстрый старт

### 1. Клонировать

```bash
git clone https://github.com/nikoussr/cloud-storage.git
cd cloud-storage
```

### 2. Настроить

```bash
cp .env.example .env
# Отредактировать .env — задать SECRET_KEY, пароли, порты
```

### 3. Запустить

```bash
docker compose up -d
```

### 4. Открыть

| Сервис | URL |
|---|---|
| Приложение | http://localhost:8080 |
| MinIO Console | http://localhost:9001 |
| Kibana | http://localhost:5601 |
| Метрики Prometheus | http://localhost:8080/metrics |

---

## Структура проекта

```
cloud-storage/
├── app/
│   ├── main.py                 # FastAPI app, lifespan, маршруты
│   ├── config.py               # Pydantic settings
│   ├── database.py             # Async SQLAlchemy engine
│   ├── dependencies.py         # JWT auth, Redis deps
│   ├── models/                 # SQLAlchemy модели
│   │   ├── user.py
│   │   ├── file.py
│   │   └── folder.py
│   ├── routes/                 # API endpoints
│   │   ├── auth.py             # /auth/*
│   │   ├── files.py            # /files/*
│   │   ├── folders.py          # /folders/*
│   │   └── share.py            # /share/*
│   ├── services/
│   │   ├── auth_service.py     # Регистрация, логин, ротация токенов
│   │   ├── storage_service.py  # MinIO wrapper
│   │   └── quota_service.py    # Квота пользователя
│   ├── middleware/
│   │   ├── logging.py          # Structlog JSON middleware
│   │   └── metrics.py          # Prometheus счётчики/гистограммы
│   └── static/                 # SPA (HTML + CSS + JS)
├── elk/
│   └── filebeat.yml            # Filebeat → Elasticsearch
├── nginx/
│   └── nginx.conf              # Reverse proxy, rate limiting, SSL
├── docker-compose.yml
├── Dockerfile
├── requirements.txt
└── .env.example
```

---

## API

<img width="1885" height="916" alt="image" src="https://github.com/user-attachments/assets/8e1cf659-b81d-47f4-8fa4-67978083aca1" />
<img width="1884" height="871" alt="image" src="https://github.com/user-attachments/assets/812a9853-b25a-4617-aaa4-9f85a7f40050" />

---

## Журнал инцидентов
\#TODO: дописать
