# Detector de Fauna

Analiza fotografías y videos de cámaras trampa con MegaDetector V6. La interfaz
web recibe trabajos y un worker independiente los procesa aunque se cierre el
navegador. Detecta animales, personas y vehículos; no identifica especies.

## Docker

```sh
docker compose up -d --build
```

Abrir `http://localhost:8501`. Desde otra computadora de la red, usar la IP del
servidor. Docker inicia la interfaz y el worker. Los originales y resultados
persisten en el volumen `megadetector-trabajos` y los pesos en
`megadetector-models`. Para importar tandas grandes, copiar una carpeta a
`importar/` y elegirla en la interfaz.

Actualizar el código requiere reconstruir ambos servicios con el comando
anterior. No eliminar los volúmenes al actualizar.

## Linux sin Docker

Python 3.11 y las bibliotecas del sistema `libgl1` y `libglib2.0-0`.
`instalar.sh` prepara el entorno Conda. Alternativamente:

```sh
python3.11 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
python servir.py --server.address 0.0.0.0 --server.port 8501
```

En otra terminal, con el mismo entorno activo:

```sh
python worker.py
```

Usar **`python servir.py`**, que añade las descargas desde disco al servidor
Streamlit. Ejecutar solo `streamlit run streamlit_app.py` no habilita esa ruta.
El adaptador de descargas usa una API interna de Streamlit 1.32.0; su integración
se prueba en `tests/test_web.py` y debe verificarse al cambiar esa versión.

Fuera de Docker, los trabajos se guardan en `datos/trabajos/` junto al código.
`RUTA_TRABAJOS` y `RUTA_IMPORTAR` permiten cambiar las rutas. Ambos procesos deben
usar la misma configuración. Ejecutar un único worker por directorio de trabajos.

## Resultados y recuperación

- **Con detección:** imágenes anotadas o video original con su cuadro de evidencia.
- **Sin detección:** originales analizados correctamente sin detecciones suficientes.
- **Error:** no se logró analizar el archivo. No se considera vacío.
- **Incompleto:** no se pudo completar el muestreo del video, por límite o lectura.

Los videos se muestrean a un cuadro por segundo, hasta 120 cuadros, y se detienen
al encontrar una detección. Un video que excede el límite sin detecciones queda
incompleto. El muestreo puede omitir movimientos rápidos incluso en videos
analizados completamente; los resultados requieren criterio humano.

Las incidencias aparecen en la interfaz y sus originales permanecen en el
trabajo. Se puede volver a analizar el trabajo incluso con el mismo umbral.
Los ZIP solo contienen los resultados válidos. Las imágenes están directamente
en las carpetas `animal`, `persona`, `carro`, `bajo_umbral` o `vacias`.
Los JPG conservan su nombre original; los PNG y los cuadros de video reciben
un sufijo estable para evitar colisiones. Cada registro conserva la relación
entre original y resultado.

Al reiniciar, se comprueban el registro confirmado, el original y las salidas
antes de omitir un archivo. Un resultado incompleto se vuelve a procesar.
Los trabajos antiguos terminados siguen disponibles. Los trabajos antiguos
interrumpidos se recalculan; sus resultados previos se guardan en una subcarpeta
`anteriores-*`. Para corregir resultados antiguos por el cambio de canales RGB/BGR,
crear un nuevo análisis: no se modifican retrospectivamente.

## Consola

```sh
python procesar_carpeta.py /ruta/fotos -s /ruta/resultados -u 20
```

La misma ejecución reanuda éxitos verificables y reintenta errores. Para usar otro
umbral, modelo o entrada, indicar **otra carpeta de salida**; no se mezclan
resultados. Las salidas antiguas sin configuración verificable también requieren
una carpeta nueva. El detalle se exporta a `resultados.csv`; los registros por
archivo permiten reanudar aunque se interrumpa antes de exportarlo.
La salida del proceso es 1 si quedan errores o videos incompletos, y 0 si todo
termina correctamente.

## Límites y acceso

Cada tanda admite por defecto hasta 50.000 archivos y 20 GiB descomprimidos.
Se pueden ajustar `MAX_ARCHIVOS_TRABAJO` y `MAX_BYTES_TRABAJO` en la interfaz.
La extracción usa bloques pequeños, comprueba espacio disponible y descarta
la tanda completa si hay un error. Reservar espacio adicional para resultados
y ZIP: estos límites no son una cuota global de almacenamiento.

La aplicación es un espacio compartido para una red de confianza: no tiene
cuentas ni permisos por propietario. Cualquier persona con acceso puede ver,
descargar y eliminar trabajos terminados. Para exponerla fuera de esa red,
colocarla detrás de un control de acceso. Eliminar trabajos activos está
bloqueado para evitar conflictos con el worker.

## Pruebas

```sh
python -m unittest discover -s tests -v
```

Las pruebas usan directorios temporales y un detector simulado; no descargan
pesos ni modifican datos reales. Las pruebas HTTP abren puertos de localhost.
Cubren errores, reanudación, colisiones, canales de color, videos, importación,
descargas parciales y filtros de la galería. No miden la precisión del modelo.
