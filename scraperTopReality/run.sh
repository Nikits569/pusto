#!/bin/bash
set -e

source /var/www/app/pusto/pusto/venv/bin/activate

cd /var/www/app/pusto/scraperTopReality

python checker.py
python topReality.py
python translate.py
python tunel.py