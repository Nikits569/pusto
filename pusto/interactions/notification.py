import smtplib
from email.mime.text import MIMEText
from pathlib import Path
from dotenv import load_dotenv
import os
import pymysql
from config import DB_CONFIG

# .env лежит в /var/www/app/pusto/.env (на уровень выше папки pusto/pusto)
BASE_DIR = Path(__file__).resolve().parent.parent  # это /var/www/app/pusto/pusto
load_dotenv(BASE_DIR.parent / ".env")

EMAIL_HOST = "smtp.gmail.com"
EMAIL_PORT = 587
EMAIL_HOST_USER = os.getenv("EMAIL_HOST_USER")
EMAIL_HOST_PASSWORD = os.getenv("EMAIL_HOST_PASSWORD")


def send_mail(subject, message, to_email):
    msg = MIMEText(message, 'plain', 'utf-8')
    msg['Subject'] = subject
    msg['From'] = EMAIL_HOST_USER
    msg['To'] = to_email

    with smtplib.SMTP(EMAIL_HOST, EMAIL_PORT) as server:
        server.starttls()
        server.login(EMAIL_HOST_USER, EMAIL_HOST_PASSWORD)
        server.send_message(msg)

connect = pymysql.connect(**DB_CONFIG)

# обычные поля с равенством (без budget_from/budget_to)
notification_map = {
    'city': 'city',
    'category_id': 'productCategory',
    'rooms': 'rooms',
    'caseType': 'type'
}

try:
    with connect.cursor() as cursor:

        cursor.execute('''
        SELECT * FROM interactions_notification
        ''')

        notification = {}

        for i in cursor.fetchall():
            for j in i:
                if i[j] is None:
                    continue
                if i['id'] not in notification:
                    notification[i['id']] = {}
                notification[i['id']][j] = i[j]

            # определяем таблицу и имя колонки для бюджета
            if i['type'] in ('sell_category', 'buy_category'):
                db = 'ads_thingspost'
                budget_column = 'price'
                url_segment = 'things'
            elif i['type'] in ('findNeighbor', 'rent'):
                db = 'ads_neighborpost'
                budget_column = 'budget'
                url_segment = 'neighbors'
            else:
                continue

            row = notification[i['id']]

            exist = {}
            for y in notification_map.keys():
                if y in row:
                    exist[notification_map[y]] = row[y]

            conditions = [f'{key} = %s' for key in exist.keys()]
            values = list(exist.values())

            budget_from = row.get('budget_from')
            budget_to = row.get('budget_to')

            if budget_from is not None:
                conditions.append(f'{budget_column} >= %s')
                values.append(budget_from)

            if budget_to is not None:
                conditions.append(f'{budget_column} <= %s')
                values.append(budget_to)

            if not conditions:
                continue

            where_clause = ' AND '.join(conditions)

            print('------------------------- new --------------------------')

            cursor.execute(f'''
                SELECT * FROM {db} WHERE caseType = %s AND {where_clause} ORDER BY created_at DESC LIMIT 1
            ''', [i['type']] + values)
            post = cursor.fetchall()

            if not post:
                continue

            cursor.execute('''
                SELECT * FROM interactions_notification 
                WHERE (last_checked_id IS NULL OR last_checked_id != %s) AND id = %s
            ''', (post[0]['id'], i['id']))
            check = cursor.fetchall()

            if check:

                cursor.execute('''
                    UPDATE interactions_notification SET last_checked_id = %s WHERE id = %s
                ''', (post[0]['id'], i['id']))
                connect.commit()
                price_value = post[0][budget_column]

                # Название категории по id
                category_name = None
                if 'productCategory' in exist:
                    cursor.execute('SELECT title_uk FROM ads_category WHERE id = %s', (exist['productCategory'],))
                    cat_result = cursor.fetchone()
                    if cat_result:
                        category_name = cat_result['title_uk']

                # Собираем читаемое описание параметров фильтра
                filter_lines = []
                if 'city' in exist:
                    filter_lines.append(f"Місто: {exist['city']}")
                if category_name:
                    filter_lines.append(f"Категорія: {category_name}")
                elif 'productCategory' in exist:
                    filter_lines.append(f"Категорія: {exist['productCategory']}")
                if 'rooms' in exist:
                    filter_lines.append(f"Кімнати: {exist['rooms']}")
                if 'type' in exist:
                    filter_lines.append(f"Тип: {exist['type']}")
                if budget_from is not None or budget_to is not None:
                    if budget_from is not None and budget_to is not None:
                        filter_lines.append(f"Бюджет: {budget_from}€ - {budget_to}€")
                    elif budget_from is not None:
                        filter_lines.append(f"Бюджет: від {budget_from}€")
                    else:
                        filter_lines.append(f"Бюджет: до {budget_to}€")

                filter_text = "\n".join(filter_lines)

                message = f"""Знайдено нове оголошення за вашим фільтром!

                Ваші параметри пошуку:
                {filter_text}

                Оголошення:
                {post[0]['title']}
                Ціна: {price_value}€

                Переглянути оголошення:
                https://pusto.sk/uk/page/{url_segment}/{post[0]['slug_title']}-{post[0]['id']}

                Якщо ви більше не хочете отримувати такі сповіщення, відповідьте на цей лист з проханням відключити фільтр, або напишіть нам на сайті.
                """

                send_mail(
                    subject=f"Нове оголошення: {post[0]['title']}",
                    message=message,
                    to_email=i['email'],
                )
                print(post)
            print('-------------')

finally:
    connect.close()