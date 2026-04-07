# Secure Messenger - Инструкция по развёртыванию

## 📋 Описание

Мессенджер со сквозным шифрованием (E2EE), использующий современные криптографические протоколы:
- **ECDH (P-256)** - обмен ключами по протоколу Диффи-Хеллмана
- **AES-256-GCM** - шифрование сообщений
- **SHA-256** - хэширование для проверки целостности
- **SQLite** - база данных для хранения пользователей и зашифрованных сообщений

## 🏗️ Архитектура

```
┌─────────────┐      WebSocket      ┌─────────────┐
│   Клиент    │ ◄─────────────────► │   Сервер    │
│  (Vue 3)    │                     │ (Node.js)   │
│             │                     │             │
│ Web Crypto  │                     │  SQLite DB  │
│    API      │                     │             │
└─────────────┘                     └─────────────┘
```

## 🚀 Быстрый старт (локальная разработка)

### 1. Установка зависимостей

```bash
cd /workspace
npm install
```

### 2. Запуск в режиме разработки

```bash
# Запуск клиента и сервера одновременно
npm run dev
```

Или по отдельности:
```bash
# Терминал 1 - сервер
npm run dev:server

# Терминал 2 - клиент
npm run dev:client
```

### 3. Доступ к приложению

- Клиент: http://localhost:5173
- Сервер: http://localhost:3001
- WebSocket: ws://localhost:3001

## 🌐 Развёртывание на продакшен-сервере

### Вариант 1: Docker (рекомендуется)

#### 1. Создайте Dockerfile

```dockerfile
FROM node:20-alpine

WORKDIR /app

COPY package*.json ./
RUN npm ci --only=production

COPY . .

RUN npm run build

EXPOSE 3001

ENV NODE_ENV=production

CMD ["node", "server/index.js"]
```

#### 2. Сборка и запуск

```bash
# Сборка образа
docker build -t secure-messenger .

# Запуск контейнера
docker run -d \
  -p 3001:3001 \
  -v messenger-data:/app \
  --name messenger \
  secure-messenger
```

### Вариант 2: Прямое развёртывание на Linux сервере

#### 1. Подготовка сервера

```bash
# Обновление системы
sudo apt update && sudo apt upgrade -y

# Установка Node.js 20
curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
sudo apt install -y nodejs

# Установка PM2 для управления процессом
sudo npm install -g pm2
```

#### 2. Загрузка проекта

```bash
# Клонирование репозитория или загрузка файлов
git clone <your-repo-url> /opt/messenger
cd /opt/messenger

# Установка зависимостей
npm ci --only=production
```

#### 3. Сборка клиента

```bash
npm run build
```

#### 4. Настройка переменных окружения

Создайте файл `.env`:
```bash
PORT=3001
NODE_ENV=production
```

#### 5. Запуск через PM2

```bash
# Запуск приложения
pm2 start server/index.js --name messenger

# Автозапуск при загрузке системы
pm2 startup
pm2 save
```

#### 6. Настройка Nginx (опционально, для HTTPS)

```bash
sudo apt install -y nginx
```

Конфигурация `/etc/nginx/sites-available/messenger`:
```nginx
server {
    listen 80;
    server_name your-domain.com;

    location / {
        proxy_pass http://localhost:3001;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_cache_bypass $http_upgrade;
    }

    # WebSocket поддержка
    location /socket.io/ {
        proxy_pass http://localhost:3001/socket.io/;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
    }
}
```

```bash
# Включение конфигурации
sudo ln -s /etc/nginx/sites-available/messenger /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl restart nginx

# Получение SSL сертификата (Let's Encrypt)
sudo apt install -y certbot python3-certbot-nginx
sudo certbot --nginx -d your-domain.com
```

### Вариант 3: Развёртывание на VPS (DigitalOcean, Linode, Hetzner)

1. Создайте VPS с Ubuntu 22.04
2. Следуйте инструккам из "Вариант 2"
3. Откройте порты в фаерволе:
   ```bash
   sudo ufw allow 22/tcp    # SSH
   sudo ufw allow 80/tcp    # HTTP
   sudo ufw allow 443/tcp   # HTTPS
   sudo ufw enable
   ```

### Вариант 4: PaaS платформы (Railway, Render, Fly.io)

#### Railway.app

1. Создайте аккаунт на [railway.app](https://railway.app)
2. Подключите GitHub репозиторий
3. Добавьте переменные окружения:
   - `NODE_ENV=production`
   - `PORT=3001`
4. Deploy!

#### Render.com

1. Создайте "Web Service"
2. Подключите репозиторий
3. Build Command: `npm install && npm run build`
4. Start Command: `node server/index.js`
5. Добавьте переменные окружения

## 🔧 Конфигурация

### Переменные окружения

| Переменная | Описание | По умолчанию |
|------------|----------|--------------|
| `PORT` | Порт сервера | `3001` |
| `NODE_ENV` | Окружение (production/development) | `development` |
| `VITE_SOCKET_URL` | URL WebSocket сервера для клиента | `http://localhost:3001` |

### База данных

База данных SQLite автоматически создаётся в файле `messenger.db` в корне проекта.

**Структура БД:**
- `users` - пользователи (логин, хэш пароля, публичный ключ)
- `messages` - зашифрованные сообщения
- `conversations` - диалоги между пользователями

## 🔐 Безопасность

### Что защищено:
✅ Сообщения шифруются на устройстве отправителя (E2EE)  
✅ Ключи никогда не передаются серверу  
✅ Пароли хранятся в хэшированном виде (bcrypt)  
✅ Используется TLS для передачи данных (при настройке HTTPS)  

### Что НЕ защищено:
⚠️ Метаданные (кто с кем общается, время сообщений)  
⚠️ Публичные ключи пользователей (хранятся на сервере)  

### Рекомендации по безопасности:
1. Всегда используйте HTTPS в продакшене
2. Регулярно обновляйте зависимости
3. Настройте фаервол
4. Используйте fail2ban для защиты от brute-force атак
5. Делайте резервные копии базы данных

## 📊 Мониторинг

### Логи приложения

```bash
# Просмотр логов PM2
pm2 logs messenger

# В реальном времени
pm2 logs messenger --lines 100
```

### Статус приложения

```bash
pm2 status
pm2 show messenger
```

### Здоровье сервера

```bash
curl http://localhost:3001/api/health
curl http://localhost:3001/api/users
```

## 🔄 Обновление

```bash
# Остановка приложения
pm2 stop messenger

# Обновление кода
git pull origin main

# Установка новых зависимостей
npm install

# Пересборка клиента
npm run build

# Перезапуск
pm2 restart messenger
```

## 🆘 Troubleshooting

### Ошибка подключения к WebSocket
- Проверьте CORS настройки в `server/index.js`
- Убедитесь, что порт 3001 открыт
- Проверьте `VITE_SOCKET_URL` в клиенте

### Ошибка базы данных
- Проверьте права доступа к файлу `messenger.db`
- Убедитесь, что есть место на диске

### Приложение не запускается
```bash
# Проверка логов
pm2 logs messenger --err

# Проверка Node.js версии
node --version  # должна быть 18+

# Пересборка native модулей
npm rebuild better-sqlite3
```

## 📱 Использование

1. Откройте приложение в браузере
2. Зарегистрируйте первого пользователя
3. Откройте другое окно/браузер и зарегистрируйте второго пользователя
4. Выберите контакт из списка и начните общение
5. Все сообщения автоматически шифруются и дешифруются

## 📄 Лицензия

MIT License
