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
    """
    Un archivo está listo si su resultado ya existe en alguna salida.

    Las fotografías con detección se guardan anotadas como .jpg; los videos se
    copian con su nombre original. Se comprueban ambas formas para que retomar
    un trabajo interrumpido funcione en los dos casos.
    """
    dir_con = trabajos.ruta_con_deteccion(id_trabajo)
    return (
        os.path.exists(os.path.join(dir_con, nombre))
        or os.path.exists(os.path.join(dir_con, nombre_anotado(nombre)))
        or os.path.exists(os.path.join(
            trabajos.ruta_sin_deteccion(id_trabajo), nombre))
    )


def guardar_anotada(imagen, destino):
    """
    Escribe la imagen anotada de forma atómica.

    Sin esto, un corte a mitad de la escritura dejaría un archivo truncado
    que `ya_procesada` daría por bueno, y esa fotografía nunca se volvería a
    procesar. Escribir aparte y renombrar evita que exista un estado
    intermedio visible.
    """
    temporal = destino + ".tmp"
    imagen.save(temporal, format="JPEG", quality=85)
    os.replace(temporal, destino)


def copiar(origen, destino):
    """Copia de forma atómica, por el mismo motivo que guardar_anotada."""
    temporal = destino + ".tmp"
    shutil.copy2(origen, temporal)
    os.replace(temporal, destino)


def comprimir(carpeta, destino):
    """Arma un ZIP leyendo desde disco, sin cargarlo entero en memoria."""
    temporal = destino + ".tmp"
    with zipfile.ZipFile(temporal, "w", zipfile.ZIP_DEFLATED) as zf:
        for nombre in sorted(os.listdir(carpeta)):
            if nombre.endswith(".tmp"):
                continue  # resto de una escritura interrumpida
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

    log.info("Trabajo %s: %d archivos, umbral %.2f",
             datos.get("nombre", id_trabajo), len(archivos), umbral)

    # Los contadores salen del registro de resultados, que tiene una línea por
    # archivo procesado. Contar archivos de las carpetas daría mal: un video
    # con detección deja dos (el video y el cuadro), y podría haber restos .tmp
    # de una interrupción.
    resultados = trabajos.leer_resultados(id_trabajo)
    con = sum(1 for r in resultados if r["detecciones"])
    sin = sum(1 for r in resultados if not r["detecciones"])
    detecciones = sum(len(r["detecciones"]) for r in resultados)

    for indice, nombre in enumerate(archivos, 1):
        if ya_procesada(id_trabajo, nombre):
            continue  # se retoma tras un reinicio

        origen = os.path.join(entrada, nombre)
        try:
            casi = None
            if pipeline.es_video(nombre):
                encontradas, anotada, segundo = pipeline.process_video(origen, umbral)

                if encontradas:
                    # El video se entrega tal cual, acompañado del cuadro donde
                    # apareció el animal: así se revisa la evidencia sin tener
                    # que reproducir el video completo.
                    raiz = os.path.splitext(nombre)[0]
                    guardar_anotada(
                        anotada,
                        os.path.join(dir_con, f"{raiz}_segundo{segundo:.0f}.jpg"),
                    )
                    # El video se copia al final: es lo que marca la
                    # fotografía como procesada al retomar un trabajo
                    copiar(origen, os.path.join(dir_con, nombre))
                    con += 1
                else:
                    copiar(origen, os.path.join(dir_sin, nombre))
                    sin += 1
            else:
                imagen = Image.open(origen)
                anotada, encontradas, casi = pipeline.process_image(imagen, umbral)

                if encontradas:
                    # Solo se recodifica cuando hubo algo que dibujar. La
                    # extensión se ajusta a .jpg para que el archivo no mienta
                    # sobre su contenido, que es lo que pasaba antes con los .png.
                    guardar_anotada(
                        anotada, os.path.join(dir_con, nombre_anotado(nombre)))
                    con += 1
                else:
                    # Sin detecciones la imagen no cambia: se entrega intacta
                    copiar(origen, os.path.join(dir_sin, nombre))
                    sin += 1

            detecciones += len(encontradas)
            trabajos.registrar_resultado(id_trabajo, nombre, encontradas, casi)

        except Exception:
            log.exception("Falló el archivo %s", nombre)
            # Se cuenta como vacío para no bloquear el resto de la tanda
            copiar(origen, os.path.join(dir_sin, nombre))
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
