"""Trabajos persistentes compartidos por la interfaz y el worker."""
from datetime import datetime
import json
import os
from pathlib import Path
import shutil
import tempfile
import time
import uuid
import zipfile

BASE = Path(__file__).resolve().parent
RUTA_TRABAJOS = os.environ.get("RUTA_TRABAJOS", str(BASE / "datos" / "trabajos"))
RUTA_IMPORTAR = os.environ.get("RUTA_IMPORTAR", str(BASE / "importar"))
MAX_BYTES = int(os.environ.get("MAX_BYTES_TRABAJO", str(20 * 1024**3)))
MAX_ARCHIVOS = int(os.environ.get("MAX_ARCHIVOS_TRABAJO", "50000"))
EXTENSIONES = {".jpg", ".jpeg", ".png", ".mp4", ".avi", ".mov", ".mkv", ".m4v", ".mpg", ".mpeg", ".wmv"}
PENDIENTE, PROCESANDO, TERMINADO, ERROR = "pendiente", "procesando", "terminado", "error"


def _ruta(id_trabajo, *partes):
    if not id_trabajo or Path(id_trabajo).name != id_trabajo or id_trabajo in (".", ".."):
        raise ValueError("Identificador de trabajo inválido.")
    return os.path.join(RUTA_TRABAJOS, id_trabajo, *partes)


def ruta_entrada(id_trabajo):
    return _ruta(id_trabajo, "entrada")


def ruta_con_deteccion(id_trabajo):
    return _ruta(id_trabajo, "con_deteccion")


def ruta_sin_deteccion(id_trabajo):
    return _ruta(id_trabajo, "sin_deteccion")


def ruta_zip(id_trabajo, cual):
    if cual not in ("con_deteccion", "sin_deteccion"):
        raise ValueError("Descarga inválida.")
    return _ruta(id_trabajo, f"{cual}.zip")


def leer(id_trabajo):
    try:
        with open(_ruta(id_trabajo, "trabajo.json"), encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def escribir(id_trabajo, datos):
    destino = _ruta(id_trabajo, "trabajo.json")
    with tempfile.NamedTemporaryFile(mode="w", dir=Path(destino).parent,
                                     encoding="utf-8", delete=False) as f:
        temporal = f.name
        try:
            json.dump(datos, f, ensure_ascii=False, indent=2)
            f.flush()
            os.fsync(f.fileno())
        except BaseException:
            os.unlink(temporal)
            raise
    try:
        os.replace(temporal, destino)
    finally:
        if os.path.exists(temporal):
            os.unlink(temporal)


def _nombre_libre(carpeta, nombre):
    raiz, extension = os.path.splitext(nombre)
    destino = os.path.join(carpeta, nombre)
    contador = 2
    while os.path.exists(destino):
        destino = os.path.join(carpeta, f"{raiz}_{contador}{extension}")
        contador += 1
    return destino


class Limites:
    def __init__(self):
        self.bytes = self.archivos = 0

    def reservar(self, size, carpeta):
        if self.archivos + 1 > MAX_ARCHIVOS or self.bytes + size > MAX_BYTES:
            raise ValueError("La tanda supera el límite de archivos o tamaño descomprimido.")
        if shutil.disk_usage(carpeta).free < size + 100 * 1024**2:
            raise ValueError("No queda suficiente espacio en disco para importar la tanda.")
        self.bytes += size
        self.archivos += 1


def _extraer_zip(archivo, destino, limites):
    with zipfile.ZipFile(archivo) as zf:
        for info in zf.infolist():
            base = os.path.basename(info.filename.replace("\\", "/"))
            if info.is_dir() or base.startswith(".") or Path(base).suffix.lower() not in EXTENSIONES:
                continue
            limites.reservar(info.file_size, destino)
            with zf.open(info) as origen, open(_nombre_libre(destino, base), "wb") as salida:
                restante = info.file_size
                while bloque := origen.read(min(1024**2, restante + 1)):
                    restante -= len(bloque)
                    if restante < 0:
                        raise ValueError("El ZIP contiene tamaños inconsistentes.")
                    salida.write(bloque)


def _crear(nombre, umbral, llenar):
    if not 0 <= umbral <= 1:
        raise ValueError("El umbral debe estar entre 0 y 1.")
    os.makedirs(RUTA_TRABAJOS, exist_ok=True)
    id_trabajo = f"{datetime.now():%Y%m%d-%H%M%S}-{uuid.uuid4().hex}"
    # Una tanda fallida nunca se publica ni deja archivos huérfanos.
    with tempfile.TemporaryDirectory(prefix=".importando-", dir=RUTA_TRABAJOS) as temporal:
        entrada = Path(temporal) / "entrada"
        entrada.mkdir()
        limites = Limites()
        llenar(str(entrada), limites)
        if not limites.archivos:
            raise ValueError("No hay fotografías ni videos compatibles.")
        datos = dict(version=3, id=id_trabajo, nombre=nombre or id_trabajo, estado=PENDIENTE,
                     umbral=umbral, total=limites.archivos, procesadas=0, con_deteccion=0,
                     sin_deteccion=0, detecciones=0, errores=0, incompletos=0,
                     creado=time.time(), iniciado=None, terminado=None, error=None)
        (Path(temporal) / "trabajo.json").write_text(json.dumps(datos, ensure_ascii=False), encoding="utf-8")
        os.rename(temporal, _ruta(id_trabajo))
    return id_trabajo


def crear(nombre, umbral, archivos):
    def llenar(destino, limites):
        for archivo in archivos:
            seguro = os.path.basename(archivo.name.replace("\\", "/"))
            if seguro.lower().endswith(".zip"):
                archivo.seek(0)
                _extraer_zip(archivo, destino, limites)
            elif Path(seguro).suffix.lower() in EXTENSIONES and not seguro.startswith("."):
                contenido = archivo.getbuffer()
                limites.reservar(len(contenido), destino)
                with open(_nombre_libre(destino, seguro), "wb") as f:
                    f.write(contenido)
            else:
                raise ValueError(f"Formato no admitido: {seguro}")
    return _crear(nombre, umbral, llenar)


def _dentro_de(ruta, base):
    return Path(ruta).resolve().is_relative_to(Path(base).resolve())


def carpetas_importables():
    base = Path(RUTA_IMPORTAR)
    if not base.is_dir():
        return []
    opciones = []
    for carpeta in [base] + sorted(p for p in base.iterdir() if p.is_dir()):
        if not _dentro_de(carpeta, base):
            continue
        n = sum(p.is_file() and _dentro_de(p, base) and p.suffix.lower() in EXTENSIONES
                for p in carpeta.iterdir())
        if n:
            opciones.append((str(carpeta), "(raíz)" if carpeta == base else carpeta.name, n))
    return opciones


def _llenar_carpeta(ruta, destino, limites, base=None, enlazar=False):
    for p in sorted(Path(ruta).iterdir()):
        if not p.is_file() or p.suffix.lower() not in EXTENSIONES:
            continue
        if base is not None and not _dentro_de(p, base):
            raise ValueError("Un archivo enlazado está fuera del directorio de importación.")
        limites.reservar(p.stat().st_size, destino)
        hacia = Path(destino) / p.name
        if enlazar:
            try:
                os.link(p, hacia)
                continue
            except OSError:
                pass
        # Importar crea una instantánea: cambios posteriores no alteran el trabajo.
        shutil.copy2(p, hacia)


def crear_desde_carpeta(ruta, nombre, umbral):
    if not _dentro_de(ruta, RUTA_IMPORTAR):
        raise ValueError("La carpeta está fuera del directorio de importación.")
    return _crear(nombre or Path(ruta).name, umbral,
                  lambda d, l: _llenar_carpeta(ruta, d, l, base=RUTA_IMPORTAR))


def reprocesar(id_origen, nombre, umbral):
    origen = leer(id_origen)
    if not origen or origen["estado"] not in (TERMINADO, ERROR):
        raise ValueError("Solo se pueden reanalizar trabajos terminados o con error.")
    return _crear(nombre or f"{origen['nombre']} (umbral {umbral * 100:.0f}%)", umbral,
                  lambda d, l: _llenar_carpeta(ruta_entrada(id_origen), d, l, enlazar=True))


def listar():
    if not os.path.isdir(RUTA_TRABAJOS):
        return []
    datos = [leer(n) for n in os.listdir(RUTA_TRABAJOS) if not n.startswith(".")]
    return sorted((d for d in datos if d), key=lambda d: d.get("creado", 0), reverse=True)


def eliminar(id_trabajo):
    datos = leer(id_trabajo)
    if datos and datos["estado"] in (PENDIENTE, PROCESANDO):
        raise ValueError("Espera a que termine el trabajo antes de eliminarlo.")
    shutil.rmtree(_ruta(id_trabajo))


def leer_resultados(id_trabajo):
    carpeta = Path(_ruta(id_trabajo, "registros"))
    if carpeta.is_dir():
        registros = []
        for ruta in carpeta.glob("*.json"):
            try:
                registros.append(json.loads(ruta.read_text(encoding="utf-8")))
            except (OSError, ValueError):
                continue
        return registros
    # Compatibilidad de lectura: los trabajos terminados anteriores no se modifican.
    try:
        lineas = Path(_ruta(id_trabajo, "resultados.jsonl")).read_text(encoding="utf-8").splitlines()
    except OSError:
        return []
    registros = {}
    for linea in lineas:
        try:
            r = json.loads(linea)
            registros[r["archivo"]] = r
        except (ValueError, KeyError):
            continue
    return list(registros.values())
