"""
Procesador de trabajos en segundo plano.

Corre como un contenedor aparte de la interfaz web: toma los trabajos que se
van encolando y los procesa uno por uno, escribiendo los resultados a disco
conforme avanza. Como no depende de ninguna sesión de navegador, el usuario
puede cerrar la pestaña o apagar su computadora sin perder el trabajo.

Si el propio worker se reinicia a media tanda, al arrancar retoma el trabajo
donde se quedó: las fotografías ya procesadas están en disco y se saltan.
"""
import logging
import os
import shutil
import time
import zipfile

from PIL import Image

import pipeline
import trabajos

INTERVALO_SONDEO = 3  # segundos entre revisiones de la cola

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("worker")


def nombre_anotado(nombre):
    """Las anotadas siempre se guardan como JPEG, sea cual sea el original."""
    return os.path.splitext(nombre)[0] + ".jpg"


def ya_procesada(id_trabajo, nombre):
    """Una fotografía está lista si su resultado ya existe en alguna salida."""
    return (
        os.path.exists(os.path.join(
            trabajos.ruta_con_deteccion(id_trabajo), nombre_anotado(nombre)))
        or os.path.exists(os.path.join(
            trabajos.ruta_sin_deteccion(id_trabajo), nombre))
    )


def comprimir(carpeta, destino):
    """Arma un ZIP leyendo desde disco, sin cargarlo entero en memoria."""
    temporal = destino + ".tmp"
    with zipfile.ZipFile(temporal, "w", zipfile.ZIP_DEFLATED) as zf:
        for nombre in sorted(os.listdir(carpeta)):
            zf.write(os.path.join(carpeta, nombre), arcname=nombre)
    os.replace(temporal, destino)


def procesar(id_trabajo):
    datos = trabajos.leer(id_trabajo)
    if not datos:
        return

    umbral = datos.get("umbral", 0.2)
    entrada = trabajos.ruta_entrada(id_trabajo)
    dir_con = trabajos.ruta_con_deteccion(id_trabajo)
    dir_sin = trabajos.ruta_sin_deteccion(id_trabajo)

    archivos = sorted(os.listdir(entrada))
    datos["estado"] = trabajos.PROCESANDO
    datos["iniciado"] = datos.get("iniciado") or time.time()
    datos["total"] = len(archivos)
    trabajos.escribir(id_trabajo, datos)

    log.info("Trabajo %s: %d fotografías, umbral %.2f",
             datos.get("nombre", id_trabajo), len(archivos), umbral)

    con = len(os.listdir(dir_con))
    sin = len(os.listdir(dir_sin))
    detecciones = sum(len(r["detecciones"]) for r in trabajos.leer_resultados(id_trabajo))

    for indice, nombre in enumerate(archivos, 1):
        if ya_procesada(id_trabajo, nombre):
            continue  # se retoma tras un reinicio

        origen = os.path.join(entrada, nombre)
        try:
            imagen = Image.open(origen)
            anotada, encontradas = pipeline.process_image(imagen, umbral)

            if encontradas:
                # Solo se recodifica cuando hubo algo que dibujar. La extensión
                # se ajusta a .jpg para que el archivo no mienta sobre su
                # contenido, que es lo que pasaba antes con los .png.
                anotada.save(
                    os.path.join(dir_con, nombre_anotado(nombre)),
                    format="JPEG", quality=85,
                )
                con += 1
            else:
                # Sin detecciones la fotografía no cambia: se entrega intacta
                shutil.copy2(origen, os.path.join(dir_sin, nombre))
                sin += 1

            detecciones += len(encontradas)
            trabajos.registrar_resultado(id_trabajo, nombre, encontradas)

        except Exception:
            log.exception("Falló la fotografía %s", nombre)
            # Se cuenta como vacía para no bloquear el resto de la tanda
            shutil.copy2(origen, os.path.join(dir_sin, nombre))
            sin += 1
            trabajos.registrar_resultado(id_trabajo, nombre, [])

        datos["procesadas"] = indice
        datos["con_deteccion"] = con
        datos["sin_deteccion"] = sin
        datos["detecciones"] = detecciones
        trabajos.escribir(id_trabajo, datos)

    log.info("Comprimiendo resultados de %s", id_trabajo)
    if con:
        comprimir(dir_con, trabajos.ruta_zip(id_trabajo, "con_deteccion"))
    if sin:
        comprimir(dir_sin, trabajos.ruta_zip(id_trabajo, "sin_deteccion"))

    datos["estado"] = trabajos.TERMINADO
    datos["terminado"] = time.time()
    trabajos.escribir(id_trabajo, datos)
    log.info("Terminado %s: %d con detección, %d sin detección", id_trabajo, con, sin)


def siguiente_trabajo():
    """
    El más antiguo que esté pendiente. Los que quedaron en 'procesando' tras un
    corte se retoman primero, porque ya tienen avance que aprovechar.
    """
    pendientes, interrumpidos = [], []
    for datos in trabajos.listar():
        if datos["estado"] == trabajos.PENDIENTE:
            pendientes.append(datos)
        elif datos["estado"] == trabajos.PROCESANDO:
            interrumpidos.append(datos)
    # listar() entrega del más reciente al más antiguo, así que el último
    # elemento es el más viejo: se atiende por orden de llegada.
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
        except Exception:
            log.exception("Error procesando el trabajo %s", id_trabajo)
            datos = trabajos.leer(id_trabajo)
            if datos:
                datos["estado"] = trabajos.ERROR
                datos["error"] = "Ocurrió un error al procesar. Revisa los registros."
                trabajos.escribir(id_trabajo, datos)


if __name__ == "__main__":
    main()
