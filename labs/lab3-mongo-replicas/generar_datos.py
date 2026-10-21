#!/usr/bin/env python3
"""Genera la semilla del Laboratorio 3 (eventos de una boletería) de forma determinista.

No modifique este archivo. Produce, en ``labs/lab3-mongo-replicas/data/``:

* ``eventos.jsonl``   — un evento por línea (un documento por evento);
* ``MANIFEST.json``   — conteos y suma SHA-256 que su carga debe reproducir.

La misma semilla produce siempre los mismos bytes: así su carga se puede verificar
contra el manifiesto, igual que se hará con el generador del Proyecto 2.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import random
from datetime import date, timedelta

from common import DATA

CATEGORIAS = ["concierto", "teatro", "deporte", "festival", "conferencia"]
CIUDADES = [
    "San José", "Heredia", "Alajuela", "Cartago",
    "Liberia", "Limón", "Puntarenas", "San Carlos",
]
RECINTOS = [
    "Arena Central", "Teatro del Valle", "Anfiteatro Los Cedros",
    "Auditorio Norte", "Parque de Eventos Sur", "Gimnasio Municipal", "Plaza Mayor",
]
ADJETIVOS = ["Vibrante", "Nocturno", "Clásico", "Urbano", "Andino", "Tropical", "Solar", "Eléctrico"]
ETIQUETAS = ["familiar", "al aire libre", "accesible", "18+", "transmisión en vivo"]
PATROCINADORES = ["Café Volcán", "Banco Ceiba", "Cerveza Quetzal", "Seguros Arenal"]
# (nombre, precio en colones, fracción de la capacidad de la zona General)
ZONAS = [("General", 8_000, 1.0), ("Preferencial", 18_000, 0.5), ("VIP", 45_000, 0.2), ("Palco", 70_000, 0.1)]


def generar_evento(rng: random.Random, i: int, inicio: date) -> dict:
    categoria = rng.choice(CATEGORIAS)
    base = rng.choice([100, 200, 300, 500])
    extras = rng.sample(ZONAS[1:], k=rng.randint(1, 3))
    zonas = []
    for nombre, precio, fraccion in [ZONAS[0], *extras]:
        capacidad = max(10, int(base * fraccion))
        zonas.append(
            {
                "nombre": nombre,
                "precio": precio + rng.choice([0, 0, 2_000, 5_000]),
                "capacidad": capacidad,
                "disponibles": capacidad,
            }
        )
    evento = {
        "_id": f"EV-{i:04d}",
        "nombre": f"{categoria.capitalize()} {rng.choice(ADJETIVOS)} {i}",
        "categoria": categoria,
        "ciudad": rng.choice(CIUDADES),
        "recinto": rng.choice(RECINTOS),
        "fecha": (inicio + timedelta(days=rng.randint(0, 240))).isoformat(),
        "etiquetas": rng.sample(ETIQUETAS, k=rng.randint(1, 3)),
        "zonas": zonas,
    }
    # Sin campos nulos: el patrocinador solo existe en el 30 % de los eventos.
    if rng.random() < 0.30:
        evento["patrocinador"] = rng.choice(PATROCINADORES)
    return evento


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--eventos", type=int, default=400)
    parser.add_argument("--semilla", type=int, default=2026)
    args = parser.parse_args()

    rng = random.Random(args.semilla)
    inicio = date(2026, 11, 1)
    DATA.mkdir(parents=True, exist_ok=True)
    ruta = DATA / "eventos.jsonl"

    zonas_total = 0
    capacidad_total = 0
    with ruta.open("w", encoding="utf-8", newline="\n") as f:
        for i in range(1, args.eventos + 1):
            ev = generar_evento(rng, i, inicio)
            zonas_total += len(ev["zonas"])
            capacidad_total += sum(z["capacidad"] for z in ev["zonas"])
            f.write(json.dumps(ev, ensure_ascii=False, sort_keys=True) + "\n")

    sha = hashlib.sha256(ruta.read_bytes()).hexdigest()
    manifiesto = {
        "semilla": args.semilla,
        "eventos": args.eventos,
        "zonas": zonas_total,
        "capacidad_total": capacidad_total,
        "sha256_eventos_jsonl": sha,
    }
    (DATA / "MANIFEST.json").write_text(
        json.dumps(manifiesto, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(json.dumps(manifiesto, indent=2, ensure_ascii=False))
    print(f"\nEscrito: {ruta}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
