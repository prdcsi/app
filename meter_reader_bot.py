import os
import logging
from datetime import datetime
from decimal import Decimal

import psycopg2
from psycopg2.extras import RealDictCursor
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes

# Импорт модуля хранилища
from s3_storage import create_storage

# Настройки
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN', 'YOUR_TELEGRAM_BOT_TOKEN')
DB_CONFIG = {
    'dbname': os.getenv('DB_NAME', 'meter_db'),
    'user': os.getenv('DB_USER', 'postgres'),
    'password': os.getenv('DB_PASSWORD', 'postgres'),
    'host': os.getenv('DB_HOST', 'localhost'),
    'port': os.getenv('DB_PORT', '5432'),
}

# Инициализация хранилища (S3 или локальное)
storage = create_storage()

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Типы счетчиков для отображения
METER_TYPES = {
    'water_cold': '💧 ХВС',
    'water_hot': '🔥 ГВС',
    'electricity': '⚡ Электричество',
    'gas': '🔥 Газ'
}


def get_db_connection():
    """Получение соединения с базой данных"""
    return psycopg2.connect(**DB_CONFIG)


def init_user(telegram_id: int, username: str, first_name: str, last_name: str):
    """Инициализация пользователя в БД"""
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO users (telegram_id, username, first_name, last_name)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (telegram_id) DO UPDATE SET
                    username = EXCLUDED.username,
                    first_name = EXCLUDED.first_name,
                    last_name = EXCLUDED.last_name
            """, (telegram_id, username, first_name, last_name))
        conn.commit()
    finally:
        conn.close()


def get_user_addresses(telegram_id: int):
    """Получение адресов пользователя"""
    conn = get_db_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT a.id, a.street, a.building, a.apartment, ua.is_primary
                FROM addresses a
                JOIN user_addresses ua ON a.id = ua.address_id
                WHERE ua.user_id = %s
                ORDER BY ua.is_primary DESC, a.street, a.building, a.apartment
            """, (telegram_id,))
            return cur.fetchall()
    finally:
        conn.close()


def get_all_addresses():
    """Получение всех доступных адресов"""
    conn = get_db_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT id, street, building, apartment
                FROM addresses
                ORDER BY street, building, apartment
            """)
            return cur.fetchall()
    finally:
        conn.close()


def add_user_address(telegram_id: int, address_id: int):
    """Привязка адреса к пользователю"""
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            # Сначала снимаем флаг primary с других адресов
            cur.execute("""
                UPDATE user_addresses SET is_primary = FALSE WHERE user_id = %s
            """, (telegram_id,))
            
            # Добавляем новый адрес как основной
            cur.execute("""
                INSERT INTO user_addresses (user_id, address_id, is_primary)
                VALUES (%s, %s, TRUE)
                ON CONFLICT (user_id, address_id) DO UPDATE SET
                    is_primary = TRUE,
                    created_at = CURRENT_TIMESTAMP
            """, (telegram_id, address_id))
        conn.commit()
    finally:
        conn.close()


def get_meters_for_address(address_id: int):
    """Получение приборов учета для адреса"""
    conn = get_db_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT m.id, m.name, m.meter_type, m.serial_number
                FROM meters m
                WHERE m.address_id = %s
                ORDER BY m.meter_type, m.name
            """, (address_id,))
            return cur.fetchall()
    finally:
        conn.close()


def get_last_reading(meter_id: int):
    """Получение последнего показания для счетчика"""
    conn = get_db_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT value, submitted_at, photo_path
                FROM readings
                WHERE meter_id = %s
                ORDER BY submitted_at DESC
                LIMIT 1
            """, (meter_id,))
            return cur.fetchone()
    finally:
        conn.close()


def add_reading(meter_id: int, user_id: int, value: Decimal, photo_path: str = None, 
                photo_url: str = None, photo_key: str = None, comment: str = None):
    """Добавление нового показания"""
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO readings (meter_id, user_id, value, photo_path, photo_url, photo_key, comment)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            """, (meter_id, user_id, value, photo_path, photo_url, photo_key, comment))
        conn.commit()
    finally:
        conn.close()


def get_readings_history(meter_id: int, limit: int = 10):
    """Получение истории показаний для счетчика"""
    conn = get_db_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT r.value, r.submitted_at, r.photo_url, r.photo_key, r.comment
                FROM readings r
                WHERE r.meter_id = %s
                ORDER BY r.submitted_at DESC
                LIMIT %s
            """, (meter_id, limit))
            return cur.fetchall()
    finally:
        conn.close()


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /start"""
    user = update.effective_user
    init_user(user.id, user.username, user.first_name, user.last_name)
    
    await update.message.reply_text(
        f"👋 Здравствуйте, {user.first_name}!\n\n"
        "Я бот для передачи показаний приборов учета.\n\n"
        "Команды:\n"
        "/cabinet - Личный кабинет\n"
        "/select_address - Выбрать адрес\n"
        "/help - Помощь"
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /help"""
    await update.message.reply_text(
        "📖 **Помощь**\n\n"
        "Этот бот помогает передавать показания приборов учета.\n\n"
        "**Как использовать:**\n"
        "1. Выберите адрес через /select_address\n"
        "2. Откройте личный кабинет /cabinet\n"
        "3. Нажмите 'Передать' на нужном счетчике\n"
        "4. Отправьте фото или введите числовое значение\n\n"
        "**Поддерживаемые типы:**\n"
        "💧 ХВС - Холодное водоснабжение\n"
        "🔥 ГВС - Горячее водоснабжение\n"
        "⚡ Электричество\n"
        "🔥 Газ"
    )


async def select_address(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /select_address"""
    addresses = get_all_addresses()
    
    if not addresses:
        await update.message.reply_text("❌ В системе нет доступных адресов.")
        return
    
    keyboard = []
    for addr in addresses:
        display = f"🏠 {addr['street']}, д. {addr['building']}, кв. {addr['apartment']}"
        keyboard.append([InlineKeyboardButton(display, callback_data=f"addr_{addr['id']}")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        "🏠 **Выберите ваш адрес:**",
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )


async def address_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка выбора адреса"""
    query = update.callback_query
    await query.answer()
    
    data = query.data
    if not data.startswith("addr_"):
        return
    
    address_id = int(data.split("_")[1])
    telegram_id = query.from_user.id
    
    # Привязываем адрес к пользователю
    add_user_address(telegram_id, address_id)
    
    # Получаем информацию об адресе
    conn = get_db_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT * FROM addresses WHERE id = %s", (address_id,))
            address = cur.fetchone()
    finally:
        conn.close()
    
    await query.edit_message_text(
        f"✅ Адрес выбран:\n"
        f"🏠 {address['street']}, д. {address['building']}, кв. {address['apartment']}\n\n"
        "Теперь используйте /cabinet для просмотра приборов учета."
    )


async def cabinet(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /cabinet - Личный кабинет"""
    user = update.effective_user
    telegram_id = user.id
    
    # Проверяем адреса пользователя
    user_addresses = get_user_addresses(telegram_id)
    
    if not user_addresses:
        keyboard = [[InlineKeyboardButton("🏠 Выбрать адрес", callback_data="cmd_select_address")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(
            "⚠️ У вас еще не выбран адрес.\n"
            "Пожалуйста, выберите адрес для просмотра приборов учета.",
            reply_markup=reply_markup
        )
        return
    
    # Берем основной адрес
    current_address = next((a for a in user_addresses if a['is_primary']), user_addresses[0])
    address_id = current_address['id']
    
    # Получаем счетчики
    meters = get_meters_for_address(address_id)
    
    # Формируем сообщение
    address_str = f"🏠 {current_address['street']}, д. {current_address['building']}, кв. {current_address['apartment']}"
    
    message = f"👤 **Личный кабинет**\n\n{address_str}\n\n"
    message += "**📊 Приборы учета:**\n"
    
    if not meters:
        message += "\n❌ Для этого адреса нет зарегистрированных приборов учета."
    else:
        for meter in meters:
            last_reading = get_last_reading(meter['id'])
            meter_icon = METER_TYPES.get(meter['meter_type'], '📍')
            
            message += f"\n{meter_icon} **{meter['name']}**\n"
            if meter['serial_number']:
                message += f"   Серийный номер: `{meter['serial_number']}`\n"
            
            if last_reading:
                date_str = last_reading['submitted_at'].strftime('%d.%m.%Y %H:%M')
                message += f"   Последнее показание: **{last_reading['value']}**\n"
                message += f"   Дата передачи: _{date_str}_\n"
            else:
                message += "   Последнее показание: _нет данных_\n"
    
    # Кнопки управления
    keyboard = []
    
    # Кнопки для каждого счетчика
    for meter in meters:
        meter_icon = METER_TYPES.get(meter['meter_type'], '📍')
        keyboard.append([
            InlineKeyboardButton(f"{meter_icon} {meter['name']}", callback_data=f"meter_{meter['id']}")
        ])
    
    keyboard.append([
        InlineKeyboardButton("🔄 Обновить", callback_data="refresh_cabinet"),
        InlineKeyboardButton("🏠 Сменить адрес", callback_data="cmd_select_address")
    ])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        message,
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )


async def meter_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка выбора счетчика"""
    query = update.callback_query
    await query.answer()
    
    data = query.data
    if not data.startswith("meter_"):
        return
    
    meter_id = int(data.split("_")[1])
    
    # Получаем информацию о счетчике
    conn = get_db_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT m.*, a.street, a.building, a.apartment
                FROM meters m
                JOIN addresses a ON m.address_id = a.id
                WHERE m.id = %s
            """, (meter_id,))
            meter = cur.fetchone()
    finally:
        conn.close()
    
    last_reading = get_last_reading(meter_id)
    meter_icon = METER_TYPES.get(meter['meter_type'], '📍')
    
    message = f"{meter_icon} **{meter['name']}**\n\n"
    message += f"🏠 Адрес: {meter['street']}, д. {meter['building']}, кв. {meter['apartment']}\n"
    if meter['serial_number']:
        message += f"🔢 Серийный номер: `{meter['serial_number']}`\n"
    
    if last_reading:
        date_str = last_reading['submitted_at'].strftime('%d.%m.%Y %H:%M')
        message += f"\n📊 Последнее показание: **{last_reading['value']}**\n"
        message += f"📅 Дата: _{date_str}_\n"
    else:
        message += "\n⚠️ Показаний еще не было."
    
    keyboard = [
        [InlineKeyboardButton("📝 Передать показание", callback_data=f"submit_{meter_id}")],
        [InlineKeyboardButton("🔙 Назад", callback_data="refresh_cabinet")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        message,
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )


async def submit_reading_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Запрос на передачу показания"""
    query = update.callback_query
    await query.answer()
    
    data = query.data
    if not data.startswith("submit_"):
        return
    
    meter_id = int(data.split("_")[1])
    
    await query.edit_message_text(
        "📝 **Передача показания**\n\n"
        "Отправьте мне:\n"
        "1. 📸 Фото счетчика (я распознаю цифры автоматически)\n"
        "2. 🔢 Или просто числовое значение текстом\n\n"
        "Или нажмите /cancel для отмены.",
        parse_mode='Markdown'
    )
    
    context.user_data['waiting_for_reading'] = meter_id


async def handle_photo_or_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка фото или текста с показанием"""
    user = update.effective_user
    meter_id = context.user_data.get('waiting_for_reading')
    
    if meter_id is None:
        return
    
    photo_path = None
    photo_url = None
    photo_key = None
    value = None
    
    # Если это фото
    if update.message.photo:
        photo = update.message.photo[-1]  # Берем фото лучшего качества
        file = await photo.get_file()
        
        # Скачиваем файл в память
        photo_bytes = await file.download_as_bytearray()
        
        # Загружаем в хранилище (S3 или локальное)
        photo_url, photo_key = storage.upload_photo(
            file_bytes=bytes(photo_bytes),
            user_id=user.id,
            meter_id=meter_id,
            content_type='image/jpeg'
        )
        
        if photo_url:
            logger.info(f"Photo uploaded: {photo_url}")
        else:
            logger.warning("Failed to upload photo")
        
        # TODO: Здесь можно добавить OCR распознавание
        await update.message.reply_text(
            "📸 Фото получено и сохранено!\n"
            "Теперь введите числовое значение показания вручную,\n"
            "или я попробую распознать его автоматически (функция в разработке).",
            parse_mode='Markdown'
        )
        return
    
    # Если это текст
    if update.message.text:
        try:
            value = Decimal(update.message.text.replace(',', '.'))
        except:
            await update.message.reply_text(
                "❌ Неверный формат. Пожалуйста, отправьте число (например: 123.45)"
            )
            return
    
    if value is not None:
        # Сохраняем показание с фото (если есть)
        add_reading(meter_id, user.id, value, photo_path, photo_url, photo_key)
        
        # Получаем информацию о счетчике для ответа
        conn = get_db_connection()
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("SELECT name, meter_type FROM meters WHERE id = %s", (meter_id,))
                meter = cur.fetchone()
        finally:
            conn.close()
        
        meter_icon = METER_TYPES.get(meter['meter_type'], '📍')
        
        # Формируем ответ с возможностью просмотра фото
        response = f"✅ Показание принято!\n\n"
        response += f"{meter_icon} {meter['name']}\n"
        response += f"Значение: **{value}**\n"
        response += f"Дата: _{datetime.now().strftime('%d.%m.%Y %H:%M')}_\n"
        
        if photo_url:
            keyboard = [[InlineKeyboardButton("📷 Просмотреть фото", callback_data=f"view_photo_{meter_id}")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            response += "\n📎 Фото прикреплено к показанию."
        else:
            reply_markup = None
        
        await update.message.reply_text(
            response,
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
        
        context.user_data['waiting_for_reading'] = None


async def view_photo_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Просмотр фото последнего показания"""
    query = update.callback_query
    await query.answer()
    
    data = query.data
    if not data.startswith("view_photo_"):
        return
    
    meter_id = int(data.split("_")[2])
    
    # Получаем последнее показание с фото
    last_reading = get_last_reading(meter_id)
    
    if last_reading and last_reading.get('photo_url'):
        photo_url = storage.get_photo_url(last_reading['photo_key']) if last_reading.get('photo_key') else last_reading['photo_url']
        
        if photo_url:
            await query.message.reply_photo(photo=photo_url, caption="📷 Фото показания")
        else:
            await query.message.reply_text("❌ Не удалось получить ссылку на фото")
    else:
        await query.message.reply_text("❌ Для этого показания нет фото")


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отмена текущего действия"""
    context.user_data['waiting_for_reading'] = None
    await update.message.reply_text("❌ Действие отменено. Используйте /cabinet для возврата в личный кабинет.")


async def refresh_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обновление личного кабинета"""
    query = update.callback_query
    await query.answer("Обновляю...")
    
    # Имитируем команду cabinet
    # Нужно создать фейковый update.message для вызова cabinet
    class FakeMessage:
        def __init__(self, original_update):
            self._update = original_update
        
        async def reply_text(self, text, reply_markup=None, parse_mode=None):
            await self._update.callback_query.message.reply_text(
                text, reply_markup=reply_markup, parse_mode=parse_mode
            )
    
    fake_update = Update(
        update_id=update.update_id,
        message=FakeMessage(update)
    )
    await cabinet(fake_update, context)


async def cmd_select_address_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Переход к выбору адреса"""
    query = update.callback_query
    await query.answer()
    await select_address(update, context)


def main():
    """Запуск бота"""
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    
    # Обработчики команд
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("cabinet", cabinet))
    application.add_handler(CommandHandler("select_address", select_address))
    application.add_handler(CommandHandler("cancel", cancel))
    
    # Обработчики callback query
    application.add_handler(CallbackQueryHandler(address_callback, pattern="^addr_"))
    application.add_handler(CallbackQueryHandler(meter_callback, pattern="^meter_"))
    application.add_handler(CallbackQueryHandler(submit_reading_callback, pattern="^submit_"))
    application.add_handler(CallbackQueryHandler(refresh_callback, pattern="^refresh_cabinet"))
    application.add_handler(CallbackQueryHandler(cmd_select_address_callback, pattern="^cmd_select_address"))
    application.add_handler(CallbackQueryHandler(view_photo_callback, pattern="^view_photo_"))
    
    # Обработчики сообщений (фото и текст)
    application.add_handler(MessageHandler(filters.PHOTO, handle_photo_or_text))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_photo_or_text))
    
    logger.info("Бот запущен...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == '__main__':
    main()
