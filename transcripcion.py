"""
Transcribe los episodios recientes de los podcasts de The Compound y los escribe en el Sheet.
No usa YouTube: baja el MP3 del feed RSS de audio y lo transcribe con faster-whisper.
Secrets: SHEET_URL y GCP_SA_KEY.
"""
import os, sys, json, re, gc, urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime

# ------------------------------ AJUSTES ------------------------------
FEEDS = {
    "The Compound and Friends": "https://feeds.megaphone.fm/TCP4771071679",
    "Animal Spirits":           "https://feeds.megaphone.fm/TCP6464651487",
}
HORAS      = 30        # antiguedad maxima del episodio
MAX_EPS    = 2         # cuantos episodios transcribir como mucho por corrida
MODELO     = "base"    # tiny = mas rapido y peor; base = equilibrio; small = mejor y lento
HOJA       = "podcast"
CHUNK      = 40000     # una celda de Sheets aguanta 50.000 caracteres
MAX_MB     = 250       # no bajar audios mas grandes que esto

SHEET_URL = os.environ.get("SHEET_URL", "")
SA_KEY    = os.environ.get("GCP_SA_KEY", "")
if not SHEET_URL or not SA_KEY:
    sys.exit("Faltan los secrets SHEET_URL y/o GCP_SA_KEY.")

UA = {"User-Agent": "Mozilla/5.0 (compatible; LBFinanzasBot/1.0)"}


def limpiar_html(texto):
    if not texto:
        return ""
    texto = re.sub(r"<br\s*/?>", " ", texto)
    texto = re.sub(r"<[^>]+>", " ", texto)
    texto = (texto.replace("&amp;", "&").replace("&lt;", "<")
                  .replace("&gt;", ">").replace("&nbsp;", " ").replace("&#39;", "'"))
    return re.sub(r"\s+", " ", texto).strip()


def episodios_recientes():
    """Recorre los feeds y devuelve los episodios publicados dentro de la ventana."""
    corte, salida = datetime.now(timezone.utc) - timedelta(hours=HORAS), []
    for programa, url in FEEDS.items():
        try:
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=60) as r:
                raiz = ET.fromstring(r.read())
        except Exception as e:
            print(f"[!] No se pudo leer el feed de {programa}: {e}")
            continue

        for item in raiz.findall(".//channel/item"):
            fecha_txt = item.findtext("pubDate")
            if not fecha_txt:
                continue
            try:
                publicado = parsedate_to_datetime(fecha_txt)
            except Exception:
                continue
            if publicado.tzinfo is None:
                publicado = publicado.replace(tzinfo=timezone.utc)
            if publicado < corte:
                continue

            enc = item.find("enclosure")
            if enc is None or not enc.get("url"):
                continue
            salida.append({
                "programa":  programa,
                "titulo":    (item.findtext("title") or "").strip(),
                "publicado": publicado,
                "audio":     enc.get("url"),
                "pagina":    (item.findtext("link") or "").strip(),
                "desc":      limpiar_html(item.findtext("description"))[:3000],
            })
    return sorted(salida, key=lambda e: e["publicado"], reverse=True)[:MAX_EPS]


def bajar_audio(ep, destino):
    req = urllib.request.Request(ep["audio"], headers=UA)
    with urllib.request.urlopen(req, timeout=600) as r, open(destino, "wb") as fh:
        leido = 0
        while True:
            trozo = r.read(1 << 20)
            if not trozo:
                break
            leido += len(trozo)
            if leido > MAX_MB * 1024 * 1024:
                raise RuntimeError(f"audio mayor a {MAX_MB} MB, se descarta")
            fh.write(trozo)
    print(f"  audio: {leido / 1024 / 1024:.1f} MB")


def transcribir(ruta):
    from faster_whisper import WhisperModel
    modelo = WhisperModel(MODELO, device="cpu", compute_type="int8")
    segmentos, info = modelo.transcribe(ruta, beam_size=1, vad_filter=True,
                                        condition_on_previous_text=False)
    print(f"  idioma detectado: {info.language} · duracion: {info.duration/60:.0f} min")
    texto = " ".join(s.text.strip() for s in segmentos)
    del modelo
    gc.collect()
    return re.sub(r"\s+", " ", texto).strip()


def main():
    episodios = episodios_recientes()
    ahora = datetime.now(timezone.utc).strftime("%d/%m/%Y %H:%M UTC")
    filas = []

    if not episodios:
        print(f"Sin episodios nuevos en las ultimas {HORAS} horas.")
        filas = [["(sin episodios nuevos)", "", "", ahora, "", "", ""]]
    else:
        for ep in episodios:
            print(f"\n{ep['programa']} — {ep['titulo']}")
            publicado = ep["publicado"].strftime("%d/%m/%Y %H:%M UTC")
            ruta = "/tmp/episodio.mp3"
            texto = ""
            try:
                bajar_audio(ep, ruta)
                texto = transcribir(ruta)
                print(f"  transcripcion: {len(texto):,} caracteres")
            except Exception as e:
                print(f"  [!] fallo la transcripcion: {e}")
            finally:
                if os.path.exists(ruta):
                    os.remove(ruta)

            if not texto:
                filas.append([ep["programa"], ep["titulo"], ep["pagina"], publicado,
                              ep["desc"], "sin transcripcion", ""])
                continue

            trozos = [texto[i:i + CHUNK] for i in range(0, len(texto), CHUNK)]
            for n, trozo in enumerate(trozos, 1):
                filas.append([ep["programa"], ep["titulo"], ep["pagina"], publicado,
                              ep["desc"] if n == 1 else "",
                              f"{n}/{len(trozos)}", trozo])

    import gspread
    from google.oauth2.service_account import Credentials

    creds = Credentials.from_service_account_info(
        json.loads(SA_KEY),
        scopes=["https://www.googleapis.com/auth/spreadsheets",
                "https://www.googleapis.com/auth/drive"])
    sh = gspread.authorize(creds).open_by_url(SHEET_URL)

    encabezado = ["Programa", "Titulo", "Pagina", "Publicado", "Descripcion",
                  "Parte", "Transcripcion"]
    try:
        ws = sh.worksheet(HOJA); ws.clear()
    except gspread.WorksheetNotFound:
        ws = sh.add_worksheet(title=HOJA, rows=max(len(filas) + 10, 50), cols=9)
    ws.update(values=[encabezado] + filas, range_name="A1")

    con_texto = sum(1 for f in filas if f[6])
    print(f"\nListo · {len(filas)} filas en «{HOJA}» ({con_texto} con transcripcion)\n{sh.url}")


if __name__ == "__main__":
    main()
