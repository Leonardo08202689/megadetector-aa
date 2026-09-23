"""
Gestión de trabajos de análisis.

Un trabajo es una carpeta en disco con las fotografías de entrada, los
resultados y un archivo de estado. Al vivir en disco y no en la sesión del
navegador, el procesamiento sobrevive a que el usuario cierre la pestaña,
apague su computadora o se reinicie el servidor.

Estructura de cada trabajo:

    <RUTA_TRABAJOS>/<id>/
        trabajo.json        estado, umbral, avance y totales
        entrada/            fotografías tal como se subieron
        con_deteccion/      fotografías anotadas
        sin_deteccion/      copias intactas de las que salieron vacías
        resultados.jsonl    una línea por fotografía procesada
        con_deteccion.zip   se generan al terminar
        sin_deteccion.zip
"""
import json
import os
import shutil
import time
import uuid
from datetime import datetime

# El directorio vive en un volumen compartido entre la interfaz y el worker.
RUTA_TRABAJOS = os.environ.get("RUTA_TRABAJOS", "/datos/trabajos")

# Carpeta del servidor desde donde se pueden importar archivos sin subirlos por
# el navegador. Para tandas de miles de archivos la subida por el navegador es
# frágil: depende de que la pestaña aguante y no se puede reanudar. Copiarlos
# antes con rsync o scp sí reanuda y no depende del navegador.
RUTA_IMPORTAR = os.environ.get("RUTA_IMPORTAR", "/datos/importar")

# Extensiones aceptadas. Se define aquí, y no en pipeline, para que la interfaz
# web no tenga que importar torch solo para saber qué archivos listar.
EXTENSIONES = {
    ".jpg", ".jpeg", ".png",
    ".mp4", ".avi", ".mov", ".mkv", ".m4v", ".mpg", ".mpeg", ".wmv",
}

# Estados posibles de un trabajo
PENDIENTE = "pendiente"
PROCESANDO = "procesando"
TERMINADO = "terminado"
ERROR = "error"


def _ruta(id_trabajo, *partes):
    return os.path.join(RUTA_TRABAJOS, id_trabajo, *partes)


def ruta_entrada(id_trabajo):
    return _ruta(id_trabajo, "entrada")


def ruta_con_deteccion(id_trabajo):
    return _ruta(id_trabajo, "con_deteccion")


def ruta_sin_deteccion(id_trabajo):
    return _ruta(id_trabajo, "sin_deteccion")


def ruta_zip(id_trabajo, cual):
    """cual: 'con_deteccion' o 'sin_deteccion'"""
    return _ruta(id_trabajo, f"{cual}.zip")


def _ruta_estado(id_trabajo):
    return _ruta(id_trabajo, "trabajo.json")


def leer(id_trabajo):
    """Devuelve el estado del trabajo, o None si no se puede leer."""
    try:
        with open(_ruta_estado(id_trabajo), encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        # Puede fallar si el worker está escribiendo justo en ese instante;
        # quien llama simplemente reintentará en el siguiente refresco.
        return None


def escribir(id_trabajo, datos):
    """Guarda el estado de forma atómica para que nadie lea un archivo a medias."""
    destino = _ruta_estado(id_trabajo)
    temporal = destino + ".tmp"
    with open(temporal, "w", encoding="utf-8") as f:
        json.dump(datos, f, ensure_ascii=False, indent=2)
    os.replace(temporal, destino)


def crear(nombre, umbral, archivos):
    """
    Crea un trabajo nuevo y guarda las fotografías en disco.

    Args:
        nombre: etiqueta que pone el usuario para reconocerlo
        umbral: float 0-1
        archivos: lista de objetos de st.file_uploader

    Returns:
        id del trabajo creado
    """
    id_trabajo = f"{datetime.now():%Y%m%d-%H%M%S}-{uuid.uuid4().hex[:6]}"
    os.makedirs(ruta_entrada(id_trabajo), exist_ok=True)
    os.makedirs(ruta_con_deteccion(id_trabajo), exist_ok=True)
    os.makedirs(ruta_sin_deteccion(id_trabajo), exist_ok=True)

    for archivo in archivos:
        # basename evita que un nombre con rutas escriba fuera de la carpeta
        seguro = os.path.basename(archivo.name)
        with open(os.path.join(ruta_entrada(id_trabajo), seguro), "wb") as f:
            f.write(archivo.getbuffer())

    escribir(id_trabajo, {
        "id": id_trabajo,
        "nombre": nombre or id_trabajo,
        "estado": PENDIENTE,
        "umbral": umbral,
        "total": len(archivos),
        "procesadas": 0,
        "con_deteccion": 0,
        "sin_deteccion": 0,
        "detecciones": 0,
        "creado": time.time(),
        "iniciado": None,
        "terminado": None,
        "error": None,
    })
    return id_trabajo


def _dentro_de(ruta, base):
    """True si `ruta` está dentro de `base`, resolviendo enlaces simbólicos."""
    ruta = os.path.realpath(ruta)
    base = os.path.realpath(base)
    return ruta == base or ruta.startswith(base + os.sep)


def carpetas_importables():
    """
    Carpetas disponibles en RUTA_IMPORTAR, con cuántos archivos tiene cada una.

    Se listan la raíz y sus subcarpetas directas: suficiente para organizar por
    cámara o por salida de campo, sin exponer el resto del sistema de archivos.
    """
    if not os.path.isdir(RUTA_IMPORTAR):
        return []

    def contar(ruta):
        try:
            return sum(
                1 for n in os.listdir(ruta)
                if os.path.splitext(n)[1].lower() in EXTENSIONES
                and os.path.isfile(os.path.join(ruta, n))
            )
        except OSError:
            return 0

    opciones = []
    sueltos = contar(RUTA_IMPORTAR)
    if sueltos:
        opciones.append((RUTA_IMPORTAR, "(raíz)", sueltos))

    try:
        for nombre in sorted(os.listdir(RUTA_IMPORTAR)):
            ruta = os.path.join(RUTA_IMPORTAR, nombre)
            if os.path.isdir(ruta):
                cuantos = contar(ruta)
                if cuantos:
                    opciones.append((ruta, nombre, cuantos))
    except OSError:
        pass
    return opciones


def crear_desde_carpeta(ruta, nombre, umbral):
    """
    Crea un trabajo con los archivos de una carpeta del servidor.

    No pasa nada por el navegador: los archivos ya están en disco. Se intenta
    enlazarlos en lugar de copiarlos; si la carpeta está en otro sistema de
    archivos que los trabajos, se copian.
    """
    if not _dentro_de(ruta, RUTA_IMPORTAR):
        raise ValueError("La carpeta está fuera del directorio de importación.")

    archivos = sorted(
        n for n in os.listdir(ruta)
        if os.path.splitext(n)[1].lower() in EXTENSIONES
        and os.path.isfile(os.path.join(ruta, n))
    )
    if not archivos:
        raise ValueError("La carpeta no tiene fotografías ni videos.")

    id_trabajo = f"{datetime.now():%Y%m%d-%H%M%S}-{uuid.uuid4().hex[:6]}"
    os.makedirs(ruta_entrada(id_trabajo), exist_ok=True)
    os.makedirs(ruta_con_deteccion(id_trabajo), exist_ok=True)
    os.makedirs(ruta_sin_deteccion(id_trabajo), exist_ok=True)

    for archivo in archivos:
        desde = os.path.join(ruta, archivo)
        hacia = os.path.join(ruta_entrada(id_trabajo), archivo)
        try:
            os.link(desde, hacia)
        except OSError:
            shutil.copy2(desde, hacia)

    escribir(id_trabajo, {
        "id": id_trabajo,
        "nombre": nombre or os.path.basename(ruta.rstrip("/")) or id_trabajo,
        "estado": PENDIENTE,
        "umbral": umbral,
        "total": len(archivos),
        "procesadas": 0,
        "con_deteccion": 0,
        "sin_deteccion": 0,
        "detecciones": 0,
        "creado": time.time(),
        "iniciado": None,
        "terminado": None,
        "error": None,
    })
    return id_trabajo


def reprocesar(id_origen, nombre, umbral):
    """
    Crea un trabajo nuevo reutilizando las fotografías de otro.

    Sirve para volver a analizar con un umbral distinto sin tener que subir
    otra vez los archivos. Se usan enlaces duros para no duplicar el espacio
    en disco: son el mismo archivo con dos nombres, así que borrar un trabajo
    no afecta al otro.
    """
    origen = leer(id_origen)
    id_nuevo = f"{datetime.now():%Y%m%d-%H%M%S}-{uuid.uuid4().hex[:6]}"
    os.makedirs(ruta_entrada(id_nuevo), exist_ok=True)
    os.makedirs(ruta_con_deteccion(id_nuevo), exist_ok=True)
    os.makedirs(ruta_sin_deteccion(id_nuevo), exist_ok=True)

    archivos = os.listdir(ruta_entrada(id_origen))
    for archivo in archivos:
        desde = os.path.join(ruta_entrada(id_origen), archivo)
        hacia = os.path.join(ruta_entrada(id_nuevo), archivo)
        try:
            os.link(desde, hacia)
        except OSError:
            # Sistemas de archivos que no admiten enlaces duros
            shutil.copy2(desde, hacia)

    escribir(id_nuevo, {
        "id": id_nuevo,
        "nombre": nombre or f"{origen.get('nombre', id_origen)} (umbral {umbral*100:.0f}%)",
        "estado": PENDIENTE,
        "umbral": umbral,
        "total": len(archivos),
        "procesadas": 0,
        "con_deteccion": 0,
        "sin_deteccion": 0,
        "detecciones": 0,
        "creado": time.time(),
        "iniciado": None,
        "terminado": None,
        "error": None,
    })
    return id_nuevo


def listar():
    """Todos los trabajos, del más reciente al más antiguo."""
    if not os.path.isdir(RUTA_TRABAJOS):
        return []
    trabajos = []
    for id_trabajo in os.listdir(RUTA_TRABAJOS):
        datos = leer(id_trabajo)
        if datos:
            trabajos.append(datos)
    return sorted(trabajos, key=lambda t: t.get("creado", 0), reverse=True)


def eliminar(id_trabajo):
    """Borra el trabajo y todas sus fotografías."""
    shutil.rmtree(os.path.join(RUTA_TRABAJOS, id_trabajo), ignore_errors=True)


def registrar_resultado(id_trabajo, archivo, detecciones, casi=None):
    """
    Añade una línea al historial de resultados del trabajo.

    `casi` es la mejor detección que no alcanzó el umbral. Sirve para explicar
    por qué una fotografía quedó como vacía: distingue "el modelo no vio nada"
    de "vio algo con poca confianza y se descartó".
    """
    registro = {
        "archivo": archivo,
        "detecciones": [
            {"clase": d["category"], "confianza": round(d["confidence"], 4)}
            for d in detecciones
        ],
    }
    if casi:
        registro["casi"] = {
            "clase": casi["category"],
            "confianza": round(casi["confidence"], 4),
        }
    with open(_ruta(id_trabajo, "resultados.jsonl"), "a", encoding="utf-8") as f:
        f.write(json.dumps(registro, ensure_ascii=False) + "\n")


def leer_resultados(id_trabajo):
    """Lee el historial de resultados; devuelve lista vacía si aún no hay."""
    ruta = _ruta(id_trabajo, "resultados.jsonl")
    if not os.path.exists(ruta):
        return []
    resultados = []
    with open(ruta, encoding="utf-8") as f:
        for linea in f:
            linea = linea.strip()
            if linea:
                try:
                    resultados.append(json.loads(linea))
                except json.JSONDecodeError:
                    # Última línea a medio escribir: se ignora
                    pass
    return resultados
