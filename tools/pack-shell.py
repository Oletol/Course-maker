#!/usr/bin/env python3
"""Упаковывает папку shell в один файл assets/shell-files.js для страницы мастер-класса.

Страница читает этот файл, подставляет ключи Firebase участника и собирает архив
в браузере. Запуск из папки Course–maker: python3 tools/pack-shell.py
"""
import base64, gzip, json, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "shell"
OUT = ROOT / "assets" / "shell-files.js"

README = """# Оболочка курса

Файлы сайта курса. Что с ними делать:

1. Создайте на github.com новый публичный репозиторий.
2. Add file, Upload files, перетащите в окно папку `docs` и файл `firestore.rules`, Commit changes.
3. Settings, Pages, Deploy from a branch, ветка main, папка /docs, Save.
4. Через две-три минуты откройте `https://ВАШ-ЛОГИН.github.io/ИМЯ-РЕПОЗИТОРИЯ/setup.html`
   и пройдите шаги оттуда: эта страница сама проверяет каждый шаг.

Ключи Firebase уже вписаны в `docs/js/firebase-config.js`.

---

# Course shell

The files of your course website. What to do with them:

1. Create a new public repository on github.com.
2. Add file, Upload files, drag the `docs` folder and the file `firestore.rules` in, Commit changes.
3. Settings, Pages, Deploy from a branch, branch main, folder /docs, Save.
4. In two or three minutes open `https://YOUR-LOGIN.github.io/YOUR-REPOSITORY/setup.html`
   and follow the steps there: that page checks each step for you.

Your Firebase keys are already in `docs/js/firebase-config.js`.
"""

if not SRC.is_dir():
    sys.exit(f"Нет папки {SRC}. Сначала запустите tools/trim-shell.py")

files = {}
for p in sorted(SRC.rglob("*")):
    if not p.is_file() or p.name.startswith("."):
        continue
    files[str(p.relative_to(SRC))] = p.read_text(encoding="utf-8")
files["README.md"] = README

raw = json.dumps(files, ensure_ascii=False).encode("utf-8")
packed = base64.b64encode(gzip.compress(raw, 9)).decode("ascii")
OUT.parent.mkdir(parents=True, exist_ok=True)
OUT.write_text(
    "// Файлы оболочки для раздела «Готовая оболочка». Собран скриптом tools/pack-shell.py,\n"
    "// править руками не нужно. Внутри — JSON {путь: содержимое}, сжатый gzip и закодированный base64.\n"
    f"window.SHELL_PACK = \"{packed}\";\n", encoding="utf-8")
print(f"{len(files)} файлов, {len(raw) // 1024} КБ текста -> {OUT.stat().st_size // 1024} КБ в {OUT.name}")
