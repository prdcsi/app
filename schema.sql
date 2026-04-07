-- Схема базы данных для бота учета показаний

-- Таблица адресов (Жилые помещения)
CREATE TABLE IF NOT EXISTS addresses (
    id SERIAL PRIMARY KEY,
    street VARCHAR(255) NOT NULL,
    building VARCHAR(50) NOT NULL,
    apartment VARCHAR(50) NOT NULL,
    UNIQUE(street, building, apartment)
);

-- Таблица приборов учета (Счетчики)
CREATE TABLE IF NOT EXISTS meters (
    id SERIAL PRIMARY KEY,
    address_id INTEGER NOT NULL REFERENCES addresses(id) ON DELETE CASCADE,
    name VARCHAR(100) NOT NULL, -- Например: "ХВС Кухня", "Электричество"
    meter_type VARCHAR(50) NOT NULL, -- 'water_cold', 'water_hot', 'electricity', 'gas'
    serial_number VARCHAR(100), -- Серийный номер счетчика
    UNIQUE(address_id, name)
);

-- Таблица пользователей (Жители)
CREATE TABLE IF NOT EXISTS users (
    telegram_id BIGINT PRIMARY KEY,
    username VARCHAR(255),
    first_name VARCHAR(255),
    last_name VARCHAR(255),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Привязка пользователей к адресам (Личный кабинет)
CREATE TABLE IF NOT EXISTS user_addresses (
    user_id BIGINT NOT NULL REFERENCES users(telegram_id) ON DELETE CASCADE,
    address_id INTEGER NOT NULL REFERENCES addresses(id) ON DELETE CASCADE,
    is_primary BOOLEAN DEFAULT TRUE, -- Основной адрес пользователя
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (user_id, address_id)
);

-- История показаний с поддержкой фото в S3
CREATE TABLE IF NOT EXISTS readings (
    id SERIAL PRIMARY KEY,
    meter_id INTEGER NOT NULL REFERENCES meters(id) ON DELETE CASCADE,
    user_id BIGINT NOT NULL REFERENCES users(telegram_id) ON DELETE SET NULL,
    value DECIMAL(10, 3) NOT NULL,
    photo_path VARCHAR(255), -- Локальный путь к фото (устаревшее)
    photo_url TEXT, -- URL фотографии в S3 или другом хранилище
    photo_key TEXT, -- Ключ объекта в S3 для управления файлом
    submitted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    comment TEXT
);

-- Индексы для ускорения выборок
CREATE INDEX IF NOT EXISTS idx_readings_meter_id ON readings(meter_id);
CREATE INDEX IF NOT EXISTS idx_readings_submitted_at ON readings(submitted_at DESC);
CREATE INDEX IF NOT EXISTS idx_user_addresses_user_id ON user_addresses(user_id);
CREATE INDEX IF NOT EXISTS idx_meters_address_id ON meters(address_id);

-- ==========================================
-- ЗАПОЛНЕНИЕ ТЕСТОВЫМИ ДАННЫМИ
-- ==========================================

-- Добавляем адреса
INSERT INTO addresses (street, building, apartment) VALUES
('ул. Ленина', '10', '5'),
('ул. Ленина', '10', '12'),
('пр. Мира', '45', '88'),
('пер. Гагарина', '3', '2')
ON CONFLICT (street, building, apartment) DO NOTHING;

-- Добавляем счетчики для адресов
-- Адрес: ул. Ленина, 10, 5 (id=1)
INSERT INTO meters (address_id, name, meter_type, serial_number) VALUES
(1, 'ХВС Кухня', 'water_cold', 'SN12345678'),
(1, 'ГВС Кухня', 'water_hot', 'SN87654321'),
(1, 'Электричество', 'electricity', 'EL99887766')
ON CONFLICT (address_id, name) DO NOTHING;

-- Адрес: пр. Мира, 45, 88 (id=3)
INSERT INTO meters (address_id, name, meter_type, serial_number) VALUES
(3, 'Газ', 'gas', 'GS11223344'),
(3, 'ХВС Ванная', 'water_cold', 'SN55667788')
ON CONFLICT (address_id, name) DO NOTHING;

-- Добавляем несколько исторических показаний для демонстрации
-- Для счетчика ХВС Кухня (id=1)
INSERT INTO readings (meter_id, value, submitted_at, comment) VALUES
(1, 120.5, NOW() - INTERVAL '30 days', 'Первое показание'),
(1, 135.0, NOW() - INTERVAL '15 days', 'Показание за прошлый месяц');

-- Для счетчика ГВС Кухня (id=2)
INSERT INTO readings (meter_id, value, submitted_at) VALUES
(2, 45.2, NOW() - INTERVAL '15 days');

-- Для счетчика Электричество (id=3)
INSERT INTO readings (meter_id, value, submitted_at) VALUES
(3, 1540.0, NOW() - INTERVAL '10 days');
