try:
    import serial
    print("✅ pyserial installed successfully")
except ImportError:
    print("❌ pyserial not installed")

try:
    import sqlite3
    print("✅ sqlite3 available (built-in)")
except ImportError:
    print("❌ sqlite3 not available")

try:
    import threading
    print("✅ threading available (built-in)") 
except ImportError:
    print("❌ threading not available")

try:
    import datetime
    print("✅ datetime available (built-in)")
except ImportError:
    print("❌ datetime not available")