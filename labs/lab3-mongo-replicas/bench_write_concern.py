#!/usr/bin/env python3
"""Paso 9 — ¿Cuánto cuesta cada garantía de escritura? (TODO 4)

Mide la latencia de ``insert_one`` bajo cuatro garantías distintas:

==============  ========================================================
variante        qué espera el cliente antes de recibir la respuesta
==============  ========================================================
w1              que el primario haya aplicado la escritura
w1_journal      que el primario la haya aplicado Y escrito en su journal
majority        que una mayoría de miembros con datos la tengan
w3              que los tres miembros la tengan
==============  ========================================================

Usted escribe SOLO la función que mide (TODO 4); el resto (variantes, calentamiento,
percentiles, CSV) ya está hecho.

    bench_write_concern.py                 # 300 muestras por variante
    bench_write_concern.py --n 500 --csv evidence/write-concern.csv
"""

from __future__ import annotations

import argparse
import time

from pymongo import WriteConcern
from pymongo.collection import Collection

from common import BD, conectar, escribir_csv, fallo, ok, percentil

# (nombre, w, j)
VARIANTES = [
    ("w1", 1, None),
    ("w1_journal", 1, True),
    ("majority", "majority", None),
    ("w3", 3, None),
]


def medir_escrituras(
    coleccion: Collection, w: int | str, j: bool | None, n: int, wtimeout_ms: int = 5000
) -> list[float]:
    """TODO 4 — Haga ``n`` inserciones y devuelva la latencia de cada una en milisegundos.

    1. Cree una vista de ``coleccion`` con la garantía pedida usando
       ``coleccion.with_options(write_concern=WriteConcern(w=..., j=..., wtimeout=...))``.
       No cree un cliente nuevo por variante.
    2. En cada iteración, inserte un documento pequeño con ``insert_one`` (por ejemplo
       ``{"i": i, "relleno": "x" * 100}``) y mida SOLO esa llamada con
       ``time.perf_counter()``. Convierta a milisegundos.
    3. Devuelva la lista de ``n`` latencias, en el orden en que se midieron.

    Piense antes de ejecutar: ¿qué variante espera que sea la más lenta y cuál la más
    rápida? ¿Cuánto cree que cambia ``j=True``? Anote su predicción en la bitácora.
    """
    raise NotImplementedError("TODO 4: medir_escrituras")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--n", type=int, default=300, help="muestras por variante")
    parser.add_argument("--warmup", type=int, default=30)
    parser.add_argument("--csv", default="evidence/write-concern.csv")
    args = parser.parse_args()

    client = conectar()
    col = client[BD]["bench_wc"]
    col.drop()

    filas: list[dict] = []
    resumen: list[tuple] = []
    for nombre, w, j in VARIANTES:
        try:
            medir_escrituras(col, w, j, args.warmup)  # calentamiento: no se reporta
            lat = medir_escrituras(col, w, j, args.n)
        except NotImplementedError as exc:
            print(f"PENDIENTE: {exc}")
            return 1
        if len(lat) != args.n or any(x <= 0 for x in lat):
            fallo(f"{nombre}: se esperaban {args.n} latencias positivas, llegaron {len(lat)}")
            return 1
        total_s = sum(lat) / 1000
        resumen.append(
            (nombre, len(lat), percentil(lat, 50), percentil(lat, 95), percentil(lat, 99), len(lat) / total_s)
        )
        filas += [{"variante": nombre, "i": i, "latencia_ms": f"{x:.3f}"} for i, x in enumerate(lat)]

    ok("las cuatro variantes devolvieron la cantidad esperada de muestras")
    print(f"\n{'variante':<12} {'n':>5} {'p50_ms':>8} {'p95_ms':>8} {'p99_ms':>8} {'ops/s':>8}")
    for nombre, n, p50, p95, p99, ops in resumen:
        print(f"{nombre:<12} {n:>5} {p50:>8.2f} {p95:>8.2f} {p99:>8.2f} {ops:>8.0f}")
    escribir_csv(args.csv, ["variante", "i", "latencia_ms"], filas)
    print(f"\nMuestras crudas: {args.csv}")
    print("Declare en el reporte: máquina, RAM, SO, n, calentamiento y que los tres miembros "
          "comparten una sola computadora (sin latencia de red real).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
