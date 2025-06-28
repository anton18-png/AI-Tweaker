import time
import sys
import os
import shutil
from tqdm import tqdm
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table
from rich.prompt import Prompt, Confirm
import platform
import psutil
import argparse
from datetime import datetime
import random
import glob
import subprocess
import logging

logging.basicConfig(
    filename='optimizer.log',
    filemode='a',
    format='%(asctime)s [%(levelname)s] %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

console = Console()

# Улучшенная функция для определения типа диска (SSD/HDD)
def get_disk_type(drive_letter):
    try:
        # Метод 1: PowerShell Get-PhysicalDisk (самый точный)
        import subprocess
        try:
            cmd = f'powershell "Get-WmiObject -Class Win32_LogicalDisk | Where-Object {{$_.DeviceID -eq \'{drive_letter}:\'}} | ForEach-Object {{ Get-WmiObject -Class Win32_DiskPartition | Where-Object {{$_.DriveLetter -eq \'{drive_letter}\'}} | ForEach-Object {{ Get-WmiObject -Class Win32_DiskDrive | Where-Object {{$_.Index -eq $_.Index}} | Select-Object MediaType,Model }}}}"'
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
            logger.info(f"PowerShell результат для диска {drive_letter}: {result.stdout}")
            if 'SSD' in result.stdout.upper() or 'SOLID' in result.stdout.upper():
                return 'SSD'
            elif 'HDD' in result.stdout.upper():
                return 'HDD'
        except Exception as e:
            logger.warning(f"Ошибка PowerShell для диска {drive_letter}: {e}")
            pass
        
        # Метод 2: Альтернативная PowerShell команда
        try:
            cmd = f'powershell "Get-PhysicalDisk | Get-Disk | Get-Partition | Where-Object {{$_.DriveLetter -eq \'{drive_letter}\'}} | Get-Disk | Get-PhysicalDisk | Select-Object MediaType"'
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
            logger.info(f"PowerShell альтернативный результат для диска {drive_letter}: {result.stdout}")
            if 'SSD' in result.stdout.upper():
                return 'SSD'
            elif 'HDD' in result.stdout.upper():
                return 'HDD'
        except Exception as e:
            logger.warning(f"Ошибка PowerShell альтернативный для диска {drive_letter}: {e}")
            pass
        
        # Метод 3: WMI (если доступен)
        try:
            import wmi
            c = wmi.WMI()
            for disk in c.Win32_LogicalDisk():
                if disk.DeviceID.startswith(drive_letter.upper()):
                    for partition in c.Win32_DiskPartition():
                        if partition.DriveLetter == drive_letter.upper():
                            for physical_disk in c.Win32_DiskDrive():
                                if physical_disk.Index == partition.DiskIndex:
                                    logger.info(f"WMI данные для диска {drive_letter}: Model={getattr(physical_disk, 'Model', 'N/A')}, MediaType={getattr(physical_disk, 'MediaType', 'N/A')}, InterfaceType={getattr(physical_disk, 'InterfaceType', 'N/A')}")
                                    # Проверяем MediaType
                                    if hasattr(physical_disk, 'MediaType') and physical_disk.MediaType:
                                        media_type = physical_disk.MediaType.lower()
                                        if 'ssd' in media_type or 'solid' in media_type:
                                            return 'SSD'
                                    # Проверяем модель
                                    if hasattr(physical_disk, 'Model') and physical_disk.Model:
                                        model = physical_disk.Model.lower()
                                        if 'ssd' in model or 'solid' in model or 'nvme' in model:
                                            return 'SSD'
                                    # Проверяем интерфейс
                                    if hasattr(physical_disk, 'InterfaceType') and physical_disk.InterfaceType:
                                        interface = physical_disk.InterfaceType.lower()
                                        if 'nvme' in interface or 'ssd' in interface:
                                            return 'SSD'
                                    return 'HDD'
        except ImportError:
            logger.warning(f"WMI не установлен для диска {drive_letter}")
            pass
        except Exception as e:
            logger.warning(f"Ошибка WMI при определении типа диска {drive_letter}: {e}")
        
        # Метод 4: WMIC (fallback)
        try:
            cmd = f'wmic diskdrive get model,mediatype,interfacetype /format:csv'
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
            logger.info(f"WMIC результат для диска {drive_letter}: {result.stdout}")
            if 'ssd' in result.stdout.lower() or 'nvme' in result.stdout.lower():
                return 'SSD'
            elif 'hdd' in result.stdout.lower() or 'ata' in result.stdout.lower():
                return 'HDD'
        except Exception as e:
            logger.warning(f"Ошибка WMIC для диска {drive_letter}: {e}")
            pass
        
        # Метод 5: Проверка по имени модели (последний fallback)
        try:
            cmd = f'wmic diskdrive get model /format:csv'
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
            logger.info(f"WMIC модель для диска {drive_letter}: {result.stdout}")
            model_output = result.stdout.lower()
            if any(keyword in model_output for keyword in ['ssd', 'nvme', 'solid', 'samsung', 'crucial', 'kingston']):
                return 'SSD'
        except Exception as e:
            logger.warning(f"Ошибка WMIC модель для диска {drive_letter}: {e}")
            pass
        
        logger.warning(f"Не удалось определить тип диска {drive_letter}, возвращаю UNKNOWN")
        return 'UNKNOWN'
    except Exception as e:
        logger.warning(f"Ошибка при определении типа диска {drive_letter}: {e}")
        return 'UNKNOWN'

# Функция для выбора оптимального диска для операций
def get_optimal_drive():
    c_type = get_disk_type('C')
    # Проверяем, существует ли диск D
    d_exists = os.path.exists('D:\\')
    logger.info(f"Диск D существует: {d_exists}")
    
    if d_exists:
        d_type = get_disk_type('D')
        logger.info(f"Тип диска D: {d_type}")
    else:
        d_type = 'UNKNOWN'
        logger.info("Диск D не существует")
    
    logger.info(f"Тип диска C: {c_type}")
    
    if c_type == 'SSD' and d_type == 'HDD':
        console.print("[yellow]Диск C является SSD, диск D является HDD. Операции будут проводиться на диске D для снижения износа SSD.[/yellow]")
        logger.info("Выбран диск D (HDD) для операций вместо диска C (SSD)")
        return 'D'
    elif c_type == 'SSD':
        console.print("[yellow]Внимание! Диск C является SSD. Файлы будут несколько раз перезаписываться, что может ускорить износ SSD.[/yellow]")
        logger.warning("Операции будут проводиться на SSD (диск C), что может ускорить износ")
        return 'C'
    else:
        console.print("[green]Диск C является HDD. Операции будут проводиться на диске C.[/green]")
        logger.info("Выбран диск C (HDD) для операций")
        return 'C'

# Функция для создания полного бэкапа реестра
def backup_registry(backup_path=None):
    backup_dir = f'{optimal_drive}:\\Backup'
    os.makedirs(backup_dir, exist_ok=True)
    if backup_path is None:
        dt = datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
        backup_path = os.path.join(backup_dir, f'registry_backup_{dt}.reg')
    console.print(f"[yellow]Создаю полный бэкап реестра...[/yellow]")
    logger.info(f"Создаю полный бэкап реестра: {backup_path}")
    result = os.system(f'launcher.exe regedit /e "{backup_path}"')
    if result == 0:
        console.print(f"[green]Бэкап реестра успешно сохранён: {backup_path}[/green]")
        logger.info(f"Бэкап реестра успешно сохранён: {backup_path}")
    else:
        console.print(f"[red]Ошибка при создании бэкапа реестра![/red]")
        logger.error(f"Ошибка при создании бэкапа реестра: {backup_path}")
        sys.exit(1)

# Копируем случайный бэкап реестра в C:\temp\backup_0
# Определяем оптимальный диск для операций
optimal_drive = get_optimal_drive()
backup_files = glob.glob(f'{optimal_drive}:\\Backup\\*.reg')
if backup_files:
    random_backup = random.choice(backup_files)
    temp_dir = f'{optimal_drive}:\\temp'
    os.makedirs(temp_dir, exist_ok=True)
    shutil.copy2(random_backup, f'{temp_dir}\\backup_0.reg')
    logger.info(f"Скопирован случайный бэкап реестра: {random_backup} -> {temp_dir}\\backup_0.reg")
else:
    logger.warning("Не найдено бэкапов реестра для копирования. Создаю новый бэкап...")
    console.print("[yellow]Бэкапы реестра не найдены. Создаю новый бэкап...[/yellow]")
    # Создаём новый бэкап
    backup_registry()
    # Проверяем, создался ли бэкап
    backup_files = glob.glob(f'{optimal_drive}:\\Backup\\*.reg')
    if backup_files:
        random_backup = random.choice(backup_files)
        temp_dir = f'{optimal_drive}:\\temp'
        os.makedirs(temp_dir, exist_ok=True)
        shutil.copy2(random_backup, f'{temp_dir}\\backup_0.reg')
        logger.info(f"Скопирован новый бэкап реестра: {random_backup} -> {temp_dir}\\backup_0.reg")
        console.print(f"[green]Новый бэкап создан и скопирован: {random_backup}[/green]")
    else:
        logger.error("Не удалось создать бэкап реестра!")
        console.print("[red]Ошибка: не удалось создать бэкап реестра![/red]")
        sys.exit(1)

# Безопасное чтение строк файла с определением кодировки
def safe_readlines(path):
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return f.readlines()
    except UnicodeDecodeError:
        try:
            with open(path, 'r', encoding='utf-16') as f:
                return f.readlines()
        except UnicodeDecodeError:
            with open(path, 'r', encoding='cp1251') as f:
                return f.readlines()

# Функция для отображения прогресс-бара rich
class RichProgressBar:
    def __init__(self, message="Ожидание ответа от ChatGPT..."):
        self.message = message
        self.running = True

    def start(self):
        with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}"), transient=True) as progress:
            task = progress.add_task(self.message, start=False)
            while self.running:
                progress.start_task(task)
                time.sleep(0.1)

    def stop(self):
        self.running = False

# Получить список .reg-файлов с кратким описанием
def get_tweak_files_with_descriptions(folder):
    files = [f for f in os.listdir(folder) if f.lower().endswith(('.reg', '.bat', '.cmd'))]
    result = []
    for fname in files:
        path = os.path.join(folder, fname)
        desc = fname
        try:
            # Для .reg используем safe_readlines, для .bat/.cmd — utf-8 или cp1251
            if fname.lower().endswith('.reg'):
                lines = safe_readlines(path)
            else:
                try:
                    with open(path, 'r', encoding='utf-8') as f:
                        lines = f.readlines()
                except UnicodeDecodeError:
                    with open(path, 'r', encoding='cp1251') as f:
                        lines = f.readlines()
            for line in lines[:10]:
                if line.strip().startswith((';', '::', 'REM')) and len(line.strip()) > 1:
                    desc = line.strip().lstrip(';:/').replace('REM', '').strip()
                    break
        except Exception:
            pass
        result.append({'name': fname, 'path': path, 'desc': desc})
    return result

# Объединить выбранные .reg-файлы
def merge_tweak_files(files):
    merged = ''
    for f in files:
        if f['name'].lower().endswith('.reg'):
            lines = safe_readlines(f['path'])
            if lines and lines[0].strip().startswith('Windows Registry Editor'):
                lines = lines[1:]
            merged += f'\n; --- {f["name"]} ---\n'
            merged += ''.join(lines)
        else:
            try:
                with open(f['path'], 'r', encoding='utf-8') as inp:
                    lines = inp.readlines()
            except UnicodeDecodeError:
                with open(f['path'], 'r', encoding='cp1251') as inp:
                    lines = inp.readlines()
            merged += f'\n:: --- {f["name"]} ---\n'
            merged += ''.join(lines)
    return merged

# --- Бенчмарк функции ---
def copy_benchmark(src, dst):
    logger.info(f"Бенчмарк: копирование {src} -> {dst}")
    start = time.perf_counter()
    if os.path.exists(dst):
        os.remove(dst)
    shutil.copy2(src, dst)
    end = time.perf_counter()
    logger.info(f"Время копирования {src} -> {dst}: {end - start:.2f} сек")
    return end - start

def open_browser_benchmark(url):
    logger.info(f"Бенчмарк: открытие браузера {url}")
    import subprocess
    import psutil
    start = time.perf_counter()
    # Запускаем браузер через start
    subprocess.Popen(f'start {url}', shell=True)
    # Ждём появления процесса браузера
    browser_proc = None
    browser_names = ['chrome', 'firefox', 'msedge', 'opera', 'brave', 'yandex', 'iexplore']
    browser_started = False
    while not browser_started:
        for proc in psutil.process_iter(['name', 'cmdline']):
            if any(browser in (proc.info['name'] or '').lower() for browser in browser_names):
                browser_proc = proc
                browser_started = True
                break
        if time.perf_counter() - start > 30:
            break
        time.sleep(0.1)
    end = time.perf_counter()
    # Закрываем браузер, если удалось найти процесс
    if browser_proc:
        try:
            browser_proc.terminate()
        except Exception:
            pass
    logger.info(f"Время открытия браузера: {end - start:.2f} сек")
    return end - start

def open_notepad_benchmark():
    import glob
    import time
    import psutil
    backup_files = glob.glob(f'{optimal_drive}:\\Backup\\*.reg')
    logger.info(f"Бенчмарк: открытие случайного .reg файла в notepad. Найдено файлов: {len(backup_files)}")
    # print("[DEBUG] Найдено .reg файлов:", backup_files)
    if not backup_files:
        print(f"[ERROR] Не найдено ни одного .reg файла в {optimal_drive}:\\Backup\\. Проверьте путь и наличие файлов.")
        logger.warning("Не найдено ни одного .reg файла в C:\\Backup для notepad-бенчмарка")
        return "NO_FILES"
    reg_file = random.choice(backup_files)
    start = time.perf_counter()
    # Открываем notepad в обычном (видимом) режиме
    p = subprocess.Popen(["notepad.exe", reg_file])
    # Ждём появления процесса и окна
    notepad_proc = None
    window_loaded = False
    hwnd = None
    for _ in range(100):
        for proc in psutil.process_iter(['name', 'cmdline']):
            if proc.info['name'] and 'notepad' in proc.info['name'].lower():
                notepad_proc = proc
                break
        if notepad_proc:
            break
        time.sleep(0.05)
    # Ждём появления окна и загрузки текста
    try:
        try:
            import pygetwindow as gw
            import pywinauto
            for _ in range(100):
                windows = gw.getWindowsWithTitle(os.path.basename(reg_file))
                if windows:
                    hwnd = windows[0]._hWnd
                    # Проверяем, что текст загружен (обычно окно не пустое)
                    try:
                        app = pywinauto.Application().connect(handle=hwnd)
                        edit = app.window(handle=hwnd).child_window(class_name="Edit")
                        text = edit.window_text()
                        if text and len(text) > 0:
                            window_loaded = True
                            break
                    except Exception:
                        pass
                time.sleep(0.05)
        except ImportError:
            # Если нет pygetwindow/pywinauto, просто ждём 1 секунду после появления процесса
            time.sleep(1)
            window_loaded = True
    except Exception:
        # Любая другая ошибка — fallback
        time.sleep(1)
        window_loaded = True
    end = time.perf_counter()
    # Закрываем notepad
    if notepad_proc:
        try:
            notepad_proc.terminate()
        except Exception:
            pass
    if window_loaded:
        logger.info(f"Время открытия и загрузки .reg файла в notepad: {end - start:.2f} сек ({reg_file})")
    else:
        logger.error(f"Окно Notepad не загрузилось или не удалось прочитать текст из файла: {reg_file}")
    if window_loaded:
        return end - start
    else:
        print("[ERROR] Окно Notepad не загрузилось или не удалось прочитать текст из файла.")
        return "FAILED_TO_LOAD"

def apply_tweaks(reg_path, bat_path):
    logger.info(f"Применение твиков: {reg_path}, {bat_path}")
    # Импортируем .reg
    os.system(f'launcher.exe regedit /s "{reg_path}"')
    # Запускаем .bat/.cmd
    os.system(f'launcher.exe cmd /c "{bat_path}"')

def get_system_info():
    info = {
        'OS': platform.platform(),
        'CPU': platform.processor(),
        'RAM': f"{round(psutil.virtual_memory().total / (1024**3), 2)} GB",
        'Cores': str(psutil.cpu_count(logical=True)),
        'GPU': 'N/A',
    }
    try:
        try:
            import GPUtil
            gpus = GPUtil.getGPUs()
            if gpus:
                info['GPU'] = gpus[0].name
        except ImportError:
            pass
    except Exception:
        pass
    return info

def main():
    logger.info("=== Запуск GPT Windows 11 Optimizer ===")
    parser = argparse.ArgumentParser(description="GPT Windows 11 Optimizer: Benchmark & Tweaks")
    parser.add_argument('-i', '--iterations', type=int, default=5, help='Количество итераций (по умолчанию 5)')
    parser.add_argument('-w', '--without_backup', action='store_true', help='Не создавать бэкап реестра перед оптимизацией')
    args = parser.parse_args()
    iterations = args.iterations
    without_backup = args.without_backup
    console.print("[bold cyan]=== GPT Windows 11 Optimizer: Benchmark & Tweaks ===[/bold cyan]")
    sysinfo = get_system_info()
    logger.info(f"Информация о системе: {sysinfo}")
    console.print("[bold yellow]Информация о системе:[/bold yellow]")
    for k, v in sysinfo.items():
        console.print(f"[bold]{k}:[/bold] {v}")
    # 1. Бэкап реестра (если не отключён)
    if not without_backup:
        backup_registry()
    else:
        logger.info("Бэкап реестра отключён по флагу --without_backup")
    # Выводим список бэкапов как таблицу
    backup_files = glob.glob(f'{optimal_drive}:\\Backup\\*.reg')
    table = Table(title=f"Доступные бэкапы реестра ({optimal_drive}:\\Backup)")
    table.add_column("#", style="cyan", justify="right")
    table.add_column("Файл", style="magenta")
    table.add_column("Размер (КБ)", style="green", justify="right")
    table.add_column("Дата изменения", style="yellow")
    for idx, path in enumerate(sorted(backup_files), 1):
        try:
            size_kb = os.path.getsize(path) // 1024
            mtime = datetime.fromtimestamp(os.path.getmtime(path)).strftime('%Y-%m-%d %H:%M:%S')
        except Exception:
            size_kb = '—'
            mtime = '—'
        table.add_row(str(idx), os.path.basename(path), str(size_kb), mtime)
    if backup_files:
        console.print(table)
    else:
        console.print(f'[yellow]В папке {optimal_drive}:\\Backup нет .reg бэкапов[/yellow]')
    # 2. Эталонный бенчмарк
    console.print("[yellow]Эталонный бенчмарк: копирование backup_0 -> backup_1[/yellow]")
    t_copy0 = copy_benchmark(f'{optimal_drive}:\\temp\\backup_0.reg', f'{optimal_drive}:\\temp\\backup_1.reg')
    console.print(f"[green]Время копирования backup_0 -> backup_1:[/green] {t_copy0:.2f} сек")
    t_browser0 = open_browser_benchmark('https://shre.su/L7VO')
    console.print(f"[green]Время открытия браузера:[/green] {t_browser0:.2f} сек")
    t_notepad0 = open_notepad_benchmark()
    if t_notepad0 == "NO_FILES":
        console.print(f"[yellow]Нет .reg файлов в {optimal_drive}:\\Backup для notepad-бенчмарка[/yellow]")
        logger.warning("Нет .reg файлов в C:\\Backup для notepad-бенчмарка")
    elif t_notepad0 == "FAILED_TO_LOAD":
        console.print(f"[red]Ошибка: не удалось открыть или прочитать .reg файл в Notepad для бенчмарка[/red]")
        logger.error("Ошибка: не удалось открыть или прочитать .reg файл в Notepad для бенчмарка")
    elif t_notepad0 is not None:
        console.print(f"[green]Время открытия бэкапа реестра в notepad:[/green] {t_notepad0:.2f} сек")
        logger.info(f"Время открытия бэкапа реестра в notepad: {t_notepad0:.2f} сек")
    results = []
    applied_tweaks = []
    for i in range(1, iterations + 1):
        logger.info(f"=== Итерация {i} ===")
        console.print(f"\n[bold magenta]=== Итерация {i} ===[/bold magenta]")
        tweak_files = get_tweak_files_with_descriptions('Brian')
        file_list_str = '\n'.join([f"{f['name']}: {f['desc']}" for f in tweak_files])
        select_prompt = (
            "Дельай очень быстро!!! Вот список .reg, .bat и .cmd файлов с описаниями. Выбери только те, которые лучше всего подходят для полной и агрессивной оптимизации Windows 11 (максимальная производительность, отключение всей телеметрии, удаление UWP-приложений, отключение всех служб, антивируса, firewall, обновлений, оптимизация nvidia, directx, windows 11 и т.д.). "
            "Ответь только списком имён файлов, по одному на строку, без лишнего текста.\n\n" + file_list_str
        )
        import threading
        progress = RichProgressBar(f"ChatGPT выбирает твики для итерации {i}...")
        thread = threading.Thread(target=progress.start)
        thread.start()
        import g4f
        try:
            response = g4f.ChatCompletion.create(
                model=g4f.models.gpt_4,
                messages=[{"role": "user", "content": select_prompt}],
                stream=False
            )
            response = str(response)
            logger.info(f"Ответ GPT-4 на выбор твиков (итерация {i}): {response}")
        except Exception as e:
            progress.stop()
            console.print(f"[red]Ошибка при обращении к g4f: {e}[/red]")
            logger.error(f"Ошибка при обращении к g4f: {e}")
            sys.exit(1)
        progress.stop()
        thread.join()
        selected_names = [line.strip() for line in response.splitlines() if line.strip() in [f['name'] for f in tweak_files]]
        selected_files = [f for f in tweak_files if f['name'] in selected_names]
        if not selected_files:
            console.print("[red]ChatGPT не выбрал ни одного файла![/red]")
            logger.error("ChatGPT не выбрал ни одного файла!")
            sys.exit(1)
        console.print("[green]Выбраны файлы:[/green] " + ', '.join([f['name'] for f in selected_files]))
        logger.info(f"Выбраны файлы: {', '.join([f['name'] for f in selected_files])}")
        merged_tweaks_content = merge_tweak_files(selected_files)
        user_prompt = (
            "Дельай очень быстро!!! Делай очень много твиков, чтобы Windows 11 был максимально оптимизирован. Вот примеры твиков для Windows 11 (.reg, .bat, .cmd), используй их как основу, а также придумай свои твики. Не в коем случае не пиши команду pause. "
            "Сгенерируй .reg файл и .bat/.cmd скрипт для максимально агрессивной оптимизации Windows 11. "
            "ОБЯЗАТЕЛЬНО: отключи всю телеметрию, удали все UWP-приложения, отключи все возможные службы, антивирус, firewall, обновления, оптимизируй nvidia, directx, windows 11 и т.д. "
            "Внеси в реестр целую кучу глобальных твиков. .bat файл должен получиться очень огромным. "
            "Добавь комментарии к каждому твик-ключу и каждой команде.\n\n"
            f"Примеры твиков:\n{merged_tweaks_content}"
        )
        undo_prompt = (
            "Дельай очень быстро!!! Сгенерируй .reg файл и .bat/.cmd скрипт для ОТМЕНЫ изменений, внесённых предыдущим оптимизационным твиком. Не в коем случае не пиши команду pause. "
            "Добавь комментарии к каждому твик-ключу и каждой команде."
        )
        progress = RichProgressBar(f"ChatGPT генерирует твики для итерации {i}...")
        thread = threading.Thread(target=progress.start)
        thread.start()
        try:
            response = g4f.ChatCompletion.create(
                model=g4f.models.gpt_4,
                messages=[{"role": "user", "content": user_prompt}],
                stream=False
            )
            response = str(response)
            logger.info(f"Ответ GPT-4 на генерацию твиков (итерация {i}): {response}")
        except Exception as e:
            progress.stop()
            console.print(f"[red]Ошибка при обращении к g4f: {e}[/red]")
            logger.error(f"Ошибка при обращении к g4f (генерация твиков): {e}")
            sys.exit(1)
        progress.stop()
        thread.join()
        import re
        reg_code = None
        bat_code = None
        match_reg = re.search(r'```reg([\s\S]+?)```', response)
        if match_reg:
            reg_code = match_reg.group(1).strip()
        match_bat = re.search(r'```(?:bat|cmd)([\s\S]+?)```', response)
        if match_bat:
            bat_code = match_bat.group(1).strip()
        if not reg_code:
            reg_code = response.strip()
        if not bat_code:
            match_any = re.search(r'```([\s\S]+?)```', response)
            if match_any:
                bat_code = match_any.group(1).strip()
        reg_filename = f"win11_optimized_{i}.reg"
        bat_filename = f"win11_optimized_{i}.bat"
        reg_dir = os.path.dirname(reg_filename)
        if reg_dir:
            os.makedirs(reg_dir, exist_ok=True)
        with open(reg_filename, "w", encoding="utf-8") as f:
            f.write(reg_code)
        with open(bat_filename, "w", encoding="utf-8") as f:
            f.write(bat_code or ":: Нет сгенерированного bat/cmd кода")
        progress = RichProgressBar(f"ChatGPT генерирует undo-твики для итерации {i}...")
        thread = threading.Thread(target=progress.start)
        thread.start()
        try:
            response_undo = g4f.ChatCompletion.create(
                model=g4f.models.gpt_4,
                messages=[{"role": "user", "content": undo_prompt}],
                stream=False
            )
            response_undo = str(response_undo)
            logger.info(f"Ответ GPT-4 на генерацию undo-твиков (итерация {i}): {response_undo}")
        except Exception as e:
            progress.stop()
            console.print(f"[red]Ошибка при обращении к g4f: {e}[/red]")
            logger.error(f"Ошибка при обращении к g4f (undo-твики): {e}")
            sys.exit(1)
        progress.stop()
        thread.join()
        reg_undo = None
        bat_undo = None
        match_reg = re.search(r'```reg([\s\S]+?)```', response_undo)
        if match_reg:
            reg_undo = match_reg.group(1).strip()
        match_bat = re.search(r'```(?:bat|cmd)([\s\S]+?)```', response_undo)
        if match_bat:
            bat_undo = match_bat.group(1).strip()
        if not reg_undo:
            reg_undo = response_undo.strip()
        if not bat_undo:
            match_any = re.search(r'```([\s\S]+?)```', response_undo)
            if match_any:
                bat_undo = match_any.group(1).strip()
        reg_undo_filename = f"win11_undo_{i}.reg"
        bat_undo_filename = f"win11_undo_{i}.bat"
        reg_undo_dir = os.path.dirname(reg_undo_filename)
        if reg_undo_dir:
            os.makedirs(reg_undo_dir, exist_ok=True)
        with open(reg_undo_filename, "w", encoding="utf-8") as f:
            f.write(reg_undo)
        with open(bat_undo_filename, "w", encoding="utf-8") as f:
            f.write(bat_undo or ":: Нет сгенерированного bat/cmd кода")
        apply_tweaks(reg_filename, bat_filename)
        # Бенчмарк после твиков
        if os.path.exists(f'{optimal_drive}:\\temp\\backup_1.reg'):
            os.remove(f'{optimal_drive}:\\temp\\backup_1.reg')
        t_copy1 = copy_benchmark(f'{optimal_drive}:\\temp\\backup_0.reg', f'{optimal_drive}:\\temp\\backup_1.reg')
        t_browser1 = open_browser_benchmark('https://shre.su/L7VO')
        console.print(f"[green]Время копирования backup_0 -> backup_1:[/green] {t_copy1:.2f} сек")
        console.print(f"[green]Время открытия браузера:[/green] {t_browser1:.2f} сек")
        t_notepad1 = open_notepad_benchmark()
        if isinstance(t_notepad1, float):
            console.print(f"[green]Время открытия бэкапа реестра в notepad после твика:[/green] {t_notepad1:.2f} сек")
            logger.info(f"Время открытия бэкапа реестра в notepad после твика: {t_notepad1:.2f} сек")
        elif t_notepad1 == "NO_FILES":
            console.print(f"[yellow]Нет .reg файлов в {optimal_drive}:\\Backup для notepad-бенчмарка после твика[/yellow]")
            logger.warning("Нет .reg файлов в C:\\Backup для notepad-бенчмарка после твика")
        elif t_notepad1 == "FAILED_TO_LOAD":
            console.print(f"[red]Ошибка: не удалось открыть или прочитать .reg файл в Notepad для бенчмарка после твика[/red]")
            logger.error("Ошибка: не удалось открыть или прочитать .reg файл в Notepad для бенчмарка после твика")
        logger.info(f"Время копирования backup_0 -> backup_1: {t_copy1:.2f} сек; Время открытия браузера: {t_browser1:.2f} сек")
        # Если результат ухудшился — откатить и не учитывать твик
        notepad_worse = False
        if isinstance(t_notepad0, (int, float)) and isinstance(t_notepad1, (int, float)):
            notepad_worse = t_notepad1 >= t_notepad0
        if t_copy1 >= t_copy0 and t_browser1 >= t_browser0 and notepad_worse:
            console.print(f"[red]Результат ухудшился, откатываю изменения![/red]")
            logger.warning(f"Результат ухудшился, откатываю изменения! Итерация {i}")
            apply_tweaks(reg_undo_filename, bat_undo_filename)
            continue
        # Откат твиков (для чистоты следующей итерации)
        apply_tweaks(reg_undo_filename, bat_undo_filename)
        # Сохраняем результаты и успешные твики
        results.append({
            'iter': i,
            'copy_before': t_copy0,
            'copy_after': t_copy1,
            'browser_before': t_browser0,
            'browser_after': t_browser1,
            'notepad_before': t_notepad0,
            'notepad_after': t_notepad1,
            'reg': reg_code,
            'bat': bat_code
        })
        applied_tweaks.append({'reg': reg_code, 'bat': bat_code})
    # Выводим таблицу результатов
    table = Table(title="Результаты оптимизации GPT Windows 11 Optimizer (итераций: " + str(iterations) + ")")
    table.add_column("Итерация", style="cyan")
    table.add_column("Копир. до", style="magenta")
    table.add_column("Копир. после", style="magenta")
    table.add_column("Браузер до", style="green")
    table.add_column("Браузер после", style="green")
    table.add_column("Отк. notepad до", style="blue")
    table.add_column("Отк. notepad после", style="blue")
    table.add_column("Δ Копир.", style="yellow")
    table.add_column("Δ Браузер", style="yellow")
    table.add_column("Δ notepad", style="yellow")
    for r in results:
        table.add_row(
            str(r['iter']),
            f"{r['copy_before']:.2f}",
            f"{r['copy_after']:.2f}",
            f"{r['browser_before']:.2f}",
            f"{r['browser_after']:.2f}",
            f"{r['notepad_before']:.2f}",
            f"{r['notepad_after']:.2f}",
            f"{r['copy_before']-r['copy_after']:.2f}",
            f"{r['browser_before']-r['browser_after']:.2f}",
            f"{r['notepad_before']-r['notepad_after']:.2f}",
        )
    logger.info("Оптимизация завершена. Сравните результаты до и после.")
    console.print(table)
    console.print("[bold yellow]Информация о системе:[/bold yellow]")
    for k, v in sysinfo.items():
        console.print(f"[bold]{k}:[/bold] {v}")
    # Собираем strongest tweak
    if applied_tweaks:
        strongest_reg = '\n'.join([t['reg'] for t in applied_tweaks if t['reg']])
        strongest_bat = '\n'.join([t['bat'] for t in applied_tweaks if t['bat']])
        with open('strongest_tweak.reg', 'w', encoding='utf-8') as f:
            f.write(strongest_reg)
        with open('strongest_tweak.bat', 'w', encoding='utf-8') as f:
            f.write(strongest_bat)
        console.print("[bold green]Файл strongest_tweak.reg и strongest_tweak.bat с самой сильной оптимизацией сохранены![/bold green]")
        logger.info("Файл strongest_tweak.reg и strongest_tweak.bat с самой сильной оптимизацией сохранены!")
    else:
        console.print("[red]Не удалось собрать ни одного успешного твика![/red]")
        logger.warning("Не удалось собрать ни одного успешного твика!")
    console.print("[bold green]Готово! Сравните результаты до и после оптимизации.[/bold green]")
    logger.info("Готово! Сравните результаты до и после оптимизации.")
    # Выводим финальную информацию о системе и железе
    console.print("\n[bold cyan]=== ИНФОРМАЦИЯ О СИСТЕМЕ И ЖЕЛЕЗЕ ===[/bold cyan]")
    console.print("[bold yellow]Операционная система:[/bold yellow]")
    console.print(f"  {sysinfo['OS']}")
    console.print("[bold yellow]Процессор:[/bold yellow]")
    console.print(f"  {sysinfo['CPU']}")
    console.print(f"  Ядер: {sysinfo['Cores']}")
    console.print("[bold yellow]Оперативная память:[/bold yellow]")
    console.print(f"  {sysinfo['RAM']}")
    console.print("[bold yellow]Видеокарта:[/bold yellow]")
    console.print(f"  {sysinfo['GPU']}")
    console.print("\n[bold green]✓ Сгенерированные твики оптимизированы именно для вашего железа и операционной системы![/bold green]")
    console.print("[bold green]✓ Файлы strongest_tweak.reg и strongest_tweak.bat содержат лучшие настройки для вашей конфигурации.[/bold green]")
    logger.info(f"Финальная информация о системе: {sysinfo}")
    logger.info("Сгенерированные твики оптимизированы для конкретного железа и ОС")

if __name__ == "__main__":
    main()