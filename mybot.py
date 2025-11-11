import logging
from datetime import datetime, timedelta
import sqlite3
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes, MessageHandler, filters
import asyncio

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Токен бота
BOT_TOKEN = "8297386105:AAH3ombr86k2yJF3udsVnk_5Y46ZK1Y1DTc"

# ID главного администратора (ВАШ ID)
MAIN_ADMIN_ID = 1246951810
ADMIN_IDS = [MAIN_ADMIN_ID]

# Список доступных групп
GROUPS = ["ПСН-24", "ПСН-23", "ПСН-25", "ТСН-25", "ТСН-24", "ТСН-23", "СТН-25"]

# Дата начала учебного года
def get_academic_year_start():
    now = datetime.now()
    return datetime(now.year, 9, 1) if now.month >= 9 else datetime(now.year - 1, 9, 1)

# Расчет текущей учебной недели
def get_current_week():
    start_date = get_academic_year_start()
    now = datetime.now()
    
    if now.month < 9:
        start_date = datetime(now.year - 1, 9, 1)
    
    delta = now - start_date
    week_number = delta.days // 7 + 1
    is_even_week = week_number % 2 == 0
    
    return week_number, "Четная" if is_even_week else "Нечетная"

# Расписание для ПСН-24
SCHEDULE = {
    "ПСН-24": {
        "Четная": {
            "Понедельник": "1. Разговор о важном (411)\n2. Основы алгоритмизации и программирования (411)\n3. Физическая культура (1 п/гр)",
            "Вторник": "1. Классный час (411)\n2. Информационные технологии (411)\n3. Архитектура аппаратных средств (410)",
            "Среда": "1. 1С: Предприятие (411)\n2. Основы алгоритмизации и программирования (420)\n3. Информационные технологии (411)",
            "Четверг": "1. История (512)\n2. История (512)",
            "Пятница": "1. Физическая культура (2 п/гр) 18:30-20:05",
            "Суббота": "Выходной",
            "Воскресенье": "Выходной"
        },
        "Нечетная": {
            "Понедельник": "1. Основы алгоритмизации и программирования (511)\n2. Элементы высшей математики (511)\n3. Математическое моделирование (413)",
            "Вторник": "1. 3D-моделирование (413)\n2. Математическое моделирование (511)\n3. Элементы высшей математики (511)",
            "Среда": "1. Иностранный язык (408/403)\n2. Теория вероятностей (511)\n3. 1С: Предприятие (411) / Основы алгоритмизации (413)",
            "Четверг": "1. Теория вероятностей (511)\n2. 1С: Предприятие (411) / Основы алгоритмизации (413)",
            "Пятница": "Выходной",
            "Суббота": "Выходной",
            "Воскресенье": "Выходной"
        }
    }
}

# Заполняем расписание для остальных групп
for group in GROUPS:
    if group not in SCHEDULE:
        SCHEDULE[group] = SCHEDULE["ПСН-24"]

# Инициализация базы данных
def init_db():
    conn = sqlite3.connect('university_bot.db', check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            first_name TEXT,
            group_name TEXT,
            last_active DATETIME DEFAULT CURRENT_TIMESTAMP,
            is_banned BOOLEAN DEFAULT FALSE,
            is_admin BOOLEAN DEFAULT FALSE
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS chats (
            chat_id INTEGER PRIMARY KEY,
            chat_title TEXT,
            added_date DATETIME DEFAULT CURRENT_TIMESTAMP,
            is_active BOOLEAN DEFAULT TRUE,
            chat_group TEXT
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS chat_users (
            chat_id INTEGER,
            user_id INTEGER,
            group_name TEXT,
            PRIMARY KEY (chat_id, user_id)
        )
    ''')
    conn.commit()
    conn.close()

# Сохранение пользователя
def save_user(user_id, username, first_name, group_name):
    conn = sqlite3.connect('university_bot.db', check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute('''
        INSERT OR REPLACE INTO users (user_id, username, first_name, group_name, last_active)
        VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
    ''', (user_id, username, first_name, group_name))
    conn.commit()
    conn.close()

# Получение пользователя
def get_user(user_id):
    try:
        conn = sqlite3.connect('university_bot.db', check_same_thread=False)
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM users WHERE user_id = ?', (user_id,))
        user = cursor.fetchone()
        conn.close()
        return user
    except Exception as e:
        logger.error(f"Ошибка при получении пользователя {user_id}: {e}")
        return None

# Поиск пользователя по username
def find_user_by_username(username):
    try:
        conn = sqlite3.connect('university_bot.db', check_same_thread=False)
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM users WHERE username = ?', (username,))
        user = cursor.fetchone()
        conn.close()
        return user
    except Exception as e:
        logger.error(f"Ошибка при поиске пользователя по username {username}: {e}")
        return None

# Получение пользователей по группе
def get_users_by_group(group_name):
    try:
        conn = sqlite3.connect('university_bot.db', check_same_thread=False)
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM users WHERE group_name = ? AND is_banned = FALSE', (group_name,))
        users = cursor.fetchall()
        conn.close()
        return users
    except Exception as e:
        logger.error(f"Ошибка при получении пользователей группы {group_name}: {e}")
        return []

# Получение всех пользователей
def get_all_users():
    try:
        conn = sqlite3.connect('university_bot.db', check_same_thread=False)
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM users ORDER BY last_active DESC')
        users = cursor.fetchall()
        conn.close()
        return users
    except Exception as e:
        logger.error(f"Ошибка при получении всех пользователей: {e}")
        return []

# Получение активных пользователей
def get_active_users():
    try:
        conn = sqlite3.connect('university_bot.db', check_same_thread=False)
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM users WHERE is_banned = FALSE ORDER BY last_active DESC')
        users = cursor.fetchall()
        conn.close()
        return users
    except Exception as e:
        logger.error(f"Ошибка при получении активных пользователей: {e}")
        return []

# Получение всех чатов
def get_all_chats():
    try:
        conn = sqlite3.connect('university_bot.db', check_same_thread=False)
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM chats WHERE is_active = TRUE')
        chats = cursor.fetchall()
        conn.close()
        return chats
    except Exception as e:
        logger.error(f"Ошибка при получении чатов: {e}")
        return []

# Добавление чата
def add_chat(chat_id, chat_title):
    try:
        conn = sqlite3.connect('university_bot.db', check_same_thread=False)
        cursor = conn.cursor()
        cursor.execute('''
            INSERT OR REPLACE INTO chats (chat_id, chat_title, added_date, is_active)
            VALUES (?, ?, CURRENT_TIMESTAMP, TRUE)
        ''', (chat_id, chat_title))
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        logger.error(f"Ошибка при добавлении чата {chat_id}: {e}")
        return False

# Установка группы для чата
def set_chat_group(chat_id, group_name):
    try:
        conn = sqlite3.connect('university_bot.db', check_same_thread=False)
        cursor = conn.cursor()
        cursor.execute('UPDATE chats SET chat_group = ? WHERE chat_id = ?', (group_name, chat_id))
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        logger.error(f"Ошибка при установке группы для чата {chat_id}: {e}")
        return False

# Получение группы чата
def get_chat_group(chat_id):
    try:
        conn = sqlite3.connect('university_bot.db', check_same_thread=False)
        cursor = conn.cursor()
        cursor.execute('SELECT chat_group FROM chats WHERE chat_id = ?', (chat_id,))
        result = cursor.fetchone()
        conn.close()
        return result[0] if result else None
    except Exception as e:
        logger.error(f"Ошибка при получении группы чата {chat_id}: {e}")
        return None

# Сохранение пользователя чата
def save_chat_user(chat_id, user_id, group_name):
    try:
        conn = sqlite3.connect('university_bot.db', check_same_thread=False)
        cursor = conn.cursor()
        cursor.execute('''
            INSERT OR REPLACE INTO chat_users (chat_id, user_id, group_name)
            VALUES (?, ?, ?)
        ''', (chat_id, user_id, group_name))
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        logger.error(f"Ошибка при сохранении пользователя чата {chat_id}: {e}")
        return False

# Получение группы пользователя в чате
def get_chat_user_group(chat_id, user_id):
    try:
        conn = sqlite3.connect('university_bot.db', check_same_thread=False)
        cursor = conn.cursor()
        cursor.execute('SELECT group_name FROM chat_users WHERE chat_id = ? AND user_id = ?', (chat_id, user_id))
        result = cursor.fetchone()
        conn.close()
        return result[0] if result else None
    except Exception as e:
        logger.error(f"Ошибка при получении группы пользователя чата {chat_id}: {e}")
        return None

# Обновление активности
def update_user_activity(user_id):
    try:
        conn = sqlite3.connect('university_bot.db', check_same_thread=False)
        cursor = conn.cursor()
        cursor.execute('UPDATE users SET last_active = CURRENT_TIMESTAMP WHERE user_id = ?', (user_id,))
        conn.commit()
        conn.close()
    except Exception as e:
        logger.error(f"Ошибка при обновлении активности пользователя {user_id}: {e}")

# Бан пользователя
def ban_user(user_id):
    try:
        conn = sqlite3.connect('university_bot.db', check_same_thread=False)
        cursor = conn.cursor()
        cursor.execute('UPDATE users SET is_banned = TRUE WHERE user_id = ?', (user_id,))
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        logger.error(f"Ошибка при бане пользователя {user_id}: {e}")
        return False

# Разбан пользователя
def unban_user(user_id):
    try:
        conn = sqlite3.connect('university_bot.db', check_same_thread=False)
        cursor = conn.cursor()
        cursor.execute('UPDATE users SET is_banned = FALSE WHERE user_id = ?', (user_id,))
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        logger.error(f"Ошибка при разбане пользователя {user_id}: {e}")
        return False

# Сделать администратором
def make_admin(user_id):
    try:
        conn = sqlite3.connect('university_bot.db', check_same_thread=False)
        cursor = conn.cursor()
        cursor.execute('UPDATE users SET is_admin = TRUE WHERE user_id = ?', (user_id,))
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        logger.error(f"Ошибка при выдаче прав админа пользователю {user_id}: {e}")
        return False

# Проверка админа (безопасная версия)
def is_admin(user_id):
    try:
        if user_id in ADMIN_IDS:
            return True
        
        user = get_user(user_id)
        if user and len(user) > 6:
            return bool(user[6])  # user[6] - is_admin
        return False
    except Exception as e:
        logger.error(f"Ошибка при проверке прав админа для {user_id}: {e}")
        return False

# Проверка главного админа
def is_main_admin(user_id):
    return user_id == MAIN_ADMIN_ID

# Проверка бана (безопасная версия)
def is_banned(user_id):
    try:
        user = get_user(user_id)
        if user and len(user) > 5:
            return bool(user[5])  # user[5] - is_banned
        return False
    except Exception as e:
        logger.error(f"Ошибка при проверке бана для {user_id}: {e}")
        return False

# День недели на русском
def get_russian_weekday(date=None):
    if date is None:
        date = datetime.now()
    
    weekdays = {
        0: "Понедельник",
        1: "Вторник",
        2: "Среда", 
        3: "Четверг",
        4: "Пятница",
        5: "Суббота",
        6: "Воскресенье"
    }
    return weekdays[date.weekday()]

# Главное меню
async def main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Проверка на групповой чат
    if update.effective_chat.type in ['group', 'supergroup']:
        await update.message.reply_text("❌ Бот не работает в групповых чатах. Используйте бота в личных сообщениях.")
        return
    
    user = update.effective_user
    
    # Безопасная проверка бана
    try:
        if is_banned(user.id):
            if update.callback_query:
                await update.callback_query.edit_message_text("❌ Вы заблокированы и не можете использовать бота.")
            else:
                await update.message.reply_text("❌ Вы заблокированы и не можете использовать бота.")
            return
    except Exception as e:
        logger.error(f"Ошибка при проверке бана в главном меню: {e}")
    
    keyboard = [
        [InlineKeyboardButton("Информация о боте", callback_data="info")],
        [InlineKeyboardButton("Кто я?", callback_data="whoami")],
        [InlineKeyboardButton("Какая сейчас неделя?", callback_data="current_week")],
        [InlineKeyboardButton("Сменить группу", callback_data="change_group")],
        [InlineKeyboardButton("Расписание", callback_data="schedule")]
    ]
    
    # Безопасная проверка админа
    try:
        if is_admin(user.id):
            keyboard.append([InlineKeyboardButton("👑 Админ-панель", callback_data="admin_panel")])
    except Exception as e:
        logger.error(f"Ошибка при проверке админа в главном меню: {e}")
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    if update.callback_query:
        await update.callback_query.edit_message_text("Главное меню:", reply_markup=reply_markup)
    else:
        await update.message.reply_text("Главное меню:", reply_markup=reply_markup)

# Команда /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Обработка добавления в группу
    if update.effective_chat.type in ['group', 'supergroup']:
        chat = update.effective_chat
        add_chat(chat.id, chat.title)
        
        welcome_text = (
            "👋 Спасибо, что добавили меня в беседу!\n\n"
            "📢 Чтобы я мог нормально работать, пожалуйста:\n"
            "1. Выдайте мне права администратора\n"
            "2. Разрешите отправлять сообщения\n\n"
            "ℹ️ Бот будет присылать расписание и рассылку в эту беседу.\n"
            "💬 Для личного использования напишите мне в личные сообщения."
        )
        
        await update.message.reply_text(welcome_text)
        return
    
    # Личные сообщения
    user = update.effective_user
    
    # Безопасная проверка бана
    try:
        if is_banned(user.id):
            await update.message.reply_text("❌ Вы заблокированы и не можете использовать бота.")
            return
    except Exception as e:
        logger.error(f"Ошибка при проверке бана в /start: {e}")
    
    try:
        update_user_activity(user.id)
        user_data = get_user(user.id)
        
        if user_data and user_data[3]:  # Проверяем что группа выбрана
            await main_menu(update, context)
        else:
            keyboard = [[InlineKeyboardButton("Выбрать группу", callback_data="select_group")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await update.message.reply_text(
                f"Привет, {user.first_name}! Добро пожаловать в бот расписания университета.\n"
                "Для начала работы выберите свою группу:",
                reply_markup=reply_markup
            )
    except Exception as e:
        logger.error(f"Ошибка в команде /start: {e}")
        await update.message.reply_text("⚠️ Произошла ошибка. Попробуйте еще раз.")

# Команда /group для выбора группы в чате
async def group_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type not in ['group', 'supergroup']:
        await update.message.reply_text("❌ Эта команда работает только в групповых чатах.")
        return
    
    user = update.effective_user
    chat_id = update.effective_chat.id
    
    # Проверяем, выбрал ли пользователь уже группу в этом чате
    current_group = get_chat_user_group(chat_id, user.id)
    
    if current_group:
        await update.message.reply_text(
            f"📚 Вы уже выбрали группу {current_group} в этом чате.\n"
            f"Чтобы изменить группу, используйте команду /group снова."
        )
        return
    
    # Показываем выбор группы
    keyboard = []
    for group in GROUPS:
        keyboard.append([InlineKeyboardButton(group, callback_data=f"chat_group_{group}")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        "📚 Выберите вашу группу для получения расписания в этом чате:",
        reply_markup=reply_markup
    )

# Обработчик кнопок
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user = query.from_user
    
    # Проверка на групповой чат для обычных команд
    if (update.effective_chat.type in ['group', 'supergroup'] and 
        not query.data.startswith('chat_group_')):
        await query.edit_message_text("❌ Бот не работает в групповых чатах. Используйте бота в личных сообщениях.")
        return
    
    # Безопасная проверка бана
    try:
        if is_banned(user.id):
            await query.edit_message_text("❌ Вы заблокированы и не можете использовать бота.")
            return
    except Exception as e:
        logger.error(f"Ошибка при проверке бана в обработчике кнопок: {e}")
    
    try:
        update_user_activity(user.id)
        
        if query.data == "select_group":
            await show_group_selection(query)
        elif query.data == "info":
            await show_bot_info(query)
        elif query.data == "whoami":
            await show_user_info(query, user)
        elif query.data == "current_week":
            await show_current_week(query)
        elif query.data == "change_group":
            await show_group_selection(query)
        elif query.data == "schedule":
            await show_today_schedule(query, user)
        elif query.data == "main_menu":
            await main_menu(update, context)
        elif query.data == "admin_panel":
            await show_admin_panel(query, user)
        elif query.data == "admin_broadcast":
            await show_broadcast_groups(query, context)
        elif query.data == "admin_schedule_broadcast":
            await confirm_schedule_broadcast(query, context)
        elif query.data == "confirm_schedule_send":
            await send_schedule_broadcast_now(update, context)
        elif query.data == "admin_stats":
            await show_admin_stats(query)
        elif query.data == "admin_ban":
            await start_ban_user(query, context)
        elif query.data == "admin_unban":
            await start_unban_user(query, context)
        elif query.data == "admin_make_admin":
            await start_make_admin(query, context)
        elif query.data == "admin_back":
            await main_menu(update, context)
        elif query.data == "confirm_broadcast":
            await confirm_broadcast(update, context)
        elif query.data.startswith("broadcast_group_"):
            group_name = query.data.replace("broadcast_group_", "")
            context.user_data['selected_groups'] = [group_name]
            await start_broadcast_message(query, context)
        elif query.data == "broadcast_all_groups":
            context.user_data['selected_groups'] = "all"
            await start_broadcast_message(query, context)
        elif query.data.startswith("chat_group_"):
            # Обработка выбора группы в чате
            group_name = query.data.replace("chat_group_", "")
            chat_id = update.effective_chat.id
            
            save_chat_user(chat_id, user.id, group_name)
            
            await query.edit_message_text(
                f"✅ Отлично, {user.first_name}! Вы выбрали группу {group_name}.\n\n"
                f"📅 Теперь вы будете получать расписание для группы {group_name} в этом чате."
            )
        elif query.data.startswith("group_"):
            group_name = query.data.replace("group_", "")
            save_user(user.id, user.username, user.first_name, group_name)
            await query.edit_message_text(
                f"Отлично! Вы выбрали группу: {group_name}",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("В главное меню", callback_data="main_menu")]])
            )
    except Exception as e:
        logger.error(f"Ошибка в обработчике кнопок: {e}")
        await query.edit_message_text("⚠️ Произошла ошибка. Попробуйте еще раз.")

# Показать выбор группы
async def show_group_selection(query):
    keyboard = []
    for group in GROUPS:
        keyboard.append([InlineKeyboardButton(group, callback_data=f"group_{group}")])
    keyboard.append([InlineKeyboardButton("Назад", callback_data="main_menu")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text("Выберите вашу группу:", reply_markup=reply_markup)

# Показать информацию о боте
async def show_bot_info(query):
    info_text = (
        "🤖 Бот расписания университета\n\n"
        "Функции бота:\n"
        "• Показ расписания занятий\n"
        "• Ежедневная рассылка расписания\n"
        "• Выбор и смена группы\n"
        "• Информация о пользователе\n"
        "• Определение четности недели\n\n"
        "Бот разработан для удобного доступа к расписанию занятий."
    )
    await query.edit_message_text(
        info_text,
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Назад", callback_data="main_menu")]])
    )

# Показать информацию о пользователе
async def show_user_info(query, user):
    user_data = get_user(user.id)
    if user_data and len(user_data) > 3:
        group_name = user_data[3]
        admin_status = "✅ Да" if is_admin(user.id) else "❌ Нет"
        ban_status = "❌ Да" if is_banned(user.id) else "✅ Нет"
        
        info_text = (
            f"👤 Ваш профиль:\n\n"
            f"Ваш ник: @{user.username if user.username else 'Не указан'}\n"
            f"Имя: {user.first_name}\n"
            f"Ваша группа: {group_name}\n"
            f"Администратор: {admin_status}\n"
            f"Заблокирован: {ban_status}"
        )
    else:
        info_text = "Вы еще не выбрали группу."
    
    await query.edit_message_text(
        info_text,
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Назад", callback_data="main_menu")]])
    )

# Показать текущую неделю
async def show_current_week(query):
    week_number, week_type = get_current_week()
    start_date = get_academic_year_start()
    
    message = (
        f"📅 Информация о неделе:\n\n"
        f"Тип недели: {week_type}\n"
        f"Номер недели: {week_number}\n"
        f"Начало учебного года: {start_date.strftime('%d.%m.%Y')}"
    )
    
    await query.edit_message_text(
        message,
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Назад", callback_data="main_menu")]])
    )

# Показать расписание на сегодня
async def show_today_schedule(query, user):
    user_data = get_user(user.id)
    if not user_data or len(user_data) <= 3 or not user_data[3]:
        await query.edit_message_text(
            "Сначала выберите группу!",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Выбрать группу", callback_data="select_group")]])
        )
        return
    
    group_name = user_data[3]
    today = get_russian_weekday()
    week_number, week_type = get_current_week()
    
    if group_name in SCHEDULE and week_type in SCHEDULE[group_name] and today in SCHEDULE[group_name][week_type]:
        schedule_text = SCHEDULE[group_name][week_type][today]
        message = f"📅 Расписание на сегодня ({today}) для группы {group_name}:\n\n{schedule_text}\n\n({week_type} неделя, неделя №{week_number})"
    else:
        message = f"На сегодня ({today}) расписание для группы {group_name} не найдено."
    
    await query.edit_message_text(
        message,
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Назад", callback_data="main_menu")]])
    )

# Админ-панель
async def show_admin_panel(query, user):
    if not is_admin(user.id):
        await query.edit_message_text("Доступ запрещен!")
        return
    
    keyboard = [
        [InlineKeyboardButton("📊 Статистика", callback_data="admin_stats")],
        [InlineKeyboardButton("📢 Рассылка сообщения", callback_data="admin_broadcast")],
        [InlineKeyboardButton("📅 Рассылка расписания", callback_data="admin_schedule_broadcast")],
        [InlineKeyboardButton("🔨 Забанить студента", callback_data="admin_ban")],
        [InlineKeyboardButton("🔓 Разбанить студента", callback_data="admin_unban")],
    ]
    
    # Только главный админ может назначать админов
    if is_main_admin(user.id):
        keyboard.append([InlineKeyboardButton("👑 Выдать права админа", callback_data="admin_make_admin")])
    
    keyboard.append([InlineKeyboardButton("Назад", callback_data="main_menu")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text("👑 Админ-панель:", reply_markup=reply_markup)

# Статистика
async def show_admin_stats(query):
    if not is_admin(query.from_user.id):
        await query.edit_message_text("Доступ запрещен!")
        return
    
    users = get_all_users()
    total_users = len(users)
    banned_users = len([u for u in users if len(u) > 5 and u[5]])
    admin_users = len([u for u in users if (len(u) > 6 and u[6]) or u[0] in ADMIN_IDS])
    
    chats = get_all_chats()
    total_chats = len(chats)
    
    group_stats = {}
    for user in users:
        if len(user) > 3 and user[3]:
            group = user[3]
            group_stats[group] = group_stats.get(group, 0) + 1
    
    stats_text = (
        f"📊 Статистика бота:\n\n"
        f"👤 Пользователи:\n"
        f"Всего: {total_users}\n"
        f"Заблокированных: {banned_users}\n"
        f"Администраторов: {admin_users}\n\n"
        f"💬 Чаты:\n"
        f"Всего: {total_chats}\n\n"
        f"📚 По группам:\n"
    )
    
    for group, count in group_stats.items():
        stats_text += f"{group}: {count} пользователей\n"
    
    await query.edit_message_text(
        stats_text,
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Назад", callback_data="admin_panel")]])
    )

# Показать выбор групп для рассылки
async def show_broadcast_groups(query, context):
    if not is_admin(query.from_user.id):
        await query.edit_message_text("Доступ запрещен!")
        return
    
    keyboard = []
    
    # Кнопки для отдельных групп
    for group in GROUPS:
        keyboard.append([InlineKeyboardButton(f"📨 {group}", callback_data=f"broadcast_group_{group}")])
    
    # Кнопка для всех групп
    keyboard.append([InlineKeyboardButton("📨 ВСЕМ ГРУППАМ", callback_data="broadcast_all_groups")])
    keyboard.append([InlineKeyboardButton("Назад", callback_data="admin_panel")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(
        "Выберите группу для рассылки:",
        reply_markup=reply_markup
    )

# Начать ввод сообщения для рассылки
async def start_broadcast_message(query, context):
    if not is_admin(query.from_user.id):
        await query.edit_message_text("Доступ запрещен!")
        return
    
    context.user_data['awaiting_broadcast'] = True
    
    selected_groups = context.user_data.get('selected_groups', [])
    if selected_groups == "all":
        groups_text = "ВСЕМ ГРУППАМ"
    else:
        groups_text = ", ".join(selected_groups)
    
    await query.edit_message_text(
        f"Выбрана рассылка для: {groups_text}\n\n"
        "Введите сообщение для рассылки:",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Отмена", callback_data="admin_panel")]])
    )

# Подтверждение рассылки расписания
async def confirm_schedule_broadcast(query, context):
    if not is_admin(query.from_user.id):
        await query.edit_message_text("Доступ запрещен!")
        return
    
    keyboard = [
        [InlineKeyboardButton("✅ Да, разослать расписание", callback_data="confirm_schedule_send")],
        [InlineKeyboardButton("❌ Отмена", callback_data="admin_panel")]
    ]
    
    tomorrow = datetime.now() + timedelta(days=1)
    weekday = get_russian_weekday(tomorrow)
    week_number, week_type = get_current_week()
    
    await query.edit_message_text(
        f"📅 Подтвердите рассылку расписания на завтра:\n\n"
        f"Дата: {tomorrow.strftime('%d.%m.%Y')}\n"
        f"День недели: {weekday}\n"
        f"Тип недели: {week_type}\n"
        f"Номер недели: {week_number}\n\n"
        f"Рассылка будет отправлена всем пользователям и чатам.",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

# Отправка расписания сейчас
async def send_schedule_broadcast_now(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if not is_admin(query.from_user.id):
        await query.edit_message_text("Доступ запрещен!")
        return
    
    await query.edit_message_text("🔄 Начинаю рассылку расписания...")
    
    # Используем существующую функцию рассылки
    await send_daily_schedule(context)
    
    await query.edit_message_text(
        "✅ Рассылка расписания завершена!",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("В админ-панель", callback_data="admin_panel")]])
    )

# Начать бан по username
async def start_ban_user(query, context):
    if not is_admin(query.from_user.id):
        await query.edit_message_text("Доступ запрещен!")
        return
    
    context.user_data['awaiting_ban'] = True
    await query.edit_message_text(
        "Введите @username пользователя для блокировки (например, @username):",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Отмена", callback_data="admin_panel")]])
    )

# Начать разбан по username
async def start_unban_user(query, context):
    if not is_admin(query.from_user.id):
        await query.edit_message_text("Доступ запрещен!")
        return
    
    context.user_data['awaiting_unban'] = True
    await query.edit_message_text(
        "Введите @username пользователя для разблокировки (например, @username):",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Отмена", callback_data="admin_panel")]])
    )

# Начать выдачу прав админа по username
async def start_make_admin(query, context):
    if not is_main_admin(query.from_user.id):
        await query.edit_message_text("❌ Эта функция доступна только главному администратору!")
        return
    
    context.user_data['awaiting_make_admin'] = True
    await query.edit_message_text(
        "Введите @username пользователя для выдачи прав администратора (например, @username):",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Отмена", callback_data="admin_panel")]])
    )

# Обработчик админ-сообщений
async def handle_admin_messages(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    
    if not is_admin(user.id):
        return
    
    message_text = update.message.text.strip()
    
    if context.user_data.get('awaiting_broadcast'):
        selected_groups = context.user_data.get('selected_groups', [])
        
        if selected_groups == "all":
            users = get_active_users()
            groups_text = "ВСЕМ ГРУППАМ"
        else:
            users = []
            for group in selected_groups:
                users.extend(get_users_by_group(group))
            groups_text = ", ".join(selected_groups)
        
        chats = get_all_chats()
        total_recipients = len(users) + len(chats)
        
        context.user_data['broadcast_message'] = message_text
        context.user_data['broadcast_groups'] = selected_groups
        context.user_data['awaiting_broadcast'] = False
        
        keyboard = [
            [InlineKeyboardButton("✅ Да, отправить", callback_data="confirm_broadcast")],
            [InlineKeyboardButton("❌ Отмена", callback_data="admin_panel")]
        ]
        
        await update.message.reply_text(
            f"Подтвердите рассылку для: {groups_text}\n\n"
            f"Сообщение:\n{message_text}\n\n"
            f"Получателей: {total_recipients}\n"
            f"(Пользователи: {len(users)}, Чаты: {len(chats)})",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    
    elif context.user_data.get('awaiting_ban'):
        if message_text.startswith('@'):
            username = message_text[1:]  # Убираем @
            user_to_ban = find_user_by_username(username)
            if user_to_ban:
                if ban_user(user_to_ban[0]):
                    context.user_data['awaiting_ban'] = False
                    await update.message.reply_text(
                        f"✅ Пользователь @{username} заблокирован!",
                        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("В админ-панель", callback_data="admin_panel")]])
                    )
                else:
                    await update.message.reply_text("❌ Ошибка при блокировке пользователя!")
            else:
                await update.message.reply_text("❌ Пользователь с таким username не найден!")
        else:
            await update.message.reply_text("❌ Введите username в формате @username")
    
    elif context.user_data.get('awaiting_unban'):
        if message_text.startswith('@'):
            username = message_text[1:]  # Убираем @
            user_to_unban = find_user_by_username(username)
            if user_to_unban:
                if unban_user(user_to_unban[0]):
                    context.user_data['awaiting_unban'] = False
                    await update.message.reply_text(
                        f"✅ Пользователь @{username} разблокирован!",
                        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("В админ-панель", callback_data="admin_panel")]])
                    )
                else:
                    await update.message.reply_text("❌ Ошибка при разблокировке пользователя!")
            else:
                await update.message.reply_text("❌ Пользователь с таким username не найден!")
        else:
            await update.message.reply_text("❌ Введите username в формате @username")
    
    elif context.user_data.get('awaiting_make_admin'):
        if message_text.startswith('@'):
            username = message_text[1:]  # Убираем @
            user_to_admin = find_user_by_username(username)
            if user_to_admin:
                if make_admin(user_to_admin[0]):
                    context.user_data['awaiting_make_admin'] = False
                    await update.message.reply_text(
                        f"✅ Пользователю @{username} выданы права администратора!",
                        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("В админ-панель", callback_data="admin_panel")]])
                    )
                else:
                    await update.message.reply_text("❌ Ошибка при выдаче прав администратора!")
            else:
                await update.message.reply_text("❌ Пользователь с таким username не найден!")
        else:
            await update.message.reply_text("❌ Введите username в формате @username")

# Подтверждение и отправка рассылки
async def confirm_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if not is_admin(query.from_user.id):
        await query.edit_message_text("Доступ запрещен!")
        return
    
    message_text = context.user_data.get('broadcast_message', '')
    selected_groups = context.user_data.get('broadcast_groups', [])
    
    if not message_text:
        await query.edit_message_text("Ошибка: сообщение не найдено")
        return
    
    if selected_groups == "all":
        users = get_active_users()
        groups_text = "ВСЕМ ГРУППАМ"
    else:
        users = []
        for group in selected_groups:
            users.extend(get_users_by_group(group))
        groups_text = ", ".join(selected_groups)
    
    chats = get_all_chats()
    
    sent_count = 0
    failed_count = 0
    
    total_recipients = len(users) + len(chats)
    await query.edit_message_text(f"Начинаю рассылку для: {groups_text}\n\n0/{total_recipients}")
    
    # Рассылка пользователям
    for i, user_data in enumerate(users):
        user_id = user_data[0]
        try:
            await context.bot.send_message(chat_id=user_id, text=message_text)
            sent_count += 1
        except Exception as e:
            failed_count += 1
        
        if i % 10 == 0:
            await query.edit_message_text(f"Рассылка для: {groups_text}\nПользователи... {i+1}/{len(users)}")
    
    # Рассылка в чаты
    for j, chat_data in enumerate(chats):
        chat_id = chat_data[0]
        try:
            await context.bot.send_message(chat_id=chat_id, text=message_text)
            sent_count += 1
        except Exception as e:
            failed_count += 1
        
        if j % 5 == 0:
            await query.edit_message_text(f"Рассылка для: {groups_text}\nЧаты... {j+1}/{len(chats)}")
    
    await query.edit_message_text(
        f"✅ Рассылка завершена!\n\n"
        f"Для: {groups_text}\n"
        f"Успешно: {sent_count}\n"
        f"Не удалось: {failed_count}\n"
        f"Всего получателей: {total_recipients}",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("В админ-панель", callback_data="admin_panel")]])
    )

# Рассылка расписания
async def send_daily_schedule(context: ContextTypes.DEFAULT_TYPE):
    tomorrow = datetime.now() + timedelta(days=1)
    weekday = get_russian_weekday(tomorrow)
    week_number, week_type = get_current_week()
    
    all_users = get_active_users()
    all_chats = get_all_chats()
    
    # Рассылка пользователям
    for user_data in all_users:
        if len(user_data) > 3 and user_data[3]:
            user_id, username, first_name, group_name, last_active = user_data[0], user_data[1], user_data[2], user_data[3], user_data[4]
            
            if group_name in SCHEDULE and week_type in SCHEDULE[group_name] and weekday in SCHEDULE[group_name][week_type]:
                schedule_text = SCHEDULE[group_name][week_type][weekday]
                message = (
                    f"📅 Расписание на завтра ({weekday}) для группы {group_name}:\n\n"
                    f"{schedule_text}\n\n"
                    f"({week_type} неделя, неделя №{week_number})"
                )
            else:
                message = f"На завтра ({weekday}) расписание для группы {group_name} не найдено."
            
            try:
                await context.bot.send_message(chat_id=user_id, text=message)
            except Exception as e:
                logger.error(f"Не удалось отправить сообщение пользователю {user_id}: {e}")
    
    # Рассылка в чаты
    for chat_data in all_chats:
        chat_id = chat_data[0]
        message = (
            f"📅 Расписание на завтра ({weekday}):\n\n"
            f"({week_type} неделя, неделя №{week_number})\n\n"
            f"Для получения полного расписания вашей группы "
            f"напишите боту в личные сообщения и выберите свою группу."
        )
        
        try:
            await context.bot.send_message(chat_id=chat_id, text=message)
        except Exception as e:
            logger.error(f"Не удалось отправить сообщение в чат {chat_id}: {e}")

# Обработчик всех сообщений
async def handle_all_messages(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Игнорируем сообщения из групповых чатов (кроме команды /start и /group)
    if (update.effective_chat.type in ['group', 'supergroup'] and 
        not update.message.text.startswith('/start') and 
        not update.message.text.startswith('/group')):
        return
    
    user = update.effective_user
    update_user_activity(user.id)

# Обработчик ошибок
async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.error(msg="Exception while handling an update:", exc_info=context.error)

# Основная функция
def main():
    init_db()
    application = Application.builder().token(BOT_TOKEN).build()
    
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("group", group_command))
    application.add_handler(CallbackQueryHandler(button_handler))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_admin_messages))
    application.add_handler(MessageHandler(filters.ALL, handle_all_messages))
    application.add_error_handler(error_handler)
    
    job_queue = application.job_queue
    if job_queue:
        job_queue.run_daily(send_daily_schedule, time=datetime.strptime("19:00", "%H:%M").time())
        print("Ежедневная рассылка настроена на 19:00")
    else:
        print("Предупреждение: JobQueue не доступна")
    
    print("Бот запускается...")
    application.run_polling()

if __name__ == "__main__":
    main()