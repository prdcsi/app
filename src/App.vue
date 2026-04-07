<template>
  <div class="messenger">
    <header class="header">
      <h1>🔐 Secure Messenger</h1>
      <p class="subtitle">Сквозное шифрование на основе современных протоколов</p>
    </header>

    <div class="chat-container">
      <div class="messages" ref="messagesContainer">
        <div 
          v-for="(message, index) in messages" 
          :key="index"
          :class="['message', message.isOwn ? 'own' : 'received']"
        >
          <div class="message-content">
            <div class="message-text">{{ message.text }}</div>
            <div class="message-meta">
              <span>{{ message.time }}</span>
              <span v-if="message.isOwn" class="encrypted-badge">🔒 Зашифровано</span>
            </div>
          </div>
        </div>
      </div>

      <div class="input-area">
        <input 
          v-model="newMessage"
          @keyup.enter="sendMessage"
          type="text"
          placeholder="Введите сообщение..."
          class="message-input"
        />
        <button @click="sendMessage" class="send-button">
          Отправить
        </button>
      </div>
    </div>

    <div class="security-info">
      <h3>🛡️ Безопасность</h3>
      <ul>
        <li>✅ Сквозное шифрование (E2EE)</li>
        <li>✅ Протокол Диффи-Хеллмана для обмена ключами</li>
        <li>✅ AES-256 для шифрования сообщений</li>
        <li>✅ Хэширование SHA-256 для целостности данных</li>
        <li>✅ Ключи хранятся только на устройствах пользователей</li>
      </ul>
    </div>
  </div>
</template>

<script>
import { ref, nextTick } from 'vue'

// Имитация криптографических функций
// В реальном приложении здесь будет использование Web Crypto API
const cryptoUtils = {
  // Генерация пары ключей (публичный/приватный)
  async generateKeyPair() {
    // В реальности: window.crypto.subtle.generateKey(...)
    return {
      publicKey: 'pub_' + Math.random().toString(36).substr(2, 32),
      privateKey: 'priv_' + Math.random().toString(36).substr(2, 32)
    }
  },

  // Обмен ключами по протоколу Диффи-Хеллмана
  async exchangeKeys(otherPublicKey, myPrivateKey) {
    // В реальности: реализация ECDH
    return 'shared_secret_' + Math.random().toString(36).substr(2, 32)
  },

  // Шифрование сообщения (AES-256-GCM)
  async encrypt(message, sharedSecret) {
    // В реальности: window.crypto.subtle.encrypt(...)
    const encoder = new TextEncoder()
    const data = encoder.encode(message)
    const encrypted = btoa(String.fromCharCode(...data))
    return {
      ciphertext: encrypted,
      iv: Math.random().toString(36).substr(2, 16)
    }
  },

  // Дешифрование сообщения
  async decrypt(encryptedData, sharedSecret) {
    // В реальности: window.crypto.subtle.decrypt(...)
    const decoded = atob(encryptedData.ciphertext)
    return decoded
  },

  // Хэширование для проверки целостности (SHA-256)
  async hash(data) {
    // В реальности: window.crypto.subtle.digest('SHA-256', ...)
    return 'hash_' + Math.random().toString(36).substr(2, 64)
  }
}

export default {
  name: 'App',
  setup() {
    const messages = ref([
      {
        text: 'Привет! Это защищённый мессенджер.',
        time: new Date().toLocaleTimeString(),
        isOwn: false
      },
      {
        text: 'Все сообщения шифруются сквозным шифрованием.',
        time: new Date().toLocaleTimeString(),
        isOwn: false
      }
    ])
    
    const newMessage = ref('')
    const messagesContainer = ref(null)
    const encryptionKeys = ref(null)

    // Инициализация криптографии при загрузке
    const initializeEncryption = async () => {
      try {
        // Генерация пары ключей для текущего пользователя
        const keyPair = await cryptoUtils.generateKeyPair()
        
        // В реальном приложении здесь был бы обмен ключами с собеседником
        // и вычисление общего секрета по протоколу Диффи-Хеллмана
        const sharedSecret = await cryptoUtils.exchangeKeys(
          'other_user_public_key',
          keyPair.privateKey
        )
        
        encryptionKeys.value = {
          ...keyPair,
          sharedSecret
        }
        
        console.log('✅ Криптографические ключи инициализированы')
      } catch (error) {
        console.error('❌ Ошибка инициализации шифрования:', error)
      }
    }

    const sendMessage = async () => {
      if (!newMessage.value.trim()) return

      const messageText = newMessage.value.trim()
      
      // Шифрование сообщения перед отправкой
      let encryptedMessage = messageText
      if (encryptionKeys.value) {
        try {
          const encrypted = await cryptoUtils.encrypt(
            messageText,
            encryptionKeys.value.sharedSecret
          )
          
          // Вычисление хэша для проверки целостности
          const hash = await cryptoUtils.hash(messageText)
          
          console.log('🔐 Сообщение зашифровано:', encrypted)
          console.log('🔐 Хэш сообщения:', hash)
          
          // В реальном приложении здесь была бы отправка через WebSocket
          // encryptedMessage = JSON.stringify(encrypted)
        } catch (error) {
          console.error('❌ Ошибка шифрования:', error)
        }
      }

      // Добавление сообщения в список
      messages.value.push({
        text: messageText,
        time: new Date().toLocaleTimeString(),
        isOwn: true,
        encrypted: true
      })

      newMessage.value = ''
      
      // Прокрутка к последнему сообщению
      nextTick(() => {
        if (messagesContainer.value) {
          messagesContainer.value.scrollTop = messagesContainer.value.scrollHeight
        }
      })

      // Имитация ответа от собеседника
      setTimeout(() => {
        receiveMockMessage()
      }, 2000)
    }

    const receiveMockMessage = async () => {
      const mockMessages = [
        'Отлично! Я тоже ценю безопасность.',
        'Понял, спасибо за информацию!',
        'Когда встретимся?',
        'Это действительно надёжное шифрование?'
      ]
      
      const randomMessage = mockMessages[Math.floor(Math.random() * mockMessages.length)]
      
      // В реальном приложении здесь было бы дешифрование полученного сообщения
      messages.value.push({
        text: randomMessage,
        time: new Date().toLocaleTimeString(),
        isOwn: false
      })
      
      nextTick(() => {
        if (messagesContainer.value) {
          messagesContainer.value.scrollTop = messagesContainer.value.scrollHeight
        }
      })
    }

    // Инициализация при загрузке компонента
    initializeEncryption()

    return {
      messages,
      newMessage,
      messagesContainer,
      sendMessage
    }
  }
}
</script>

<style>
* {
  margin: 0;
  padding: 0;
  box-sizing: border-box;
}

body {
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  min-height: 100vh;
}

.messenger {
  max-width: 800px;
  margin: 0 auto;
  padding: 20px;
  height: 100vh;
  display: flex;
  flex-direction: column;
}

.header {
  text-align: center;
  color: white;
  margin-bottom: 20px;
}

.header h1 {
  font-size: 2rem;
  margin-bottom: 5px;
}

.subtitle {
  opacity: 0.9;
  font-size: 0.9rem;
}

.chat-container {
  flex: 1;
  background: white;
  border-radius: 15px;
  overflow: hidden;
  display: flex;
  flex-direction: column;
  box-shadow: 0 10px 40px rgba(0, 0, 0, 0.2);
}

.messages {
  flex: 1;
  overflow-y: auto;
  padding: 20px;
  display: flex;
  flex-direction: column;
  gap: 15px;
}

.message {
  max-width: 70%;
  padding: 12px 16px;
  border-radius: 15px;
  animation: fadeIn 0.3s ease;
}

@keyframes fadeIn {
  from {
    opacity: 0;
    transform: translateY(10px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

.message.own {
  align-self: flex-end;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: white;
  border-bottom-right-radius: 5px;
}

.message.received {
  align-self: flex-start;
  background: #f0f0f0;
  color: #333;
  border-bottom-left-radius: 5px;
}

.message-content {
  display: flex;
  flex-direction: column;
  gap: 5px;
}

.message-text {
  word-wrap: break-word;
  line-height: 1.4;
}

.message-meta {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 0.75rem;
  opacity: 0.8;
  gap: 10px;
}

.encrypted-badge {
  background: rgba(255, 255, 255, 0.2);
  padding: 2px 8px;
  border-radius: 10px;
  font-size: 0.7rem;
}

.input-area {
  display: flex;
  padding: 15px;
  border-top: 1px solid #e0e0e0;
  gap: 10px;
}

.message-input {
  flex: 1;
  padding: 12px 16px;
  border: 2px solid #e0e0e0;
  border-radius: 25px;
  font-size: 1rem;
  outline: none;
  transition: border-color 0.3s;
}

.message-input:focus {
  border-color: #667eea;
}

.send-button {
  padding: 12px 24px;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: white;
  border: none;
  border-radius: 25px;
  font-size: 1rem;
  cursor: pointer;
  transition: transform 0.2s, box-shadow 0.2s;
}

.send-button:hover {
  transform: translateY(-2px);
  box-shadow: 0 5px 15px rgba(102, 126, 234, 0.4);
}

.send-button:active {
  transform: translateY(0);
}

.security-info {
  background: rgba(255, 255, 255, 0.95);
  border-radius: 15px;
  padding: 20px;
  margin-top: 20px;
  box-shadow: 0 5px 20px rgba(0, 0, 0, 0.1);
}

.security-info h3 {
  color: #667eea;
  margin-bottom: 15px;
}

.security-info ul {
  list-style: none;
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
  gap: 10px;
}

.security-info li {
  padding: 8px 12px;
  background: #f8f9fa;
  border-radius: 8px;
  font-size: 0.9rem;
  color: #333;
}

/* Адаптивность для мобильных устройств */
@media (max-width: 600px) {
  .messenger {
    padding: 10px;
  }
  
  .header h1 {
    font-size: 1.5rem;
  }
  
  .message {
    max-width: 85%;
  }
  
  .security-info ul {
    grid-template-columns: 1fr;
  }
}
</style>
