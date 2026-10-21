#!/usr/bin/env python3
"""Sonda de escrituras para observar el comportamiento del conjunto durante una falla.

Cada ``--interval`` segundos inserta un documento con un número de secuencia (``seq``)
en ``escrituras_sonda`` y registra si el servidor confirmó (``ok``) o no (``error``),
cuánto tardó y cuándo terminó. Al final imprime un resumen.

El anfitrión crea ``--signal-file`` con el instante (epoch) de la falla justo después
de provocarla; la sonda lo lee y marca las filas como ``antes-falla`` o ``despues-falla``.

**Un error NO significa que la escritura no ocurrió.** Un ``WTimeoutError`` indica que
el primario aplicó la escritura pero no logró la garantía pedida a tiempo; una conexión
cortada puede haber ocurrido antes o después de aplicar. Por eso ``verificar_rpo.py``
compara contra lo que realmente quedó en la base.

    sonda_escrituras.py --duration 40 --signal-file evidence/falla-a-stop.epoch \\
        --csv evidence/falla-a.csv --label "Falla A"
"""

from __future__ import annotations

import argparse
import time
import uuid
from pathlib import Path

from pymongo import MongoClient

from common import BD, URI, escribir_csv, percentil, utc_now

CAMPOS = [
    "run", "label", "phase", "seq", "status",
    "latency_ms", "completed_epoch", "completed_utc", "error",
]


def leer_senal(ruta: Path) -> float | None:
    try:
        return float(ruta.read_text(encoding="utf-8").strip())
    except (FileNotFoundError, ValueError):
        return None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--duration", type=float, default=40)
    parser.add_argument("--interval", type=float, default=0.5)
    parser.add_argument("--label", default="Falla")
    parser.add_argument("--run-id", default=None, help="identificador de la corrida (por defecto, uno nuevo)")
    parser.add_argument("--signal-file", default="evidence/falla-stop.epoch")
    parser.add_argument("--csv", default="evidence/falla.csv")
    parser.add_argument("--w", default="majority", help="garantía de escritura: 1, 2, 3 o majority")
    parser.add_argument("--wtimeout-ms", type=int, default=2000)
    parser.add_argument("--seleccion-ms", type=int, default=3000,
                        help="cuánto espera el driver por un primario antes de dar error")
    parser.add_argument("--sin-reintentos", action="store_true",
                        help="desactiva retryWrites para ver los errores sin que el driver los oculte")
    args = parser.parse_args()

    w = int(args.w) if args.w.isdigit() else args.w
    run = args.run_id or f"r{uuid.uuid4().hex[:8]}"
    cliente = MongoClient(
        URI,
        w=w,
        wtimeoutMS=args.wtimeout_ms,
        retryWrites=not args.sin_reintentos,
        serverSelectionTimeoutMS=args.seleccion_ms,
        connectTimeoutMS=2000,
        socketTimeoutMS=5000,
        heartbeatFrequencyMS=1000,
    )
    col = cliente[BD]["escrituras_sonda"]
    senal = Path(args.signal_file)

    print(f"[{args.label}] run={run} w={w} wtimeout={args.wtimeout_ms} ms "
          f"retryWrites={not args.sin_reintentos}")
    filas: list[dict] = []
    seq = 0
    t0 = time.time()
    while time.time() - t0 < args.duration:
        parada = leer_senal(senal)
        ini = time.perf_counter()
        estado, error = "ok", ""
        try:
            col.insert_one({"_id": f"{run}-{seq:06d}", "run": run, "seq": seq, "t_cliente": utc_now()})
        except Exception as exc:  # noqa: BLE001 — la sonda registra cualquier fallo
            estado, error = "error", type(exc).__name__
        ms = (time.perf_counter() - ini) * 1000
        fin = time.time()
        fase = "despues-falla" if parada is not None and fin >= parada else "antes-falla"
        filas.append(
            {
                "run": run, "label": args.label, "phase": fase, "seq": seq, "status": estado,
                "latency_ms": f"{ms:.1f}", "completed_epoch": f"{fin:.6f}",
                "completed_utc": utc_now(), "error": error,
            }
        )
        print(f"{fase:<13} {estado:<5} seq={seq:<5} {ms:8.1f} ms {error}")
        seq += 1
        time.sleep(max(0.0, args.interval - ms / 1000))

    escribir_csv(args.csv, CAMPOS, filas)
    resumir(filas, leer_senal(senal))
    print(f"\nEvidencia: {args.csv}  (run={run})")
    return 0


def resumir(filas: list[dict], parada: float | None) -> None:
    oks = [f for f in filas if f["status"] == "ok"]
    errs = [f for f in filas if f["status"] == "error"]
    print(f"\nIntentos: {len(filas)} · confirmados: {len(oks)} · errores: {len(errs)}")
    tipos: dict[str, int] = {}
    for f in errs:
        tipos[f["error"]] = tipos.get(f["error"], 0) + 1
    if tipos:
        print("Errores por tipo: " + ", ".join(f"{k}={v}" for k, v in sorted(tipos.items())))
    if parada is None:
        print("No se leyó señal de falla: no se calcula RTO.")
        return
    for fase in ("antes-falla", "despues-falla"):
        lat = [float(f["latency_ms"]) for f in oks if f["phase"] == fase]
        if lat:
            print(f"Latencia de escrituras confirmadas {fase:<13}: n={len(lat):<4} "
                  f"p50={percentil(lat, 50):.1f} ms  p99={percentil(lat, 99):.1f} ms  máx={max(lat):.1f} ms")
    despues_ok = [f for f in oks if float(f["completed_epoch"]) >= parada]
    if despues_ok:
        rto = (float(despues_ok[0]["completed_epoch"]) - parada) * 1000
        print(f"Primera escritura confirmada tras la señal: seq={despues_ok[0]['seq']} "
              f"a {rto:.0f} ms de la falla (compruébelo en el CSV).")
    primer_error = next((f for f in errs if float(f["completed_epoch"]) >= parada), None)
    if primer_error is None:
        print("No hubo errores tras la señal: la falla no interrumpió las escrituras.")
        return
    previo = [f for f in oks if float(f["completed_epoch"]) < float(primer_error["completed_epoch"])]
    posterior = [f for f in oks if float(f["completed_epoch"]) > float(primer_error["completed_epoch"])]
    if previo and posterior:
        ventana = (float(posterior[0]["completed_epoch"]) - float(previo[-1]["completed_epoch"])) * 1000
        print(f"Ventana sin escrituras confirmadas: {ventana:.0f} ms "
              f"(del seq={previo[-1]['seq']} al seq={posterior[0]['seq']}).")
    elif not posterior:
        print("No se observó recuperación antes de terminar la sonda: alargue --duration "
              "o restaure los nodos antes.")


if __name__ == "__main__":
    raise SystemExit(main())
