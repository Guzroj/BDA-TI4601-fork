#!/usr/bin/env python3
"""Verifica el trabajo del estudiante sin configurar ni corregir el conjunto de réplicas."""

from __future__ import annotations

import sys
from collections.abc import Callable

from pymongo.errors import PyMongoError

from common import BD, conectar, manifest

NOMBRE_CONJUNTO = "rs-lab3"


def check(etiqueta: str, aserto: Callable[[], bool], pista: str) -> bool:
    try:
        paso = aserto()
    except (PyMongoError, KeyError, IndexError, TypeError) as exc:
        print(f"[FAIL] {etiqueta}: {str(exc).splitlines()[0]}")
        print(f"       Pista: {pista}")
        return False
    if paso:
        print(f"[ OK ] {etiqueta}")
        return True
    print(f"[FAIL] {etiqueta}")
    print(f"       Pista: {pista}")
    return False


def tiene_indice(coleccion, clave: list[tuple[str, int]]) -> bool:
    return any(list(v["key"]) == clave for v in coleccion.index_information().values())


def main() -> int:
    client = conectar(serverSelectionTimeoutMS=8000)
    admin = client.admin
    try:
        estado = admin.command("replSetGetStatus")
        cfg = admin.command("replSetGetConfig")["config"]
    except PyMongoError as exc:
        print(f"[FAIL] conexión al conjunto de réplicas: {str(exc).splitlines()[0]}")
        print("       Pista: ¿ejecutó rs.initiate() (Paso 2)? ¿hay un primario? `make lab3-status`.")
        return 1
    m = manifest()
    db = client[BD]

    miembros = estado["members"]
    resultados = [
        check(
            f"el conjunto se llama {NOMBRE_CONJUNTO} y tiene 3 miembros",
            lambda: estado["set"] == NOMBRE_CONJUNTO and len(miembros) == 3,
            "el _id de rs.initiate debe coincidir con --replSet del Compose; revise sus members",
        ),
        check(
            "los 3 miembros están sanos (health = 1)",
            lambda: all(x["health"] == 1 for x in miembros),
            "algún contenedor está detenido o aún arrancando; `make lab3-status`",
        ),
        check(
            "hay exactamente 1 PRIMARY y 2 SECONDARY",
            lambda: sorted(x["stateStr"] for x in miembros) == ["PRIMARY", "SECONDARY", "SECONDARY"],
            "espere unos segundos a que termine la elección; revise rs.status()",
        ),
        check(
            "los 3 miembros votan (votes = 1, priority > 0)",
            lambda: all(x["votes"] == 1 and x["priority"] > 0 for x in cfg["members"]),
            "no configure árbitros ni prioridad 0 en este laboratorio",
        ),
        check(
            f"eventos tiene {m['eventos']} documentos (los del manifiesto)",
            lambda: db.eventos.count_documents({}) == m["eventos"],
            "ejecute cargar.py (Paso 5) y complete los TODO 1 y 2",
        ),
        check(
            "existen los índices compuestos de eventos y ordenes",
            lambda: tiene_indice(db.eventos, [("categoria", 1), ("fecha", 1)])
            and tiene_indice(db.ordenes, [("evento_id", 1), ("estado", 1)]),
            "TODO 2 de cargar.py: índice (categoria, fecha) en eventos y (evento_id, estado) en ordenes",
        ),
    ]

    # Información (no cuenta): retraso entre miembros.
    optimes = [x["optimeDate"] for x in miembros if "optimeDate" in x]
    if optimes:
        print(f"\nDiferencia máxima de optime entre miembros: {(max(optimes) - min(optimes)).total_seconds():.1f} s")

    pasaron = sum(resultados)
    print(f"\nResultado: {pasaron}/{len(resultados)} verificaciones.")
    if pasaron != len(resultados):
        print("El verificador no modificó el conjunto. Corrija el primer FAIL y repita.")
        return 1
    print("Configuración lista para observación, mediciones y fallas.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
