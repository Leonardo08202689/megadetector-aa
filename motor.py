"""Procesamiento compartido por la cola y la consola, con recuperación por archivo."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import uuid

from PIL import Image
import pipeline

VERSION = 3
CLASES = {"animal": "animal", "person": "persona", "vehicle": "carro"}


def escribir_json(ruta, datos):
    ruta = Path(ruta)
    temporal = ruta.with_name(ruta.name + ".tmp")
    with temporal.open("w", encoding="utf-8") as f:
        json.dump(datos, f, ensure_ascii=False, indent=2)
        f.flush()
        os.fsync(f.fileno())
    os.replace(temporal, ruta)


def preparar(entrada, salida, umbral, migrar=False):
    """Nunca mezcla resultados de entradas, modelos o umbrales distintos."""
    if not 0 <= umbral <= 1:
        raise ValueError("El umbral debe estar entre 0 y 1.")
    salida = Path(salida)
    salida.mkdir(parents=True, exist_ok=True)
    config = {"version": VERSION, "entrada": str(Path(entrada).resolve()),
              "umbral": umbral, "modelo": pipeline.MODEL_VERSION,
              "fps_muestreo": pipeline.FPS_MUESTREO, "max_cuadros": pipeline.MAX_CUADROS}
    ruta = salida / "analisis.json"
    if ruta.exists():
        anterior = json.loads(ruta.read_text())
        if {k: v for k, v in anterior.items() if k != "version"} != {
                k: v for k, v in config.items() if k != "version"}:
            raise ValueError("La salida pertenece a otro análisis. Usa otra carpeta con --salida.")
        if anterior["version"] == 2:
            aplanar(salida)
            escribir_json(ruta, config)
        elif anterior != config:
            raise ValueError("Versión de resultados no compatible. Usa otra carpeta con --salida.")
    else:
        anteriores = [salida / n for n in ("con_deteccion", "sin_deteccion", "registros",
                      "resultados.csv", "resultados.jsonl", "con_deteccion.zip", "sin_deteccion.zip")
                      if (salida / n).exists()]
        con_datos = any(p.is_file() or any(p.iterdir()) for p in anteriores)
        if con_datos and not migrar:
            raise ValueError("Resultados anteriores sin configuración verificable. Usa otra carpeta con --salida.")
        if con_datos:
            respaldo = salida / ("anteriores-" + uuid.uuid4().hex)
            respaldo.mkdir()
            for p in anteriores:
                p.rename(respaldo / p.name)
        escribir_json(ruta, config)
    (salida / "registros").mkdir(exist_ok=True)
    return config


def identidad(nombre):
    return hashlib.sha256(nombre.encode("utf-8")).hexdigest()


def nombre_anotado(nombre):
    """Los JPG conservan su nombre; los otros llevan un sufijo estable y único."""
    if Path(nombre).suffix.lower() == ".jpg":
        return nombre
    base = Path(nombre)
    return f"{base.stem}__{base.suffix[1:].lower()}_{identidad(nombre)[:12]}.jpg"


def nombre_cuadro(nombre, segundo):
    return f"{Path(nombre).stem}__video_{identidad(nombre)[:12]}_segundo_{segundo:.3f}.jpg"


def ruta_aplanada(ruta, nombre):
    """Traduce una salida por archivo del formato anterior al formato plano."""
    partes = Path(ruta).parts
    if len(partes) != 4:
        return Path(ruta)
    grupo, clase, carpeta_original, archivo = partes
    if carpeta_original != nombre:
        return Path(ruta)
    if grupo == "sin_deteccion":
        return Path(grupo, clase, nombre)
    if archivo == "anotada.jpg":
        return Path(grupo, clase, nombre_anotado(nombre))
    if archivo.startswith("cuadro_") and archivo.endswith(".jpg"):
        return Path(grupo, clase, f"{Path(nombre).stem}__video_{identidad(nombre)[:12]}_segundo_{archivo[7:]}")
    return Path(grupo, clase, nombre)


def aplanar(salida):
    """Convierte resultados previos sin volver a ejecutar el modelo.

    Cada archivo se mueve antes de actualizar su registro. Si hay un corte,
    la siguiente ejecución retoma desde la ruta antigua o la nueva.
    """
    salida = Path(salida)
    for registro in leer_registros(salida):
        nombre = registro["archivo"]
        cambios = False
        etapas = set()
        for salida_archivo in registro.get("salidas", []):
            vieja = Path(salida_archivo["ruta"])
            nueva = ruta_aplanada(vieja, nombre)
            if nueva == vieja:
                continue
            origen, destino = salida / vieja, salida / nueva
            # La carpeta antigua puede llamarse exactamente como el JPG que
            # quedará en su lugar. Muévela primero a un nombre temporal.
            etapa = origen.parent.with_name(".aplanando-" + identidad(nombre))
            if destino.is_dir() and destino == origen.parent:
                if etapa.exists():
                    raise FileExistsError(f"Existe una migración temporal en {etapa}.")
                os.replace(origen.parent, etapa)
            if not origen.exists() and etapa.is_dir():
                origen = etapa / origen.name
            if etapa.is_dir():
                etapas.add(etapa)
            if origen.is_file():
                destino.parent.mkdir(parents=True, exist_ok=True)
                if destino.exists():
                    raise FileExistsError(f"Ya existe {destino}; se detuvo la reorganización.")
                os.replace(origen, destino)
            salida_archivo["ruta"] = nueva.as_posix()
            cambios = True
        if cambios:
            escribir_json(salida / "registros" / (identidad(nombre) + ".json"), registro)
        for etapa in etapas:
            try:
                etapa.rmdir()
            except OSError:
                pass
        for grupo, carpetas in (("con_deteccion", list(CLASES.values()) + ["otras"]),
                                ("sin_deteccion", ["bajo_umbral", "vacias"])):
            for carpeta in carpetas:
                try:
                    (salida / grupo / carpeta / nombre).rmdir()
                except OSError:
                    pass


def leer_registros(salida):
    resultados = []
    for ruta in sorted((Path(salida) / "registros").glob("*.json")):
        try:
            resultados.append(json.loads(ruta.read_text(encoding="utf-8")))
        except (OSError, ValueError):
            continue
    return resultados


def vigente(registro, origen, salida):
    if not registro or registro.get("estado") != "ok":
        return False
    try:
        stat = Path(origen).stat()
        return (registro.get("origen") == [stat.st_size, stat.st_mtime_ns]
                and bool(registro.get("salidas"))
                and all((Path(salida) / s["ruta"]).stat().st_size == s["bytes"]
                        for s in registro["salidas"]))
    except OSError:
        return False


def limpiar_salidas(salida, nombre):
    """Retira solo las salidas que pertenecen a este archivo original."""
    for grupo, carpetas in (("con_deteccion", list(CLASES.values()) + ["otras"]),
                            ("sin_deteccion", ["bajo_umbral", "vacias"])):
        for carpeta in carpetas:
            ruta = Path(salida) / grupo / carpeta / nombre
            if ruta.is_dir():
                shutil.rmtree(ruta)
            elif ruta.is_file():
                ruta.unlink()  # original sin detección o video original
            if grupo == "con_deteccion":
                (ruta.parent / nombre_anotado(nombre)).unlink(missing_ok=True)
                if pipeline.es_video(nombre):
                    patron = f"{Path(nombre).stem}__video_{identidad(nombre)[:12]}_segundo_*.jpg"
                    for cuadro in ruta.parent.glob(patron):
                        cuadro.unlink()


def enlazar(origen, destino):
    try:
        os.link(origen, destino)
    except OSError:
        shutil.copy2(origen, destino)


def analizar(origen, salida, umbral):
    """Publica el registro solo después de escribir todas las salidas.

    Un corte antes del registro obliga a rehacer el archivo. Los errores nunca
    producen una copia en sin_deteccion; el original queda en entrada.
    """
    origen, salida = Path(origen), Path(salida)
    nombre = origen.name
    limpiar_salidas(salida, nombre)
    registro = {"archivo": nombre, "estado": "ok", "detecciones": [], "salidas": []}
    try:
        stat = origen.stat()
        registro["origen"] = [stat.st_size, stat.st_mtime_ns]
        video = pipeline.es_video(nombre)
        if video:
            detecciones, anotada, segundo, casi = pipeline.process_video(str(origen), umbral)
        else:
            with Image.open(origen) as imagen:
                anotada, detecciones, casi = pipeline.process_image(imagen, umbral)
            segundo = None
        rutas = []
        if detecciones:
            carpetas = sorted({CLASES.get(d["category"], "otras") for d in detecciones})
            primera_foto = primer_video = None
            for clase in carpetas:
                carpeta = salida / "con_deteccion" / clase
                carpeta.mkdir(parents=True, exist_ok=True)
                foto = carpeta / (nombre_cuadro(nombre, segundo) if video else nombre_anotado(nombre))
                if primera_foto is None:
                    anotada.save(foto, format="JPEG", quality=85)
                    primera_foto = foto
                else:
                    enlazar(primera_foto, foto)
                rutas.append(foto)
                if video:
                    destino = carpeta / nombre
                    if primer_video is None:
                        shutil.copy2(origen, destino)
                        primer_video = destino
                    else:
                        enlazar(primer_video, destino)
                    rutas.append(destino)
        else:
            carpeta = salida / "sin_deteccion" / ("bajo_umbral" if casi else "vacias")
            carpeta.mkdir(parents=True, exist_ok=True)
            destino = carpeta / nombre
            shutil.copy2(origen, destino)
            rutas.append(destino)
        registro["detecciones"] = [{"clase": d["category"], "confianza": float(d["confidence"]),
                                    "bbox": d["bbox"]} for d in detecciones]
        if casi:
            registro["casi"] = {"clase": casi["category"], "confianza": float(casi["confidence"])}
        if segundo is not None:
            registro["segundo"] = segundo
        if [origen.stat().st_size, origen.stat().st_mtime_ns] != registro["origen"]:
            raise RuntimeError("El archivo original cambió durante el análisis.")
        registro["salidas"] = [{"ruta": p.relative_to(salida).as_posix(), "bytes": p.stat().st_size}
                               for p in rutas]
    except Exception as error:
        limpiar_salidas(salida, nombre)
        registro.update(estado="incompleto" if isinstance(error, pipeline.VideoIncompleto) else "error",
                        error=f"{type(error).__name__}: {error}", detecciones=[], salidas=[])
    escribir_json(salida / "registros" / (identidad(nombre) + ".json"), registro)
    return registro


def totales(registros):
    return {
        "procesadas": len(registros),
        "con_deteccion": sum(r["estado"] == "ok" and bool(r["detecciones"]) for r in registros),
        "sin_deteccion": sum(r["estado"] == "ok" and not r["detecciones"] for r in registros),
        "errores": sum(r["estado"] == "error" for r in registros),
        "incompletos": sum(r["estado"] == "incompleto" for r in registros),
        "detecciones": sum(len(r["detecciones"]) for r in registros),
    }
