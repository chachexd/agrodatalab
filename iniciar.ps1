# === AgroDataLab EnviroPro - arranque rapido (PowerShell) ===
$ErrorActionPreference = "Stop"
$Root = Split-Path $MyInvocation.MyCommand.Path -Parent
Set-Location $Root

Write-Host "`n=== Instalando dependencias ===" -ForegroundColor Green
pip install -r requirements.txt

Write-Host "`n=== Ejecutando analisis ===" -ForegroundColor Green
python analisis\main.py

Write-Host "`n=== Aplicando migraciones Django ===" -ForegroundColor Green
Set-Location web
python manage.py migrate

Write-Host "`n=== Poblando base de datos ===" -ForegroundColor Green
python manage.py poblar_bbdd --solo-resumen

Write-Host "`n=== Arrancando servidor ===" -ForegroundColor Green
Write-Host "Abre tu navegador en: http://127.0.0.1:8000/" -ForegroundColor Yellow
Write-Host "Pulsa Ctrl+C para detener.`n" -ForegroundColor Yellow
python manage.py runserver
