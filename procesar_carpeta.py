#!/usr/bin/env python3
"""Analiza una carpeta; reanuda éxitos verificables y reintenta errores."""
import argparse
import csv
import os
from pathlib import Path

import motor
import trabajos


def exportar_csv(salida, registros):
    destino = Path(salida) / "resultados.csv"
    temporal = destino.with_suffix(".csv.tmp")
    with temporal.open("w", newline="", encoding="utf-8") as f:
        escritor = csv.writer(f)
        escritor.writerow(["archivo", "resultado", "clases", "confianza_maxima", "descartado", "error"])
        for r in registros:
            estado = r["estado"]
            if estado == "ok":
                estado = "con deteccion" if r["detecciones"] else "sin deteccion"
            casi = r.get("casi", {})
            escritor.writerow([r["archivo"], estado,
                               " ".join(sorted({d["clase"] for d in r["detecciones"]})),
                               max((d["confianza"] for d in r["detecciones"]), default=0),
                               f"{casi['clase']} {casi['confianza']:.3f}" if casi else "",
                               r.get("error", "")])
    os.replace(temporal, destino)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("entrada")
    parser.add_argument("-s", "--salida", help="Por defecto: <entrada>_resultados")
    parser.add_argument("-u", "--umbral", type=float, default=20)
    args = parser.parse_args()
    entrada = Path(args.entrada).expanduser().resolve()
    salida = Path(args.salida or str(entrada) + "_resultados").expanduser().resolve()
    if not entrada.is_dir():
        parser.error("La carpeta de entrada no existe.")
    if entrada == salida or salida in entrada.parents:
        parser.error("La salida no puede ser la entrada ni una carpeta que la contenga.")
    archivos = sorted(p for p in entrada.iterdir() if p.is_file() and p.suffix.lower() in trabajos.EXTENSIONES)
    if not archivos:
        parser.error("No hay fotografías ni videos.")
    try:
        motor.preparar(entrada, salida, args.umbral / 100)
    except ValueError as error:
        parser.error(str(error))
    previos = {r["archivo"]: r for r in motor.leer_registros(salida)}
    # Evitar resultados obsoletos si se retiró un archivo de la entrada.
    for nombre in previos.keys() - {p.name for p in archivos}:
        motor.limpiar_salidas(salida, nombre)
        (salida / "registros" / (motor.identidad(nombre) + ".json")).unlink()
    resultados = []
    for indice, origen in enumerate(archivos, 1):
        registro = previos.get(origen.name)
        if not motor.vigente(registro, origen, salida):
            registro = motor.analizar(origen, salida, args.umbral / 100)
        resultados.append(registro)
        print(f"[{indice}/{len(archivos)}] {origen.name}: {registro['estado']} {registro.get('error', '')}", flush=True)
    exportar_csv(salida, resultados)
    print(motor.totales(resultados))
    print(f"Detalle: {salida / 'resultados.csv'}")
    return 1 if any(r["estado"] != "ok" for r in resultados) else 0


if __name__ == "__main__":
    raise SystemExit(main())
