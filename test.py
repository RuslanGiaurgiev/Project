import serial.tools.list_ports

def find_arduino_ports():
    ports = serial.tools.list_ports.comports()
    print("=== Available COM ports ===")
    for port in ports:
        print(f"Port: {port.device}")
        print(f"Description: {port.description}")
        print(f"Hardware ID: {port.hwid}")
        print("-" * 30)
    
    # Ищем Arduino по описанию
    arduino_ports = [
        port.device for port in ports
        if 'arduino' in port.description.lower() or 'ch340' in port.description.lower()
    ]
    
    if arduino_ports:
        print(f"Arduino found on: {arduino_ports[0]}")
        return arduino_ports[0]
    else:
        print("No Arduino found. Available ports:")
        for port in ports:
            print(f"  {port.device} - {port.description}")
        return None

# Замени в основном коде строку подключения на:
port = find_arduino_ports() or 'COM3'