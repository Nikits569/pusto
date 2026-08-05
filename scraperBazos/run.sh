#!/bin/bash
set -e

source /var/www/app/pusto/pusto/venv/bin/activate

cd /var/www/app/pusto/scraperBazos

python main.py
python translate.py
python GPTfilter/main.py
python tunel.py
