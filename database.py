# database.py
import sqlite3
import logging
from datetime import datetime, timedelta
import os

logger = logging.getLogger(__name__)

class Database:
    def __init__(self, db_path='data/university_bot.db'):
        self.db_path = db_path
        self._ensure_data_directory()
        self.init_db()
    
    def _ensure_data_directory(self):
        """Убедиться, что папка data существует"""
        data_dir = os.path.dirname(self.db_path)
        if data_dir and not os.path.exists(data_dir):
            os.makedirs(data_dir, exist_ok=True)
            logger.info(f"✅ Создана папка: {data_dir}")
    
    def get_connection(self):
        """Создает соединение с базой данных"""
        return sqlite3.connect(self.db_path, check_same_thread=False)
    
    def init_db(self):
        """Инициализация базы данных"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # Создаем таблицу для браков
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS marriages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user1_id INTEGER NOT NULL,
                user2_id INTEGER NOT NULL,
                user1_username TEXT,
                user2_username TEXT,
                chat_id INTEGER NOT NULL,
                married_date DATETIME DEFAULT CURRENT_TIMESTAMP,
                is_active BOOLEAN DEFAULT TRUE,
                last_seks_date TEXT,
                UNIQUE(user1_id, user2_id, chat_id)
            )
        ''')
        
        # Создаем таблицу для предложений брака
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS marriage_proposals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                proposer_id INTEGER NOT NULL,
                target_id INTEGER NOT NULL,
                chat_id INTEGER NOT NULL,
                message_id INTEGER NOT NULL,
                created_at DATETIME DEFAULT (datetime('now')),
                is_active BOOLEAN DEFAULT TRUE
            )
        ''')
        
        # Создаем таблицу users
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                first_name TEXT,
                group_name TEXT,
                subgroup TEXT DEFAULT 'Обе подгруппы',
                last_active DATETIME DEFAULT (datetime('now')),
                is_banned BOOLEAN DEFAULT FALSE,
                is_admin BOOLEAN DEFAULT FALSE,
                is_main_admin BOOLEAN DEFAULT FALSE,
                balance INTEGER DEFAULT 1000
            )
        ''')
        
        # Создаем таблицу chats
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS chats (
                chat_id INTEGER PRIMARY KEY,
                chat_title TEXT,
                added_date DATETIME DEFAULT (datetime('now')),
                is_active BOOLEAN DEFAULT TRUE,
                chat_group TEXT
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS chat_users (
                chat_id INTEGER,
                user_id INTEGER,
                group_name TEXT,
                subgroup TEXT DEFAULT 'Обе подгруппы',
                PRIMARY KEY (chat_id, user_id)
            )
        ''')
        
        # Таблица admin_logs
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS admin_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                admin_username TEXT,
                admin_user_id INTEGER,
                action TEXT,
                target_username TEXT,
                target_user_id INTEGER,
                timestamp DATETIME DEFAULT (datetime('now'))
            )
        ''')
        
        # Создаем индексы
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_marriages_chat ON marriages(chat_id, is_active)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_marriages_users ON marriages(user1_id, user2_id, is_active)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_proposals_created ON marriage_proposals(created_at)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_proposals_active ON marriage_proposals(is_active)')
        
        # Добавляем главного администратора если его нет
        from main import MAIN_ADMIN_ID
        cursor.execute('SELECT * FROM users WHERE user_id = ?', (MAIN_ADMIN_ID,))
        if not cursor.fetchone():
            cursor.execute('''
                INSERT INTO users (user_id, username, first_name, group_name, is_admin, is_main_admin, balance)
                VALUES (?, ?, ?, ?, TRUE, TRUE, 10000)
            ''', (MAIN_ADMIN_ID, "bokalpivka", "Admin", "ПСН-24"))
        
        conn.commit()
        conn.close()
        logger.info("✅ База данных инициализирована успешно")
    
    # ==================== ПОЛЬЗОВАТЕЛИ ====================
    
    def save_user_with_subgroup(self, user_id, username, first_name, group_name, subgroup):
        """Сохранить пользователя с подгруппой"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            cursor.execute('''
                INSERT OR REPLACE INTO users (user_id, username, first_name, group_name, subgroup, last_active)
                VALUES (?, ?, ?, ?, ?, datetime('now'))
            ''', (user_id, username, first_name, group_name, subgroup))
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            logger.error(f"Ошибка при сохранении пользователя {user_id}: {e}")
            return False
    
    def get_user(self, user_id):
        """Получить пользователя"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM users WHERE user_id = ?', (user_id,))
            user = cursor.fetchone()
            conn.close()
            return user
        except Exception as e:
            logger.error(f"Ошибка при получении пользователя {user_id}: {e}")
            return None
    
    def find_user_by_username(self, username):
        """Найти пользователя по username"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM users WHERE username = ?', (username,))
            user = cursor.fetchone()
            conn.close()
            return user
        except Exception as e:
            logger.error(f"Ошибка при поиске пользователя по username {username}: {e}")
            return None
    
    def get_users_by_group(self, group_name):
        """Получить пользователей по группе"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM users WHERE group_name = ? AND is_banned = FALSE', (group_name,))
            users = cursor.fetchall()
            conn.close()
            return users
        except Exception as e:
            logger.error(f"Ошибка при получении пользователей группы {group_name}: {e}")
            return []
    
    def get_all_users(self):
        """Получить всех пользователей"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM users ORDER BY last_active DESC')
            users = cursor.fetchall()
            conn.close()
            return users
        except Exception as e:
            logger.error(f"Ошибка при получении всех пользователей: {e}")
            return []
    
    def get_active_users(self):
        """Получить активных пользователей"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM users WHERE is_banned = FALSE ORDER BY last_active DESC')
            users = cursor.fetchall()
            conn.close()
            return users
        except Exception as e:
            logger.error(f"Ошибка при получении активных пользователей: {e}")
            return []
    
    def update_user_activity(self, user_id):
        """Обновить активность пользователя"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            cursor.execute('UPDATE users SET last_active = datetime("now") WHERE user_id = ?', (user_id,))
            conn.commit()
            conn.close()
        except Exception as e:
            logger.error(f"Ошибка при обновлении активности пользователя {user_id}: {e}")
    
    def update_user_subgroup(self, user_id, subgroup):
        """Обновить подгруппу пользователя"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            cursor.execute('UPDATE users SET subgroup = ? WHERE user_id = ?', (subgroup, user_id))
            conn.commit()
            conn.close()
            logger.info(f"Подгруппа пользователя {user_id} обновлена на {subgroup}")
            return True
        except Exception as e:
            logger.error(f"Ошибка при обновлении подгруппы пользователя {user_id}: {e}")
            return False
    
    # ==================== БАЛАНС ====================
    
    def get_user_balance(self, user_id):
        """Получить баланс пользователя"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            cursor.execute('SELECT balance FROM users WHERE user_id = ?', (user_id,))
            result = cursor.fetchone()
            conn.close()
            return result[0] if result else 1000
        except Exception as e:
            logger.error(f"Ошибка при получении баланса пользователя {user_id}: {e}")
            return 1000
    
    def update_user_balance(self, user_id, amount):
        """Обновить баланс пользователя"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            cursor.execute('UPDATE users SET balance = ? WHERE user_id = ?', (amount, user_id))
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            logger.error(f"Ошибка при обновлении баланса пользователя {user_id}: {e}")
            return False
    
    def add_user_balance(self, user_id, amount):
        """Добавить сумму к балансу пользователя"""
        current_balance = self.get_user_balance(user_id)
        new_balance = current_balance + amount
        return self.update_user_balance(user_id, new_balance)
    
    # ==================== АДМИНИСТРИРОВАНИЕ ====================
    
    def ban_user(self, user_id):
        """Забанить пользователя"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            cursor.execute('UPDATE users SET is_banned = TRUE WHERE user_id = ?', (user_id,))
            conn.commit()
            conn.close()
            logger.info(f"Пользователь {user_id} забанен")
            return True
        except Exception as e:
            logger.error(f"Ошибка при бане пользователя {user_id}: {e}")
            return False
    
    def unban_user(self, user_id):
        """Разбанить пользователя"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            cursor.execute('UPDATE users SET is_banned = FALSE WHERE user_id = ?', (user_id,))
            conn.commit()
            conn.close()
            logger.info(f"Пользователь {user_id} разбанен")
            return True
        except Exception as e:
            logger.error(f"Ошибка при разбане пользователя {user_id}: {e}")
            return False
    
    def make_admin(self, user_id):
        """Сделать администратором"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            cursor.execute('UPDATE users SET is_admin = TRUE WHERE user_id = ?', (user_id,))
            conn.commit()
            conn.close()
            logger.info(f"Пользователь {user_id} стал администратором")
            return True
        except Exception as e:
            logger.error(f"Ошибка при выдаче прав админа пользователю {user_id}: {e}")
            return False
    
    def remove_admin(self, user_id):
        """Убрать права администратора"""
        try:
            from main import MAIN_ADMIN_ID
            if user_id == MAIN_ADMIN_ID:
                return False
                
            conn = self.get_connection()
            cursor = conn.cursor()
            cursor.execute('UPDATE users SET is_admin = FALSE WHERE user_id = ?', (user_id,))
            conn.commit()
            conn.close()
            logger.info(f"Пользователь {user_id} лишен прав администратора")
            return True
        except Exception as e:
            logger.error(f"Ошибка при снятии прав админа у пользователя {user_id}: {e}")
            return False
    
    def get_all_admins(self):
        """Получить всех администраторов"""
        try:
            from main import ADMIN_IDS
            conn = self.get_connection()
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM users WHERE is_admin = TRUE OR is_main_admin = TRUE OR user_id IN ({})'.format(','.join('?' for _ in ADMIN_IDS)), ADMIN_IDS)
            admins = cursor.fetchall()
            conn.close()
            return admins
        except Exception as e:
            logger.error(f"Ошибка при получении администраторов: {e}")
            return []
    
    def log_admin_action(self, admin_username, admin_user_id, action, target_username=None, target_user_id=None):
        """Логировать действие администратора"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO admin_logs (admin_username, admin_user_id, action, target_username, target_user_id, timestamp)
                VALUES (?, ?, ?, ?, ?, datetime('now'))
            ''', (admin_username, admin_user_id, action, target_username, target_user_id))
            conn.commit()
            conn.close()
            logger.info(f"Admin action logged: {admin_username} ({admin_user_id}) - {action}")
        except Exception as e:
            logger.error(f"Ошибка при логировании действия администратора: {e}")
    
    def get_admin_logs(self, limit=50):
        """Получить логи администраторов"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            cursor.execute('''
                SELECT id, admin_username, admin_user_id, action, target_username, target_user_id, timestamp 
                FROM admin_logs 
                ORDER BY datetime(timestamp) DESC 
                LIMIT ?
            ''', (limit,))
            logs = cursor.fetchall()
            conn.close()
            return logs
        except Exception as e:
            logger.error(f"Ошибка при получении логов администраторов: {e}")
            return []
    
    # ==================== ЧАТЫ ====================
    
    def add_chat(self, chat_id, chat_title):
        """Добавить чат"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            cursor.execute('''
                INSERT OR REPLACE INTO chats (chat_id, chat_title, added_date, is_active)
                VALUES (?, ?, datetime('now'), TRUE)
            ''', (chat_id, chat_title))
            conn.commit()
            conn.close()
            logger.info(f"Чат добавлен: {chat_title} (ID: {chat_id})")
            return True
        except Exception as e:
            logger.error(f"Ошибка при добавлении чата {chat_id}: {e}")
            return False
    
    def get_all_chats(self):
        """Получить все чаты"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM chats WHERE is_active = TRUE')
            chats = cursor.fetchall()
            conn.close()
            return chats
        except Exception as e:
            logger.error(f"Ошибка при получении чатов: {e}")
            return []
    
    def get_chats_by_group(self, group_name):
        """Получить чаты по группе"""
        try:
            conn = self.get_connection()
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
    
    def save_chat_user_with_subgroup(self, chat_id, user_id, group_name, subgroup):
        """Сохранить пользователя чата с подгруппой"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            cursor.execute('''
                INSERT OR REPLACE INTO chat_users (chat_id, user_id, group_name, subgroup)
                VALUES (?, ?, ?, ?)
            ''', (chat_id, user_id, group_name, subgroup))
            conn.commit()
            conn.close()
            logger.info(f"Пользователь {user_id} добавлен в чат {chat_id} с группой {group_name} и подгруппой {subgroup}")
            return True
        except Exception as e:
            logger.error(f"Ошибка при сохранении пользователя чата {chat_id}: {e}")
            return False
    
    def get_chat_user_group(self, chat_id, user_id):
        """Получить группу пользователя в чате"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            cursor.execute('SELECT group_name FROM chat_users WHERE chat_id = ? AND user_id = ?', (chat_id, user_id))
            result = cursor.fetchone()
            conn.close()
            return result[0] if result else None
        except Exception as e:
            logger.error(f"Ошибка при получении группы пользователя чата {chat_id}: {e}")
            return None
    
    def get_main_chat_group(self, chat_id):
        """Получить основную группу чата"""
        try:
            conn = self.get_connection()
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
    
    def get_all_chats_with_info(self):
        """Получить все чаты с информацией"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            cursor.execute('''
                SELECT c.chat_id, c.chat_title, c.chat_group, 
                       COUNT(cu.user_id) as user_count
                FROM chats c
                LEFT JOIN chat_users cu ON c.chat_id = cu.chat_id
                WHERE c.is_active = TRUE
                GROUP BY c.chat_id, c.chat_title, c.chat_group
                ORDER BY c.chat_title
            ''')
            chats = cursor.fetchall()
            conn.close()
            return chats
        except Exception as e:
            logger.error(f"Ошибка при получении информации о чатах: {e}")
            return []
    
    # ==================== БРАКИ ====================
    
    def create_marriage(self, user1_id, user1_username, user2_id, user2_username, chat_id):
        """Создать брак"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT * FROM marriages 
                WHERE chat_id = ? AND is_active = TRUE 
                AND ((user1_id = ? AND user2_id = ?) OR (user1_id = ? AND user2_id = ?))
            ''', (chat_id, user1_id, user2_id, user2_id, user1_id))
            
            existing_marriage = cursor.fetchone()
            if existing_marriage:
                conn.close()
                return False, "Эти пользователи уже состоят в браке!"
            
            cursor.execute('''
                INSERT INTO marriages (user1_id, user2_id, user1_username, user2_username, chat_id)
                VALUES (?, ?, ?, ?, ?)
            ''', (user1_id, user2_id, user1_username, user2_username, chat_id))
            
            conn.commit()
            conn.close()
            logger.info(f"Брак создан: {user1_id} и {user2_id} в чате {chat_id}")
            return True, "Брак успешно создан!"
        except Exception as e:
            logger.error(f"Ошибка при создании брака: {e}")
            return False, "Ошибка при создании брака"
    
    def break_marriage(self, user1_id, user2_id, chat_id):
        """Расторгнуть брак"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            cursor.execute('''
                UPDATE marriages 
                SET is_active = FALSE 
                WHERE chat_id = ? AND is_active = TRUE 
                AND ((user1_id = ? AND user2_id = ?) OR (user1_id = ? AND user2_id = ?))
            ''', (chat_id, user1_id, user2_id, user2_id, user1_id))
            
            rows_affected = cursor.rowcount
            conn.commit()
            conn.close()
            
            if rows_affected > 0:
                logger.info(f"Брак расторгнут: {user1_id} и {user2_id} в чате {chat_id}")
                return True, "Брак расторгнут!"
            else:
                return False, "Брак не найден!"
        except Exception as e:
            logger.error(f"Ошибка при расторжении брака: {e}")
            return False, "Ошибка при расторжении брака"
    
    def get_marriage(self, user_id, chat_id):
        """Получить информацию о браке пользователя в чате"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT * FROM marriages 
                WHERE chat_id = ? AND is_active = TRUE 
                AND (user1_id = ? OR user2_id = ?)
            ''', (chat_id, user_id, user_id))
            
            marriage = cursor.fetchone()
            conn.close()
            return marriage
        except Exception as e:
            logger.error(f"Ошибка при получении брака: {e}")
            return None
    
    def get_chat_marriages(self, chat_id):
        """Получить все активные браки в чате"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT * FROM marriages 
                WHERE chat_id = ? AND is_active = TRUE 
                ORDER BY married_date DESC
            ''', (chat_id,))
            
            marriages = cursor.fetchall()
            conn.close()
            return marriages
        except Exception as e:
            logger.error(f"Ошибка при получении браков чата: {e}")
            return []
    
    def set_last_seks_date(self, marriage_id, date_str):
        """Установить дату последнего секса для брака"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            cursor.execute('''
                UPDATE marriages 
                SET last_seks_date = ? 
                WHERE id = ?
            ''', (date_str, marriage_id))
            
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            logger.error(f"Ошибка при установке даты секса: {e}")
            return False
    
    def get_last_seks_date(self, marriage_id):
        """Получить дату последнего секса для брака"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            cursor.execute('SELECT last_seks_date FROM marriages WHERE id = ?', (marriage_id,))
            result = cursor.fetchone()
            conn.close()
            return result[0] if result else None
        except Exception as e:
            logger.error(f"Ошибка при получении даты секса: {e}")
            return None
    
    # ==================== ПРЕДЛОЖЕНИЯ БРАКА ====================
    
    def create_marriage_proposal(self, proposer_id, target_id, chat_id, message_id):
        """Создать предложение о браке"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            cursor.execute('''
                UPDATE marriage_proposals 
                SET is_active = FALSE 
                WHERE proposer_id = ? AND target_id = ? AND chat_id = ?
            ''', (proposer_id, target_id, chat_id))
            
            cursor.execute('''
                INSERT INTO marriage_proposals (proposer_id, target_id, chat_id, message_id, created_at)
                VALUES (?, ?, ?, ?, datetime('now'))
            ''', (proposer_id, target_id, chat_id, message_id))
            
            conn.commit()
            conn.close()
            logger.info(f"Предложение брака создано: {proposer_id} -> {target_id} в чате {chat_id}")
            return True
        except Exception as e:
            logger.error(f"Ошибка при создании предложения брака: {e}")
            return False
    
    def deactivate_marriage_proposal(self, proposal_id):
        """Деактивировать предложение о браке"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            cursor.execute('''
                UPDATE marriage_proposals 
                SET is_active = FALSE 
                WHERE id = ?
            ''', (proposal_id,))
            
            conn.commit()
            conn.close()
            logger.info(f"Предложение брака деактивировано: {proposal_id}")
            return True
        except Exception as e:
            logger.error(f"Ошибка при деактивации предложения брака: {e}")
            return False
    
    def get_active_proposal(self, proposer_id, target_id, chat_id):
        """Получить активное предложение между пользователями"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT * FROM marriage_proposals 
                WHERE proposer_id = ? AND target_id = ? AND chat_id = ? AND is_active = TRUE
            ''', (proposer_id, target_id, chat_id))
            
            proposal = cursor.fetchone()
            conn.close()
            return proposal
        except Exception as e:
            logger.error(f"Ошибка при получении предложения брака: {e}")
            return None
    
    def get_old_proposals(self, minutes=20):
        """Получить устаревшие предложения"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            time_threshold = datetime.now() - timedelta(minutes=minutes)
            
            cursor.execute('''
                SELECT * FROM marriage_proposals 
                WHERE is_active = TRUE AND datetime(created_at) < datetime(?)
            ''', (time_threshold.strftime('%Y-%m-%d %H:%M:%S'),))
            
            old_proposals = cursor.fetchall()
            conn.close()
            return old_proposals
        except Exception as e:
            logger.error(f"Ошибка при получении устаревших предложений: {e}")
            return []
    
    def get_user_active_proposals(self, user_id, chat_id):
        """Получить активные предложения пользователя в чате"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT * FROM marriage_proposals 
                WHERE proposer_id = ? AND chat_id = ? AND is_active = TRUE
            ''', (user_id, chat_id))
            
            proposals = cursor.fetchall()
            conn.close()
            return proposals
        except Exception as e:
            logger.error(f"Ошибка при получении активных предложений пользователя: {e}")
            return []

# Создаем глобальный экземпляр базы данных
db = Database()
