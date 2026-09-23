#!/usr/bin/env python3
"""
Procesa una carpeta de fotografías y videos desde la línea de comandos.

Pensado para tandas grandes en una máquina con tarjeta gráfica, donde el
análisis es del orden de veinte veces más rápido que en el servidor. Usa la
GPU automáticamente si hay una disponible; si no, cae a CPU.

    python procesar_carpeta.py ~/fotos
    python procesar_carpeta.py ~/fotos -s ~/resultados -u 15

Separa los archivos en <salida>/con_deteccion y <salida>/sin_deteccion, y
escribe un resultados.csv con una línea por archivo.

Se puede interrumpir con Ctrl+C y volver a ejecutarlo: continúa donde se quedó.
"""
import argparse
import csv
import os
import shutil
import sys
import time

from PIL import Image

import pipeline
from worker import copiar, guardar_anotada, nombre_anotado

EXTENSIONES = {".jpg", ".jpeg", ".png"} | pipeline.EXTENSIONES_VIDEO

# Subcarpetas dentro de con_deteccion, una por tipo detectado.
CARPETA_CLASE = {"animal": "animal", "person": "persona", "vehicle": "carro"}


def enlazar(origen, destino):
    """
    Deja el mismo archivo en otra carpeta sin ocupar espacio de nuevo.

    Una fotografía con un animal y una persona aparece en las dos subcarpetas;
    con enlaces duros es el mismo archivo con dos nombres, no una copia.
    """
    if os.path.exists(destino):
        return
    try:
        os.link(origen, destino)
    except OSError:
        shutil.copy2(origen, destino)


def subcarpetas(dir_con, detecciones):
    """Carpetas donde debe aparecer una fotografía, según lo que se detectó."""
    clases = sorted({d["category"] for d in detecciones})
    rutas = [os.path.join(dir_con, CARPETA_CLASE[c])
             for c in clases if c in CARPETA_CLASE]
    return rutas or [dir_con]


def formato(segundos):
    segundos = int(segundos)
    if segundos < 60:
        return f"{segundos}s"
    if segundos < 3600:
        return f"{segundos // 60}m {segundos % 60:02d}s"
    return f"{segundos // 3600}h {(segundos % 3600) // 60:02d}m"


def main():
    parser = argparse.ArgumentParser(
        description="Detecta fauna en una carpeta de fotografías y videos.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("entrada", help="carpeta con las fotografías o videos")
    parser.add_argument("-s", "--salida",
                        help="carpeta de resultados (por defecto: <entrada>_resultados)")
    parser.add_argument("-u", "--umbral", type=float, default=20,
                        help="umbral de confianza en porcentaje (por defecto: 20)")
    args = parser.parse_args()

    entrada = os.path.abspath(os.path.expanduser(args.entrada))
    if not os.path.isdir(entrada):
        sys.exit(f"No existe la carpeta: {entrada}")

    salida = os.path.abspath(os.path.expanduser(
        args.salida or entrada.rstrip("/") + "_resultados"))
    dir_con = os.path.join(salida, "con_deteccion")
    dir_sin = os.path.join(salida, "sin_deteccion")
    os.makedirs(dir_sin, exist_ok=True)
    # Una subcarpeta por tipo dentro de con_deteccion
    for sub in CARPETA_CLASE.values():
        os.makedirs(os.path.join(dir_con, sub), exist_ok=True)
    ruta_csv = os.path.join(salida, "resultados.csv")

    umbral = args.umbral / 100.0

    archivos = sorted(
        n for n in os.listdir(entrada)
        if os.path.splitext(n)[1].lower() in EXTENSIONES
        and os.path.isfile(os.path.join(entrada, n))
    )
    if not archivos:
        sys.exit(f"No hay fotografías ni videos en {entrada}")

    # Lo ya procesado en una ejecución anterior se salta
    hechos = set()
    if os.path.exists(ruta_csv):
        with open(ruta_csv, newline="", encoding="utf-8") as f:
            hechos = {fila["archivo"] for fila in csv.DictReader(f)}

    pendientes = [n for n in archivos if n not in hechos]

    print(f"Carpeta   : {entrada}")
    print(f"Resultados: {salida}")
    print(f"Umbral    : {args.umbral:.0f}%")
    if hechos:
        print(f"Ya procesados en una ejecución anterior: {len(hechos)}")
    print(f"Por procesar: {len(pendientes)} de {len(archivos)}")

    print("\nCargando el modelo...", flush=True)
    pipeline.get_model()
    print(f"Dispositivo: {pipeline.DEVICE}"
          f"{'  (sin GPU disponible, será lento)' if pipeline.DEVICE == 'cpu' else ''}\n",
          flush=True)

    nuevo = not os.path.exists(ruta_csv)
    con = sin = 0
    inicio = time.time()

    with open(ruta_csv, "a", newline="", encoding="utf-8") as f:
        escritor = csv.writer(f)
        if nuevo:
            escritor.writerow(["archivo", "resultado", "clases",
                               "confianza_maxima", "descartado"])

        for indice, nombre in enumerate(pendientes, 1):
            origen = os.path.join(entrada, nombre)
            try:
                if pipeline.es_video(nombre):
                    detecciones, anotada, segundo = pipeline.process_video(origen, umbral)
                    casi = None
                    if detecciones:
                        raiz = os.path.splitext(nombre)[0]
                        cuadro = f"{raiz}_segundo{segundo:.0f}.jpg"
                        carpetas = subcarpetas(dir_con, detecciones)
                        guardar_anotada(anotada, os.path.join(carpetas[0], cuadro))
                        copiar(origen, os.path.join(carpetas[0], nombre))
                        for otra in carpetas[1:]:
                            enlazar(os.path.join(carpetas[0], cuadro),
                                    os.path.join(otra, cuadro))
                            enlazar(os.path.join(carpetas[0], nombre),
                                    os.path.join(otra, nombre))
                else:
                    anotada, detecciones, casi = pipeline.process_image(
                        Image.open(origen), umbral)
                    if detecciones:
                        salida_jpg = nombre_anotado(nombre)
                        carpetas = subcarpetas(dir_con, detecciones)
                        guardar_anotada(anotada,
                                        os.path.join(carpetas[0], salida_jpg))
                        for otra in carpetas[1:]:
                            enlazar(os.path.join(carpetas[0], salida_jpg),
                                    os.path.join(otra, salida_jpg))

                if detecciones:
                    con += 1
                else:
                    copiar(origen, os.path.join(dir_sin, nombre))
                    sin += 1

                escritor.writerow([
                    nombre,
                    "con deteccion" if detecciones else "sin deteccion",
                    " ".join(sorted({d["category"] for d in detecciones})),
                    f"{max((d['confidence'] for d in detecciones), default=0):.3f}",
                    f"{casi['category']} {casi['confidence']:.3f}" if casi else "",
                ])
                f.flush()

            except Exception as error:
                print(f"  ! {nombre}: {type(error).__name__}: {error}", flush=True)
                escritor.writerow([nombre, "error", "", "", ""])
                f.flush()

            if indice % 20 == 0 or indice == len(pendientes):
                transcurrido = time.time() - inicio
                ritmo = transcurrido / indice
                faltan = (len(pendientes) - indice) * ritmo
                print(f"  [{indice}/{len(pendientes)}]  "
                      f"{con} con · {sin} sin  ·  {ritmo:.2f}s por archivo  ·  "
                      f"faltan {formato(faltan)}", flush=True)

    total = time.time() - inicio
    print(f"\nTerminado en {formato(total)}")
    print(f"  Con detección: {con}")
    for clase, sub in CARPETA_CLASE.items():
        ruta = os.path.join(dir_con, sub)
        cuantas = len(os.listdir(ruta)) if os.path.isdir(ruta) else 0
        print(f"      {sub:<8}: {cuantas}")
    print(f"  Sin detección: {sin}")
    print(f"  Detalle en   : {ruta_csv}")


if __name__ == "__main__":
    main()
