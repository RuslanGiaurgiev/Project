from flask import Flask, request, jsonify, render_template
import sqlite3
import datetime
import threading
import time
from typing import Optional, Tuple
import logging

# Настройка логирования
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

app = Flask(__name__)

class NFCSystem:
    def __init__(self):
        self.master_key = "34B226517F9E36"  # ⬅️ ЗАМЕНИ НА СВОЙ UID МАСТЕР-КАРТЫ
        self.registration_mode = False
        self.access_log = []
        self.init_database()
    
    def init_database(self):
        """Инициализация базы данных"""
        conn = sqlite3.connect('nfc_database.db', check_same_thread=False)
        c = conn.cursor()
        
        # Таблица пользователей
        c.execute('''CREATE TABLE IF NOT EXISTS users
                    (id INTEGER PRIMARY KEY AUTOINCREMENT,
                     uid TEXT UNIQUE NOT NULL,
                     name TEXT NOT NULL,
                     created_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
        
        # Таблица мастер-ключей
        c.execute('''CREATE TABLE IF NOT EXISTS master_keys
                    (uid TEXT PRIMARY KEY,
                     description TEXT)''')
        
        # Таблица логов доступа
        c.execute('''CREATE TABLE IF NOT EXISTS access_logs
                    (id INTEGER PRIMARY KEY AUTOINCREMENT,
                     uid TEXT NOT NULL,
                     action TEXT NOT NULL,
                     result TEXT NOT NULL,
                     timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
        
        # Добавляем мастер-ключ если его нет
        c.execute("INSERT OR IGNORE INTO master_keys (uid, description) VALUES (?, ?)",
                 (self.master_key, "Main Master Key"))
        
        conn.commit()
        conn.close()
        logger.info("Database initialized")
    
    def log_access(self, uid: str, action: str, result: str):
        """Логирование действий в базу данных"""
        conn = sqlite3.connect('nfc_database.db', check_same_thread=False)
        c = conn.cursor()
        c.execute("INSERT INTO access_logs (uid, action, result) VALUES (?, ?, ?)",
                 (uid, action, result))
        conn.commit()
        conn.close()
        
        # Также сохраняем в оперативной памяти для веб-интерфейса
        log_entry = {
            'timestamp': datetime.datetime.now().strftime('%H:%M:%S'),
            'uid': uid,
            'action': action,
            'result': result
        }
        self.access_log.append(log_entry)
        
        # Ограничиваем размер лога
        if len(self.access_log) > 100:
            self.access_log.pop(0)
        
        logger.info(f"Access log: {uid} - {action} - {result}")
    
    def handle_nfc_scan(self, uid: str) -> Tuple[str, str]:
        """Обработка сканирования NFC карты"""
        logger.info(f"Processing UID: {uid}")
        
        # Проверяем мастер-ключ
        if uid == self.master_key:
            self.registration_mode = not self.registration_mode
            mode_status = "ACTIVE" if self.registration_mode else "INACTIVE"
            response = f"MASTER_KEY:{mode_status}"
            action = "Master key authentication"
            result = f"Registration mode {mode_status}"
            
            self.log_access(uid, action, result)
            return response, result
        
        # Режим регистрации - регистрируем новую карту
        elif self.registration_mode:
            user_name = self.register_user(uid)
            response = f"REGISTERED:{user_name}"
            action = "User registration"
            result = f"Registered as {user_name}"
            
            self.log_access(uid, action, result)
            return response, result
        
        # Обычная проверка доступа
        else:
            user_info = self.check_user_access(uid)
            if user_info:
                response = f"ACCESS_GRANTED:{user_info}"
                action = "Access check"
                result = f"Access granted to {user_info}"
            else:
                response = "ACCESS_DENIED"
                action = "Access check"
                result = "Access denied - unknown card"
            
            self.log_access(uid, action, result)
            return response, result
    
    def register_user(self, uid: str) -> str:
        """Регистрация нового пользователя"""
        conn = sqlite3.connect('nfc_database.db', check_same_thread=False)
        c = conn.cursor()
        
        # Проверяем, не зарегистрирован ли уже
        c.execute("SELECT name FROM users WHERE uid = ?", (uid,))
        existing_user = c.fetchone()
        
        if existing_user:
            conn.close()
            return f"Already registered as {existing_user[0]}"
        
        # Создаем уникальное имя пользователя
        timestamp = datetime.datetime.now().strftime('%m%d%H%M%S')
        user_name = f"User_{timestamp}"
        
        try:
            c.execute("INSERT INTO users (uid, name) VALUES (?, ?)", (uid, user_name))
            conn.commit()
            conn.close()
            logger.info(f"New user registered: {user_name} (UID: {uid})")
            return user_name
        except sqlite3.IntegrityError as e:
            conn.close()
            logger.error(f"Registration error: {e}")
            return "Registration failed - user exists"
    
    def check_user_access(self, uid: str) -> Optional[str]:
        """Проверка доступа пользователя"""
        conn = sqlite3.connect('nfc_database.db', check_same_thread=False)
        c = conn.cursor()
        c.execute("SELECT name FROM users WHERE uid = ?", (uid,))
        user = c.fetchone()
        conn.close()
        
        return user[0] if user else None
    
    def get_all_users(self):
        """Получение списка всех пользователей"""
        conn = sqlite3.connect('nfc_database.db', check_same_thread=False)
        c = conn.cursor()
        c.execute("SELECT * FROM users ORDER BY created_date DESC")
        users = c.fetchall()
        conn.close()
        
        user_list = []
        for user in users:
            user_list.append({
                'id': user[0],
                'uid': user[1],
                'name': user[2],
                'created_date': user[3]
            })
        
        return user_list
    
    def get_access_logs(self, limit: int = 50):
        """Получение логов доступа"""
        conn = sqlite3.connect('nfc_database.db', check_same_thread=False)
        c = conn.cursor()
        c.execute("SELECT * FROM access_logs ORDER BY timestamp DESC LIMIT ?", (limit,))
        logs = c.fetchall()
        conn.close()
        
        log_list = []
        for log in logs:
            log_list.append({
                'id': log[0],
                'uid': log[1],
                'action': log[2],
                'result': log[3],
                'timestamp': log[4]
            })
        
        return log_list
    
    def delete_user(self, user_id: int) -> bool:
        """Удаление пользователя"""
        try:
            conn = sqlite3.connect('nfc_database.db', check_same_thread=False)
            c = conn.cursor()
            c.execute("DELETE FROM users WHERE id = ?", (user_id,))
            conn.commit()
            conn.close()
            logger.info(f"User {user_id} deleted")
            return True
        except Exception as e:
            logger.error(f"Error deleting user: {e}")
            return False
    
    def get_system_status(self):
        """Получение статуса системы"""
        conn = sqlite3.connect('nfc_database.db', check_same_thread=False)
        c = conn.cursor()
        
        c.execute("SELECT COUNT(*) FROM users")
        user_count = c.fetchone()[0]
        
        c.execute("SELECT COUNT(*) FROM access_logs WHERE date(timestamp) = date('now')")
        today_scans = c.fetchone()[0]
        
        conn.close()
        
        return {
            'registration_mode': self.registration_mode,
            'total_users': user_count,
            'scans_today': today_scans,
            'master_key': self.master_key,
            'server_uptime': get_uptime()
        }

# Глобальный экземпляр системы
nfc_system = NFCSystem()

# Время запуска сервера
start_time = datetime.datetime.now()

def get_uptime():
    """Получение времени работы сервера"""
    uptime = datetime.datetime.now() - start_time
    hours, remainder = divmod(int(uptime.total_seconds()), 3600)
    minutes, seconds = divmod(remainder, 60)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}"

# ==================== FLASK ROUTES ====================

@app.route('/')
def index():
    """Главная страница с веб-интерфейсом"""
    system_status = nfc_system.get_system_status()
    recent_logs = nfc_system.get_access_logs(10)
    
    return render_template('index.html', 
                         status=system_status,
                         logs=recent_logs,
                         registration_mode=nfc_system.registration_mode)

@app.route('/nfc', methods=['POST'])
def handle_nfc():
    """Основной endpoint для обработки NFC запросов"""
    try:
        uid = request.form.get('uid')
        
        if not uid:
            return "ERROR: No UID provided", 400
        
        logger.info(f"Received NFC scan: {uid}")
        
        response, result = nfc_system.handle_nfc_scan(uid)
        return response
        
    except Exception as e:
        logger.error(f"Error processing NFC request: {e}")
        return "ERROR: Internal server error", 500

@app.route('/api/users', methods=['GET'])
def get_users():
    """API для получения списка пользователей"""
    users = nfc_system.get_all_users()
    return jsonify(users)

@app.route('/api/users/<int:user_id>', methods=['DELETE'])
def delete_user(user_id):
    """API для удаления пользователя"""
    if nfc_system.delete_user(user_id):
        return jsonify({"status": "success", "message": "User deleted"})
    else:
        return jsonify({"status": "error", "message": "Failed to delete user"}), 500

@app.route('/api/logs', methods=['GET'])
def get_logs():
    """API для получения логов"""
    limit = request.args.get('limit', 50, type=int)
    logs = nfc_system.get_access_logs(limit)
    return jsonify(logs)

@app.route('/api/status', methods=['GET'])
def get_status():
    """API для получения статуса системы"""
    status = nfc_system.get_system_status()
    return jsonify(status)

@app.route('/api/registration', methods=['POST'])
def toggle_registration():
    """API для переключения режима регистрации"""
    nfc_system.registration_mode = not nfc_system.registration_mode
    mode_status = "ACTIVE" if nfc_system.registration_mode else "INACTIVE"
    
    nfc_system.log_access("SYSTEM", "Registration mode toggle", f"Mode set to {mode_status}")
    
    return jsonify({
        "status": "success",
        "registration_mode": nfc_system.registration_mode,
        "message": f"Registration mode {mode_status}"
    })

@app.route('/api/master_key', methods=['GET'])
def get_master_key():
    """API для получения информации о мастер-ключе"""
    return jsonify({"master_key": nfc_system.master_key})

# ==================== HTML TEMPLATE ====================

@app.route('/template')
def template():
    """Страница с HTML шаблоном для отладки"""
    return '''
    <!DOCTYPE html>
    <html>
    <head>
        <title>NFC Access Control</title>
        <style>
            body { font-family: Arial, sans-serif; margin: 20px; }
            .status { background: #f0f0f0; padding: 15px; border-radius: 5px; margin-bottom: 20px; }
            .log-entry { border-bottom: 1px solid #ddd; padding: 5px 0; }
            .granted { color: green; }
            .denied { color: red; }
            .master { color: blue; }
            .registered { color: orange; }
        </style>
    </head>
    <body>
        <h1>NFC Access Control System</h1>
        
        <div class="status">
            <h3>System Status</h3>
            <p>Registration Mode: <strong id="regStatus">Loading...</strong></p>
            <p>Total Users: <span id="userCount">0</span></p>
            <p>Scans Today: <span id="scanCount">0</span></p>
            <p>Server Uptime: <span id="uptime">00:00:00</span></p>
            <button onclick="toggleRegistration()">Toggle Registration Mode</button>
        </div>
        
        <div>
            <h3>Recent Activity</h3>
            <div id="activityLog"></div>
        </div>
        
        <script>
            function updateStatus() {
                fetch('/api/status')
                    .then(r => r.json())
                    .then(data => {
                        document.getElementById('regStatus').textContent = 
                            data.registration_mode ? 'ACTIVE' : 'INACTIVE';
                        document.getElementById('regStatus').className = 
                            data.registration_mode ? 'registered' : '';
                        document.getElementById('userCount').textContent = data.total_users;
                        document.getElementById('scanCount').textContent = data.scans_today;
                        document.getElementById('uptime').textContent = data.server_uptime;
                    });
                
                fetch('/api/logs?limit=10')
                    .then(r => r.json())
                    .then(logs => {
                        const logDiv = document.getElementById('activityLog');
                        logDiv.innerHTML = logs.map(log => `
                            <div class="log-entry">
                                <strong>${log.timestamp}</strong> - 
                                UID: ${log.uid} - 
                                <span class="${getLogClass(log.result)}">${log.result}</span>
                            </div>
                        `).join('');
                    });
            }
            
            function getLogClass(result) {
                if (result.includes('granted')) return 'granted';
                if (result.includes('denied')) return 'denied';
                if (result.includes('Master')) return 'master';
                if (result.includes('Registered')) return 'registered';
                return '';
            }
            
            function toggleRegistration() {
                fetch('/api/registration', {method: 'POST'})
                    .then(r => r.json())
                    .then(data => {
                        alert(data.message);
                        updateStatus();
                    });
            }
            
            // Обновляем статус каждые 5 секунд
            setInterval(updateStatus, 5000);
            updateStatus();
        </script>
    </body>
    </html>
    '''

# ==================== ЗАПУСК СЕРВЕРА ====================

if __name__ == '__main__':
    logger.info("=== Starting NFC Access Control Server ===")
    logger.info(f"Master Key UID: {nfc_system.master_key}")
    logger.info("Server will run on http://0.0.0.0:8000")
    logger.info("Available endpoints:")
    logger.info("  POST /nfc - Process NFC scan")
    logger.info("  GET  /api/users - Get all users")
    logger.info("  GET  /api/status - Get system status")
    logger.info("  GET  /template - Web interface")
    logger.info("=" * 50)
    
    try:
        app.run(host='0.0.0.0', port=8000, debug=True, threaded=True)
    except KeyboardInterrupt:
        logger.info("Server stopped by user")
    except Exception as e:
        logger.error(f"Server error: {e}")