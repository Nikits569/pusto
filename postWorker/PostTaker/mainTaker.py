import subprocess
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent

scripts = [
    BASE_DIR / "postChecker" / "checker.py",
    BASE_DIR / "GPTfilter" / "main.py",
    BASE_DIR / "mediaDownloader" / "mediaDownloader.py",
    BASE_DIR / "translator" / "translate.py",
    BASE_DIR / "tunel" / "PostTunel1.0.py",
]

for script in scripts:
    print(f"Запускаю {script}...")
    subprocess.run([sys.executable, str(script)], check=True)

print("Все скрипты выполнены")