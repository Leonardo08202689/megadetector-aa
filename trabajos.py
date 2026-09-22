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


def registrar_resultado(id_trabajo, archivo, detecciones):
    """Añade una línea al historial de resultados del trabajo."""
    with open(_ruta(id_trabajo, "resultados.jsonl"), "a", encoding="utf-8") as f:
        f.write(json.dumps({
            "archivo": archivo,
            "detecciones": [
                {"clase": d["category"], "confianza": round(d["confidence"], 4)}
                for d in detecciones
            ],
        }, ensure_ascii=False) + "\n")


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
