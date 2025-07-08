@echo off

:: Укажите путь к 7za.exe, если он не находится в переменной PATH
set "sevenZipPath=7za.exe"  
set "archivePath=tweaks.7z"
set "targetFolder=Brian"

:: Проверка наличия папки Brian
if exist "%targetFolder%" (
    echo Папка "%targetFolder%" уже существует. Архив не будет распакован.
    exit /b
)

:: Проверка наличия файла tweaks.7z
if exist "%archivePath%" (
    echo Распаковка архива %archivePath%...
    "%sevenZipPath%" x "%archivePath%"
    echo Архив успешно распакован.
) else (
    echo Файл %archivePath% не найден.
)

launcher.exe main.exe