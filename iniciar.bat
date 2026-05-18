@echo off
REM === AgroDataLab EnviroPro - arranque rapido ===
echo.
echo === Instalando dependencias ===
pip install -r requirements.txt
echo.
echo === Ejecutando analisis y generando graficas ===
python analisis\main.py
echo.
echo === Aplicando migraciones Django ===
cd web
python manage.py migrate
echo.
echo === Poblando base de datos (850 lecturas + 1824 alertas) ===
python manage.py poblar_bbdd --solo-resumen
echo.
echo === Arrancando servidor ===
echo Abre tu navegador en: http://127.0.0.1:8000/
echo.
echo Usuario admin opcional: python manage.py createsuperuser
echo Pulsa Ctrl+C para detener el servidor.
echo.
python manage.py runserver
