import express from 'express';
import { createServer } from 'http';
import { Server } from 'socket.io';
import cors from 'cors';
import Database from 'better-sqlite3';
import bcrypt from 'bcryptjs';
import { fileURLToPath } from 'url';
import { dirname, join } from 'path';

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);

// Инициализация Express
const app = express();
const server = createServer(app);

// Настройка CORS
app.use(cors({
  origin: ['http://localhost:5173', 'http://localhost:3000', 'https://yourdomain.com'],
  credentials: true
}));

app.use(express.json());

// Инициализация базы данных SQLite
const db = new Database(join(__dirname, '../messenger.db'));

// Создание таблиц
db.exec(`
  CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    public_key TEXT NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
  );

  CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sender_id INTEGER NOT NULL,
    receiver_id INTEGER NOT NULL,
    encrypted_content TEXT NOT NULL,
    iv TEXT NOT NULL,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (sender_id) REFERENCES users(id),
    FOREIGN KEY (receiver_id) REFERENCES users(id)
  );

  CREATE TABLE IF NOT EXISTS conversations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user1_id INTEGER NOT NULL,
    user2_id INTEGER NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(user1_id, user2_id),
    FOREIGN KEY (user1_id) REFERENCES users(id),
    FOREIGN KEY (user2_id) REFERENCES users(id)
  );

  CREATE INDEX IF NOT EXISTS idx_messages_sender ON messages(sender_id);
  CREATE INDEX IF NOT EXISTS idx_messages_receiver ON messages(receiver_id);
  CREATE INDEX IF NOT EXISTS idx_messages_timestamp ON messages(timestamp);
`);

// Подготовленные запросы для безопасности
const stmts = {
  createUser: db.prepare('INSERT INTO users (username, password_hash, public_key) VALUES (?, ?, ?)'),
  getUserByUsername: db.prepare('SELECT * FROM users WHERE username = ?'),
  getUserById: db.prepare('SELECT id, username, public_key FROM users WHERE id = ?'),
  getAllUsers: db.prepare('SELECT id, username, public_key FROM users'),
  saveMessage: db.prepare('INSERT INTO messages (sender_id, receiver_id, encrypted_content, iv) VALUES (?, ?, ?, ?)'),
  getMessages: db.prepare(`
    SELECT m.id, m.sender_id, m.receiver_id, m.encrypted_content, m.iv, m.timestamp, 
           s.username as sender_username, r.username as receiver_username
    FROM messages m
    JOIN users s ON m.sender_id = s.id
    JOIN users r ON m.receiver_id = r.id
    WHERE (m.sender_id = ? AND m.receiver_id = ?) OR (m.sender_id = ? AND m.receiver_id = ?)
    ORDER BY m.timestamp ASC
  `),
  getConversations: db.prepare(`
    SELECT DISTINCT 
      CASE WHEN u1.id = ? THEN u2.id ELSE u1 END as partner_id,
      CASE WHEN u1.id = ? THEN u2.username ELSE u1.username END as partner_username,
      CASE WHEN u1.id = ? THEN u2.public_key ELSE u1.public_key END as partner_public_key,
      (SELECT encrypted_content FROM messages 
       WHERE (sender_id = ? AND receiver_id = partner_id) OR (sender_id = partner_id AND receiver_id = ?)
       ORDER BY timestamp DESC LIMIT 1) as last_message,
      (SELECT timestamp FROM messages 
       WHERE (sender_id = ? AND receiver_id = partner_id) OR (sender_id = partner_id AND receiver_id = ?)
       ORDER BY timestamp DESC LIMIT 1) as last_message_time
    FROM conversations c
    JOIN users u1 ON c.user1_id = u1.id
    JOIN users u2 ON c.user2_id = u2.id
    WHERE c.user1_id = ? OR c.user2_id = ?
    ORDER BY last_message_time DESC
  `),
  createConversation: db.prepare('INSERT OR IGNORE INTO conversations (user1_id, user2_id) VALUES (?, ?)')
};

// Socket.IO с поддержкой E2EE
const io = new Server(server, {
  cors: {
    origin: ['http://localhost:5173', 'http://localhost:3000', 'https://yourdomain.com'],
    credentials: true
  },
  connectionStateRecovery: {
    maxDisconnectionDuration: 2 * 60 * 1000,
    skipMiddlewares: true
  }
});

// Хранилище активных пользователей
const activeUsers = new Map();

io.on('connection', (socket) => {
  console.log(`Пользователь подключился: ${socket.id}`);

  // Регистрация пользователя
  socket.on('register', async (data, callback) => {
    try {
      const { username, password, publicKey } = data;
      
      if (!username || !password || !publicKey) {
        return callback({ success: false, error: 'Все поля обязательны' });
      }

      // Проверка существования пользователя
      const existingUser = stmts.getUserByUsername.get(username);
      if (existingUser) {
        return callback({ success: false, error: 'Пользователь уже существует' });
      }

      // Хеширование пароля
      const passwordHash = await bcrypt.hash(password, 10);

      // Создание пользователя
      const result = stmts.createUser.run(username, passwordHash, publicKey);
      
      activeUsers.set(socket.id, { userId: result.lastInsertRowid, username });
      socket.join(`user_${result.lastInsertRowid}`);

      callback({ 
        success: true, 
        userId: result.lastInsertRowid,
        message: 'Регистрация успешна'
      });

      // Уведомление о новом пользователе
      io.emit('user_registered', { userId: result.lastInsertRowid, username });
    } catch (error) {
      console.error('Ошибка регистрации:', error);
      callback({ success: false, error: 'Ошибка регистрации' });
    }
  });

  // Вход пользователя
  socket.on('login', async (data, callback) => {
    try {
      const { username, password } = data;
      
      if (!username || !password) {
        return callback({ success: false, error: 'Введите логин и пароль' });
      }

      const user = stmts.getUserByUsername.get(username);
      if (!user) {
        return callback({ success: false, error: 'Пользователь не найден' });
      }

      const validPassword = await bcrypt.compare(password, user.password_hash);
      if (!validPassword) {
        return callback({ success: false, error: 'Неверный пароль' });
      }

      activeUsers.set(socket.id, { userId: user.id, username: user.username });
      socket.join(`user_${user.id}`);

      callback({ 
        success: true, 
        userId: user.id,
        username: user.username,
        publicKey: user.public_key,
        message: 'Вход выполнен'
      });

      // Уведомление о входе
      io.emit('user_online', { userId: user.id, username: user.username });
    } catch (error) {
      console.error('Ошибка входа:', error);
      callback({ success: false, error: 'Ошибка входа' });
    }
  });

  // Получение списка пользователей
  socket.on('get_users', (callback) => {
    try {
      const users = stmts.getAllUsers.all();
      const usersWithStatus = users.map(user => ({
        ...user,
        online: Array.from(activeUsers.values()).some(u => u.userId === user.id)
      }));
      callback({ success: true, users: usersWithStatus });
    } catch (error) {
      console.error('Ошибка получения пользователей:', error);
      callback({ success: false, error: 'Ошибка получения пользователей' });
    }
  });

  // Отправка зашифрованного сообщения
  socket.on('send_message', (data, callback) => {
    try {
      const { senderId, receiverId, encryptedContent, iv } = data;
      
      if (!senderId || !receiverId || !encryptedContent || !iv) {
        return callback({ success: false, error: 'Все поля обязательны' });
      }

      // Сохранение сообщения в БД
      const result = stmts.saveMessage.run(senderId, receiverId, encryptedContent, iv);

      // Создание диалога если не существует
      const user1 = Math.min(senderId, receiverId);
      const user2 = Math.max(senderId, receiverId);
      stmts.createConversation.run(user1, user2);

      // Отправка сообщения получателю в реальном времени
      io.to(`user_${receiverId}`).emit('new_message', {
        id: result.lastInsertRowid,
        senderId,
        receiverId,
        encryptedContent,
        iv,
        timestamp: new Date().toISOString()
      });

      callback({ 
        success: true, 
        messageId: result.lastInsertRowid,
        message: 'Сообщение отправлено'
      });
    } catch (error) {
      console.error('Ошибка отправки сообщения:', error);
      callback({ success: false, error: 'Ошибка отправки сообщения' });
    }
  });

  // Получение истории сообщений
  socket.on('get_messages', (data, callback) => {
    try {
      const { userId, contactId } = data;
      
      if (!userId || !contactId) {
        return callback({ success: false, error: 'Не указаны пользователи' });
      }

      const messages = stmts.getMessages.all(userId, contactId, contactId, userId);
      callback({ success: true, messages });
    } catch (error) {
      console.error('Ошибка получения сообщений:', error);
      callback({ success: false, error: 'Ошибка получения сообщений' });
    }
  });

  // Получение списка диалогов
  socket.on('get_conversations', (data, callback) => {
    try {
      const { userId } = data;
      
      if (!userId) {
        return callback({ success: false, error: 'Не указан пользователь' });
      }

      const conversations = stmts.getConversations.all(
        userId, userId, userId, userId, userId, userId, userId, userId, userId
      );
      callback({ success: true, conversations });
    } catch (error) {
      console.error('Ошибка получения диалогов:', error);
      callback({ success: false, error: 'Ошибка получения диалогов' });
    }
  });

  // Отключение пользователя
  socket.on('disconnect', () => {
    const user = activeUsers.get(socket.id);
    if (user) {
      activeUsers.delete(socket.id);
      io.emit('user_offline', { userId: user.userId, username: user.username });
      console.log(`Пользователь отключился: ${user.username}`);
    }
  });
});

// REST API для проверки статуса
app.get('/api/health', (req, res) => {
  res.json({ status: 'ok', uptime: process.uptime() });
});

app.get('/api/users', (req, res) => {
  try {
    const users = stmts.getAllUsers.all();
    const usersWithStatus = users.map(user => ({
      ...user,
      online: Array.from(activeUsers.values()).some(u => u.userId === user.id)
    }));
    res.json({ success: true, users: usersWithStatus });
  } catch (error) {
    res.status(500).json({ success: false, error: error.message });
  }
});

// Обслуживание статических файлов в продакшене
if (process.env.NODE_ENV === 'production') {
  const distPath = join(__dirname, '../dist');
  app.use(express.static(distPath));
  
  app.get('*', (req, res) => {
    res.sendFile(join(distPath, 'index.html'));
  });
}

// Запуск сервера
const PORT = process.env.PORT || 3001;
server.listen(PORT, () => {
  console.log(`🚀 Сервер запущен на порту ${PORT}`);
  console.log(`📊 WebSocket: ws://localhost:${PORT}`);
  if (process.env.NODE_ENV === 'production') {
    console.log(`🌐 HTTP: http://localhost:${PORT}`);
  }
});

// Обработка закрытия процесса
process.on('SIGINT', () => {
  console.log('\nЗакрытие сервера...');
  db.close();
  server.close(() => {
    console.log('Сервер остановлен');
    process.exit(0);
  });
});
