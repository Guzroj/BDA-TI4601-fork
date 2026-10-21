"""Utilidades compartidas del Laboratorio 3. Léalas primero; no necesita modificarlas.

Todas las herramientas del laboratorio se conectan con la misma URI (variable
``MONGO_URI``, inyectada por Compose) y usan ``w="majority"`` como garantía de
escritura por defecto. Las sondas que comparan garantías la sobrescriben
colección por colección o cliente por cliente.
"""

from __future__ import annotations

import csv
import json
import math
import os
import sys
import warnings
from datetime import datetime, timezone
from pathlib import Path

from pymongo import MongoClient

# pymongo avisa de que ``wtimeout`` será reemplazado por ``pymongo.timeout()``.
# Seguimos usando ``wtimeout`` porque es el nombre que aparece en la documentación
# de MongoDB y en el contrato del Proyecto 2.
warnings.filterwarnings("ignore", category=DeprecationWarning)

AQUI = Path(__file__).resolve().parent
DATA = AQUI / "data"
EVIDENCE = Path(os.environ.get("EVIDENCE_DIR", "evidence"))

BD = os.environ.get("MONGO_DB", "boleteria")
URI = os.environ.get(
    "MONGO_URI",
    "mongodb://mongo-1:27017,mongo-2:27017,mongo-3:27017/?replicaSet=rs-lab3",
)


def conectar(**opciones) -> MongoClient:
    """Cliente del conjunto de réplicas con ``w=majority`` salvo que se indique otra cosa."""
    opciones.setdefault("w", "majority")
    opciones.setdefault("serverSelectionTimeoutMS", 5000)
    return MongoClient(URI, **opciones)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


def percentil(valores: list[float], p: float) -> float:
    """Percentil por rango más cercano (*nearest rank*), igual que en el Lab 1."""
    if not valores:
        raise ValueError("no hay muestras")
    ordenados = sorted(valores)
    rango = max(1, math.ceil(p / 100 * len(ordenados)))
    return ordenados[rango - 1]


def escribir_csv(ruta: str | Path, campos: list[str], filas: list[dict]) -> None:
    ruta = Path(ruta)
    ruta.parent.mkdir(parents=True, exist_ok=True)
    with ruta.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=campos)
        w.writeheader()
        w.writerows(filas)


def manifest() -> dict:
    """Lee ``data/MANIFEST.json`` (lo produce ``generar_datos.py``)."""
    ruta = DATA / "MANIFEST.json"
    if not ruta.exists():
        print(
            "No existe data/MANIFEST.json. Ejecute primero generar_datos.py (Paso 4).",
            file=sys.stderr,
        )
        raise SystemExit(2)
    return json.loads(ruta.read_text(encoding="utf-8"))


def ok(mensaje: str) -> None:
    print(f"OK: {mensaje}")


def fallo(mensaje: str) -> None:
    print(f"VERIFICACIÓN FALLÓ: {mensaje}")
