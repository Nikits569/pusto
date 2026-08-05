#!/bin/bash
set -ex

source /var/www/app/pusto/pusto/venv/bin/activate
cd /var/www/app/pusto/scraperReality

echo "===== $(date) ====="
which python
python --version
pwd

python checker.py
python reality.py
python translate.py
python tunel.py