import serial
import serial.tools.list_ports
import sqlite3
import datetime
import time
import threading
from typing import Optional, Tuple

class NFCServer:
    def __init__(self):
        self.serial_port = self.find_arduino_port()
        self.baudrate = 9600
        self.ser = None
        self.registration_mode = False
        self.master_key = "34B226517F9E36"  #master-key
        
    def find_arduino_port(self):
        """Автоматический поиск порта Arduino"""
        ports = serial.tools.list_ports.comports()
        
        print("Searching for Arduino...")
        for port in ports:
            print(f"Found: {port.device} - {port.description}")
            
            # проверяем common Arduino descriptions
            if any(keyword in port.description.lower() for keyword in 
                  ['arduino', 'ch340', 'usb serial', 'com3', 'com4']):
                print(f"✅ Arduino detected on: {port.device}")
                return port.device
        
        # пробуем COM3
        print("⚠️  Arduino not auto-detected, trying COM3")
        return 'COM3'
    
    def init_database(self):
        """Инициализация базы данных"""
        conn = sqlite3.connect('nfc_database.db')
        c = conn.cursor()
        
        c.execute('''CREATE TABLE IF NOT EXISTS users
                    (id INTEGER PRIMARY KEY AUTOINCREMENT,
                     uid TEXT UNIQUE,
                     name TEXT,
                     created_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
        
        c.execute('''CREATE TABLE IF NOT EXISTS access_logs
                    (id INTEGER PRIMARY KEY AUTOINCREMENT,
                     uid TEXT,
                     action TEXT,
                     timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
        
        conn.commit()
        conn.close()
        print("Database initialized")
    
    def connect_serial(self):
        """Подключение к Arduino с повторными попытками"""
        max_retries = 5
        for attempt in range(max_retries):
            try:
                print(f"Attempt {attempt + 1} to connect to {self.serial_port}...")
                self.ser = serial.Serial(self.serial_port, self.baudrate, timeout=1)
                time.sleep(2)  # ждем инициализации Arduino
                print(f"✅ Connected to {self.serial_port} at {self.baudrate} baud")
                return True
                
            except serial.SerialException as e:
                print(f"❌ Attempt {attempt + 1} failed: {e}")
                
                if attempt < max_retries - 1:
                    print("Waiting 3 seconds before retry...")
                    time.sleep(3)
                    
                    # пробуем найти порт заново
                    self.serial_port = self.find_arduino_port()
        
        print("❌ All connection attempts failed")
        return False

   
    def log_access(self, uid: str, action: str):
        """Логирование действий"""
        conn = sqlite3.connect('nfc_database.db')
        c = conn.cursor()
        c.execute("INSERT INTO access_logs (uid, action) VALUES (?, ?)", 
                 (uid, action))
        conn.commit()
        conn.close()
    
    def handle_uid(self, uid: str) -> Tuple[str, str]:
        """Обработка UID карты"""
        print(f"Processing UID: {uid}")
        
        # проверяем мастер-ключ
        if uid == self.master_key:
            self.registration_mode = not self.registration_mode
            mode_status = "ACTIVE" if self.registration_mode else "INACTIVE"
            response = f"MASTER_KEY:{mode_status}"
            action = f"Registration mode {mode_status}"
            print(f"Master key - Registration mode: {mode_status}")
        
        elif self.registration_mode:
            # режим регистрации - регистрируем новую карту
            result = self.register_user(uid)
            response = f"REGISTERED:{result}"
            action = f"Registered: {result}"
        
        else:
            # проверка доступа
            user = self.check_user(uid)
            if user:
                response = f"ACCESS_GRANTED:{user}"
                action = f"Access granted: {user}"
            else:
                response = "ACCESS_DENIED"
                action = "Access denied"
        
        # логируем 
        self.log_access(uid, action)
        return response, action
    
    def register_user(self, uid: str) -> str:
        """Регистрация нового пользователя"""
        conn = sqlite3.connect('nfc_database.db')
        c = conn.cursor()
        
        # проверяем, не зарегистрирован ли уже
        c.execute("SELECT name FROM users WHERE uid=?", (uid,))
        existing = c.fetchone()
        
        if existing:
            conn.close()
            return f"Already registered as {existing[0]}"
        
        # регистрируем нового пользователя
        user_name = f"User_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}"
        try:
            c.execute("INSERT INTO users (uid, name) VALUES (?, ?)", 
                     (uid, user_name))
            conn.commit()
            conn.close()
            return user_name
        except sqlite3.IntegrityError:
            conn.close()
            return "Registration failed"
    
    def check_user(self, uid: str) -> Optional[str]:
        """Проверка зарегистрированного пользователя"""
        conn = sqlite3.connect('nfc_database.db')
        c = conn.cursor()
        c.execute("SELECT name FROM users WHERE uid=?", (uid,))
        user = c.fetchone()
        conn.close()
        
        return user[0] if user else None
    
    def send_to_arduino(self, message: str):
        """Отправка сообщения в Arduino"""
        if self.ser and self.ser.is_open:
            try:
                self.ser.write(f"{message}\n".encode('utf-8'))
                print(f"Sent to Arduino: {message}")
            except serial.SerialException as e:
                print(f"Send error: {e}")
    
    def list_users(self):
        """Показать всех пользователей"""
        conn = sqlite3.connect('nfc_database.db')
        c = conn.cursor()
        c.execute("SELECT * FROM users ORDER BY created_date DESC")
        users = c.fetchall()
        conn.close()
        
        print("\n=== REGISTERED USERS ===")
        for user in users:
            print(f"ID: {user[0]}, UID: {user[1]}, Name: {user[2]}, Created: {user[3]}")
        print(f"Total: {len(users)} users\n")
    
    def monitor_serial(self):
        """Мониторинг Serial порта"""
        print("Starting serial monitor...")
        
        while True:
            try:
                if self.ser and self.ser.in_waiting > 0:
                    line = self.ser.readline().decode('utf-8').strip()
                    
                    if line.startswith("UID:"):
                        uid = line[4:]  # извлекаем UID после "UID:"
                        print(f"\nReceived UID: {uid}")
                        
                        # обрабатываем UID
                        response, action = self.handle_uid(uid)
                        
                        # отправляем ответ в Arduino
                        self.send_to_arduino(response)
                        
                        # выводим в консоль
                        print(f"Action: {action}")
                        print(f"Response: {response}")
                        print("-" * 40)
                
                time.sleep(0.1)
                
            except KeyboardInterrupt:
                print("\nStopping server...")
                break
            except Exception as e:
                print(f"Error in monitor: {e}")
                time.sleep(1)
    
    def start(self):
        """Запуск сервера"""
        print("=== NFC Access Control System ===")
        print(f"Master Key UID: {self.master_key}")
        print("Commands: 'users' - show users, 'exit' - quit")
        print("=" * 50)
        
        
        self.init_database()
        
        if not self.connect_serial():
            print("❌ Failed to connect to Arduino")
            print("\nTroubleshooting steps:")
            print("1. Close Arduino IDE and Serial Monitor")
            print("2. Disconnect and reconnect Arduino")
            print("3. Check Device Manager for correct COM port")
            print("4. Try running as Administrator")
            return
        
        # запускаем мониторинг в отдельном потоке
        monitor_thread = threading.Thread(target=self.monitor_serial, daemon=True)
        monitor_thread.start()
        
        # основной цикл для команд
        try:
            while True:
                command = input().strip().lower()
                
                if command == 'users':
                    self.list_users()
                elif command == 'exit':
                    break
                elif command == 'status':
                    status = "ACTIVE" if self.registration_mode else "INACTIVE"
                    print(f"Registration mode: {status}")
                elif command == 'clear':
                    confirm = input("Clear all users? (y/n): ")
                    if confirm.lower() == 'y':
                        conn = sqlite3.connect('nfc_database.db')
                        c = conn.cursor()
                        c.execute("DELETE FROM users")
                        conn.commit()
                        conn.close()
                        print("All users cleared")
                else:
                    print("Unknown command. Available: users, status, clear, exit")
        
        except KeyboardInterrupt:
            print("\nShutting down...")
        
        finally:
            if self.ser:
                self.ser.close()

if __name__ == '__main__':
    server = NFCServer()

    server.start()
