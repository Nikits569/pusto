#!/bin/bash
set -e

source /var/www/app/pusto/pusto/venv/bin/activate

cd /var/www/app/pusto/scraperReality

python reality.py
python translate.py
python tunel.py