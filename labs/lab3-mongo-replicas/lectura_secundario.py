#!/usr/bin/env python3
"""Paso 7 — ¿Puedo leer en un secundario lo que acabo de escribir?

Para cada intento: se escribe un documento en el primario y **inmediatamente** se lee
desde un secundario (``ReadPreference.SECONDARY``). Si el secundario todavía no lo
tiene, la lectura es obsoleta (*stale*): el sistema respondió, pero con una versión
anterior de los datos. Es la consistencia eventual de las réplicas, medida.

==========================  =======================================================
modo                        qué configura
==========================  =======================================================
w1_secundario               escritura w=1; lectura en secundario
majority_secundario         escritura w=majority; lectura en secundario
causal_majority             sesión causalmente consistente, w=majority y lectura
                            con readConcern majority en secundario
==========================  =======================================================

Herramienta provista: no tiene TODO. Usted la ejecuta, predice el resultado antes y
lo interpreta con el teorema CAP (diapositivas 13 a 15).

    lectura_secundario.py                  # 500 intentos por modo
    lectura_secundario.py --n 1000 --csv evidence/lectura-secundario.csv
"""

from __future__ import annotations

import argparse

from pymongo import ReadPreference, WriteConcern
from pymongo.read_concern import ReadConcern

from common import BD, conectar, escribir_csv

MODOS = {
    "w1_secundario": {"w": 1, "rc": None, "causal": False},
    "majority_secundario": {"w": "majority", "rc": None, "causal": False},
    "causal_majority": {"w": "majority", "rc": "majority", "causal": True},
}


def ejecutar(client, modo: str, n: int) -> int:
    cfg = MODOS[modo]
    col = client[BD]["lecturas"]
    escribe = col.with_options(write_concern=WriteConcern(w=cfg["w"], wtimeout=5000))
    opciones_lectura = {"read_preference": ReadPreference.SECONDARY}
    if cfg["rc"]:
        opciones_lectura["read_concern"] = ReadConcern(cfg["rc"])
    lee = col.with_options(**opciones_lectura)

    obsoletas = 0
    for i in range(n):
        doc = {"_id": f"{modo}-{i}", "i": i}
        if cfg["causal"]:
            with client.start_session(causal_consistency=True) as sesion:
                escribe.insert_one(doc, session=sesion)
                visto = lee.find_one({"_id": doc["_id"]}, session=sesion)
        else:
            escribe.insert_one(doc)
            visto = lee.find_one({"_id": doc["_id"]})
        if visto is None:
            obsoletas += 1
    return obsoletas


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--n", type=int, default=500)
    parser.add_argument("--csv", default="evidence/lectura-secundario.csv")
    args = parser.parse_args()

    client = conectar()
    client[BD]["lecturas"].drop()

    filas = []
    print(f"{'modo':<22} {'n':>6} {'obsoletas':>10} {'% obsoletas':>12}")
    for modo in MODOS:
        obsoletas = ejecutar(client, modo, args.n)
        pct = 100 * obsoletas / args.n
        print(f"{modo:<22} {args.n:>6} {obsoletas:>10} {pct:>11.1f}%")
        filas.append({"modo": modo, "n": args.n, "obsoletas": obsoletas, "pct": f"{pct:.2f}"})
    escribir_csv(args.csv, ["modo", "n", "obsoletas", "pct"], filas)
    print(f"\nResumen: {args.csv}")
    print("Recuerde: los tres miembros comparten una computadora; en una red real el retraso "
          "de replicación sería mayor.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
