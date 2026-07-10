from db import cursor, conn

def init_db_schema():
    # Инициализация таблиц базы данных.
    # При запуске парсер сам создаёт нужные таблицы, если они ещё не существуют.

    # Таблица объявлений категории "товары".
    #cursor.execute("""
    #    CREATE TABLE IF NOT EXISTS products (
    #        id INT AUTO_INCREMENT PRIMARY KEY,
    #        chat_id VARCHAR(255),
    #        user_id VARCHAR(255),
    #        message_id VARCHAR(255),
    #        timePost DATETIME,
    #        chat_title VARCHAR(255),
    #        text TEXT,
    #        price VARCHAR(255),
    #        city VARCHAR(255),
    #        contact_telegram VARCHAR(255),
#
    #        has_photo BOOLEAN NOT NULL DEFAULT 0,
    #        photo_id VARCHAR(255),
    #        photo_hash VARCHAR(255),
#
    #        preview_image VARCHAR(255) NULL,
#
    #        categoria VARCHAR(255) DEFAULT 'NONE'
    #    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    #    """)

    # Таблица объявлений категории "работа".
    # cursor.execute("""
    # CREATE TABLE IF NOT EXISTS jobs(
    #    id INT AUTO_INCREMENT PRIMARY KEY,
    #    chat_id VARCHAR(255),
    #    user_id VARCHAR(255),
    #    message_id VARCHAR(255),
    #    timePost DATETIME,
    #    chat_title VARCHAR(255),
    #    text TEXT,
    #    salary VARCHAR(255),
    #    city VARCHAR(255),
    #    contact_telegram VARCHAR(255),
    #
    #    has_photo BOOLEAN NOT NULL DEFAULT 0,
    #    photo_id VARCHAR(255),
    #    photo_hash VARCHAR(255),
    #
    #    preview_image VARCHAR(255) NULL,
    #
    #    categoria VARCHAR(255) DEFAULT 'NONE'
    # ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    # """)

    # Таблица объявлений категории "соседи".
    #cursor.execute("""
    #    CREATE TABLE IF NOT EXISTS neighbors (
    #        id INT AUTO_INCREMENT PRIMARY KEY,
    #        chat_id VARCHAR(255),
    #        user_id VARCHAR(255),
    #        message_id VARCHAR(255),
    #        timePost DATETIME,
    #        chat_title VARCHAR(255),
    #        text TEXT,
    #        budget VARCHAR(255),
    #        city VARCHAR(255),
    #        contact_telegram VARCHAR(255),
#
    #        has_photo BOOLEAN NOT NULL DEFAULT 0,
    #        photo_id VARCHAR(255),
    #        photo_hash VARCHAR(255),
#
    #        preview_image VARCHAR(255) NULL,
#
    #        categoria VARCHAR(255) DEFAULT 'NONE'
    #    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    #    """)

    # Таблица хэшей изображений.
    # Нужна для отслеживания дубликатов фото между объявлениями.

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS base (
            id INT AUTO_INCREMENT PRIMARY KEY,
            chat_id VARCHAR(255),
            user_id VARCHAR(255),
            message_id VARCHAR(255),
            timePost DATETIME,
            chat_title VARCHAR(255),
            text TEXT,
            price VARCHAR(255),
            city VARCHAR(255), 
            contact_telegram VARCHAR(255),

            has_photo BOOLEAN NOT NULL DEFAULT 0,
            photo_id VARCHAR(255),
            photo_hash VARCHAR(255),

            preview_image VARCHAR(255) NULL,

            categoria VARCHAR(255) DEFAULT 'NONE'
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS hashes (
            id INT AUTO_INCREMENT PRIMARY KEY,
            photo_hash VARCHAR(255)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        """)
    conn.commit()

