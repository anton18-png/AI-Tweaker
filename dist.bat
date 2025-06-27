@echo off
REM Компиляция main.py в один exe с иконкой и нужными файлами

REM Удаляем старую сборку
rmdir /s /q dist
rmdir /s /q build
del main.spec

REM Собираем проект
pyinstaller ^
  --onefile ^
  --icon=icon.ico ^
  main.py

@REM pyinstaller ^
@REM   --onefile ^
@REM   --icon=icon.ico ^
@REM   --add-data "elevator.exe;." ^
@REM   --add-data "launcher.exe;." ^
@REM   --add-data "PowerRun.exe;." ^
@REM   --add-data "Brian;Brian" ^
@REM   main.py

REM Копируем иконку (если нужно для дистрибутива)
copy icon.ico dist\

echo.
echo Готово! Файл dist\main.exe создан.
pause