import os
import hashlib
import subprocess
import requests
from pathlib import Path
import shutil
import sys
import logging
from datetime import datetime
import time

# Завершаем работу AI Tweaker
# kill_all_tweaker = 'taskkill /im "main.exe" /f'
# subprocess.call(kill_all_tweaker, shell=True)

# Определяем рабочую директорию
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
# SCRIPT_DIR = "."
os.chdir(SCRIPT_DIR)  # Устанавливаем текущую директорию

# если есть файл clean.bat, то запускаем
if os.path.exists('clean.bat'):
    start_clean_bat = 'cmd /c clean.bat'
    subprocess.call(start_clean_bat, shell=True)
    subprocess.call('del clean.bat', shell=True)
else:
    pass

# Настройка логирования
logging.basicConfig(
    filename='updater.log',
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# Конфигурация
REPO_OWNER = "anton18-png"
REPO_NAME = "AI-Tweaker"
REPO_BRANCH = "main"
GITHUB_API_URL = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/contents"
GITHUB_RAW_URL = f"https://raw.githubusercontent.com/{REPO_OWNER}/{REPO_NAME}/{REPO_BRANCH}"

# Добавляем заголовки для API GitHub
HEADERS = {
    'Accept': 'application/vnd.github.v3+json',
    'User-Agent': 'AI-Tweaker'
}

def normalize_path(path):
    """Нормализует путь файла"""
    return os.path.normpath(os.path.join(SCRIPT_DIR, path))

def calculate_file_hash(file_path):
    """Вычисляет SHA-256 хэш файла"""
    try:
        file_path = normalize_path(file_path)
        with open(file_path, 'rb') as f:
            file_hash = hashlib.sha256()
            while chunk := f.read(8192):
                file_hash.update(chunk)
            return file_hash.hexdigest()
    except Exception as e:
        logging.error(f"Ошибка при вычислении хэша файла {file_path}: {e}")
        return None

def get_remote_files(path=""):
    """Получает список файлов и их хэши из репозитория GitHub"""
    try:
        url = f"{GITHUB_API_URL}/{path}" if path else GITHUB_API_URL
        
        # Добавляем повторные попытки при сбое
        max_retries = 3
        for attempt in range(max_retries):
            try:
                response = requests.get(url, headers=HEADERS, timeout=10)
                response.raise_for_status()
                break
            except requests.RequestException as e:
                if attempt == max_retries - 1:
                    raise
                time.sleep(1)
        
        files = {}
        for item in response.json():
            if item['type'] == 'file':
                # Получаем содержимое файла для вычисления хэша
                raw_url = f"{GITHUB_RAW_URL}/{item['path']}"
                
                # Повторные попытки для загрузки содержимого
                for attempt in range(max_retries):
                    try:
                        content_response = requests.get(raw_url, headers=HEADERS, timeout=10)
                        content_response.raise_for_status()
                        break
                    except requests.RequestException as e:
                        if attempt == max_retries - 1:
                            raise
                        time.sleep(1)
                
                # Вычисляем хэш содержимого
                content_hash = hashlib.sha256(content_response.content).hexdigest()
                files[item['path']] = {
                    'sha': content_hash,
                    'download_url': raw_url,
                    'size': len(content_response.content)
                }
            elif item['type'] == 'dir':
                # Рекурсивно обходим подкаталоги
                files.update(get_remote_files(item['path']))
        
        return files
    except Exception as e:
        logging.error(f"Ошибка при получении файлов из репозитория: {e}")
        print(f"Ошибка при получении файлов из репозитория: {e}")
        return {}

def backup_file(file_path):
    """Создает резервную копию файла"""
    try:
        file_path = normalize_path(file_path)
        backup_dir = Path(SCRIPT_DIR) / "backups" / datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_dir.mkdir(parents=True, exist_ok=True)
        
        # Сохраняем структуру каталогов
        relative_path = os.path.relpath(file_path, SCRIPT_DIR)
        backup_path = backup_dir / relative_path
        backup_path.parent.mkdir(parents=True, exist_ok=True)
        
        if os.path.exists(file_path):
            shutil.copy2(file_path, backup_path)
            logging.info(f"Создана резервная копия файла {relative_path}")
            return True
        else:
            logging.warning(f"Файл {relative_path} не существует, резервная копия не создана")
            return True  # Возвращаем True, так как отсутствие файла не является ошибкой
    except Exception as e:
        logging.error(f"Ошибка при создании резервной копии {file_path}: {e}")
        print(f"Ошибка при создании резервной копии {file_path}: {e}")
        return False

def download_file(url, file_path):
    """Загружает файл из репозитория"""
    try:
        file_path = normalize_path(file_path)
        
        # Добавляем повторные попытки при сбое
        max_retries = 3
        for attempt in range(max_retries):
            try:
                response = requests.get(url, headers=HEADERS, timeout=10)
                response.raise_for_status()
                break
            except requests.RequestException as e:
                if attempt == max_retries - 1:
                    raise
                print(f"Попытка {attempt + 1} из {max_retries} загрузки файла {file_path}")
                time.sleep(1)
        
        # Создаем директории, если они не существуют
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        
        # Проверяем, не занят ли файл
        if os.path.exists(file_path):
            try:
                # Пробуем открыть файл для записи
                with open(file_path, 'ab') as f:
                    pass
            except PermissionError:
                print(f"Файл {file_path} занят другим процессом. Пропускаем...")
                return False
        
        # Записываем содержимое во временный файл
        temp_file = f"{file_path}.tmp"
        with open(temp_file, 'wb') as f:
            f.write(response.content)
        
        # Перемещаем временный файл на место целевого
        if os.path.exists(file_path):
            os.remove(file_path)
        os.rename(temp_file, file_path)
        
        relative_path = os.path.relpath(file_path, SCRIPT_DIR)
        logging.info(f"Файл {relative_path} успешно загружен")
        return True
    except Exception as e:
        logging.error(f"Ошибка при загрузке файла {file_path}: {e}")
        print(f"Ошибка при загрузке файла {file_path}: {e}")
        if os.path.exists(f"{file_path}.tmp"):
            os.remove(f"{file_path}.tmp")
        return False

def check_and_update(auto_update=False):
    """Проверяет и обновляет файлы при необходимости"""
    try:
        print("Проверка обновлений...")
        logging.info("Начало проверки обновлений")
        
        # Получаем список файлов из репозитория
        remote_files = get_remote_files()
        if not remote_files:
            print("Не удалось получить список файлов из репозитория")
            return False
        
        updates_needed = False
        files_to_update = []
        
        for file_path, remote_info in remote_files.items():
            local_path = normalize_path(file_path)
            
            # Пропускаем файлы, которые не нужно обновлять
            if file_path in ['updater.py', 'updater.log', '.git', '.gitignore']:
                continue
            
            # Проверяем существование локального файла
            if not os.path.exists(local_path):
                print(f"Файл {file_path} отсутствует локально и будет загружен")
                files_to_update.append((file_path, remote_info))
                updates_needed = True
                continue
            
            # Сравниваем хэши
            local_hash = calculate_file_hash(local_path)
            if local_hash != remote_info['sha']:
                print(f"Обнаружено несоответствие в файле {file_path}")
                files_to_update.append((file_path, remote_info))
                updates_needed = True
        
        if not updates_needed:
            print("Все файлы актуальны")
            logging.info("Проверка завершена - обновления не требуются")
            return True
        
        # Показываем список файлов для обновления
        print("\nСписок файлов для обновления:")
        for file_path, remote_info in files_to_update:
            print(f"- {file_path} (размер: {remote_info['size']/1024:.1f} KB)")
        
        # Спрашиваем пользователя о подтверждении обновления только если не включено автообновление
        # if not auto_update:
        #     response = input("\nОбнаружены обновления. Хотите обновить файлы? (y/n): ").lower()
        #     if response != 'y':
        #         print("Обновление отменено пользователем")
        #         return False
        
        # Обновляем файлы
        success_count = 0
        total_files = len(files_to_update)
        
        for index, (file_path, remote_info) in enumerate(files_to_update, 1):
            print(f"\nОбработка файла {file_path} ({index}/{total_files})")
            
            if download_file(remote_info['download_url'], file_path):
                print(f"Файл {file_path} успешно обновлен")
                success_count += 1
            else:
                print(f"Ошибка при обновлении файла {file_path}")
        
        print(f"\nОбновление завершено. Успешно обновлено {success_count} из {total_files} файлов")
        logging.info(f"Обновление завершено. Успешно обновлено {success_count} из {total_files} файлов")
        return success_count > 0
        
    except Exception as e:
        print(f"Произошла ошибка при обновлении: {e}")
        logging.error(f"Критическая ошибка при обновлении: {e}")
        return False

if __name__ == "__main__":
    try:
        print(f"Рабочая директория: {SCRIPT_DIR}")
        tweaker_file = 'main.py'
        if check_and_update():
            print("Программа обновлена успешно")
            subprocess.call(tweaker_file, shell=True)
        else:
            print("Не удалось выполнить обновление")
            subprocess.call(tweaker_file, shell=True)
    except KeyboardInterrupt:
        print("\nОбновление прервано пользователем")
        sys.exit(1) 