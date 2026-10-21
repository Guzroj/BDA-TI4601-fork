#!/usr/bin/env python3
"""Paso 8 — Compra atómica de entradas (TODO 3).

MongoDB garantiza que **una operación sobre un solo documento es atómica**, incluso
si modifica campos anidados o elementos de un arreglo. En este laboratorio todas las
zonas de un evento viven dentro del documento del evento, así que descontar entradas
puede hacerse sin transacciones entre documentos... si usted escribe la operación
correcta.

Este script lanza muchos compradores concurrentes contra un evento de prueba y
verifica que nunca se vendan más entradas de las que hay. Usa las colecciones
``pruebas_eventos`` y ``pruebas_ordenes``; no toca la semilla.

    comprar.py                          # 200 compradores, 120 entradas
    comprar.py --hilos 300 --entradas 50
"""

from __future__ import annotations

import argparse
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

from pymongo.database import Database
from pymongo.errors import DuplicateKeyError  # noqa: F401  (le servirá en el TODO 3)

from common import BD, conectar, fallo, ok

EVENTOS = "pruebas_eventos"
ORDENES = "pruebas_ordenes"


def comprar_entradas(
    db: Database,
    evento_id: str,
    zona: str,
    cantidad: int,
    orden_id: str,
    *,
    eventos: str = EVENTOS,
    ordenes: str = ORDENES,
) -> str:
    """TODO 3 — Intente comprar ``cantidad`` entradas de ``zona`` y devuelva el estado de la orden.

    Debe devolver ``"confirmada"`` o ``"agotada"``. Requisitos:

    * **Nunca** se venden más entradas de las disponibles, aunque lleguen cientos de
      compradores al mismo tiempo.
    * **Idempotencia:** el cliente genera ``orden_id`` y puede reintentar la misma
      compra si no recibió respuesta. Una orden con un ``orden_id`` ya registrado
      NO vuelve a descontar entradas; devuelva el estado que ya tiene guardado.
    * La zona se identifica por su nombre dentro del arreglo ``zonas`` del evento.

    Pistas (no es la única solución, pero sí una que pasa la verificación):

    1. Registre primero la orden en ``ordenes`` con ``_id = orden_id`` y
       ``estado = "pendiente"``. El índice único de ``_id`` detecta el reintento:
       si ``insert_one`` lanza ``DuplicateKeyError``, lea la orden existente y
       devuelva su estado.
    2. Descuente con **una sola** llamada ``update_one`` sobre el evento cuyo filtro
       exige que ESA zona tenga ``disponibles >= cantidad``, y cuyo update aplica
       ``$inc`` a ESA misma zona. Para que el filtro y el update hablen del mismo
       elemento del arreglo investigue ``$elemMatch`` y el operador posicional ``$``.
       ¿Qué pasaría si escribiera dos condiciones separadas sobre ``zonas.nombre``
       y ``zonas.disponibles``?
    3. NO lea el documento para decidir y luego escriba: entre la lectura y la
       escritura otro comprador puede cambiar el valor. La decisión debe tomarla el
       servidor, dentro de la misma operación (``matched_count`` / ``modified_count``).
    4. Actualice el estado de la orden a ``"confirmada"`` o ``"agotada"``.

    Anote en el informe qué ocurre si el proceso muere entre los pasos 2 y 4, y cómo
    lo detectaría (Paso 8, pregunta 3).
    """
    raise NotImplementedError("TODO 3: comprar_entradas")


def preparar(db: Database, entradas: int) -> None:
    db[EVENTOS].drop()
    db[ORDENES].drop()
    db[EVENTOS].insert_one(
        {
            "_id": "EV-PRUEBA",
            "nombre": "Evento de prueba",
            "zonas": [
                {"nombre": "General", "precio": 8_000, "capacidad": entradas, "disponibles": entradas},
                {"nombre": "VIP", "precio": 45_000, "capacidad": 10, "disponibles": 10},
                {"nombre": "Palco", "precio": 70_000, "capacidad": 5, "disponibles": 5},
            ],
        }
    )


def disponibles(db: Database, zona: str) -> int:
    ev = db[EVENTOS].find_one({"_id": "EV-PRUEBA"})
    return next(z["disponibles"] for z in ev["zonas"] if z["nombre"] == zona)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--hilos", type=int, default=200, help="compradores simultáneos")
    parser.add_argument("--entradas", type=int, default=120, help="entradas en la zona General")
    args = parser.parse_args()

    client = conectar()
    db = client[BD]
    preparar(db, args.entradas)
    exito = True

    # --- Prueba 1: compradores simultáneos de 1 entrada ----------------------
    def comprador(_):
        return comprar_entradas(db, "EV-PRUEBA", "General", 1, f"ORD-{uuid.uuid4()}")

    inicio = time.perf_counter()
    try:
        with ThreadPoolExecutor(max_workers=args.hilos) as pool:
            resultados = list(pool.map(comprador, range(args.hilos)))
    except NotImplementedError as exc:
        print(f"PENDIENTE: {exc}")
        return 1
    seg = time.perf_counter() - inicio

    esperadas = min(args.hilos, args.entradas)
    confirmadas = resultados.count("confirmada")
    agotadas = resultados.count("agotada")
    restantes = disponibles(db, "General")
    print(f"{args.hilos} compradores en {seg:.2f} s ({args.hilos / seg:.0f} compras/s)")
    if confirmadas == esperadas and agotadas == args.hilos - esperadas:
        ok(f"{confirmadas} confirmadas y {agotadas} agotadas (esperado {esperadas}/{args.hilos - esperadas})")
    else:
        fallo(f"confirmadas={confirmadas}, agotadas={agotadas}; esperado {esperadas}/{args.hilos - esperadas}")
        exito = False
    if restantes == args.entradas - esperadas and restantes >= 0:
        ok(f"quedan {restantes} entradas; nunca negativo")
    else:
        fallo(f"quedan {restantes}; esperado {args.entradas - esperadas}")
        exito = False
    n_ord = db[ORDENES].count_documents({"estado": "confirmada"})
    if n_ord == confirmadas:
        ok(f"{n_ord} órdenes confirmadas en {ORDENES}")
    else:
        fallo(f"{n_ord} órdenes confirmadas guardadas; la función devolvió {confirmadas}")
        exito = False

    # --- Prueba 2: compras de varias entradas (VIP: 10 disponibles) ----------
    with ThreadPoolExecutor(max_workers=3) as pool:
        vip = list(pool.map(lambda i: comprar_entradas(db, "EV-PRUEBA", "VIP", 4, f"ORD-VIP-{i}"), range(3)))
    if vip.count("confirmada") == 2 and vip.count("agotada") == 1 and disponibles(db, "VIP") == 2:
        ok("3 compradores de 4 entradas sobre 10: 2 confirmadas, 1 agotada, quedan 2")
    else:
        fallo(f"VIP: resultados={vip}, quedan {disponibles(db, 'VIP')}; esperado 2 confirmadas, 1 agotada, quedan 2")
        exito = False

    # --- Prueba 3: idempotencia ---------------------------------------------
    repetidas = [comprar_entradas(db, "EV-PRUEBA", "Palco", 1, "ORD-IDEMPOTENTE") for _ in range(5)]
    if repetidas == ["confirmada"] * 5 and disponibles(db, "Palco") == 4:
        ok("la misma orden repetida 5 veces descontó una sola entrada (quedan 4)")
    else:
        fallo(f"reintentos={repetidas}, quedan {disponibles(db, 'Palco')}; esperado 5×confirmada y 4")
        exito = False

    # --- Prueba 4: zona inexistente -------------------------------------------
    if comprar_entradas(db, "EV-PRUEBA", "Platea", 1, "ORD-ZONA-X") == "agotada":
        ok("una zona inexistente se resuelve como agotada")
    else:
        fallo("una zona inexistente debe devolver 'agotada'")
        exito = False

    ahora = datetime.now(timezone.utc).isoformat(timespec="seconds")
    print(f"\nResultado: {'todas las verificaciones pasaron' if exito else 'hay verificaciones fallidas'} ({ahora})")
    return 0 if exito else 1


if __name__ == "__main__":
    raise SystemExit(main())
