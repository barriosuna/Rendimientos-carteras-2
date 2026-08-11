
import os, json, sys
import pandas as pd, yfinance as yf
import matplotlib
matplotlib.use("Agg")           # sin pantalla: corre en un servidor
import matplotlib.pyplot as plt

# ============================== AJUSTES ==============================
TZ         = "America/Argentina/Cordoba"
MESES_HIST = 15          # historia a descargar. Tiene que ser > 13 para la ventana de 12 meses.

# Estos dos salen de los Secrets del repo (Settings -> Secrets and variables -> Actions)
SHEET_URL  = os.environ.get("SHEET_URL", "")
SA_KEY     = os.environ.get("GCP_SA_KEY", "")
if not SHEET_URL or not SA_KEY:
    sys.exit("Faltan los secrets SHEET_URL y/o GCP_SA_KEY.")

PORTFOLIOS = {
    "Futuro seguro":            {"VTI": 60, "VXUS": 30, "BND": 10},
    "Anticrisis":               {"VTI": 25, "GLD": 25, "SGOV": 25, "BND": 15, "BNDX": 10},
    "Dividendos":               {"SCHD": 25, "VIG": 25, "DGRO": 20, "IDVO": 15, "DIVO": 15},
    "Mercados Emergentes":      {"MCHI": 25, "INDA": 18, "EWZ": 15, "EWT": 12,
                                 "EWY": 10, "EWW": 9, "ILF": 6, "ARGT": 5},
    "Michael Burry - Tematica": {"MOH": 43.49, "LULU": 32.35, "SLM": 24.16},
    "Ingreso estable":          {"SGOV": 40, "SHY": 25, "LQD": 20, "IEF": 10, "TLT": 5},
    "Maximo potencial":         {"QQQ": 30, "SMH": 25, "VUG": 20, "IWO": 15, "XBI": 10},
    "Rendimientos extra":       {"VB": 25, "MTUM": 25, "QUAL": 25, "VLUE": 25},
    "Revolucion IA":            {"NVDA": 25, "CHAT": 25, "SMH": 20, "IGV": 20, "VST": 10},
}

MESES_ES = {1:"enero", 2:"febrero", 3:"marzo", 4:"abril", 5:"mayo", 6:"junio",
            7:"julio", 8:"agosto", 9:"septiembre", 10:"octubre", 11:"noviembre", 12:"diciembre"}

# ====================== FECHAS: SE CALCULAN SOLAS ======================
# No hay ninguna fecha escrita a mano en todo el script: todo sale de la fecha de hoy.
HOY     = pd.Timestamp.now(tz=TZ).tz_localize(None).normalize()
START   = (HOY - pd.DateOffset(months=MESES_HIST)).replace(day=1).strftime("%Y-%m-%d")
END     = (HOY + pd.Timedelta(days=1)).strftime("%Y-%m-%d")   # END es exclusivo: sumar 1 día incluye hoy
TICKERS = sorted({t for p in PORTFOLIOS.values() for t in p})
print(f"Corrida del {HOY:%d/%m/%Y} · {len(TICKERS)} tickers desde {START}")

# ========================= DESCARGA DE PRECIOS =========================
raw = yf.download(TICKERS, start=START, end=END, auto_adjust=True,
                  progress=False, group_by="column")

if isinstance(raw.columns, pd.MultiIndex):
    px = raw["Close"].copy()
else:
    px = raw[["Close"]].copy(); px.columns = TICKERS

px = px.dropna(how="all").ffill()
px.index = pd.to_datetime(px.index)
px = px.sort_index()

faltan = [t for t in TICKERS if t not in px.columns or px[t].isna().all()]
if faltan:
    raise RuntimeError(f"Yahoo no devolvió datos para: {faltan}. Revisá los tickers antes de publicar.")
print(f"OK: datos completos para {len(TICKERS)} tickers")

D_LAST, D_PREV = px.index[-1], px.index[-2]
print(f"Última rueda disponible: {D_LAST:%d/%m/%Y}  (anterior: {D_PREV:%d/%m/%Y})")
if (HOY - D_LAST).days >= 1:
    print(f"[nota] Todavía no cerró la rueda de hoy: el cálculo usa el cierre del {D_LAST:%d/%m/%Y}.")

# ===================== VENTANAS: TAMBIÉN AUTOMÁTICAS =====================
# Las ventanas se derivan del mes de la última rueda, no de una lista fija de meses.
me = px.resample("ME").last()
me.index = me.index.to_period("M")

p_last, p_prev = px.iloc[-1], px.iloc[-2]
M_ACT   = D_LAST.to_period("M")
DIC_ANT = pd.Period(f"{D_LAST.year - 1}-12", "M")

def cierre(periodo):
    """Precios al cierre del mes pedido, o None si no hay historia suficiente."""
    return me.loc[periodo] if periodo in me.index else None

def nombre_mes(p):
    return f"{MESES_ES[p.month]} {p.year}"

VENTANAS, meta = {}, []

def agregar(nombre, base, fin, desde, hasta, bloque):
    if base is None or fin is None:
        print(f"[!] Sin historia suficiente para '{nombre}': se omite.")
        return
    VENTANAS[nombre] = (base, fin)
    meta.append({"Ventana": nombre, "Bloque": bloque, "Desde": desde, "Hasta": hasta})

f_dia   = f"{D_LAST:%d/%m/%Y}"
MES_ANT = nombre_mes(M_ACT - 1)

# --- Bloque A: contra el último cierre disponible (al día de la fecha) ---
agregar("En el dia",     p_prev,             p_last, f"{D_PREV:%d/%m/%Y}",                f_dia, "A la fecha")
agregar("En el mes",     cierre(M_ACT - 1),  p_last, f"cierre {MES_ANT}",                 f_dia, "A la fecha")
agregar("Ult. 3 meses",  cierre(M_ACT - 3),  p_last, f"cierre {nombre_mes(M_ACT-3)}",     f_dia, "A la fecha")
agregar("YTD",           cierre(DIC_ANT),    p_last, f"cierre diciembre {D_LAST.year-1}", f_dia, "A la fecha")
agregar("Ult. 12 meses", cierre(M_ACT - 12), p_last, f"cierre {nombre_mes(M_ACT-12)}",    f_dia, "A la fecha")

# --- Bloque B: entre cierres de mes completos (lo que hacía la versión original) ---
agregar(f"Mes cerrado ({MES_ANT})", cierre(M_ACT - 2), cierre(M_ACT - 1),
        f"cierre {nombre_mes(M_ACT-2)}", f"cierre {MES_ANT}", "Meses cerrados")
agregar("3 meses cerrados",         cierre(M_ACT - 4), cierre(M_ACT - 1),
        f"cierre {nombre_mes(M_ACT-4)}", f"cierre {MES_ANT}", "Meses cerrados")
agregar("YTD cerrado",              cierre(DIC_ANT),   cierre(M_ACT - 1),
        f"cierre diciembre {D_LAST.year-1}", f"cierre {MES_ANT}", "Meses cerrados")

ventanas_meta = pd.DataFrame(meta)
COLS = list(VENTANAS.keys())
print(); print(ventanas_meta.to_string(index=False))

# ===================== RETORNOS, CARTERAS Y APORTES =====================
activos = pd.DataFrame({n: (fin / base - 1) * 100 for n, (base, fin) in VENTANAS.items()})[COLS]
activos.index.name = "Ticker"
activos = activos.round(2)

carteras = pd.DataFrame({
    nombre: {c: sum(peso / sum(pesos.values()) * activos.loc[t, c] for t, peso in pesos.items())
             for c in COLS}
    for nombre, pesos in PORTFOLIOS.items()
}).T[COLS].round(2)
carteras.index.name = "Cartera"

det = []
for nombre, pesos in PORTFOLIOS.items():
    tot = sum(pesos.values())
    for t, peso in pesos.items():
        fila = {"Cartera": nombre, "Ticker": t, "Peso %": round(peso / tot * 100, 2)}
        for c in COLS:
            fila[f"Ret {c}"]    = round(activos.loc[t, c], 2)
            fila[f"Aporte {c}"] = round(peso / tot * activos.loc[t, c], 2)
        det.append(fila)
detalle = pd.DataFrame(det)

resumen = pd.DataFrame({
    "Campo": ["Corrida", "Ultima rueda", "Rueda anterior", "Tickers", "Carteras",
              "Moneda", "Metodologia", "Fuente"],
    "Valor": [HOY.strftime("%d/%m/%Y %H:%M"), D_LAST.strftime("%d/%m/%Y"),
              D_PREV.strftime("%d/%m/%Y"), len(TICKERS), len(PORTFOLIOS), "USD",
              "Retorno total simple sobre precios ajustados (dividendos y splits reinvertidos). "
              "Cartera = promedio ponderado de sus activos, rebalanceada al inicio de cada ventana.",
              "Yahoo Finance via yfinance"],
})

pd.set_option("display.max_rows", 250); pd.set_option("display.width", 250)
print(f"\n=== CARTERAS · retorno total en USD · corte {D_LAST:%d/%m/%Y} ===")
print(carteras.to_string())
print("\n=== ACTIVOS ===")
print(activos.to_string())
print("\n=== APORTES ===")
print(detalle.to_string(index=False))

# =============================== GRÁFICO ===============================
orden        = "YTD" if "YTD" in COLS else COLS[0]
cols_grafico = [c for c in ["En el mes", "Ult. 3 meses", "YTD"] if c in COLS] or COLS[:3]

ax = carteras[cols_grafico].sort_values(orden).plot(kind="barh", figsize=(10, 6), width=0.8)
ax.axvline(0, color="black", lw=0.8)
ax.set_xlabel("Retorno total (%)")
ax.set_title(f"Carteras modelo — retorno total en USD (al {D_LAST:%d/%m/%Y})")
ax.legend(title=""); ax.grid(axis="x", alpha=0.3)
plt.tight_layout(); plt.savefig("carteras.png", dpi=140)
print("Gráfico guardado en carteras.png")

# ========================= ESCRITURA AL SHEET =========================
import gspread
from gspread_dataframe import set_with_dataframe
from google.oauth2.service_account import Credentials

creds = Credentials.from_service_account_info(
    json.loads(SA_KEY),
    scopes=["https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive"])
gc = gspread.authorize(creds)
sh = gc.open_by_url(SHEET_URL)

def volcar(titulo, df, indice=False):
    """Reemplaza por completo el contenido de una hoja."""
    df = df.reset_index() if indice else df
    df = df.astype(object).where(pd.notna(df), None)      # NaN -> celda vacía
    try:
        ws = sh.worksheet(titulo); ws.clear()
    except gspread.WorksheetNotFound:
        ws = sh.add_worksheet(title=titulo,
                              rows=max(len(df) + 10, 100),
                              cols=max(len(df.columns) + 5, 20))
    set_with_dataframe(ws, df, include_index=False, resize=True)
    print(f"  · {titulo}: {len(df)} filas")

print("\nEscribiendo al Sheet...")
for hoja, df, ix in [("carteras", carteras, True), ("activos", activos, True),
                     ("aportes", detalle, False), ("ventanas", ventanas_meta, False),
                     ("control", resumen, False)]:
    volcar(hoja, df, ix)

print(f"\nListo · corte {D_LAST:%d/%m/%Y}\n{sh.url}")
