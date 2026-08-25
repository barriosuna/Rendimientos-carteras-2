#!/usr/bin/env python3
"""
Genera public/index.html — la landing "Estrategias de inversión" de LB Finanzas.

Cruza dos fuentes:
  - Google Sheet de rendimientos (hojas `carteras`, `aportes`, `control`) → los números
  - landing/estrategias.json + landing/activos.json → nombres, textos, íconos

Corre como paso final del workflow "Rendimientos carteras", después de que el
Sheet ya fue actualizado.

Variables de entorno (reusa los secrets que ya tiene el workflow):
  SHEET_URL o SHEET_ID   URL completa del Sheet, o solo su ID
  GCP_SA_KEY o GOOGLE_SERVICE_ACCOUNT_JSON
                         credenciales del service account, como JSON o en base64

Salida: public/index.html
Códigos de salida: 0 ok · 1 error de datos (no publica nada)
"""

import base64
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
SALIDA_HTML = RAIZ / "public" / "index.html"
SALIDA_JSON = RAIZ / "public" / "api" / "estrategias.json"
SALIDA_SP500 = RAIZ / "public" / "api" / "sp500.json"

VENTANAS = ["En el dia", "En el mes", "Ult. 3 meses", "YTD", "Ult. 12 meses"]

MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio",
         "agosto", "septiembre", "octubre", "noviembre", "diciembre"]
DIAS = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]


def morir(msg):
    print(f"ERROR: {msg}", file=sys.stderr)
    sys.exit(1)


def id_del_sheet():
    """Acepta la URL completa del Sheet o solo el ID."""
    valor = os.environ.get("SHEET_URL") or os.environ.get("SHEET_ID")
    if not valor:
        morir("falta SHEET_URL (o SHEET_ID)")
    valor = valor.strip()
    m = re.search(r"/spreadsheets/d/([a-zA-Z0-9_-]+)", valor)
    return m.group(1) if m else valor


def credenciales():
    """Acepta el JSON del service account tal cual o codificado en base64."""
    crudo = (os.environ.get("GCP_SA_KEY")
             or os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON"))
    if not crudo:
        morir("falta GCP_SA_KEY (o GOOGLE_SERVICE_ACCOUNT_JSON)")
    crudo = crudo.strip()
    if not crudo.startswith("{"):
        try:
            crudo = base64.b64decode(crudo).decode("utf-8")
        except Exception:
            morir("GCP_SA_KEY no es JSON ni base64 válido")
    try:
        info = json.loads(crudo)
    except json.JSONDecodeError as e:
        morir(f"GCP_SA_KEY no es un JSON válido: {e}")
    return Credentials.from_service_account_info(
        info, scopes=["https://www.googleapis.com/auth/spreadsheets.readonly"]
    )


def abrir_sheet():
    return gspread.authorize(credenciales()).open_by_key(id_del_sheet())


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



def escribir_sp500():
    """
    Serie mensual de retorno total del S&P 500 (SPY, dividendos reinvertidos).
    La usa la calculadora de DCA. Si falla, no corta el build: la página de
    estrategias no depende de esto y la de DCA muestra su propio error.
    """
    try:
        import yfinance as yf
    except ImportError:
        print("AVISO: yfinance no instalado, no se actualiza sp500.json", file=sys.stderr)
        return

    try:
        df = yf.download("SPY", start="1993-02-01", interval="1mo",
                         auto_adjust=True, progress=False)
        if df is None or df.empty:
            raise ValueError("respuesta vacía")
        cierres = df["Close"].dropna()
        if hasattr(cierres, "columns"):
            cierres = cierres.iloc[:, 0]

        serie = [{"f": i.strftime("%Y-%m"), "c": round(float(v), 4)}
                 for i, v in cierres.items()]
        if len(serie) < 240:
            raise ValueError(f"serie demasiado corta: {len(serie)} meses")

        payload = {
            "generado": datetime.utcnow().replace(microsecond=0).isoformat() + "Z",
            "ticker": "SPY",
            "descripcion": ("Cierres mensuales ajustados por dividendos y splits. "
                            "El retorno entre dos fechas es el cociente de sus cierres."),
            "desde": serie[0]["f"],
            "hasta": serie[-1]["f"],
            "meses": len(serie),
            "serie": serie,
        }
        SALIDA_SP500.parent.mkdir(parents=True, exist_ok=True)
        SALIDA_SP500.write_text(json.dumps(payload, separators=(",", ":")),
                                encoding="utf-8")
        print(f"   {SALIDA_SP500.relative_to(RAIZ)} "
              f"({len(serie)} meses, {serie[0]['f']} a {serie[-1]['f']})")
    except Exception as e:
        print(f"AVISO: no se pudo actualizar sp500.json ({e}). "
              "Queda el que ya estaba.", file=sys.stderr)


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

    SALIDA_HTML.parent.mkdir(parents=True, exist_ok=True)
    SALIDA_HTML.write_text(html, encoding="utf-8")

    # Endpoint de solo lectura que consume la landing de Webflow.
    payload = {
        "generado": datetime.utcnow().replace(microsecond=0).isoformat() + "Z",
        "ultimaRueda": ctrl["Ultima rueda"],
        "fechaLarga": fecha_larga(fecha),
        "moneda": ctrl.get("Moneda", "USD"),
        "estrategias": estrategias,
    }
    SALIDA_JSON.parent.mkdir(parents=True, exist_ok=True)
    SALIDA_JSON.write_text(
        json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )

    print(f"OK · {len(estrategias)} estrategias · última rueda {ctrl['Ultima rueda']}")
    print(f"   {SALIDA_HTML.relative_to(RAIZ)} ({len(html):,} bytes)")
    print(f"   {SALIDA_JSON.relative_to(RAIZ)} ({SALIDA_JSON.stat().st_size:,} bytes)")

    escribir_sp500()


if __name__ == "__main__":
    main()
