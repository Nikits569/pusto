#!/bin/bash
set -e

source /var/www/app/pusto/pusto/venv/bin/activate

cd /var/www/app/pusto/postWorker/PostTaker

python postChecker/checker.py
python GPTfilter/main.py
python translator/translate.py
python tunel/PostTunel1.0.py