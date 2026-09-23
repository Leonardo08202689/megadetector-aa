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


# Subcarpetas dentro de con_deteccion, una por tipo detectado, para poder
# revisar por separado la fauna de la actividad humana.
CARPETA_CLASE = {"animal": "animal", "person": "persona", "vehicle": "carro"}

# Subcarpetas dentro de sin_deteccion. Separar las fotografías donde el modelo
# vio algo que no alcanzó el umbral de aquellas donde no vio nada: las
# primeras son las que vale la pena revisar a ojo antes de descartarlas, las
# segundas se pueden dar por vacías con más tranquilidad.
BAJO_UMBRAL = "bajo_umbral"
SIN_NADA = "vacias"


def carpeta_vacia(dir_sin, casi):
    """Dónde va una fotografía sin detección, según si hubo algo descartado."""
    destino = os.path.join(dir_sin, BAJO_UMBRAL if casi else SIN_NADA)
    os.makedirs(destino, exist_ok=True)
    return destino


def nombre_anotado(nombre):
    """Las anotadas siempre se guardan como JPEG, sea cual sea el original."""
    return os.path.splitext(nombre)[0] + ".jpg"


def salidas_existentes(id_trabajo):
    """
    Nombres de archivo que ya se produjeron en este trabajo.

    Se recorre en profundidad porque las detecciones viven en subcarpetas por
    tipo. Se calcula una sola vez al empezar en lugar de comprobar rutas
    archivo por archivo: con tandas de miles, mirar el disco en cada vuelta
    del bucle se nota.
    """
    hechos = set()
    for raiz in (trabajos.ruta_con_deteccion(id_trabajo),
                 trabajos.ruta_sin_deteccion(id_trabajo)):
        for carpeta, _subcarpetas, archivos in os.walk(raiz):
            for archivo in archivos:
                if not archivo.endswith(".tmp"):
                    hechos.add(archivo)
    return hechos


def subcarpetas(dir_con, detecciones):
    """Carpetas donde debe quedar una fotografía, según lo que se detectó."""
    clases = sorted({d["category"] for d in detecciones})
    rutas = [os.path.join(dir_con, CARPETA_CLASE[c])
             for c in clases if c in CARPETA_CLASE]
    for ruta in rutas:
        os.makedirs(ruta, exist_ok=True)
    return rutas or [dir_con]


def enlazar(origen, destino):
    """
    Deja el mismo archivo en otra subcarpeta sin ocupar espacio de nuevo.

    Una fotografía con un animal y una persona aparece en las dos: con enlaces
    duros es el mismo archivo con dos nombres, no una copia.
    """
    if os.path.exists(destino):
        return
    try:
        os.link(origen, destino)
    except OSError:
        shutil.copy2(origen, destino)


def guardar_anotada(imagen, destino):
    """
    Escribe la imagen anotada de forma atómica.

    Sin esto, un corte a mitad de la escritura dejaría un archivo truncado
    que `salidas_existentes` daría por bueno, y esa fotografía nunca se
    volvería a procesar. Escribir aparte y renombrar evita que exista un
    estado intermedio visible.
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
        # Se recorre en profundidad para incluir las subcarpetas por tipo, y
        # se conserva su ruta relativa para que al descomprimir aparezcan
        # animal, persona y carro por separado.
        for actual, _subs, archivos in os.walk(carpeta):
            for nombre in sorted(archivos):
                if nombre.endswith(".tmp"):
                    continue  # resto de una escritura interrumpida
                completa = os.path.join(actual, nombre)
                zf.write(completa, arcname=os.path.relpath(completa, carpeta))
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

    hechos = salidas_existentes(id_trabajo)

    for indice, nombre in enumerate(archivos, 1):
        if nombre in hechos or nombre_anotado(nombre) in hechos:
            continue  # se retoma tras un reinicio

        origen = os.path.join(entrada, nombre)
        try:
            casi = None
            if pipeline.es_video(nombre):
                encontradas, anotada, segundo, casi = pipeline.process_video(origen, umbral)

                if encontradas:
                    # El video se entrega tal cual, acompañado del cuadro donde
                    # apareció el animal: así se revisa la evidencia sin tener
                    # que reproducir el video completo.
                    raiz = os.path.splitext(nombre)[0]
                    cuadro = f"{raiz}_segundo{segundo:.0f}.jpg"
                    carpetas = subcarpetas(dir_con, encontradas)
                    guardar_anotada(anotada, os.path.join(carpetas[0], cuadro))
                    # El video se copia al final: es lo que marca el archivo
                    # como procesado al retomar un trabajo
                    copiar(origen, os.path.join(carpetas[0], nombre))
                    for otra in carpetas[1:]:
                        enlazar(os.path.join(carpetas[0], cuadro),
                                os.path.join(otra, cuadro))
                        enlazar(os.path.join(carpetas[0], nombre),
                                os.path.join(otra, nombre))
                    con += 1
                else:
                    copiar(origen, os.path.join(carpeta_vacia(dir_sin, casi), nombre))
                    sin += 1
            else:
                imagen = Image.open(origen)
                anotada, encontradas, casi = pipeline.process_image(imagen, umbral)

                if encontradas:
                    # Solo se recodifica cuando hubo algo que dibujar. La
                    # extensión se ajusta a .jpg para que el archivo no mienta
                    # sobre su contenido, que es lo que pasaba antes con los .png.
                    destino = nombre_anotado(nombre)
                    carpetas = subcarpetas(dir_con, encontradas)
                    guardar_anotada(anotada, os.path.join(carpetas[0], destino))
                    for otra in carpetas[1:]:
                        enlazar(os.path.join(carpetas[0], destino),
                                os.path.join(otra, destino))
                    con += 1
                else:
                    # Sin detecciones la imagen no cambia: se entrega intacta
                    copiar(origen, os.path.join(carpeta_vacia(dir_sin, casi), nombre))
                    sin += 1

            detecciones += len(encontradas)
            trabajos.registrar_resultado(id_trabajo, nombre, encontradas, casi)

        except Exception:
            log.exception("Falló el archivo %s", nombre)
            # Se cuenta como vacío para no bloquear el resto de la tanda
            copiar(origen, os.path.join(carpeta_vacia(dir_sin, casi), nombre))
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
