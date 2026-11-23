@echo off
rem Programi kendi bilgisayarinda Windows uygulamasina (exe) cevirir.
rem Gereksinim: Python 3.8+ (tkinter dahil, python.org kurulumunda gelir).
rem Sonuc: dist\WarThunderSimAssist\WarThunderSimAssist.exe
rem Not: GitHub'a etiket (v1.0.0 gibi) gonderirsen bunu GitHub kendisi de yapar.

cd /d "%~dp0"
python -m pip install "pyinstaller>=6,<7" || goto :hata
pyinstaller --noconfirm --clean --windowed --name WarThunderSimAssist --icon assets\icon.ico src\warthunder_sim_assist.py || goto :hata

echo.
echo Tamam: dist\WarThunderSimAssist\WarThunderSimAssist.exe
pause
exit /b 0

:hata
echo.
echo Derleme basarisiz oldu. Yukaridaki hata mesajina bak.
pause
exit /b 1
