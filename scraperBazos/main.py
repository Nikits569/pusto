from page_config import pages, pages_item
from handlers import parse_city


def main():
    for city, url in pages.items():
        parse_city(city, url, 'reality')

    for city, categories in pages_item.items():
        for url, category in categories.items():
            parse_city(city, url, category)

if __name__ == "__main__":
    main()