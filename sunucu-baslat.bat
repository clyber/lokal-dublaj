@echo off
rem Lokal Dublaj sunucusunu baslatir (ayarlar: ayarlar.toml). Hatalar is\sunucu.log'a yazilir.
cd /d "%~dp0"
set PYTHONIOENCODING=utf-8
if not exist is mkdir is
.venv\Scripts\python sunucu.py >> is\sunucu.log 2>&1
