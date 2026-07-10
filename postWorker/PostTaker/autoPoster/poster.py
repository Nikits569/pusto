import asyncio
from telegram import Bot
import pymysql
import time
import os

from config import DB_CONFIG, TELEGRAM_POSTER_TOKEN

TABLES = ["base"]
CHAT_ID = '@BaracholkaPustoSK'

interest_ads = [52940, 52526, 52318]
language = 'uk'

bot = Bot(token=TELEGRAM_POSTER_TOKEN)

conn = pymysql.connect(**DB_CONFIG)
cursor = conn.cursor()

def getById(table, id):
    cursor.execute(
        f"select * from `{table}` where id = {id}",
    )

    return cursor.fetchall()

async def send_ads():
    for i in interest_ads:
        total = getById('ads_thingspost', i)[0]

        img = '/var/www/app/pusto/pusto/media/'+total['preview_image']
        print(img)
        price = total['price']
        city = total['city']
        text = total['text']
        link = 'https://pusto.sk/' + language + '/page/things/' + total['slug_title']+'-'+str(total['id'])

        total_msg = '🔥найкращі за сьогодні🔥'+'\n'+'ціна-'+str(price)+'€'+'\n'+'місто:'+city+'\n'+text+'\n'+link

        #await bot.send_message(chat_id=CHAT_ID, text=total_msg)
        await bot.send_photo(chat_id=CHAT_ID, photo=img, caption=total_msg)
        await asyncio.sleep(5000)

async def main():
    await send_ads()

if __name__ == "__main__":
    asyncio.run(main())