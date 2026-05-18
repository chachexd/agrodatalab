# Cómo arrancar AgroDataLab EnviroPro en tu máquina

Hola compañero. Sigue estos pasos para tener la app corriendo localmente.

## Requisitos previos

- **Python 3.10 o superior** instalado. Descárgalo de <https://www.python.org/downloads/> y
  durante la instalación marca la casilla **"Add Python to PATH"**.
- Comprueba que funciona abriendo PowerShell y escribiendo `python --version`.

## Arranque en 3 pasos

### 1. Descomprime el zip donde quieras

Por ejemplo en `C:\Users\TUUSUARIO\Documents\AgroDataLab\proyecto`.

### 2. Abre PowerShell en esa carpeta

Click derecho dentro de la carpeta → "Abrir en Terminal" (o navega con `cd`).

### 3. Doble clic en `iniciar.bat`

Eso instala dependencias, ejecuta el análisis, aplica migraciones,
puebla la base de datos y arranca el servidor.

Cuando veas en la consola:

```
Starting development server at http://127.0.0.1:8000/
```

abre tu navegador en <http://127.0.0.1:8000/> y verás la página de inicio
verde de **AgroDataLab EnviroPro**.

## Si prefieres hacerlo a mano (sin .bat)

```powershell
cd <ruta-al-proyecto>

# Instalar dependencias (1ª vez, ~2 min)
pip install -r requirements.txt

# Análisis (genera gráficas y dataset limpio)
python analisis\main.py

# Levantar la web
cd web
python manage.py migrate
python manage.py poblar_bbdd --solo-resumen
python manage.py runserver
```

## URLs principales

| URL | Descripción |
|---|---|
| <http://127.0.0.1:8000/> | Página de inicio |
| <http://127.0.0.1:8000/dashboard/> | KPIs, gráficas y alertas recientes |
| <http://127.0.0.1:8000/humedad/> | Lecturas y gráficas de humedad |
| <http://127.0.0.1:8000/temperatura/> | Lecturas y gráficas de temperatura |
| <http://127.0.0.1:8000/energia/> | Batería y panel solar |
| <http://127.0.0.1:8000/alertas/> | Listado de alertas con filtros |
| <http://127.0.0.1:8000/recomendaciones/> | CRUD de recomendaciones |
| <http://127.0.0.1:8000/admin/> | Panel admin de Django |

## Crear un usuario para entrar y probar el CRUD

En otra ventana de PowerShell (deja el servidor corriendo en la primera):

```powershell
cd <ruta-al-proyecto>\web
python manage.py createsuperuser
```

Te pedirá username, email y contraseña. Luego entras en
<http://127.0.0.1:8000/cuentas/login/>.

## Problemas comunes

- **"python no se reconoce"** → no instalaste Python con "Add to PATH". Reinstálalo marcando esa casilla.
- **El servidor no arranca, error de puerto en uso** → cierra el servidor antiguo o usa otro puerto: `python manage.py runserver 8001` y abre `http://127.0.0.1:8001/`.
- **Aparece "The install worked successfully"** → es la página por defecto de Django; significa que el `urls.py` no se está cargando. Verifica que la carpeta del proyecto no se descomprimió mal.
- **Para parar el servidor** → Ctrl+C en la consola.

## Estructura del proyecto

```
proyecto/
├── analisis/              # Pipeline Python: limpieza, EDA, modelo, gráficas
│   ├── analizador.py
│   ├── main.py
│   ├── notebook_analisis.ipynb
│   ├── datos/             # CSV original
│   ├── graficas/          # 12 PNGs generados
│   └── salidas/           # Datasets limpios + modelo + JSONs
├── web/                   # Aplicación Django
│   ├── manage.py
│   ├── agrodatalab/       # Configuración del proyecto
│   ├── enviropro/         # App con modelos, vistas, comandos
│   ├── templates/         # HTML
│   └── static/            # CSS
├── docs/                  # Guion del vídeo
├── README.md
├── requirements.txt
└── iniciar.bat            # Arranque rápido (doble clic)
```

Cualquier duda, pregunta al autor del proyecto. ¡A disfrutar!
