"""
Baja la transcripción del último episodio de The Compound y la escribe en el Sheet.
Usa los mismos secrets que rendimientos.py: SHEET_URL y GCP_SA_KEY.
"""
import os, sys, json, re, subprocess, glob, urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone

# ------------------------------ AJUSTES ------------------------------
CANAL_ID   = "UCBRpqrzuuqE8TZcWw75JSdw"   # The Compound
HORAS      = 36        # antigüedad máxima del episodio a buscar
MAX_VIDEOS = 2         # cuántos episodios recientes bajar como mucho
IDIOMAS    = "en,en-US,en-GB"
HOJA       = "podcast"
CHUNK      = 40000     # una celda de Sheets aguanta 50.000 caracteres

SHEET_URL = os.environ.get("SHEET_URL", "")
SA_KEY    = os.environ.get("GCP_SA_KEY", "")
if not SHEET_URL or not SA_KEY:
    sys.exit("Faltan los secrets SHEET_URL y/o GCP_SA_KEY.")

NS = {"atom": "http://www.w3.org/2005/Atom",
      "media": "http://search.yahoo.com/mrss/",
      "yt": "http://www.youtube.com/xml/schemas/2015"}


def episodios_recientes():
    """Lee el feed RSS del canal y devuelve los videos publicados dentro de la ventana."""
    url = f"https://www.youtube.com/feeds/videos.xml?channel_id={CANAL_ID}"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=30) as r:
        raiz = ET.fromstring(r.read())

    corte, salida = datetime.now(timezone.utc) - timedelta(hours=HORAS), []
    for e in raiz.findall("atom:entry", NS):
        publicado = datetime.fromisoformat(e.find("atom:published", NS).text)
        if publicado < corte:
            continue
        desc = e.find("media:group/media:description", NS)
        salida.append({
            "id":        e.find("yt:videoId", NS).text,
            "titulo":    e.find("atom:title", NS).text,
            "publicado": publicado,
            "url":       f"https://www.youtube.com/watch?v={e.find('yt:videoId', NS).text}",
            "desc":      (desc.text or "")[:2000] if desc is not None else "",
        })
    return sorted(salida, key=lambda v: v["publicado"], reverse=True)[:MAX_VIDEOS]


def limpiar_vtt(texto):
    """Convierte un .vtt de subtítulos automáticos en texto corrido sin repeticiones."""
    lineas = []
    for linea in texto.splitlines():
        linea = linea.strip()
        if (not linea or linea.startswith(("WEBVTT", "Kind:", "Language:", "NOTE"))
                or "-->" in linea or linea.isdigit()):
            continue
        linea = re.sub(r"<[^>]+>", "", linea)
        linea = re.sub(r"\[[^\]]*\]", "", linea)
        linea = re.sub(r"\s+", " ", linea).strip()
        if linea and (not lineas or linea != lineas[-1]):
            lineas.append(linea)

    fuera = []
    for l in lineas:
        if fuera and (fuera[-1].endswith(l) or l.startswith(fuera[-1][-40:])):
            solapado = fuera[-1][-40:]
            if l.startswith(solapado):
                l = l[len(solapado):].strip()
            if not l:
                continue
        fuera.append(l)
    return re.sub(r"\s+", " ", " ".join(fuera)).strip()


def bajar_transcripcion(video):
    """Descarga los subtítulos automáticos con yt-dlp. Devuelve texto plano o None."""
    destino = f"/tmp/{video['id']}"
    for f in glob.glob(destino + "*"):
        os.remove(f)
    cmd = ["yt-dlp", "--skip-download", "--write-auto-subs", "--write-subs",
           "--sub-langs", IDIOMAS, "--sub-format", "vtt/best",
           "--no-warnings", "--retries", "3", "-o", destino, video["url"]]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
    archivos = glob.glob(destino + "*.vtt")
    if not archivos:
        print(f"  [!] sin subtítulos para «{video['titulo']}»")
        if r.stderr:
            print("      ", r.stderr.strip().splitlines()[-1][:200])
        return None
    with open(archivos[0], encoding="utf-8", errors="ignore") as fh:
        texto = limpiar_vtt(fh.read())
    print(f"  · {len(texto):,} caracteres")
    return texto


def main():
    videos = episodios_recientes()
    if not videos:
        print(f"No hay episodios nuevos en las últimas {HORAS} horas.")
        filas = [["(sin episodios nuevos)", "", datetime.now(timezone.utc)
                  .strftime("%d/%m/%Y %H:%M UTC"), "", "", ""]]
    else:
        filas = []
        for v in videos:
            print(f"Bajando: {v['titulo']}")
            texto = bajar_transcripcion(v)
            if not texto:
                continue
            trozos = [texto[i:i + CHUNK] for i in range(0, len(texto), CHUNK)] or [""]
            for n, trozo in enumerate(trozos, 1):
                filas.append([v["titulo"], v["url"],
                              v["publicado"].strftime("%d/%m/%Y %H:%M UTC"),
                              v["desc"] if n == 1 else "",
                              f"{n}/{len(trozos)}", trozo])
        if not filas:
            filas = [["(episodios encontrados pero sin subtítulos)", "", datetime.now(timezone.utc)
                      .strftime("%d/%m/%Y %H:%M UTC"), "", "", ""]]

    import gspread
    from google.oauth2.service_account import Credentials

    creds = Credentials.from_service_account_info(
        json.loads(SA_KEY),
        scopes=["https://www.googleapis.com/auth/spreadsheets",
                "https://www.googleapis.com/auth/drive"])
    sh = gspread.authorize(creds).open_by_url(SHEET_URL)

    encabezado = ["Titulo", "URL", "Publicado", "Descripcion", "Parte", "Transcripcion"]
    try:
        ws = sh.worksheet(HOJA); ws.clear()
    except gspread.WorksheetNotFound:
        ws = sh.add_worksheet(title=HOJA, rows=max(len(filas) + 10, 50), cols=8)
    ws.update(values=[encabezado] + filas, range_name="A1")

    print(f"\nListo · {len(filas)} filas en la hoja «{HOJA}»\n{sh.url}")


if __name__ == "__main__":
    main()
