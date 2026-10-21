#!/usr/bin/env python3
"""Paso 5 — Carga de la semilla en el conjunto de réplicas.

Aquí hay DOS ``TODO`` (1 y 2). Cada uno termina en ``raise NotImplementedError``
que usted debe reemplazar. Después de cada TODO el script corre una verificación
automática (``OK:`` o ``VERIFICACIÓN FALLÓ:``). No cambie las firmas de las funciones.

Cada corrida vacía ``eventos`` y ``ordenes`` antes de cargar, así que puede repetirla
mientras depura.

    cargar.py                # carga completa
    cargar.py --lote 100     # lotes más pequeños
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

from pymongo import ASCENDING
from pymongo.database import Database

from common import BD, DATA, conectar, fallo, manifest, ok


def cargar_eventos(db: Database, ruta: Path, lote: int = 500) -> int:
    """TODO 1 — Cargue ``eventos.jsonl`` en la colección ``eventos`` y devuelva cuántos insertó.

    Pasos:

    1. Lea el archivo línea por línea; cada línea es un documento JSON (``json.loads``).
       No cargue el archivo completo en memoria: acumule hasta ``lote`` documentos.
    2. Inserte cada lote con ``insert_many``. Piense qué hace ``ordered=False`` cuando
       un documento falla y por qué conviene aquí.
    3. Cada documento ya trae su ``_id`` (``EV-0001``…): no deje que MongoDB genere otro.
    4. Acuérdese del último lote, que casi nunca está completo.

    La conexión que recibe ya usa ``w="majority"``: cada ``insert_many`` espera a que
    una mayoría de miembros tenga el lote. No hace falta repetirlo aquí, pero en el
    informe debe poder explicar qué esperó cada llamada.
    """
    raise NotImplementedError("TODO 1: cargar_eventos")


def crear_indices(db: Database) -> list[str]:
    """TODO 2 — Cree los dos índices mínimos del laboratorio y devuelva sus nombres.

    Las dos consultas que deben ser eficientes:

    a) ``eventos``: los eventos de una categoría desde cierta fecha, en orden de fecha::

           db.eventos.find({"categoria": c, "fecha": {"$gte": d}}).sort("fecha", 1)

    b) ``ordenes``: cuántas órdenes de un evento hay en cada estado::

           db.ordenes.count_documents({"evento_id": e, "estado": s})

    Defina un índice compuesto para cada una. El orden de los campos importa: ponga
    primero los campos de igualdad y después el de rango u orden. Justifique su
    elección en el informe con ``explain()`` (Paso 5).

    Use ``create_index`` con una lista de pares ``(campo, ASCENDING)``.
    """
    raise NotImplementedError("TODO 2: crear_indices")


def verificar_carga(db: Database, devueltos: int, m: dict) -> bool:
    bien = True
    if devueltos == m["eventos"]:
        ok(f"cargar_eventos devolvió {devueltos} documentos")
    else:
        fallo(f"cargar_eventos devolvió {devueltos}; el manifiesto dice {m['eventos']}")
        bien = False

    en_bd = db.eventos.count_documents({})
    if en_bd == m["eventos"]:
        ok(f"la colección eventos tiene {en_bd} documentos (mayoría confirmó cada lote)")
    else:
        fallo(f"la colección tiene {en_bd}; el manifiesto dice {m['eventos']}")
        bien = False

    suma = list(
        db.eventos.aggregate(
            [
                {
                    "$group": {
                        "_id": None,
                        "zonas": {"$sum": {"$size": "$zonas"}},
                        "capacidad": {"$sum": {"$sum": "$zonas.capacidad"}},
                    }
                }
            ]
        )
    )
    if suma and suma[0]["zonas"] == m["zonas"] and suma[0]["capacidad"] == m["capacidad_total"]:
        ok(f"zonas ({m['zonas']}) y capacidad total ({m['capacidad_total']}) coinciden")
    else:
        fallo(f"zonas/capacidad en la base: {suma}; esperado {m['zonas']}/{m['capacidad_total']}")
        bien = False
    return bien


def verificar_indices(db: Database) -> bool:
    esperados = {
        "eventos": [("categoria", 1), ("fecha", 1)],
        "ordenes": [("evento_id", 1), ("estado", 1)],
    }
    bien = True
    for coleccion, clave in esperados.items():
        claves = [list(v["key"]) for v in db[coleccion].index_information().values()]
        if clave in claves:
            ok(f"índice {coleccion}{clave} presente")
        else:
            fallo(f"falta el índice compuesto {clave} en {coleccion}; hay: {claves}")
            bien = False
    return bien


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--lote", type=int, default=500)
    args = parser.parse_args()

    m = manifest()
    client = conectar()
    db = client[BD]
    print(f"Escritura por defecto de este cliente: {client.write_concern.document}")
    db.eventos.drop()
    db.ordenes.drop()

    inicio = time.perf_counter()
    try:
        devueltos = cargar_eventos(db, DATA / "eventos.jsonl", args.lote)
    except NotImplementedError as exc:
        print(f"PENDIENTE: {exc}")
        return 1
    seg = time.perf_counter() - inicio
    carga_ok = verificar_carga(db, devueltos, m)
    print(f"Carga: {seg:.2f} s ({devueltos / max(seg, 1e-9):.0f} documentos/s)")

    try:
        crear_indices(db)
    except NotImplementedError as exc:
        print(f"PENDIENTE: {exc}")
        return 1
    indices_ok = verificar_indices(db)
    return 0 if carga_ok and indices_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
