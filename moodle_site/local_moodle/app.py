from app import create_app
from pathlib import Path
import urllib.parse
from flask import request, abort, send_file
import os

app = create_app()

app.config['SESSION_COOKIE_NAME'] = 'session5000'

# Корень проекта
BASE_DIR = Path(os.path.dirname(os.path.abspath(__file__))).resolve()

# Полные пути к директориям с файлами
INSTANCE_LABS_DIR = BASE_DIR / "instance" / "labs"
INSTANCE_PROTECTIONS_DIR = BASE_DIR / "instance" / "protections"

# Для проверок используем эти директории
ALLOWED_DIRS = [
    INSTANCE_LABS_DIR,
    INSTANCE_PROTECTIONS_DIR
]

# Запрещённые расширения файлов
FORBIDDEN_EXTENSIONS = {'.py', '.pyc', '.pyo', '.db', '.sqlite', '.sql', 
                        '.env', '.git', '.json', '.yml', '.yaml', '.ini',
                        '.conf', '.config', '.pem', '.key', '.crt', '.log',
                        '.txt', '.md', '.rst', '.csv'}

# Запрещённые паттерны в пути
FORBIDDEN_PATTERNS = ['app/', 'migrations/', '__pycache__/', 'venv/',
                      '.git/', 'config.py', 'requirements.txt', '.idea/',
                      '.vscode/', 'run.py', 'app.py']


@app.before_request
def prevent_path_traversal():
    """Защита от path traversal и доступа к коду"""
    
    # Проверяем только запросы к /files/
    if '/files/' not in request.path:
        return
    
    print("\n" + "="*60)
    print("[BEFORE_REQUEST] Проверка безопасности")
    
    # Извлекаем путь из URL (всё что после /files/)
    path_part = request.path.split('/files/', 1)[-1]
    print(f"[BEFORE_REQUEST] Путь из URL: {path_part}")
    
    if not path_part:
        print("[BEFORE_REQUEST] Путь пустой")
        return
    
    # Декодируем URL (например, %20 -> пробел)
    decoded = urllib.parse.unquote(path_part)
    print(f"[BEFORE_REQUEST] Декодированный путь: {decoded}")
    
    # 1. Блокируем обратные слэши (Windows path traversal)
    if "\\" in decoded:
        print(f"[SECURITY] Блокировка обратного слэша: {decoded}")
        abort(400, "Invalid path: backslash not allowed")
    
    # 2. Проверяем на попытки обхода директорий
    if '..' in decoded.split('/'):
        print(f"[SECURITY] Блокировка обхода директорий: {decoded}")
        abort(400, "Invalid path: directory traversal not allowed")
    
    # 3. Проверяем, что путь начинается с разрешённого префикса
    if not (decoded.startswith('instance/labs/') or decoded.startswith('instance/protections/')):
        print(f"[SECURITY] Блокировка неверного префикса пути: {decoded}")
        print(f"[SECURITY] Путь должен начинаться с 'instance/labs/' или 'instance/protections/'")
        abort(400, "Access denied: invalid path prefix")
    
    # 4. Проверяем на запрещённые паттерны
    for pattern in FORBIDDEN_PATTERNS:
        if pattern in decoded:
            print(f"[SECURITY] Блокировка запрещённого паттерна '{pattern}': {decoded}")
            abort(403, "Access denied: cannot access system files")
    
    # 5. Проверяем расширение файла
    if any(decoded.lower().endswith(ext) for ext in FORBIDDEN_EXTENSIONS):
        print(f"[SECURITY] Блокировка запрещённого расширения: {decoded}")
        abort(403, "Access denied: cannot download this file type")
    
    print("[BEFORE_REQUEST] Проверка безопасности пройдена")
    print("="*60)


@app.route("/files/<path:file_path>")
def files(file_path):
    """Безопасная отдача файлов с поддержкой instance/ в URL"""
    
    print("\n" + "="*60)
    print("[FILES] НАЧАЛО ОБРАБОТКИ ЗАПРОСА")
    print("="*60)
    print(f"[FILES] Полный путь из URL: {file_path}")
    print(f"[FILES] Текущая рабочая директория: {os.getcwd()}")
    print(f"[FILES] Корень проекта (BASE_DIR): {BASE_DIR}")
    
    # Проверка префикса пути
    if not (file_path.startswith('instance/labs/') or file_path.startswith('instance/protections/')):
        print(f"[ERROR] Неверный префикс пути: {file_path}")
        abort(403, "Access denied: invalid path")
    
    # Убираем 'instance/' из пути для поиска файла
    # Например: 'instance/labs/12/disk_45.vhd' -> 'labs/12/disk_45.vhd'
    relative_path = file_path.replace('instance/', '', 1)
    print(f"[FILES] Относительный путь (без instance/): {relative_path}")
    
    # Разбиваем путь на части для анализа
    path_parts = relative_path.split('/')
    print(f"[FILES] Части пути: {path_parts}")
    
    # Определяем тип директории (labs или protections)
    dir_type = path_parts[0] if path_parts else None
    print(f"[FILES] Тип директории: {dir_type}")
    
    # Формируем путь внутри целевой директории
    # Например: из 'labs/12/disk_45.vhd' берём '12/disk_45.vhd'
    inner_path = '/'.join(path_parts[1:]) if len(path_parts) > 1 else ''
    print(f"[FILES] Внутренний путь: {inner_path}")
    
    # Ищем файл в соответствующей директории
    found = False
    for allowed_dir in ALLOWED_DIRS:
        print(f"\n[FILES] Проверка директории: {allowed_dir}")
        print(f"[FILES]   Существует? {allowed_dir.exists()}")
        
        if not allowed_dir.exists():
            print(f"[FILES]   ⚠️ Директория не существует!")
            continue
        
        # Полный путь к запрашиваемому файлу
        full_path = allowed_dir / inner_path
        print(f"[FILES]   Полный путь к файлу: {full_path}")
        print(f"[FILES]   Существует? {full_path.exists()}")
        
        if full_path.exists():
            print(f"[FILES]   Это файл? {full_path.is_file()}")
            if full_path.is_file():
                file_size = full_path.stat().st_size
                print(f"[FILES]   Размер файла: {file_size} байт")
                print(f"[FILES]   Можно прочитать? {os.access(full_path, os.R_OK)}")
        
        if full_path.exists() and full_path.is_file():
            print(f"\n[FILES] ✅ ФАЙЛ НАЙДЕН: {full_path}")
            print(f"[FILES] Отправка файла пользователю...")
            found = True
            return send_file(full_path)
    
    # Если файл не найден в разрешённых директориях, ищем его во всём проекте
    if not found:
        print("\n[FILES] ❌ ФАЙЛ НЕ НАЙДЕН В РАЗРЕШЁННЫХ ДИРЕКТОРИЯХ")
        
        # Извлекаем имя файла из пути
        filename = os.path.basename(file_path)
        print(f"[FILES] Поиск файла '{filename}' во всём проекте:")
        
        found_files = []
        for root, dirs, files in os.walk(BASE_DIR):
            if filename in files:
                full_path = os.path.join(root, filename)
                found_files.append(full_path)
                print(f"  📁 {full_path}")
                
                # Проверяем, находится ли найденный файл в разрешённой директории
                path_obj = Path(full_path)
                is_allowed = False
                for allowed_dir in ALLOWED_DIRS:
                    try:
                        path_obj.relative_to(allowed_dir)
                        is_allowed = True
                        break
                    except ValueError:
                        continue
                
                if is_allowed:
                    print(f"     ✅ В разрешённой директории!")
                else:
                    print(f"     ❌ НЕ в разрешённой директории!")
        
        if found_files:
            print(f"\n[FILES] Найдено {len(found_files)} копий файла, но ни одна не в разрешённых директориях.")
            print(f"[FILES] Разрешённые директории:")
            for d in ALLOWED_DIRS:
                print(f"  - {d}")
        else:
            print(f"\n[FILES] Файл '{filename}' не найден во всём проекте!")
            print(f"[FILES] Проверьте, точно ли файл существует по пути:")
            expected_path = BASE_DIR / "instance" / "labs" / "12" / "disk_45.vhd"
            print(f"  {expected_path}")
    
    print("="*60)
    return f"File not found: {file_path}", 404


if __name__ == "__main__":
    print("\n" + "="*70)
    print("🔥 ЗАПУСК СЕРВЕРА С ЗАЩИТОЙ ОТ PATH TRAVERSAL")
    print("="*70)
    print(f"\n📂 Корень проекта: {BASE_DIR}")
    print("\n✅ Доступные директории для скачивания:")
    for d in ALLOWED_DIRS:
        status = "✓ существует" if d.exists() else "❌ НЕ существует"
        print(f"  • {d}")
        print(f"    Статус: {status}")
        if d.exists():
            # Покажем содержимое
            try:
                files = list(d.glob('**/*.vhd'))
                print(f"    Найдено .vhd файлов: {len(files)}")
                if files:
                    print(f"    Примеры:")
                    for f in files[:3]:
                        print(f"      - {f.relative_to(BASE_DIR)}")
            except Exception as e:
                print(f"    Ошибка чтения: {e}")
    
    print("\n✅ Поддерживаемые форматы URL:")
    print("  ✓ /files/instance/labs/12/disk_45.vhd")
    print("  ✓ /files/instance/protections/file.bin")
    
    print("\n❌ ЗАПРЕЩЕНО скачивать:")
    print(f"  ✗ Расширения: .py, .db, .env, .json, .config, .key, .log и др.")
    print(f"  ✗ Папки: app/, migrations/, __pycache__/, .git/")
    print("="*70 + "\n")
    
    # Запуск сервера
    app.run(host="0.0.0.0", port=5000, debug=True)