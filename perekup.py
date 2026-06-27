import os

token = os.getenv("8879391155:AAE10A4-uCQMRboGPSJSKze19V2-FXKe77I")

print("=== ПРОВЕРКА ТОКЕНА ===")
if token:
    print(f"✅ Токен найден!")
    print(f"Длина токена: {len(token)} символов")
    print(f"Первые 10 символов: {token[:10]}...")
    print(f"Содержит двоеточие: {':' in token}")
else:
    print("❌ Токен НЕ НАЙДЕН!")
    print("Переменная BOT_TOKEN пустая или отсутствует")
