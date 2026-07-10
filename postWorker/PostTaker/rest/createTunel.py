from sshtunnel import SSHTunnelForwarder
import time

SERVER_IP = ""
SSH_PORT = 0
SSH_USER = ""
SSH_PASSWORD = ""

REMOTE_DB_HOST = ""
REMOTE_DB_PORT = 0

LOCAL_BIND_HOST = ""
LOCAL_BIND_PORT = 0

print("Запуск SSH-туннеля...")

try:
    with SSHTunnelForwarder(
        (SERVER_IP, SSH_PORT),
        ssh_username=SSH_USER,
        ssh_password=SSH_PASSWORD,
        remote_bind_address=(REMOTE_DB_HOST, REMOTE_DB_PORT),
        local_bind_address=(LOCAL_BIND_HOST, LOCAL_BIND_PORT),
    ) as tunnel:
        print("Туннель запущен")
        print(f"Локальный адрес: {LOCAL_BIND_HOST}:{tunnel.local_bind_port}")
        print("Теперь Django может подключаться к БД через 127.0.0.1:13307")

        while True:
            time.sleep(1)

except Exception as e:
    print("Ошибка:",)