# Отслеживаемые чаты и темы.
# Ключ верхнего уровня — категория объявления.
# Значение — словарь chat_id -> topic_id.
# Если topic_id = None, отслеживается весь чат без темы.

target_chats = {
    4936692115: [None],
    1175233956: [None],
    1956832493: [None],
    2091082928: [None],
    2101692521: [None],
    1912835249: [14756],

    1386423654: [177319, 193366],

    1274583303: [51851, 51849],

    2240457831: [18915, 27, 26],
    1764112838: [112, 111, 82],

    2766446415: [None],
    1840072195: [None],

    1974415585: [6, 7, 8, 48143, 43167, 26112],

    2149548602: [None],
    2013028399: [2],
    1612101159: [4871, 6057, 4505, 1],


}

# Справочная информация по чатам.
# Для каждого chat_id храним человекочитаемое название и город.
2240457831
infoChats = {
    4936692115: ['TestScraping', 'Presov'],
    1175233956: ['https://t.me/baraholka_presov_kosice', 'Presov'],
    1956832493: ['https://t.me/kosiceflats', 'Kosice'],
    2091082928: ['https://t.me/arenda_nitra', 'Nitra'],
    2101692521: ['https://t.me/baraholka_nitra', 'Nitra'],
    1912835249: ['https://t.me/nitra_hack', 'Nitra'],
    1386423654: ['https://t.me/tuke_hack', 'Kosice'],
    1274583303: ['https://t.me/kosice_hack', 'Kosice'],
    2240457831: ['https://t.me/DreamCityGroupSro', 'Bratislava'],
    1764112838: ['https://t.me/GoldKeyBratislava', 'Bratislava'],
    2766446415: ['https://t.me/NashaBratislava', 'Bratislava'],
    1840072195: ['https://t.me/rent_slovakia', 'Bratislava'],
    1974415585: ['https://t.me/GoldKeyKosice', 'Kosice'],
    2149548602: ['https://t.me/prenajom_v_Kosice', 'Kosice'],
    2013028399: ['https://t.me/rent_kosice', 'Kosice'],
    1612101159: ['t.me/realestateSlovensko', 'Kosice'],

}



infoTopic = {
    18915: '1',
    27: '2',

    112: '1',
    111: '2',
}

# Список всех chat_id, которые слушает клиент.
all_ids = [chats for chats in target_chats.keys()]

