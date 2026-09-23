"""Cola persistente de análisis. Ejecutar un único worker por directorio de trabajos."""
import logging
import os
from pathlib import Path
import time
import zipfile

import motor
import trabajos

INTERVALO_SONDEO = 3
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
log = logging.getLogger("worker")


def comprimir(carpeta, destino):
    temporal = str(destino) + ".tmp"
    with zipfile.ZipFile(temporal, "w", zipfile.ZIP_DEFLATED) as zf:
        for ruta in sorted(Path(carpeta).rglob("*")):
            if ruta.is_file() and not ruta.name.endswith(".tmp"):
                zf.write(ruta, arcname=ruta.relative_to(carpeta))
    os.replace(temporal, destino)


def procesar(id_trabajo):
    datos = trabajos.leer(id_trabajo)
    if not datos:
        return
    entrada = Path(trabajos.ruta_entrada(id_trabajo))
    salida = entrada.parent
    umbral = datos["umbral"]
    motor.preparar(entrada, salida, umbral, migrar=True)
    archivos = sorted(p for p in entrada.iterdir() if p.is_file())
    datos.update(version=motor.VERSION, estado=trabajos.PROCESANDO, iniciado=datos.get("iniciado") or time.time(),
                 total=len(archivos), error=None)
    trabajos.escribir(id_trabajo, datos)
    anteriores = {r["archivo"]: r for r in motor.leer_registros(salida)}
    resultados = []
    datos.update(motor.totales([]))
    for origen in archivos:
        if not trabajos.leer(id_trabajo):
            return  # eliminado por el usuario
        registro = anteriores.get(origen.name)
        if not motor.vigente(registro, origen, salida):
            registro = motor.analizar(origen, salida, umbral)
        resultados.append(registro)
        for clave, valor in motor.totales([registro]).items():
            datos[clave] += valor
        trabajos.escribir(id_trabajo, datos)
    datos.update(motor.totales(resultados))
    for grupo in ("con_deteccion", "sin_deteccion"):
        if datos[grupo]:
            comprimir(salida / grupo, trabajos.ruta_zip(id_trabajo, grupo))
        else:
            Path(trabajos.ruta_zip(id_trabajo, grupo)).unlink(missing_ok=True)
    datos.update(estado=trabajos.TERMINADO, terminado=time.time())
    trabajos.escribir(id_trabajo, datos)
    log.info("Terminado %s: %s", id_trabajo, motor.totales(resultados))


def siguiente_trabajo():
    lista = trabajos.listar()
    interrumpidos = [d for d in lista if d["estado"] == trabajos.PROCESANDO]
    pendientes = [d for d in lista if d["estado"] == trabajos.PENDIENTE]
    cola = interrumpidos or pendientes
    return cola[-1]["id"] if cola else None


def main():
    os.makedirs(trabajos.RUTA_TRABAJOS, exist_ok=True)
    log.info("Worker listo. Vigilando %s", trabajos.RUTA_TRABAJOS)
    while True:
        id_trabajo = siguiente_trabajo()
        if id_trabajo is None:
            time.sleep(INTERVALO_SONDEO)
            continue
        try:
            procesar(id_trabajo)
        except Exception as error:
            log.exception("Error procesando %s", id_trabajo)
            datos = trabajos.leer(id_trabajo)
            if datos:
                datos.update(estado=trabajos.ERROR, error=str(error))
                trabajos.escribir(id_trabajo, datos)


if __name__ == "__main__":
    main()
