#!/usr/bin/env python3
"""Compara lo que la sonda creyó con lo que realmente quedó en MongoDB (TODO 5).

El **RPO** (cuántos datos se pueden perder) se calcula sobre lo que el sistema dijo
haber confirmado, no sobre lo que se intentó. Los intentos que terminaron en error
tienen resultado *desconocido*: pueden haberse escrito o no.

Entradas:

* el CSV de la sonda: cada ``seq`` con ``status`` ok o error;
* la colección ``escrituras_sonda``: los ``seq`` que de verdad existen para esa corrida,
  leídos con ``readConcern: majority`` (solo lo que una mayoría tiene).

Usted escribe la función que clasifica los tres conjuntos (TODO 5).

    verificar_rpo.py --autotest                      # prueba su función con casos sintéticos
    verificar_rpo.py --csv evidence/falla-b.csv      # compara contra la base
"""

from __future__ import annotations

import argparse
import csv
import sys

from pymongo.read_concern import ReadConcern

from common import BD, conectar, fallo, ok


def calcular_rpo(
    confirmados: set[int], sin_confirmar: set[int], presentes: set[int]
) -> dict[str, set[int]]:
    """TODO 5 — Clasifique los ``seq`` y devuelva un diccionario con estas cuatro claves.

    ``confirmados``    seq que la sonda recibió con status ok.
    ``sin_confirmar``  seq que la sonda recibió con status error (resultado desconocido).
    ``presentes``      seq que existen en la base de datos.

    Claves del resultado (todas conjuntos de enteros):

    * ``"perdidos"``               confirmados que NO están en la base. Si no es vacío,
                                   el RPO de las operaciones confirmadas es mayor que cero.
    * ``"desconocidos_presentes"`` intentos con error que SÍ quedaron escritos.
    * ``"desconocidos_ausentes"``  intentos con error que NO quedaron escritos.
    * ``"inesperados"``            seq presentes que la sonda nunca intentó
                                   (debería ser vacío; si no, algo está mal en la prueba).

    Son operaciones entre conjuntos: no necesita ciclos.
    """
    raise NotImplementedError("TODO 5: calcular_rpo")


def autotest() -> int:
    casos = [
        # confirmados, sin_confirmar, presentes, esperado
        ({0, 1, 2}, set(), {0, 1, 2},
         {"perdidos": set(), "desconocidos_presentes": set(), "desconocidos_ausentes": set(), "inesperados": set()}),
        ({0, 1, 2}, {3, 4}, {0, 1, 2, 3},
         {"perdidos": set(), "desconocidos_presentes": {3}, "desconocidos_ausentes": {4}, "inesperados": set()}),
        ({0, 1, 2, 5}, {3}, {0, 2, 3, 9},
         {"perdidos": {1, 5}, "desconocidos_presentes": {3}, "desconocidos_ausentes": set(), "inesperados": {9}}),
    ]
    bien = True
    try:
        for i, (c, s, p, esperado) in enumerate(casos, 1):
            obtenido = calcular_rpo(set(c), set(s), set(p))
            if obtenido == esperado:
                ok(f"caso sintético {i}")
            else:
                fallo(f"caso sintético {i}: obtuvo {obtenido}; esperado {esperado}")
                bien = False
    except NotImplementedError as exc:
        print(f"PENDIENTE: {exc}")
        return 1
    return 0 if bien else 1


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--csv", help="CSV producido por sonda_escrituras.py")
    parser.add_argument("--autotest", action="store_true")
    args = parser.parse_args()

    if args.autotest or not args.csv:
        return autotest()

    confirmados: set[int] = set()
    sin_confirmar: set[int] = set()
    runs: set[str] = set()
    with open(args.csv, encoding="utf-8") as f:
        for fila in csv.DictReader(f):
            runs.add(fila["run"])
            (confirmados if fila["status"] == "ok" else sin_confirmar).add(int(fila["seq"]))
    if len(runs) != 1:
        print(f"El CSV debe tener una sola corrida; contiene {sorted(runs)}", file=sys.stderr)
        return 2
    run = runs.pop()

    col = conectar()[BD]["escrituras_sonda"].with_options(read_concern=ReadConcern("majority"))
    presentes = {d["seq"] for d in col.find({"run": run}, {"seq": 1})}

    try:
        r = calcular_rpo(confirmados, sin_confirmar, presentes)
    except NotImplementedError as exc:
        print(f"PENDIENTE: {exc}")
        return 1

    print(f"Corrida {run}")
    print(f"  intentos .............. {len(confirmados) + len(sin_confirmar)}")
    print(f"  confirmados (ok) ...... {len(confirmados)}")
    print(f"  con error ............. {len(sin_confirmar)}")
    print(f"  presentes en la base .. {len(presentes)}  (readConcern majority)")
    print(f"  PERDIDOS (confirmados ausentes) ......... {len(r['perdidos'])}  {sorted(r['perdidos'])[:10]}")
    print(f"  errores que SÍ se escribieron ........... {len(r['desconocidos_presentes'])}  "
          f"{sorted(r['desconocidos_presentes'])[:10]}")
    print(f"  errores que NO se escribieron ........... {len(r['desconocidos_ausentes'])}")
    print(f"  inesperados (presentes, nunca intentados) {len(r['inesperados'])}")
    print("\nRPO observado sobre operaciones confirmadas:",
          "0 (ninguna se perdió)" if not r["perdidos"] else f"{len(r['perdidos'])} operaciones")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
