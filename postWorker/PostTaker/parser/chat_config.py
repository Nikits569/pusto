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
    5007496260: [None],
    1840072195: [None],
    3752323083: [None],
}

# Справочная информация по чатам.
# Для каждого chat_id храним человекочитаемое название и город.
infoChats = {
    4936692115: ['TestScraping', 'Presov'], #
    1175233956: ['Барахолка Presov', 'Presov'], #
    1386423654: ['Tuke', 'Kosice'], #
    1274583303: ['Kosice', 'Kosice'], #
    5073870568: ['TestScrapingJob', 'Presov'], #
    5007496260: ['TestScrapingNeighbors', 'Presov'],
    1840072195: ['BratislavaRent', 'Bratislava'], #
    2766446415: ['NashaBratislava', 'Bratislava'], #
    1666679455: ['Job', 'Bratislava'],  #
    3752323083: ['TestBratislavaPusto', 'TestBratislava'], #
    1956832493: ['Rent', 'Kosice'],  #
    2091082928: ['Rent', 'Nitra'], #
    2101692521: ['Baracholka', 'Nitra'], #
    1912835249: ['BaracholkaOther', 'Nitra'], #
    2240457831: ['BratislavaDreamCity', 'Bratislava'], #
    1764112838: ['BratislavaGoldKey', 'Bratislava'],


}

infoTopic = {
    18915: '1',
    27: '2',

    112: '1',
    111: '2',
}

# Список всех chat_id, которые слушает клиент.
all_ids = [chats for chats in target_chats.keys()]
