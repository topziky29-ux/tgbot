import logging
from datetime import datetime, timedelta
import sqlite3
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes, MessageHandler, filters
import asyncio
import os
import re

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Токен бота (используйте переменные окружения!)
BOT_TOKEN = os.getenv('BOT_TOKEN', "8297386105:AAH3ombr86k2yJF3udsVnk_5Y46ZK1Y1DTc")

# ID главного администратора (ВАШ ID)
MAIN_ADMIN_ID = 1246951810
ADMIN_IDS = [MAIN_ADMIN_ID]

# Список доступных групп (убрана ТСН-25)
GROUPS = ["ПСН-24", "ПСН-23", "ПСН-25", "ТСН-24", "ТСН-23", "СТН-25"]

# Глобальная переменная для хранения состояния VIP режима пользователей
USER_VIP_MODE = {}

# Время рассылки по умолчанию
BROADCAST_TIME = "19:00"

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

# Расписание звонков
BELL_SCHEDULE = {
    "Понедельник": [
        "0 пара: 08:00-08:30",
        "1 пара: 08:40-09:25 09:30-10:15", 
        "2 пара: 10:25-11:10 11:15-12:00",
        "3 пара: 13:00-13:45 13:50-14:35",
        "4 пара: 14:45-15:30 15:35-16:20",
        "5 пара: 16:30-18:05"
    ],
    "Вторник-Суббота": [
        "1 пара: 08:00-8:45 8:50-9:35",
        "2 пара: 9:45-10:30 10:35-11:20",
        "3 пара: 12:20-13:05 13:10-13:55",
        "4 пара: 14:05-14:50 14:55-15:40",
        "5 пара: 15:50-17:25"
    ]
}

# Расписание для ПСН-24
SCHEDULE = {
    "ПСН-24": {
        "Нечетная": {
            "Понедельник": 
                "1. Разговор о важном (411)\n"
                "2. Основы алгоритмизации и программирования (411) - 3-13,17 н.\n"
                "3. Физическая культура (1 п/гр) - 15 н.\n"
                "4. Архитектура аппаратных средств (410) - 1-13,17 н.\n"
                "5. 1С: Предприятие (411) - 1-13 н.\n"
                "6. История (512) - 1-17 н.",

            "Вторник": 
                "1. Основы алгоритмизации и программирования (511) - 1 н.\n"
                "   Элементы высшей математики (511) - 3-5 н.\n"
                "   Математическое моделирование (413) - 7,11,15 н. (1 п/гр), 9,13,17 н. (2 п/гр)\n"
                "2. 3D-моделирование (413) - 1-17 н.\n"
                "3. Иностранный язык (408/403) - 1-17 н.\n"
                "4. Теория вероятностей (511) - 1-17 н.",

            "Среда": 
                "1. Архитектура аппаратных средств (411) - 1-17 н. (1 п/гр)\n"
                "   Основы алгоритмизации и программирования (413) - 1-17 н. (2 п/гр)\n"
                "2. Архитектура аппаратных средств (411) - 1-17 н. (2 п/гр)\n"
                "   Основы алгоритмизации и программирования (413) - 1-17 н. (1 п/гр)\n"
                "3. Элементы высшей математики (511) - 1-13,17 н.\n"
                "   Иностранный язык (408/403) - 15 н.\n"
                "4. Операционные системы и среды (410) - 1-17 н.",

            "Четверг": 
                "2. Физическая культура (1 п/гр) - 1-17 н.\n"
                "3. Элементы высшей математики (511) - 1-17 н.\n"
                "4. Теория вероятностей (511) - 1-17 н.\n"
                "5. Информационные технологии (411) - 1-11 н.\n"
                "   Операционные системы и среды (411) - 13-17 н.",

            "Пятница": 
                "1. Операционные системы и среды (411) - 1-17 н. (1 п/гр)\n"
                "2. Информационные технологии (413) - 1-17 н. (1 п/гр)\n"
                "   1С: Предприятие (411) - 13-15 н. (2 п/гр)\n"
                "3. Теория вероятностей (511) - 1 н.\n"
                "   Основы алгоритмизации и программирования (411) - 3-9 н.\n"
                "   Математическое моделирование (411) - 11 н.\n"
                "   Операционные системы и среды (411) - 13 н.\n"
                "   Архитектура аппаратных средств (411) - 15-17 н.\n"
                "4. Операционные системы и среды (413) - 1-17 н. (2 п/гр)\n"
                "   1С: Предприятие (411) - 13-15 н. (1 п/гр)\n"
                "5. Информационные технологии (411) - 1-17 н. (2 п/гр)",

            "Суббота": "Выходной",
            "Воскресенье": "Выходной"
        },
        "Четная": {
            "Понедельник": 
                "1. Классный час (411)\n"
                "   Информационные технологии (411) - 2-18 н.\n"
                "2. Основы алгоритмизации и программирования (420) - 2 н.\n"
                "   Теория вероятностей (420) - 4 н.\n"
                "   Основы алгоритмизации и программирования (420) - 6,8,12,16 н. (1 п/гр), 10,14,18 н. (2 п/гр)\n"
                "3. Основы алгоритмизации и программирования (420) - 2-18 н. (1 п/гр)\n"
                "   Информационные технологии (411) - 2-18 н. (2 п/гр)\n"
                "4. История (512) - 2-18 н.",

            "Вторник": 
                "1. Элементы высшей математики (511) - 2-8,12-18 н.\n"
                "2. Математическое моделирование (511) - 2-8,12,14 н.\n"
                "   3D-моделирование (511) - 16 н.\n"
                "   Элементы высшей математики (511) - 18 н.\n"
                "3. Теория вероятностей (511) - 2-8,12-18 н.\n"
                "4. 1С: Предприятие (411) - 2-8,12-18 н. (1 п/гр)\n"
                "   Основы алгоритмизации и программирования (413) - 2-8,12-18 н. (2 п/гр)",

            "Среда": 
                "1. 3D-моделирование (420) - 2-16 н. (1 п/гр)\n"
                "   Архитектура аппаратных средств (411) - 2-12 н. (2 п/гр)\n"
                "   Операционные системы и среды (411) - 14-16 н. (2 п/гр)\n"
                "2. 3D-моделирование (420) - 2-16 н. (2 п/гр)\n"
                "   Архитектура аппаратных средств (411) - 2-12 н. (1 п/гр)\n"
                "   Операционные системы и среды (411) - 14-16 н. (1 п/гр)\n"
                "3. 1С: Предприятие (411) - 2-16 н. (2 п/гр)\n"
                "4. Иностранный язык (408/403) - 2-16 н.\n"
                "5. Информационные технологии (413) - 2-16 н. (1 п/гр)",

            "Четверг": 
                "2. Физическая культура (1 п/гр) - 2-16 н.\n"
                "3. История (512) - 2-16 н.\n"
                "4. Элементы высшей математики (511) - 2-16 н.\n"
                "5. Операционные системы и среды (411) - 2-16 н.",

            "Пятница": 
                "1. Теория вероятностей (511) - 2-16 н.\n"
                "2. Математическое моделирование (511) - 2-16 н.\n"
                "3. Информационные технологии (411) - 4,8 н. (2 п/гр)\n"
                "   Операционные системы и среды (411) - 12,16 н. (2 п/гр)\n"
                "   Информационные технологии (411) - 2,6,10 н. (1 п/гр)\n"
                "   Операционные системы и среды (411) - 14 н. (1 п/гр)\n"
                "4. Операционные системы и среды (411) - 2,6 н. (1 п/гр)\n"
                "   Операционные системы и среды (411) - 4 н. (2 п/гр)\n"
                "   Основы алгоритмизации и программирования (411) - 8,10 н. (2 п/гр)",

            "Суббота": "Выходной",
            "Воскресенье": "Выходной"
        }
    },
"ПСН-25": {
        "Нечетная": {
            "Понедельник": "1. Физическая культура 3-19 н.\n3. История (512) 3-19 н.\n4. Математика (511) 3-19 н.\n5. Основы безопасности и защиты Родины (201) 3-19 н.",
            "Вторник": "1. Физическая культура 1-19 н.\n3. Математика (511) 1-19 н.\n4. Иностранный язык (408/403) 1-19 н.\n5. Физика (201/212) 1 н.\n   Основы безопасности и защиты Родины (201) 3-19 н.",
            "Среда": "1. Введение в специальность (409) 1-19 н.\n2. Химия (201) 1 н.\n   Экология (201) 3 н.\n   Литература (520) 5-19 н.\n3. Физика (201) 1-13,19 н.\n   Основы безопасности и защиты Родины (201) 15-17 н.\n4. Математика (511) 1-19 н.",
            "Четверг": "1. Химия (201) 1-19 н.\n2. Информатика (411) 1-19 н.\n3. Литература (520) 3-15 н.\n   Русский язык (520) 17,19 н.\n4. Русский язык (520) 3-19 н.",
            "Пятница": "1. Физика (218) 1-13,19 н.\n   Русский язык (520) 15 н.\n2. Экология (201) 1-19 н.\n3. Иностранный язык (408/403) 1-19 н.\n4. История (512) 1-5 н.\n   Информатика (411) 7,11 н. (1 п/гр)\n   Информатика (411) 9 н. (2 п/гр)\n   Физика (212) 7 н. (2 п/гр)\n   Физика (212) 9 н. (1 п/гр)\n   Математика (511) 13-19 н.",
            "Суббота": "Выходной",
            "Воскресенье": "Выходной"
        },
        "Четная": {
            "Понедельник": "1. Разговор о важном (420)\n   Математика (511) 2-16 н.\n2. История (512) 2-16 н.\n   Физическая культура 18 н.\n3. Химия (201) 2-6 н.\n   Экология (201) 8-18 н.\n4. Информатика (411) 4,8,12,16 н. (1 п/гр)\n   Информатика (411) 2,6,10,14,18 н. (2 п/гр)\n   Химия (502) 8,12,16 н. (2 п/гр)\n   Химия (502) 6,10,14 н. (1 п/гр)",
            "Вторник": "2. Физическая культура 2-8,12-18 н.\n3. Химия (201) 2 н.\n   Русский язык (520) 4-8,12-18 н.\n4. Экология (201) 2 н.\n   Литература (520) 4-8,12-18 н.\n5. Математика (511) 2-8,12-18 н.",
            "Среда": "1. Введение в специальность (409) 2-16 н.\n2. Информатика (411) 2-16 н. (2 п/гр)\n   Физика (212) 2-14 н. (1 п/гр)\n3. Иностранный язык (408/403) 2-16 н.\n4. Информатика (411) 2-16 н. (1 п/гр)\n   Физика (212) 2-14 н. (2 п/гр)",
            "Четверг": "2. Химия (201) 2 н.\n   Литература (520) 4-16 н.\n3. Основы безопасности и защиты Родины (201) 2-16 н.\n4. История (512) 2-16 н.\n5. Математика (511) 2-16 н.",
            "Пятница": "1. Физика (218) 2-14 н.\n2. Основы безопасности и защиты Родины (201) 2-14 н.\n3. Физика (201) 2-12 н.",
            "Суббота": "Выходной",
            "Воскресенье": "Выходной"
        }
    },
           "ПСН-23": {
        "Нечетная": {
            "Понедельник": "1. Разговор о важном (413)\n2. Физическая культура (1 н.) \n   Поддержка и тестирование программных модулей (413) 3-17 н.\n3. Основы философии (512) 1-13,17 н. \n   Поддержка и тестирование программных модулей (413) 15 н.\n4. Технология разработки программного обеспечения (413) 1-17 н.\n5. Правовое обеспечение профессиональной деятельности (411) 1-17 н.",
            "Вторник": "1. Разработка программных модулей (411) 1-17 н.\n2. Компьютерные сети (410) 1-17 н.\n3. Разработка программных модулей (411) 1-17 н. (1 п/гр) \n   Поддержка и тестирование программных модулей (413) 1-17 н. (2 п/гр)\n4. Разработка программных модулей (411) 1-17 н. (2 п/гр) \n   Поддержка и тестирование программных модулей (413) 1-17 н. (1 п/гр)",
            "Среда": "1. Физическая культура 1-17 н. (1 п/гр)\n2. Разработка мобильных приложений (413) 1,3 н. \n   Поддержка и тестирование (413) 5,7 н. \n   Технология разработки ПО (413) 9-15 н. \n   Иностранный язык (408/403) 17 н.\n3. Технология разработки и защиты баз данных (413) 1-17 н.\n4. Иностранный язык (408/403) 1-17 н.",
            "Четверг": "1. Численные методы (411) 1-17 н.\n2. Дискретная математика (511) 1-17 н.\n3. Разработка мобильных приложений (411) 1-5 н. \n   Технология разработки и защиты БД (413) 7 н. \n   Технология разработки ПО (413) 9-17 н. (1 п/гр) \n   Разработка мобильных приложений (411) 7 н. \n   Компьютерные сети (411) 9-11 н. \n   Разработка программных модулей (411) 13-15 н. (2 п/гр)\n4. Разработка мобильных приложений (411) 1,3 н. \n   Поддержка и тестирование (413) 5 н. \n   Технология разработки и защиты БД (413) 7 н. \n   Технология разработки ПО (413) 9-17 н. (2 п/гр) \n   Разработка мобильных приложений (411) 7 н. \n   Компьютерные сети (411) 9,11 н. \n   Разработка программных модулей (411) 13,15 н. (1 п/гр)",
            "Пятница": "1. Дискретная математика (511) 1-17 н.\n2. Численные методы (511) 1-17 н.",
            "Суббота": "Выходной",
            "Воскресенье": "Выходной"
        },
        "Четная": {
            "Понедельник": "1. Классный час (511) \n   Основы философии (512) 2-18 н.\n2. Поддержка и тестирование программных модулей (413) 2-16 н. \n   Основы философии (512) 18 н.\n3. Технология разработки ПО (413) 2 н. \n   Технология разработки и защиты БД (413) 4-18 н.\n4. Разработка мобильных приложений (411) 2-18 н.",
            "Вторник": "1. Разработка мобильных приложений (411) 2-18 н. (1 п/гр) \n   Поддержка и тестирование (413) 2-14 н. \n   Технология разработки и защиты БД (413) 16,18 н. (2 п/гр)\n2. Разработка мобильных приложений (411) 2-18 н. (2 п/гр) \n   Поддержка и тестирование (413) 2-14 н. \n   Технология разработки и защиты БД (413) 16,18 н. (1 п/гр)\n3. Правовое обеспечение профессиональной деятельности (411) 2-18 н.\n4. Иностранный язык (408/403) 2-18 н.",
            "Среда": "1. Физическая культура 2-16 н. (1 п/гр)\n2. Технология разработки и защиты баз данных (413) 2-16 н.\n3. Технология разработки программного обеспечения (413) 2-16 н.\n4. Правовое обеспечение профессиональной деятельности (411) 2-16 н.",
            "Четверг": "1. Основы философии (512) 2-16 н.\n2. Дискретная математика (511) 2-16 н.\n3. Технология разработки и защиты баз данных (413) 2-16 н. (1 п/гр) \n   Компьютерные сети (411) 2-16 н. (2 п/гр)\n4. Технология разработки и защиты баз данных (413) 2-16 н. (2 п/гр) \n   Компьютерные сети (411) 2-16 н. (1 п/гр)",
            "Пятница": "1. Компьютерные сети (411) 2-14 н. \n   Разработка мобильных приложений (411) 16 н.\n2. Разработка программных модулей (411) 2-14 н. \n   Разработка мобильных приложений (411) 16 н.\n3. Численные методы (511) 2-16 н.",
            "Суббота": "Выходной",
            "Воскресенье": "Выходной"
        }
    },
        "СТН-25": {
        "Нечетная": {
            "Понедельник": "2. Информатика (411) 3-19 н.\n3. Математика (511) 3-19 н.\n4. Основы безопасности и защиты Родины (201) 3-19 н.\n5. История (512) 3-19 н.",
            "Вторник": "2. Информатика (411) 1 н. \n   Информатика (411) 3-19 н. (1 п/гр)\n   Физика (212) 3-13,19 н. (2 п/гр)\n3. Физика (201) 1-13,19 н.\n   Основы безопасности и защиты Родины (201) 15,17 н.\n4. Физика (201) 1 н.\n   Основы безопасности и защиты Родины (201) 3-19 н.\n5. Иностранный язык (408/403) 1-19 н.",
            "Среда": "2. Физическая культура 1-19 н.\n3. Экология (208) 1 н.\n   Химия (208) 3 н.\n   Литература (520) 5-19 н.\n4. Информатика (411) 1-19 н. (2 п/гр)\n   Физика (212) 1-13,19 н. (1 п/гр)\n5. Математика (511) 1-19 н.",
            "Четверг": "1. Русский язык (520) 3-19 н.\n2. Литература (520) 3-19 н.\n4. Химия (201) 1-15 н.\n   Экология (201) 17,19 н.\n5. Математика (511) 1-19 н.",
            "Пятница": "1. История (512) 1-19 н.\n2. Обществознание (512) 1-19 н.\n3. Физика (201) 1-11 н.\n   Математика (511) 13-19 н.\n4. Иностранный язык (408/403) 1-7,13-19 н.",
            "Суббота": "Выходной",
            "Воскресенье": "Выходной"
        },
        "Четная": {
            "Понедельник": "1. Информатика (411) 4,8,12,16 н. (2 п/гр) \n   Информатика (411) 2,6,10,14,18 н. (1 п/гр)\n   Химия (502) 8,12,16 н. (1 п/гр) \n   Химия (502) 6,10,14 н. (2 п/гр)\n2. Основы безопасности и защиты Родины (405) 2 н.\n   Русский язык (520) 4-18 н.\n3. Основы безопасности и защиты Родины (405) 2 н.\n   Литература (520) 4-18 н.\n4. История (512) 2-18 н.",
            "Вторник": "1. Физическая культура 2-18 н.\n3. Физика (218) 2-8,12-14,18 н.\n4. Физика (218) 2 н.\n   Химия (201) 4-8,12-18 н.\n5. Экология (201) 2-18 н.",
            "Среда": "1. Иностранный язык (408/403) 2-6 н.\n   Литература (520) 8-12 н.\n   Физическая культура 14-16 н.\n2. Математика (511) 2-16 н.\n3. Математика (511) 2-16 н.\n4. Иностранный язык (408/403) 2-16 н.",
            "Четверг": "1. Физическая культура 2-16 н.\n3. Математика (511) 2-16 н.\n4. Основы безопасности и защиты Родины (201) 2-16 н.\n5. Обществознание (512) 2-16 н.",
            "Пятница": "1. Основы безопасности и защиты Родины (201) 2-12 н.\n   Русский язык (520) 14,16 н.\n2. Физика (218) 2-14 н.\n   Экология (201) 16 н.\n3. Экология (201) 2-12 н.\n   Физика (212) 14 н. (2 п/гр)",
            "Суббота": "Выходной",
            "Воскресенье": "Выходной"
        }
    },
        "ТСН-24": {
        "Нечетная": {
            "Понедельник": "1. Разговор о важном (420)\n   История России (512) 1-19 н.\n2. Математика в профессиональной деятельности (511) 1-19 н.\n3. Процессы формообразования и инструменты (420) 1 н.\n   Процессы формообразования и инструменты (420) 3,7,11,15,19 н. (2 п/гр)\n   Процессы формообразования и инструменты (420) 5,9,13,17 н. (1 п/гр)\n   Материаловедение (316) 3,7,11,15,19 н. (1 п/гр)\n4. Процессы формообразования и инструменты (420) 1 н.\n   Инженерная графика (420) 3-19 н. (1 п/гр)\n   Материаловедение (316) 3,7,11,15,19 н. (2 п/гр)",
            "Вторник": "2. Физическая культура 1-19 н.\n3. Инженерная графика (420) 1-17 н.\n   Процессы формообразования и инструменты (420) 19 н. (1 п/гр)\n   Материаловедение (316) 19 н. (2 п/гр)\n4. Процессы формообразования и инструменты (420) 1-19 н.\n5. Материаловедение (316) 1-17 н.\n   Материаловедение (316) 19 н. (1 п/гр)",
            "Среда": "1. Электротехника (201) 1-19 н.\n2. Метрология, стандартизация и сертификация (409) 1-19 н.\n3. Процессы формообразования и инструменты (420) 1-19 н.\n4. Иностранный язык (408/403) 1-19 н.",
            "Четверг": "1. Техническая механика (218) 1-13,19 н.\n   Метрология, стандартизация и сертификация (409) 15,17 н.\n2. Материаловедение (316) 1-19 н.\n3. Безопасность жизнедеятельности (201) 1-19 н.\n4. Устройство ДВС (215) 1-19 н.",
            "Пятница": "1. Безопасность жизнедеятельности (201) 1-19 н.\n2. Основы бережливого производства (410) 1-19 н.\n3. История России (512) 1-9 н.\n   Инженерная графика (420) 11-19 н. (2 п/гр)\n   Устройство ДВС (215) 11-19 н. (1 п/гр)\n4. Математика в профессиональной деятельности (511) 1-9 н.\n   Инженерная графика (420) 11-15 н. (1 п/гр)\n   Устройство ДВС (215) 11-19 н. (2 п/гр)",
            "Суббота": "Выходной",
            "Воскресенье": "Выходной"
        },
        "Четная": {
            "Понедельник": "1. Техническая механика (218) 2-4 н.\n   Инженерная графика (420) 6-18 н. (2 п/гр)\n2. Техническая механика (218) 2-8 н.\n   Основы бережливого производства (410) 10-18 н.\n3. История России (512) 2-18 н.\n4. Математика в профессиональной деятельности (511) 2-18 н.",
            "Вторник": "1. Безопасность жизнедеятельности (201) 2 н.\n   Физическая культура 4-8,12-18 н.\n2. Инженерная графика (420) 2-8,12-18 н. (2 п/гр)\n   Электротехника (202) 2-8,12-18 н. (1 п/гр)\n3. Инженерная графика (420) 2-8,12-18 н. (1 п/гр)\n   Электротехника (202) 2-8,12-18 н. (2 п/гр)\n4. Устройство ДВС (215) 2-4 н.\n   Иностранный язык (408/403) 6,8,12-18 н.",
            "Среда": "1. Электротехника (201) 2-16 н.\n2. Метрология, стандартизация и сертификация (409) 2-16 н.\n3. Материаловедение (316) 2-16 н.\n4. Техническая механика (218) 2-8 н.\n   Устройство ДВС (215) 10-16 н.",
            "Четверг": "1. Математика в профессиональной деятельности (511) 2-16 н.\n2. История России (512) 2-16 н.\n3. Материаловедение (316) 2-8 н.\n   Безопасность жизнедеятельности (201) 10-16 н.\n4. Техническая механика (218) 2-14 н.",
            "Пятница": "1. Безопасность жизнедеятельности (201) 2-16 н.\n2. Процессы формообразования и инструменты (420) 2-16 н.\n3. Устройство ДВС (215) 2-8 н.",
            "Суббота": "Выходной",
            "Воскресенье": "Выходной"
        }
    },
     "ТСН-23": {
        "Нечетная": {
            "Понедельник": "2. Физическая культура 1-13 н.\n3. Технология машиностроения (410) 1-13 н.\n4. Разработка технологических процессов (208) 1-13 н.\n5. Технологическая оснастка (208) 1-13 н.",
            "Вторник": "1. Компьютерная графика (420) 1 н.\n   Техническая механика (420) 3-7 н.\n   Компьютерная графика (420) 9,13 н. (1 п/гр)\n   Компьютерная графика (420) 11 н. (2 п/гр)\n2. Технологическое оборудование (420) 1-13 н.\n3. Разработка технологических процессов (208) 1-13 н.\n4. Разработка технологических процессов (208) 1-13 н.",
            "Среда": "1. Компьютерная графика (420) 1-13 н. (2 п/гр)\n2. Компьютерная графика (420) 1-13 н. (1 п/гр)\n3. Иностранный язык (408/403) 1-13 н.\n4. Компьютерная графика (420) 1-9 н.\n   Технологическое оборудование (420) 11 н.\n   Компьютерная графика (420) 13 н. (2 п/гр)\n5. Разработка технологических процессов (208) 1-13 н.",
            "Четверг": "1. Разработка технологических процессов (208) 1-13 н.\n2. Разработка технологических процессов (208) 1-13 н.\n3. Техническая механика (420) 1-13 н.\n4. Технологическое оборудование (420) 1-13 н.",
            "Пятница": "1. Разработка технологических процессов (208) 1-13 н.\n2. Разработка технологических процессов (208) 1-13 н.\n3. Технологическая оснастка (208) 1-13 н.\n4. Технология машиностроения (410) 1-7 н.\n   Иностранный язык (408/403) 9-11 н.",
            "Суббота": "Выходной",
            "Воскресенье": "Выходной"
        },
        "Четная": {
            "Понедельник": "2. Физическая культура 2-14 н.\n3. Технология машиностроения (410) 2-14 н.\n4. Разработка технологических процессов (208) 2-14 н.\n5. Технологическая оснастка (208) 2-14 н.",
            "Вторник": "1. Физическая культура 2-6 н.\n   Компьютерная графика (420) 8,12-14 н. (1 п/гр)\n2. Компьютерная графика (420) 8,12-14 н. (2 п/гр)\n3. Иностранный язык (408/403) 2-8,12,14 н.\n4. Разработка технологических процессов (208) 2-8,12,14 н.",
            "Среда": "1. Разработка технологических процессов (208) 2-14 н.\n2. Технологическая оснастка (208) 2-14 н.\n3. Техническая механика (420) 2-14 н.\n4. Технологическое оборудование (420) 2-14 н.",
            "Четверг": "1. Разработка технологических процессов (208) 2-14 н.\n2. Технологическая оснастка (208) 2-14 н.\n3. Техническая механика (420) 2-14 н.\n4. Технологическое оборудование (420) 2-14 н.",
            "Пятница": "1. Компьютерная графика (420) 2-14 н. (1 п/гр)\n2. Разработка технологических процессов (208) 2-14 н.\n3. Компьютерная графика (420) 2-14 н. (2 п/гр)",
            "Суббота": "Выходной",
            "Воскресенье": "Выходной"
        }
    }
}
 
# Заполняем расписание для остальных групп
for group in GROUPS:
    if group not in SCHEDULE:
        SCHEDULE[group] = SCHEDULE["ПСН-24"]

# Функции для работы с VIP режимом
def set_vip_mode(user_id, enabled):
    """Установить режим VIP для пользователя"""
    USER_VIP_MODE[user_id] = enabled
    return True

def get_vip_mode(user_id):
    """Получить состояние VIP режима для пользователя"""
    return USER_VIP_MODE.get(user_id, False)

def has_vip_status(user_id):
    """Проверяет, есть ли у пользователя VIP статус (независимо от режима)"""
    try:
        user = get_user(user_id)
        if user and len(user) >= 8:
            return bool(user[7])  # user[7] - is_vip
        return False
    except Exception as e:
        logger.error(f"Ошибка при проверке VIP статуса для {user_id}: {e}")
        return False

# Инициализация базы данных
def init_db():
    conn = sqlite3.connect('university_bot.db', check_same_thread=False)
    cursor = conn.cursor()
    
    # Создаем таблицу users с правильными колонками
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            first_name TEXT,
            group_name TEXT,
            last_active DATETIME DEFAULT CURRENT_TIMESTAMP,
            is_banned BOOLEAN DEFAULT FALSE,
            is_admin BOOLEAN DEFAULT FALSE,
            is_vip BOOLEAN DEFAULT FALSE,
            is_main_admin BOOLEAN DEFAULT FALSE
        )
    ''')
    
    # Создаем таблицу chats с правильными колонками
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS chats (
            chat_id INTEGER PRIMARY KEY,
            chat_title TEXT,
            added_date DATETIME DEFAULT CURRENT_TIMESTAMP,
            is_active BOOLEAN DEFAULT TRUE,
            chat_group TEXT,
            is_vip BOOLEAN DEFAULT FALSE
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
    
    # Исправленная таблица admin_logs
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS admin_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            admin_username TEXT,
            admin_user_id INTEGER,
            action TEXT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Проверяем и добавляем отсутствующие колонки в таблицу users
    cursor.execute("PRAGMA table_info(users)")
    columns = [column[1] for column in cursor.fetchall()]
    
    if 'is_vip' not in columns:
        cursor.execute('ALTER TABLE users ADD COLUMN is_vip BOOLEAN DEFAULT FALSE')
        logger.info("Добавлена колонка is_vip в таблицу users")
    
    if 'is_main_admin' not in columns:
        cursor.execute('ALTER TABLE users ADD COLUMN is_main_admin BOOLEAN DEFAULT FALSE')
        logger.info("Добавлена колонка is_main_admin в таблицу users")
    
    # Проверяем и добавляем отсутствующие колонки в таблицу chats
    cursor.execute("PRAGMA table_info(chats)")
    columns = [column[1] for column in cursor.fetchall()]
    
    if 'chat_group' not in columns:
        cursor.execute('ALTER TABLE chats ADD COLUMN chat_group TEXT')
        logger.info("Добавлена колонка chat_group в таблицу chats")
    
    if 'is_vip' not in columns:
        cursor.execute('ALTER TABLE chats ADD COLUMN is_vip BOOLEAN DEFAULT FALSE')
        logger.info("Добавлена колонка is_vip в таблицу chats")
    
    # Проверяем и добавляем отсутствующие колонки в таблицу admin_logs
    cursor.execute("PRAGMA table_info(admin_logs)")
    columns = [column[1] for column in cursor.fetchall()]
    
    if 'admin_username' not in columns:
        cursor.execute('ALTER TABLE admin_logs ADD COLUMN admin_username TEXT')
        logger.info("Добавлена колонка admin_username в таблицу admin_logs")
    
    if 'admin_user_id' not in columns:
        cursor.execute('ALTER TABLE admin_logs ADD COLUMN admin_user_id INTEGER')
        logger.info("Добавлена колонка admin_user_id в таблицу admin_logs")
    
    if 'action' not in columns:
        cursor.execute('ALTER TABLE admin_logs ADD COLUMN action TEXT')
        logger.info("Добавлена колонка action в таблицу admin_logs")
    
    # Добавляем главного администратора в базу если его нет
    cursor.execute('SELECT * FROM users WHERE user_id = ?', (MAIN_ADMIN_ID,))
    if not cursor.fetchone():
        cursor.execute('''
            INSERT INTO users (user_id, username, first_name, group_name, is_admin, is_vip, is_main_admin)
            VALUES (?, ?, ?, ?, TRUE, TRUE, TRUE)
        ''', (MAIN_ADMIN_ID, "bokalpivka", "Admin", "ПСН-24"))
        logger.info("Главный администратор добавлен в базу")
    
    conn.commit()
    conn.close()
    logger.info("База данных инициализирована успешно")

# Получение всех чатов с информацией о количестве участников (ИСПРАВЛЕННАЯ ВЕРСИЯ)
def get_all_chats_with_info():
    try:
        conn = sqlite3.connect('university_bot.db', check_same_thread=False)
        cursor = conn.cursor()
        cursor.execute('''
            SELECT c.chat_id, c.chat_title, c.chat_group, c.is_vip, 
                   COUNT(cu.user_id) as user_count
            FROM chats c
            LEFT JOIN chat_users cu ON c.chat_id = cu.chat_id
            WHERE c.is_active = TRUE
            GROUP BY c.chat_id, c.chat_title, c.chat_group, c.is_vip
            ORDER BY c.chat_title
        ''')
        chats = cursor.fetchall()
        conn.close()
        return chats
    except Exception as e:
        logger.error(f"Ошибка при получении информации о чатах: {e}")
        return []

# Логирование действий администратора
def log_admin_action(admin_username, admin_user_id, action):
    try:
        conn = sqlite3.connect('university_bot.db', check_same_thread=False)
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO admin_logs (admin_username, admin_user_id, action)
            VALUES (?, ?, ?)
        ''', (admin_username, admin_user_id, action))
        conn.commit()
        conn.close()
        logger.info(f"Admin action logged: {admin_username} ({admin_user_id}) - {action}")
    except Exception as e:
        logger.error(f"Ошибка при логировании действия администратора: {e}")

# Сохранение пользователя
def save_user(user_id, username, first_name, group_name):
    try:
        conn = sqlite3.connect('university_bot.db', check_same_thread=False)
        cursor = conn.cursor()
        cursor.execute('''
            INSERT OR REPLACE INTO users (user_id, username, first_name, group_name, last_active)
            VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
        ''', (user_id, username, first_name, group_name))
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        logger.error(f"Ошибка при сохранении пользователя {user_id}: {e}")
        return False

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

# Получение VIP пользователей по группе
def get_vip_users_by_group(group_name):
    try:
        conn = sqlite3.connect('university_bot.db', check_same_thread=False)
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM users WHERE group_name = ? AND is_banned = FALSE AND is_vip = TRUE', (group_name,))
        users = cursor.fetchall()
        conn.close()
        return users
    except Exception as e:
        logger.error(f"Ошибка при получении VIP пользователей группы {group_name}: {e}")
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

# Получение всех администраторов
def get_all_admins():
    try:
        conn = sqlite3.connect('university_bot.db', check_same_thread=False)
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM users WHERE is_admin = TRUE OR is_main_admin = TRUE OR user_id IN ({})'.format(','.join('?' for _ in ADMIN_IDS)), ADMIN_IDS)
        admins = cursor.fetchall()
        conn.close()
        return admins
    except Exception as e:
        logger.error(f"Ошибка при получении администраторов: {e}")
        return []

# Получение всех главных администраторов
def get_main_admins():
    try:
        conn = sqlite3.connect('university_bot.db', check_same_thread=False)
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM users WHERE is_main_admin = TRUE OR user_id = ?', (MAIN_ADMIN_ID,))
        admins = cursor.fetchall()
        conn.close()
        return admins
    except Exception as e:
        logger.error(f"Ошибка при получении главных администраторов: {e}")
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

# Получение VIP чатов по группе
def get_vip_chats_by_group(group_name):
    try:
        conn = sqlite3.connect('university_bot.db', check_same_thread=False)
        cursor = conn.cursor()
        cursor.execute('''
            SELECT DISTINCT c.chat_id, c.chat_title 
            FROM chats c
            JOIN chat_users cu ON c.chat_id = cu.chat_id
            WHERE cu.group_name = ? AND c.is_active = TRUE AND c.is_vip = TRUE
        ''', (group_name,))
        chats = cursor.fetchall()
        conn.close()
        return chats
    except Exception as e:
        logger.error(f"Ошибка при получении VIP чатов группы {group_name}: {e}")
        return []

# Получение чатов по группе
def get_chats_by_group(group_name):
    try:
        conn = sqlite3.connect('university_bot.db', check_same_thread=False)
        cursor = conn.cursor()
        cursor.execute('''
            SELECT DISTINCT c.chat_id, c.chat_title 
            FROM chats c
            JOIN chat_users cu ON c.chat_id = cu.chat_id
            WHERE cu.group_name = ? AND c.is_active = TRUE
        ''', (group_name,))
        chats = cursor.fetchall()
        conn.close()
        return chats
    except Exception as e:
        logger.error(f"Ошибка при получении чатов группы {group_name}: {e}")
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
        logger.info(f"Чат добавлен: {chat_title} (ID: {chat_id})")
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
        logger.info(f"Для чата {chat_id} установлена группа: {group_name}")
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
        logger.info(f"Пользователь {user_id} добавлен в чат {chat_id} с группой {group_name}")
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

# Получение основной группы чата (по большинству пользователей)
def get_main_chat_group(chat_id):
    try:
        conn = sqlite3.connect('university_bot.db', check_same_thread=False)
        cursor = conn.cursor()
        cursor.execute('''
            SELECT group_name, COUNT(*) as count 
            FROM chat_users 
            WHERE chat_id = ? 
            GROUP BY group_name 
            ORDER BY count DESC 
            LIMIT 1
        ''', (chat_id,))
        result = cursor.fetchone()
        conn.close()
        return result[0] if result else None
    except Exception as e:
        logger.error(f"Ошибка при получении основной группы чата {chat_id}: {e}")
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
        logger.info(f"Пользователь {user_id} забанен")
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
        logger.info(f"Пользователь {user_id} разбанен")
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
        logger.info(f"Пользователь {user_id} стал администратором")
        return True
    except Exception as e:
        logger.error(f"Ошибка при выдаче прав админа пользователю {user_id}: {e}")
        return False

# Убрать права администратора
def remove_admin(user_id):
    try:
        # Нельзя убрать права у главного администратора
        if user_id == MAIN_ADMIN_ID or is_main_admin(user_id):
            return False
            
        conn = sqlite3.connect('university_bot.db', check_same_thread=False)
        cursor = conn.cursor()
        cursor.execute('UPDATE users SET is_admin = FALSE WHERE user_id = ?', (user_id,))
        conn.commit()
        conn.close()
        logger.info(f"Пользователь {user_id} лишен прав администратора")
        return True
    except Exception as e:
        logger.error(f"Ошибка при снятии прав админа у пользователя {user_id}: {e}")
        return False

# Сделать главным администратором
def make_main_admin(user_id):
    try:
        conn = sqlite3.connect('university_bot.db', check_same_thread=False)
        cursor = conn.cursor()
        cursor.execute('UPDATE users SET is_main_admin = TRUE, is_admin = TRUE WHERE user_id = ?', (user_id,))
        conn.commit()
        conn.close()
        logger.info(f"Пользователь {user_id} стал главным администратором")
        return True
    except Exception as e:
        logger.error(f"Ошибка при выдаче прав главного админа пользователю {user_id}: {e}")
        return False

# Убрать права главного администратора
def remove_main_admin(user_id):
    try:
        # Нельзя убрать права у основного главного администратора
        if user_id == MAIN_ADMIN_ID:
            return False
            
        conn = sqlite3.connect('university_bot.db', check_same_thread=False)
        cursor = conn.cursor()
        cursor.execute('UPDATE users SET is_main_admin = FALSE WHERE user_id = ?', (user_id,))
        conn.commit()
        conn.close()
        logger.info(f"Пользователь {user_id} лишен прав главного администратора")
        return True
    except Exception as e:
        logger.error(f"Ошибка при снятии прав главного админа у пользователя {user_id}: {e}")
        return False

# Выдать VIP статус пользователю
def give_vip(user_id):
    try:
        conn = sqlite3.connect('university_bot.db', check_same_thread=False)
        cursor = conn.cursor()
        cursor.execute('UPDATE users SET is_vip = TRUE WHERE user_id = ?', (user_id,))
        conn.commit()
        conn.close()
        logger.info(f"Пользователь {user_id} получил VIP статус")
        return True
    except Exception as e:
        logger.error(f"Ошибка при выдаче VIP статуса пользователю {user_id}: {e}")
        return False

# Забрать VIP статус у пользователя
def take_vip(user_id):
    try:
        conn = sqlite3.connect('university_bot.db', check_same_thread=False)
        cursor = conn.cursor()
        cursor.execute('UPDATE users SET is_vip = FALSE WHERE user_id = ?', (user_id,))
        conn.commit()
        conn.close()
        logger.info(f"Пользователь {user_id} лишен VIP статуса")
        return True
    except Exception as e:
        logger.error(f"Ошибка при снятии VIP статуса у пользователя {user_id}: {e}")
        return False

# Выдать VIP статус чату
def give_chat_vip(chat_id):
    try:
        conn = sqlite3.connect('university_bot.db', check_same_thread=False)
        cursor = conn.cursor()
        cursor.execute('UPDATE chats SET is_vip = TRUE WHERE chat_id = ?', (chat_id,))
        conn.commit()
        conn.close()
        logger.info(f"Чат {chat_id} получил VIP статус")
        return True
    except Exception as e:
        logger.error(f"Ошибка при выдаче VIP статуса чату {chat_id}: {e}")
        return False

# Забрать VIP статус у чата
def take_chat_vip(chat_id):
    try:
        conn = sqlite3.connect('university_bot.db', check_same_thread=False)
        cursor = conn.cursor()
        cursor.execute('UPDATE chats SET is_vip = FALSE WHERE chat_id = ?', (chat_id,))
        conn.commit()
        conn.close()
        logger.info(f"Чат {chat_id} лишен VIP статуса")
        return True
    except Exception as e:
        logger.error(f"Ошибка при снятии VIP статуса у чата {chat_id}: {e}")
        return False

# Проверка VIP статуса пользователя (с учетом режима)
def is_vip(user_id):
    """Проверяет, есть ли у пользователя VIP статус И включен ли VIP режим"""
    try:
        return has_vip_status(user_id) and get_vip_mode(user_id)
    except Exception as e:
        logger.error(f"Ошибка при проверке VIP статуса для {user_id}: {e}")
        return False

# Проверка главного админа
def is_main_admin(user_id):
    try:
        if user_id == MAIN_ADMIN_ID:
            return True
        
        user = get_user(user_id)
        if user and len(user) >= 9:  # Проверяем что есть достаточно колонок
            return bool(user[8])  # user[8] - is_main_admin
        return False
    except Exception as e:
        logger.error(f"Ошибка при проверке прав главного админа для {user_id}: {e}")
        return False

# Проверка VIP статуса чата
def is_chat_vip(chat_id):
    try:
        conn = sqlite3.connect('university_bot.db', check_same_thread=False)
        cursor = conn.cursor()
        cursor.execute('SELECT is_vip FROM chats WHERE chat_id = ?', (chat_id,))
        result = cursor.fetchone()
        conn.close()
        return result[0] if result else False
    except Exception as e:
        logger.error(f"Ошибка при проверке VIP статуса чата {chat_id}: {e}")
        return False

# Получение логов администраторов
def get_admin_logs(limit=50):
    try:
        conn = sqlite3.connect('university_bot.db', check_same_thread=False)
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM admin_logs ORDER BY timestamp DESC LIMIT ?', (limit,))
        logs = cursor.fetchall()
        conn.close()
        return logs
    except Exception as e:
        logger.error(f"Ошибка при получении логов администраторов: {e}")
        return []

# Проверка админа (безопасная версия)
def is_admin(user_id):
    try:
        if user_id in ADMIN_IDS or is_main_admin(user_id):
            return True
        
        user = get_user(user_id)
        if user and len(user) >= 7:  # Проверяем что есть достаточно колонок
            return bool(user[6])  # user[6] - is_admin
        return False
    except Exception as e:
        logger.error(f"Ошибка при проверке прав админа для {user_id}: {e}")
        return False

# Проверка бана (безопасная версия)
def is_banned(user_id):
    try:
        user = get_user(user_id)
        if user and len(user) >= 6:  # Проверяем что есть достаточно колонок
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

# Функция для парсинга расписания и фильтрации пар по текущей неделе (ИСПРАВЛЕННАЯ ВЕРСИЯ)
def parse_vip_schedule(schedule_text, current_week):
    if not schedule_text or not schedule_text.strip():
        return "На этот день пар нет! 🎉"
    
    lines = schedule_text.split('\n')
    filtered_lines = []
    
    for line in lines:
        if not line.strip():
            filtered_lines.append(line)
            continue
            
        # Сохраняем номер пары
        line_with_number = line
        
        # Если строка содержит информацию о неделях
        if 'н.' in line:
            # Разделяем на части до и после " - "
            if ' - ' in line:
                subject_part = line.split(' - ')[0]
                weeks_part = line.split(' - ')[1]
                
                # Проверяем все диапазоны недель в этой строке
                week_ranges = weeks_part.split(', ')
                current_week_present = False
                
                for week_range in week_ranges:
                    if 'н' in week_range:
                        week_str = week_range.split(' н')[0].strip()
                        if '-' in week_str:
                            # Диапазон недель (например, "1-13")
                            try:
                                start_week, end_week = map(int, week_str.split('-'))
                                if start_week <= current_week <= end_week:
                                    current_week_present = True
                                    break
                            except ValueError:
                                # Если не удалось распарсить диапазон, оставляем строку
                                current_week_present = True
                                break
                        else:
                            # Одиночные недели (например, "1,3,5")
                            try:
                                weeks = [int(w.strip()) for w in week_str.split(',')]
                                if current_week in weeks:
                                    current_week_present = True
                                    break
                            except ValueError:
                                # Если не удалось распарсить недели, оставляем строку
                                current_week_present = True
                                break
                
                if current_week_present:
                    filtered_lines.append(line_with_number)
            else:
                # Если нет разделителя " - ", но есть "н.", оставляем строку
                filtered_lines.append(line_with_number)
        else:
            # Если строка не содержит информации о неделях, оставляем её
            filtered_lines.append(line_with_number)
    
    result = '\n'.join(filtered_lines)
    return result if result.strip() else "На этот день пар нет! 🎉"

# Получение VIP расписания
def get_vip_schedule(group_name, weekday, week_type, current_week):
    if group_name in SCHEDULE and week_type in SCHEDULE[group_name] and weekday in SCHEDULE[group_name][week_type]:
        schedule_text = SCHEDULE[group_name][week_type][weekday]
        vip_schedule = parse_vip_schedule(schedule_text, current_week)
        return vip_schedule
    return "На этот день пар нет! 🎉"

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
        [InlineKeyboardButton("Расписание", callback_data="schedule")],
        [InlineKeyboardButton("🕒 Расписание звонков", callback_data="bell_schedule")]
    ]
    
    # Добавляем кнопку VIP статуса
    if has_vip_status(user.id):
        if get_vip_mode(user.id):
            keyboard.append([InlineKeyboardButton("⭐ VIP: ВКЛ", callback_data="toggle_vip_off")])
        else:
            keyboard.append([InlineKeyboardButton("⭐ VIP: ВЫКЛ", callback_data="toggle_vip_on")])
    else:
        keyboard.append([InlineKeyboardButton("⭐ VIP: НЕТ ДОСТУПА", callback_data="vip_info")])
    
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
            "💬 Для личного использования напишите мне в личные сообщения.\n\n"
            "⚠️ Я могу работать только в личных сообщениях. "
            "Напишите мне в ЛС для полного доступа к функциям бота."
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
    
    # Показываем выбор группы (теперь можно менять группу)
    keyboard = []
    for group in GROUPS:
        keyboard.append([InlineKeyboardButton(group, callback_data=f"chat_group_{group}")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    # Проверяем, выбрал ли пользователь уже группу в этом чате
    current_group = get_chat_user_group(chat_id, user.id)
    
    if current_group:
        await update.message.reply_text(
            f"📚 Вы уже выбрали группу {current_group} в этом чате.\n"
            f"Выберите новую группу или оставьте текущую:",
            reply_markup=reply_markup
        )
    else:
        await update.message.reply_text(
            "📚 Выберите вашу группу для получения расписания в этом чате:",
            reply_markup=reply_markup
        )

# Команда /givevip для выдачи VIP статуса беседе
async def givevip_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type not in ['group', 'supergroup']:
        await update.message.reply_text("❌ Эта команда работает только в групповых чатах.")
        return
    
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("❌ У вас нет прав для использования этой команды.")
        return
    
    chat_id = update.effective_chat.id
    if give_chat_vip(chat_id):
        # Логируем действие
        log_admin_action(
            update.effective_user.username,
            update.effective_user.id,
            f"Выдал VIP статус беседе {update.effective_chat.title} (ID: {chat_id})"
        )
        await update.message.reply_text("✅ Беседе выдан VIP статус! Теперь здесь будет приходить улучшенное расписание.")
    else:
        await update.message.reply_text("❌ Ошибка при выдаче VIP статуса.")

# Команда /takevip для снятия VIP статуса с беседы
async def takevip_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type not in ['group', 'supergroup']:
        await update.message.reply_text("❌ Эта команда работает только в групповых чатах.")
        return
    
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("❌ У вас нет прав для использования этой команды.")
        return
    
    chat_id = update.effective_chat.id
    if take_chat_vip(chat_id):
        # Логируем действие
        log_admin_action(
            update.effective_user.username,
            update.effective_user.id,
            f"Снял VIP статус с беседы {update.effective_chat.title} (ID: {chat_id})"
        )
        await update.message.reply_text("✅ VIP статус снят с беседы.")
    else:
        await update.message.reply_text("❌ Ошибка при снятии VIP статуса.")

# Команда /zakladka
async def zakladka_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("📍 Координаты: 57.857975, 39.518506")

# Команда /gangbang
async def gangbang_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Ганг Банг это известная футбольная команда, которая была создана 27 октября 2025 года. "
        "Их девиз был: скорость, напор, семь голов – один удар! Мы не идем в обход, мы идем напролом. "
        "Дриблинг, пас, гол – вот наш ритм. Готовы к буму? Но команда распалась 30 октября 2025 года."
    )

# Обработчик кнопок
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user = query.from_user
    
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
        elif query.data == "bell_schedule":
            await show_bell_schedule(query)
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
        elif query.data == "admin_remove_admin":
            await start_remove_admin(query, context)
        elif query.data == "admin_make_main_admin":
            await start_make_main_admin(query, context)
        elif query.data == "admin_remove_main_admin":
            await start_remove_main_admin(query, context)
        elif query.data == "admin_list_admins":
            await show_admin_list(query)
        elif query.data == "admin_give_vip":
            await start_give_vip(query, context)
        elif query.data == "admin_take_vip":
            await start_take_vip(query, context)
        elif query.data == "admin_logs":
            await show_admin_logs(query)
        elif query.data == "admin_chats":
            await show_admin_chats(query)
        elif query.data == "admin_change_time":
            await start_change_broadcast_time(query, context)
        elif query.data == "admin_back":
            await main_menu(update, context)
        elif query.data == "confirm_broadcast":
            await confirm_broadcast(update, context)
        elif query.data == "toggle_vip_on":
            await toggle_vip_on(query, context)
        elif query.data == "toggle_vip_off":
            await toggle_vip_off(query, context)
        elif query.data == "vip_info":
            await show_vip_info(query)
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

# Включение VIP режима
async def toggle_vip_on(query, context):
    user = query.from_user
    if has_vip_status(user.id):
        set_vip_mode(user.id, True)
        await query.edit_message_text(
            "⭐ VIP режим активирован! Теперь вы будете получать улучшенное расписание.\n\n"
            "VIP расписание показывает только те пары, которые идут на текущей неделе.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("В главное меню", callback_data="main_menu")]])
        )
    else:
        await query.edit_message_text(
            "❌ У вас нет VIP статуса.\n\n"
            "Для покупки VIP статуса обратитесь к администратору - @bokalpivka",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("В главное меню", callback_data="main_menu")]])
        )

# Выключение VIP режима
async def toggle_vip_off(query, context):
    user = query.from_user
    set_vip_mode(user.id, False)
    await query.edit_message_text(
        "⭐ VIP режим деактивирован. Вы снова будете получать обычное расписание.",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("В главное меню", callback_data="main_menu")]])
    )

# Информация о VIP статусе
async def show_vip_info(query):
    await query.edit_message_text(
        "⭐ VIP СТАТУС\n\n"
        "VIP статус дает вам доступ к улучшенному расписанию:\n"
        "• Показывает только актуальные пары на текущей неделе\n"
        "• Фильтрует расписание по номерам недель\n"
        "• Убирает лишнюю информацию\n\n"
        "Для покупки VIP статуса обратитесь к администратору - @bokalpivka",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("В главное меню", callback_data="main_menu")]])
    )

# Показать доступные беседы (ИСПРАВЛЕННАЯ ВЕРСИЯ)
async def show_admin_chats(query):
    if not is_main_admin(query.from_user.id):
        await query.edit_message_text("❌ Эта функция доступна только главному администратору!")
        return
    
    chats = get_all_chats_with_info()
    
    if not chats:
        await query.edit_message_text(
            "📊 Нет активных бесед.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Назад", callback_data="admin_panel")]])
        )
        return
    
    chats_text = "📊 Доступные беседы:\n\n"
    
    for i, chat in enumerate(chats, 1):
        chat_id, chat_title, chat_group, is_vip, user_count = chat
        
        # Получаем основную группу беседы
        main_group = get_main_chat_group(chat_id)
        group_info = main_group if main_group else "Не определена"
        
        vip_status = "⭐ VIP" if is_vip else "Обычная"
        
        chats_text += f"{i}. {chat_title}\n"
        chats_text += f"   👥 Участников: {user_count}\n"
        chats_text += f"   📚 Основная группа: {group_info}\n"
        chats_text += f"   🏷️ Статус: {vip_status}\n\n"
    
    await query.edit_message_text(
        chats_text,
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Назад", callback_data="admin_panel")]])
    )

# Показать расписание звонков
async def show_bell_schedule(query):
    bell_text = "🕒 Расписание звонков:\n\n"
    
    for day, schedule in BELL_SCHEDULE.items():
        bell_text += f"<b>{day}:</b>\n"
        for lesson in schedule:
            bell_text += f"  {lesson}\n"
        bell_text += "\n"
    
    await query.edit_message_text(
        bell_text,
        parse_mode='HTML',
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Назад", callback_data="main_menu")]])
    )

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
        "• Расписание звонков\n"
        "• Ежедневная рассылка расписания\n"
        "• Выбор и смена группы\n"
        "• Информация о пользователе\n"
        "• Определение четности недели\n"
        "• VIP расписание (только актуальные пары)\n\n"
        "Бот разработан для удобного доступа к расписанию занятий.\n\n"
        "👨‍💻 Владелец/разработчик - @bokalpivka"
    )
    await query.edit_message_text(
        info_text,
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Назад", callback_data="main_menu")]])
    )

# Показать информацию о пользователе
async def show_user_info(query, user):
    user_data = get_user(user.id)
    if user_data:
        # Безопасное извлечение данных
        group_name = user_data[3] if len(user_data) > 3 else "Не выбрана"
        admin_status = "✅ Да" if is_admin(user.id) else "❌ Нет"
        main_admin_status = "👑 Главный" if is_main_admin(user.id) else "✅ Обычный" if is_admin(user.id) else "❌ Нет"
        ban_status = "❌ Да" if is_banned(user.id) else "✅ Нет"
        vip_status = "✅ Да" if has_vip_status(user.id) else "❌ Нет"
        vip_mode = "✅ ВКЛ" if get_vip_mode(user.id) else "❌ ВЫКЛ"
        
        info_text = (
            f"👤 Ваш профиль:\n\n"
            f"Ваш ник: @{user.username if user.username else 'Не указан'}\n"
            f"Имя: {user.first_name}\n"
            f"Ваша группа: {group_name}\n"
            f"Администратор: {admin_status}\n"
            f"Тип админа: {main_admin_status}\n"
            f"Заблокирован: {ban_status}\n"
            f"VIP статус: {vip_status}\n"
            f"VIP режим: {vip_mode}"
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
    
    # Проверяем VIP статус
    if is_vip(user.id):
        # Показываем VIP расписание
        vip_schedule = get_vip_schedule(group_name, today, week_type, week_number)
        message = f"⭐ VIP РАСПИСАНИЕ на сегодня ({today}) для группы {group_name}:\n\n{vip_schedule}\n\n({week_type} неделя, неделя №{week_number})"
    else:
        # Обычное расписание
        if group_name in SCHEDULE and week_type in SCHEDULE[group_name] and today in SCHEDULE[group_name][week_type]:
            schedule_text = SCHEDULE[group_name][week_type][today]
            message = f"📅 Расписание на сегодня ({today}) для группы {group_name}:\n\n{schedule_text}\n\n({week_type} неделя, неделя №{week_number})"
        else:
            message = f"На сегодня ({today}) расписание для группы {group_name} не найдено."
    
    await query.edit_message_text(
        message,
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Назад", callback_data="main_menu")]])
    )

# Админ-панель (ОБНОВЛЕННАЯ ВЕРСИЯ)
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
    
    # Только главный админ может назначать админов, VIP и просматривать логи
    if is_main_admin(user.id):
        keyboard.append([InlineKeyboardButton("👑 Выдать права админа", callback_data="admin_make_admin")])
        keyboard.append([InlineKeyboardButton("👑 Забрать права админа", callback_data="admin_remove_admin")])
        keyboard.append([InlineKeyboardButton("👑 Выдать гл. админа", callback_data="admin_make_main_admin")])
        keyboard.append([InlineKeyboardButton("👑 Снять гл. админа", callback_data="admin_remove_main_admin")])
        keyboard.append([InlineKeyboardButton("⭐ Выдать VIP", callback_data="admin_give_vip")])
        keyboard.append([InlineKeyboardButton("⭐ Снять VIP", callback_data="admin_take_vip")])
        keyboard.append([InlineKeyboardButton("📋 Список администраторов", callback_data="admin_list_admins")])
        keyboard.append([InlineKeyboardButton("📝 Логи администратора", callback_data="admin_logs")])
        keyboard.append([InlineKeyboardButton("💬 Доступные беседы", callback_data="admin_chats")])
        keyboard.append([InlineKeyboardButton("⏰ Изменить время рассылки", callback_data="admin_change_time")])
    
    keyboard.append([InlineKeyboardButton("Назад", callback_data="main_menu")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text("👑 Админ-панель:", reply_markup=reply_markup)

# Начать изменение времени рассылки
async def start_change_broadcast_time(query, context):
    if not is_main_admin(query.from_user.id):
        await query.edit_message_text("❌ Эта функция доступна только главному администратору!")
        return
    
    context.user_data['awaiting_broadcast_time'] = True
    await query.edit_message_text(
        f"⏰ Текущее время рассылки: {BROADCAST_TIME}\n\n"
        "Введите новое время в формате ЧЧ:ММ (например, 18:30):",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Отмена", callback_data="admin_panel")]])
    )

# Статистика
async def show_admin_stats(query):
    if not is_admin(query.from_user.id):
        await query.edit_message_text("Доступ запрещен!")
        return
    
    users = get_all_users()
    total_users = len(users)
    banned_users = len([u for u in users if len(u) > 5 and u[5]])
    admin_users = len([u for u in users if (len(u) > 6 and u[6]) or u[0] in ADMIN_IDS])
    main_admin_users = len([u for u in users if (len(u) > 8 and u[8]) or u[0] == MAIN_ADMIN_ID])
    vip_users = len([u for u in users if len(u) > 7 and u[7]])
    
    chats = get_all_chats()
    total_chats = len(chats)
    vip_chats = len([c for c in chats if len(c) > 5 and c[5]])
    
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
        f"Администраторов: {admin_users}\n"
        f"Главных админов: {main_admin_users}\n"
        f"VIP пользователей: {vip_users}\n\n"
        f"💬 Чаты:\n"
        f"Всего: {total_chats}\n"
        f"VIP чатов: {vip_chats}\n\n"
        f"📚 По группам:\n"
    )
    
    for group, count in group_stats.items():
        stats_text += f"{group}: {count} пользователей\n"
    
    stats_text += f"\n⏰ Время рассылки: {BROADCAST_TIME}"
    
    await query.edit_message_text(
        stats_text,
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Назад", callback_data="admin_panel")]])
    )

# Показать список администраторов
async def show_admin_list(query):
    if not is_main_admin(query.from_user.id):
        await query.edit_message_text("❌ Эта функция доступна только главному администратору!")
        return
    
    admins = get_all_admins()
    
    if not admins:
        await query.edit_message_text(
            "📋 Список администраторов пуст.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Назад", callback_data="admin_panel")]])
        )
        return
    
    admin_list_text = "📋 Список администраторов:\n\n"
    
    for i, admin in enumerate(admins, 1):
        # Безопасное извлечение данных
        user_id = admin[0]
        username = admin[1] if len(admin) > 1 else None
        first_name = admin[2] if len(admin) > 2 else "Неизвестно"
        
        username_display = f"@{username}" if username else "Не указан"
        
        if user_id == MAIN_ADMIN_ID or (len(admin) > 8 and admin[8]):
            status = "👑 Главный"
        else:
            status = "✅ Админ"
        
        admin_list_text += f"{i}. {username_display} ({first_name}) - {status}\n"
    
    await query.edit_message_text(
        admin_list_text,
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Назад", callback_data="admin_panel")]])
    )

# Показать логи администраторов
async def show_admin_logs(query):
    if not is_main_admin(query.from_user.id):
        await query.edit_message_text("❌ Эта функция доступна только главному администратору!")
        return
    
    logs = get_admin_logs(50)
    
    if not logs:
        await query.edit_message_text(
            "📝 Логи администраторов пусты.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Назад", callback_data="admin_panel")]])
        )
        return
    
    logs_text = "📝 Логи администраторов (последние 50):\n\n"
    
    for log in logs:
        log_id, admin_username, admin_user_id, action, timestamp = log
        timestamp_str = datetime.strptime(timestamp, '%Y-%m-%d %H:%M:%S').strftime('%d.%m.%Y %H:%M')
        admin_display = f"@{admin_username}" if admin_username else f"ID: {admin_user_id}"
        
        logs_text += f"🕒 {timestamp_str}\n👤 {admin_display}\n📝 {action}\n\n"
    
    await query.edit_message_text(
        logs_text,
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
        "Отправьте сообщение для рассылки (текст, фото или видео):",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Отмена", callback_data="admin_panel")]])
    )

# Обработчик админ-сообщений (РАБОТАЕТ С МЕДИА НА 100%)
async def handle_admin_messages(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    
    if not is_admin(user.id):
        return
    
    # Если ожидаем рассылку, обрабатываем любой контент
    if context.user_data.get('awaiting_broadcast'):
        selected_groups = context.user_data.get('selected_groups', [])
        message = update.message
        
        # Определяем тип контента
        if message.photo:
            # Фото с подписью или без
            content_type = 'photo'
            file_id = message.photo[-1].file_id
            caption = message.caption or ''
            content_preview = f"📷 Фото + текст:\n{caption if caption else 'Без текста'}"
        elif message.video:
            # Видео с подписью или без
            content_type = 'video'
            file_id = message.video.file_id
            caption = message.caption or ''
            content_preview = f"🎥 Видео + текст:\n{caption if caption else 'Без текста'}"
        elif message.text:
            # Текстовое сообщение
            content_type = 'text'
            text_content = message.text
            content_preview = f"📝 Текст:\n{text_content}"
        else:
            await update.message.reply_text("❌ Неподдерживаемый тип сообщения. Отправьте текст, фото или видео.")
            return
        
        # Сохраняем данные рассылки
        context.user_data['broadcast_content'] = {
            'type': content_type,
            'text': text_content if content_type == 'text' else caption,
            'file_id': file_id if content_type in ['photo', 'video'] else None
        }
        
        context.user_data['awaiting_broadcast'] = False
        
        # Получаем список получателей
        if selected_groups == "all":
            users = get_active_users()
            chats = get_all_chats()
            groups_text = "ВСЕМ ГРУППАМ"
        else:
            users = []
            chats = []
            for group in selected_groups:
                users.extend(get_users_by_group(group))
                chats.extend(get_chats_by_group(group))
            groups_text = ", ".join(selected_groups)
        
        total_recipients = len(users) + len(chats)
        
        keyboard = [
            [InlineKeyboardButton("✅ Да, отправить", callback_data="confirm_broadcast")],
            [InlineKeyboardButton("❌ Отмена", callback_data="admin_panel")]
        ]
        
        await update.message.reply_text(
            f"Подтвердите рассылку для: {groups_text}\n\n"
            f"{content_preview}\n\n"
            f"Получателей: {total_recipients}\n"
            f"(Пользователи: {len(users)}, Чаты: {len(chats)})",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return
    
    # Обработка изменения времени рассылки
    elif context.user_data.get('awaiting_broadcast_time'):
        new_time = update.message.text.strip()
        try:
            # Проверяем формат времени
            datetime.strptime(new_time, '%H:%M')
            global BROADCAST_TIME
            BROADCAST_TIME = new_time
            context.user_data['awaiting_broadcast_time'] = False
            
            # Логируем действие
            log_admin_action(
                user.username,
                user.id,
                f"Изменил время рассылки на {new_time}"
            )
            
            await update.message.reply_text(
                f"✅ Время рассылки изменено на {new_time}\n\n"
                f"Рассылка будет выполняться каждый день в {new_time}",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("В админ-панель", callback_data="admin_panel")]])
            )
        except ValueError:
            await update.message.reply_text(
                "❌ Неверный формат времени!\n\n"
                "Введите время в формате ЧЧ:ММ (например, 18:30):",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Отмена", callback_data="admin_panel")]])
            )
    
    # Обработка бана пользователя
    elif context.user_data.get('awaiting_ban'):
        if update.message.text.startswith('@'):
            username = update.message.text[1:]  # Убираем @
            user_to_ban = find_user_by_username(username)
            if user_to_ban:
                if ban_user(user_to_ban[0]):
                    context.user_data['awaiting_ban'] = False
                    # Логируем действие
                    log_admin_action(
                        user.username,
                        user.id,
                        f"Заблокировал пользователя @{username}"
                    )
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
    
    # Обработка разбана пользователя
    elif context.user_data.get('awaiting_unban'):
        if update.message.text.startswith('@'):
            username = update.message.text[1:]  # Убираем @
            user_to_unban = find_user_by_username(username)
            if user_to_unban:
                if unban_user(user_to_unban[0]):
                    context.user_data['awaiting_unban'] = False
                    # Логируем действие
                    log_admin_action(
                        user.username,
                        user.id,
                        f"Разблокировал пользователя @{username}"
                    )
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
    
    # Обработка выдачи прав администратора
    elif context.user_data.get('awaiting_make_admin'):
        if update.message.text.startswith('@'):
            username = update.message.text[1:]  # Убираем @
            user_to_admin = find_user_by_username(username)
            if user_to_admin:
                if make_admin(user_to_admin[0]):
                    context.user_data['awaiting_make_admin'] = False
                    # Логируем действие
                    log_admin_action(
                        user.username,
                        user.id,
                        f"Выдал права администратора пользователю @{username}"
                    )
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
    
    # Обработка снятия прав администратора
    elif context.user_data.get('awaiting_remove_admin'):
        if update.message.text.startswith('@'):
            username = update.message.text[1:]  # Убираем @
            user_to_remove_admin = find_user_by_username(username)
            if user_to_remove_admin:
                if remove_admin(user_to_remove_admin[0]):
                    context.user_data['awaiting_remove_admin'] = False
                    # Логируем действие
                    log_admin_action(
                        user.username,
                        user.id,
                        f"Снял права администратора у пользователя @{username}"
                    )
                    await update.message.reply_text(
                        f"✅ У пользователя @{username} сняты права администратора!",
                        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("В админ-панель", callback_data="admin_panel")]])
                    )
                else:
                    await update.message.reply_text("❌ Ошибка при снятии прав администратора!")
            else:
                await update.message.reply_text("❌ Пользователь с таким username не найден!")
        else:
            await update.message.reply_text("❌ Введите username в формате @username")
    
    # Обработка выдачи прав главного администратора
    elif context.user_data.get('awaiting_make_main_admin'):
        if update.message.text.startswith('@'):
            username = update.message.text[1:]  # Убираем @
            user_to_main_admin = find_user_by_username(username)
            if user_to_main_admin:
                if make_main_admin(user_to_main_admin[0]):
                    context.user_data['awaiting_make_main_admin'] = False
                    # Логируем действие
                    log_admin_action(
                        user.username,
                        user.id,
                        f"Выдал права главного администратора пользователю @{username}"
                    )
                    await update.message.reply_text(
                        f"✅ Пользователю @{username} выданы права главного администратора!",
                        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("В админ-панель", callback_data="admin_panel")]])
                    )
                else:
                    await update.message.reply_text("❌ Ошибка при выдаче прав главного администратора!")
            else:
                await update.message.reply_text("❌ Пользователь с таким username не найден!")
        else:
            await update.message.reply_text("❌ Введите username в формате @username")
    
    # Обработка снятия прав главного администратора
    elif context.user_data.get('awaiting_remove_main_admin'):
        if update.message.text.startswith('@'):
            username = update.message.text[1:]  # Убираем @
            user_to_remove_main_admin = find_user_by_username(username)
            if user_to_remove_main_admin:
                if remove_main_admin(user_to_remove_main_admin[0]):
                    context.user_data['awaiting_remove_main_admin'] = False
                    # Логируем действие
                    log_admin_action(
                        user.username,
                        user.id,
                        f"Снял права главного администратора у пользователя @{username}"
                    )
                    await update.message.reply_text(
                        f"✅ У пользователя @{username} сняты права главного администратора!",
                        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("В админ-панель", callback_data="admin_panel")]])
                    )
                else:
                    await update.message.reply_text("❌ Ошибка при снятии прав главного администратора!")
            else:
                await update.message.reply_text("❌ Пользователь с таким username не найден!")
        else:
            await update.message.reply_text("❌ Введите username в формате @username")
    
    # Обработка выдачи VIP статуса
    elif context.user_data.get('awaiting_give_vip'):
        if update.message.text.startswith('@'):
            username = update.message.text[1:]  # Убираем @
            user_to_vip = find_user_by_username(username)
            if user_to_vip:
                if give_vip(user_to_vip[0]):
                    context.user_data['awaiting_give_vip'] = False
                    # Логируем действие
                    log_admin_action(
                        user.username,
                        user.id,
                        f"Выдал VIP статус пользователю @{username}"
                    )
                    await update.message.reply_text(
                        f"✅ Пользователю @{username} выдан VIP статус!",
                        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("В админ-панель", callback_data="admin_panel")]])
                    )
                else:
                    await update.message.reply_text("❌ Ошибка при выдаче VIP статуса!")
            else:
                await update.message.reply_text("❌ Пользователь с таким username не найден!")
        else:
            await update.message.reply_text("❌ Введите username в формате @username")
    
    # Обработка снятия VIP статуса
    elif context.user_data.get('awaiting_take_vip'):
        if update.message.text.startswith('@'):
            username = update.message.text[1:]  # Убираем @
            user_to_unvip = find_user_by_username(username)
            if user_to_unvip:
                if take_vip(user_to_unvip[0]):
                    context.user_data['awaiting_take_vip'] = False
                    # Логируем действие
                    log_admin_action(
                        user.username,
                        user.id,
                        f"Снял VIP статус у пользователя @{username}"
                    )
                    await update.message.reply_text(
                        f"✅ У пользователя @{username} снят VIP статус!",
                        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("В админ-панель", callback_data="admin_panel")]])
                    )
                else:
                    await update.message.reply_text("❌ Ошибка при снятии VIP статуса!")
            else:
                await update.message.reply_text("❌ Пользователь с таким username не найден!")
        else:
            await update.message.reply_text("❌ Введите username в формате @username")

# Подтверждение и отправка рассылки (РАБОТАЕТ С МЕДИА НА 100%)
async def confirm_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if not is_admin(query.from_user.id):
        await query.edit_message_text("Доступ запрещен!")
        return
    
    content_data = context.user_data.get('broadcast_content', {})
    selected_groups = context.user_data.get('selected_groups', [])
    
    if not content_data:
        await query.edit_message_text("Ошибка: данные рассылки не найдены")
        return
    
    if selected_groups == "all":
        users = get_active_users()
        chats = get_all_chats()
        groups_text = "ВСЕМ ГРУППАМ"
    else:
        users = []
        chats = []
        for group in selected_groups:
            users.extend(get_users_by_group(group))
            chats.extend(get_chats_by_group(group))
        groups_text = ", ".join(selected_groups)
    
    sent_count = 0
    failed_count = 0
    
    total_recipients = len(users) + len(chats)
    await query.edit_message_text(f"🔄 Начинаю рассылку для: {groups_text}\n\n0/{total_recipients}")
    
    # Рассылка пользователям
    for i, user_data in enumerate(users):
        user_id = user_data[0]
        try:
            if content_data['type'] == 'text':
                await context.bot.send_message(
                    chat_id=user_id, 
                    text=content_data['text']
                )
            elif content_data['type'] == 'photo':
                await context.bot.send_photo(
                    chat_id=user_id,
                    photo=content_data['file_id'],
                    caption=content_data['text']
                )
            elif content_data['type'] == 'video':
                await context.bot.send_video(
                    chat_id=user_id,
                    video=content_data['file_id'],
                    caption=content_data['text']
                )
            sent_count += 1
        except Exception as e:
            failed_count += 1
            logger.error(f"Ошибка отправки пользователю {user_id}: {e}")
        
        # Обновляем прогресс каждые 10 пользователей
        if i % 10 == 0 or i == len(users) - 1:
            progress = i + 1
            await query.edit_message_text(f"🔄 Рассылка для: {groups_text}\nПользователи... {progress}/{len(users)}")
    
    # Рассылка в чаты
    for j, chat_data in enumerate(chats):
        chat_id = chat_data[0]
        try:
            if content_data['type'] == 'text':
                await context.bot.send_message(
                    chat_id=chat_id, 
                    text=content_data['text']
                )
            elif content_data['type'] == 'photo':
                await context.bot.send_photo(
                    chat_id=chat_id,
                    photo=content_data['file_id'],
                    caption=content_data['text']
                )
            elif content_data['type'] == 'video':
                await context.bot.send_video(
                    chat_id=chat_id,
                    video=content_data['file_id'],
                    caption=content_data['text']
                )
            sent_count += 1
        except Exception as e:
            failed_count += 1
            logger.error(f"Ошибка отправки в чат {chat_id}: {e}")
        
        # Обновляем прогресс каждые 5 чатов
        if j % 5 == 0 or j == len(chats) - 1:
            progress = j + 1
            await query.edit_message_text(f"🔄 Рассылка для: {groups_text}\nЧаты... {progress}/{len(chats)}")
    
    # Формируем текст результата
    content_type_text = {
        'text': '📝 Текст',
        'photo': '📷 Фото', 
        'video': '🎥 Видео'
    }
    
    await query.edit_message_text(
        f"✅ Рассылка завершена!\n\n"
        f"Для: {groups_text}\n"
        f"Тип: {content_type_text.get(content_data['type'], 'Неизвестно')}\n"
        f"Успешно: {sent_count}\n"
        f"Не удалось: {failed_count}\n"
        f"Всего получателей: {total_recipients}",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("В админ-панель", callback_data="admin_panel")]])
    )
    
    # Логируем действие
    log_admin_action(
        query.from_user.username,
        query.from_user.id,
        f"Сделал рассылку для {groups_text}. Успешно: {sent_count}, Не удалось: {failed_count}"
    )
    
    # Очищаем данные рассылки
    context.user_data.pop('broadcast_content', None)
    context.user_data.pop('selected_groups', None)
    context.user_data.pop('awaiting_broadcast', None)

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

# Отправка расписания сейчас (ИСПРАВЛЕННАЯ ВЕРСИЯ)
async def send_schedule_broadcast_now(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if not is_admin(query.from_user.id):
        await query.edit_message_text("Доступ запрещен!")
        return
    
    await query.edit_message_text("🔄 Начинаю рассылку расписания...")
    
    # Используем существующую функцию рассылки
    await send_daily_schedule(context)
    
    # Логируем действие
    log_admin_action(
        query.from_user.username,
        query.from_user.id,
        "Выполнил ручную рассылку расписания"
    )
    
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

# Начать снятие прав админа по username
async def start_remove_admin(query, context):
    if not is_main_admin(query.from_user.id):
        await query.edit_message_text("❌ Эта функция доступна только главному администратору!")
        return
    
    context.user_data['awaiting_remove_admin'] = True
    await query.edit_message_text(
        "Введите @username пользователя для снятия прав администратора (например, @username):",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Отмена", callback_data="admin_panel")]])
    )

# Начать выдачу прав главного администратора по username
async def start_make_main_admin(query, context):
    if not is_main_admin(query.from_user.id):
        await query.edit_message_text("❌ Эта функция доступна только главному администратору!")
        return
    
    context.user_data['awaiting_make_main_admin'] = True
    await query.edit_message_text(
        "Введите @username пользователя для выдачи прав главного администратора (например, @username):",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Отмена", callback_data="admin_panel")]])
    )

# Начать снятие прав главного администратора по username
async def start_remove_main_admin(query, context):
    if not is_main_admin(query.from_user.id):
        await query.edit_message_text("❌ Эта функция доступна только главному администратору!")
        return
    
    context.user_data['awaiting_remove_main_admin'] = True
    await query.edit_message_text(
        "Введите @username пользователя для снятия прав главного администратора (например, @username):",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Отмена", callback_data="admin_panel")]])
    )

# Начать выдачу VIP статуса по username
async def start_give_vip(query, context):
    if not is_main_admin(query.from_user.id):
        await query.edit_message_text("❌ Эта функция доступна только главному администратору!")
        return
    
    context.user_data['awaiting_give_vip'] = True
    await query.edit_message_text(
        "Введите @username пользователя для выдачи VIP статуса (например, @username):",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Отмена", callback_data="admin_panel")]])
    )

# Начать снятие VIP статуса по username
async def start_take_vip(query, context):
    if not is_main_admin(query.from_user.id):
        await query.edit_message_text("❌ Эта функция доступна только главному администратору!")
        return
    
    context.user_data['awaiting_take_vip'] = True
    await query.edit_message_text(
        "Введите @username пользователя для снятия VIP статуса (например, @username):",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Отмена", callback_data="admin_panel")]])
    )

# Рассылка расписания (ПОЛНОСТЬЮ ИСПРАВЛЕННАЯ ВЕРСИЯ) с правильной логикой VIP
async def send_daily_schedule(context: ContextTypes.DEFAULT_TYPE):
    tomorrow = datetime.now() + timedelta(days=1)
    weekday = get_russian_weekday(tomorrow)
    week_number, week_type = get_current_week()
    
    logger.info(f"🔄 Начинаю ежедневную рассылку расписания на {tomorrow.strftime('%d.%m.%Y')} ({weekday})")
    
    # Для каждой группы отправляем расписание только соответствующим пользователям и чатам
    for group_name in GROUPS:
        # Получаем обычных пользователей этой группы
        users = get_users_by_group(group_name)
        
        # Получаем VIP пользователей этой группы
        vip_users = get_vip_users_by_group(group_name)
        
        # Получаем обычные чаты этой группы
        chats = get_chats_by_group(group_name)
        
        # Получаем VIP чаты этой группы
        vip_chats = get_vip_chats_by_group(group_name)
        
        # Обычное расписание
        if group_name in SCHEDULE and week_type in SCHEDULE[group_name] and weekday in SCHEDULE[group_name][week_type]:
            schedule_text = SCHEDULE[group_name][week_type][weekday]
            message = (
                f"📅 Расписание на завтра ({weekday}) для группы {group_name}:\n\n"
                f"{schedule_text}\n\n"
                f"({week_type} неделя, неделя №{week_number})"
            )
        else:
            message = f"На завтра ({weekday}) расписание для группы {group_name} не найдено."
        
        # VIP расписание
        vip_schedule = get_vip_schedule(group_name, weekday, week_type, week_number)
        vip_message = (
            f"⭐ VIP РАСПИСАНИЕ на завтра ({weekday}) для группы {group_name}:\n\n"
            f"{vip_schedule}\n\n"
            f"({week_type} неделя, неделя №{week_number})"
        )
        
        # Рассылка обычным пользователям (ТОЛЬКО обычное расписание)
        for user_data in users:
            user_id = user_data[0]
            # Проверяем, не является ли пользователь VIP с включенным режимом
            if not (has_vip_status(user_id) and get_vip_mode(user_id)):
                try:
                    await context.bot.send_message(chat_id=user_id, text=message)
                    logger.info(f"✅ Отправлено обычное расписание пользователю {user_id}")
                except Exception as e:
                    logger.error(f"❌ Не удалось отправить расписание пользователю {user_id}: {e}")
        
        # Рассылка VIP пользователям (ТОЛЬКО VIP расписание если режим включен)
        for user_data in vip_users:
            user_id = user_data[0]
            # Проверяем, включен ли VIP режим у пользователя
            if get_vip_mode(user_id):
                try:
                    await context.bot.send_message(chat_id=user_id, text=vip_message)
                    logger.info(f"✅ Отправлено VIP расписание пользователю {user_id}")
                except Exception as e:
                    logger.error(f"❌ Не удалось отправить VIP расписание пользователю {user_id}: {e}")
            else:
                # Если VIP режим выключен, отправляем обычное расписание
                try:
                    await context.bot.send_message(chat_id=user_id, text=message)
                    logger.info(f"✅ Отправлено обычное расписание VIP пользователю {user_id} (режим выключен)")
                except Exception as e:
                    logger.error(f"❌ Не удалось отправить расписание VIP пользователю {user_id}: {e}")
        
        # Рассылка в обычные чаты (ТОЛЬКО обычное расписание)
        for chat_data in chats:
            chat_id = chat_data[0]
            # Проверяем, не является ли чат VIP
            if not is_chat_vip(chat_id):
                try:
                    await context.bot.send_message(chat_id=chat_id, text=message)
                    logger.info(f"✅ Отправлено обычное расписание в чат {chat_id}")
                except Exception as e:
                    logger.error(f"❌ Не удалось отправить расписание в чат {chat_id}: {e}")
        
        # Рассылка в VIP чаты (ТОЛЬКО VIP расписание)
        for chat_data in vip_chats:
            chat_id = chat_data[0]
            try:
                await context.bot.send_message(chat_id=chat_id, text=vip_message)
                logger.info(f"✅ Отправлено VIP расписание в VIP чат {chat_id}")
            except Exception as e:
                logger.error(f"❌ Не удалось отправить VIP расписание в VIP чат {chat_id}: {e}")
    
    # Отправляем общее сообщение в чаты без выбранной группы
    all_chats = get_all_chats()
    chats_with_groups = set()
    
    # Собираем все чаты, у которых есть выбранные группы
    for group_name in GROUPS:
        group_chats = get_chats_by_group(group_name)
        for chat in group_chats:
            chats_with_groups.add(chat[0])
    
    # Отправляем сообщение только в чаты без выбранной группы
    for chat_data in all_chats:
        chat_id = chat_data[0]
        if chat_id not in chats_with_groups:
            message = (
                f"📅 Расписание на завтра ({weekday}):\n\n"
                f"({week_type} неделя, неделя №{week_number})\n\n"
                f"Для получения полного расписания вашей группы "
                f"используйте команду /group в этом чате."
            )
            try:
                await context.bot.send_message(chat_id=chat_id, text=message)
                logger.info(f"✅ Отправлено общее сообщение в чат {chat_id}")
            except Exception as e:
                logger.error(f"❌ Не удалось отправить общее сообщение в чат {chat_id}: {e}")
    
    logger.info("✅ Ежедневная рассылка расписания завершена")

# Обработчик всех сообщений
async def handle_all_messages(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Игнорируем сообщения из групповых чатов (кроме команды /start и /group)
    if (update.effective_chat.type in ['group', 'supergroup'] and 
        not update.message.text.startswith('/start') and 
        not update.message.text.startswith('/group') and
        not update.message.text.startswith('/givevip') and
        not update.message.text.startswith('/takevip') and
        not update.message.text.startswith('/zakladka') and
        not update.message.text.startswith('/gangbang')):
        return
    
    user = update.effective_user
    update_user_activity(user.id)

# Обработчик ошибок
async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.error(msg="Exception while handling an update:", exc_info=context.error)

# Основная функция
def main():
    # Добавляем более детальное логирование для отладки
    logging.getLogger('httpx').setLevel(logging.WARNING)
    
    init_db()
    application = Application.builder().token(BOT_TOKEN).build()
    
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("group", group_command))
    application.add_handler(CommandHandler("givevip", givevip_command))
    application.add_handler(CommandHandler("takevip", takevip_command))
    application.add_handler(CommandHandler("zakladka", zakladka_command))
    application.add_handler(CommandHandler("gangbang", gangbang_command))
    application.add_handler(CallbackQueryHandler(button_handler))
    
    # Обработчик для всех сообщений от админов (включая медиа)
    application.add_handler(MessageHandler(
        filters.TEXT | filters.PHOTO | filters.VIDEO, 
        handle_admin_messages
    ))
    
    application.add_handler(MessageHandler(filters.ALL, handle_all_messages))
    application.add_error_handler(error_handler)
    
    job_queue = application.job_queue
    if job_queue:
        # Рассылка расписания каждый день в установленное время
        job_queue.run_daily(
            send_daily_schedule, 
            time=datetime.strptime(BROADCAST_TIME, "%H:%M").time()
        )
        logger.info(f"✅ Ежедневная рассылка настроена на {BROADCAST_TIME}")
    else:
        logger.error("❌ JobQueue не доступна")
    
    logger.info("✅ Бот запускается...")
    application.run_polling()

if __name__ == "__main__":
    main()
