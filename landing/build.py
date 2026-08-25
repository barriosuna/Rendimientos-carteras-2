#!/usr/bin/env python3
"""
Genera public/index.html — la landing "Estrategias de inversión" de LB Finanzas.

Cruza dos fuentes:
  - Google Sheet de rendimientos (hojas `carteras`, `aportes`, `control`) → los números
  - landing/estrategias.json + landing/activos.json → nombres, textos, íconos

Corre como paso final del workflow "Rendimientos carteras", después de que el
Sheet ya fue actualizado.

Variables de entorno:
  SHEET_ID                     ID del Sheet de rendimientos
  GOOGLE_SERVICE_ACCOUNT_JSON  credenciales del service account (el JSON completo)

Salida: public/index.html
Códigos de salida: 0 ok · 1 error de datos (no publica nada)
"""

import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path

import gspread
from google.oauth2.service_account import Credentials

RAIZ = Path(__file__).resolve().parent.parent
LANDING = RAIZ / "landing"
SALIDA = RAIZ / "public" / "index.html"

VENTANAS = ["En el dia", "En el mes", "Ult. 3 meses", "YTD", "Ult. 12 meses"]

MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio",
         "agosto", "septiembre", "octubre", "noviembre", "diciembre"]
DIAS = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]


def morir(msg):
    print(f"ERROR: {msg}", file=sys.stderr)
    sys.exit(1)


def abrir_sheet():
    crudo = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON")
    sheet_id = os.environ.get("SHEET_ID")
    if not crudo:
        morir("falta GOOGLE_SERVICE_ACCOUNT_JSON")
    if not sheet_id:
        morir("falta SHEET_ID")
    creds = Credentials.from_service_account_info(
        json.loads(crudo),
        scopes=["https://www.googleapis.com/auth/spreadsheets.readonly"],
    )
    return gspread.authorize(creds).open_by_key(sheet_id)


def num(v):
    """Convierte el texto de una celda a float. Tolera coma decimal y vacíos."""
    if v is None:
        return None
    s = str(v).strip().replace("\u2212", "-")
    if not s or s in {"-", "n/a", "N/A"}:
        return None
    if "," in s and "." not in s:
        s = s.replace(",", ".")
    try:
        return float(s)
    except ValueError:
        return None


def leer_control(sh):
    """Devuelve el dict de la hoja `control` y valida que la corrida sea reciente."""
    filas = sh.worksheet("control").get_all_records()
    ctrl = {f["Campo"]: f["Valor"] for f in filas if f.get("Campo")}

    rueda = str(ctrl.get("Ultima rueda", "")).strip()
    if not rueda:
        morir("la hoja `control` no tiene 'Ultima rueda'")

    try:
        fecha = datetime.strptime(rueda.split()[0], "%d/%m/%Y")
    except ValueError:
        morir(f"no se pudo interpretar 'Ultima rueda': {rueda!r}")

    dias = (datetime.now() - fecha).days
    if dias > 5:
        morir(
            f"la última rueda es del {rueda} ({dias} días atrás). "
            "El workflow de cálculo no corrió: no se publica nada."
        )
    if dias > 3:
        print(f"AVISO: la última rueda es del {rueda} ({dias} días atrás).",
              file=sys.stderr)

    return ctrl, fecha


def leer_carteras(sh):
    filas = sh.worksheet("carteras").get_all_records()
    out = {}
    for f in filas:
        nombre = str(f.get("Cartera", "")).strip()
        if nombre:
            out[nombre] = [num(f.get(v)) for v in VENTANAS]
    return out


def leer_aportes(sh):
    filas = sh.worksheet("aportes").get_all_records()
    out = {}
    for f in filas:
        cartera = str(f.get("Cartera", "")).strip()
        ticker = str(f.get("Ticker", "")).strip()
        if not cartera or not ticker:
            continue
        out.setdefault(cartera, []).append({
            "t": ticker,
            "peso": num(f.get("Peso %")),
            "r12m": num(f.get("Ret Ult. 12 meses")),
        })
    return out


def fecha_larga(d):
    return f"{DIAS[d.weekday()]} {d.day} de {MESES[d.month - 1]} de {d.year}"


def main():
    meta = json.loads((LANDING / "estrategias.json").read_text(encoding="utf-8"))
    nombres_activos = json.loads((LANDING / "activos.json").read_text(encoding="utf-8"))
    plantilla = (LANDING / "template.html").read_text(encoding="utf-8")

    sh = abrir_sheet()
    ctrl, fecha = leer_control(sh)
    carteras = leer_carteras(sh)
    aportes = leer_aportes(sh)

    estrategias = []
    faltantes = []

    for e in meta:
        clave = e.get("nombreEnSheet") or e["nombre"]

        if clave not in carteras:
            faltantes.append(f"{e['id']}: no está en la hoja `carteras` como {clave!r}")
            continue
        ret = carteras[clave]
        if any(v is None for v in ret):
            faltantes.append(f"{e['id']}: hay ventanas vacías en `carteras`")
            continue

        comp = sorted(aportes.get(clave, []), key=lambda a: -(a["peso"] or 0))
        if not comp:
            faltantes.append(f"{e['id']}: no tiene filas en la hoja `aportes`")
            continue

        estrategias.append({
            "id": e["id"],
            "nombre": e["nombre"],
            "subtitulo": e["subtitulo"],
            "icono": e.get("icono", ""),
            "riesgo": e["riesgo"],
            "riesgoKey": e["riesgoKey"],
            "plazo": e["plazo"],
            "ret": ret,
            "activos": [{
                "t": a["t"],
                "peso": a["peso"],
                "nombre": nombres_activos.get(a["t"], ""),
                "r12m": a["r12m"],
            } for a in comp[:5]],
            "totalActivos": len(comp),
            "descripcion": e["descripcion"],
            "serie": e.get("serie"),
        })

    if faltantes:
        morir("no se pudo armar la página:\n  - " + "\n  - ".join(faltantes))

    html = plantilla.replace(
        "__DATOS__", json.dumps(estrategias, ensure_ascii=False, indent=1)
    ).replace("__FECHA_LARGA__", fecha_larga(fecha))

    if "__DATOS__" in html or "__FECHA_LARGA__" in html:
        morir("quedaron tokens sin reemplazar en la plantilla")
    if re.search(r"\bs/d\b", re.sub(r"a\.r12m===null\?'s/d'", "", html)):
        print("AVISO: quedó algún 's/d' en la página.", file=sys.stderr)

    SALIDA.parent.mkdir(parents=True, exist_ok=True)
    SALIDA.write_text(html, encoding="utf-8")

    print(f"OK · {len(estrategias)} estrategias · última rueda {ctrl['Ultima rueda']} "
          f"· {SALIDA.relative_to(RAIZ)} ({len(html):,} bytes)")


if __name__ == "__main__":
    main()
