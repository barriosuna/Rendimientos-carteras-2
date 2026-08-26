#!/usr/bin/env python3
"""
Regenera public/embed/estrategias.css y .js a partir de landing/template.html.

La plantilla es la única fuente de verdad del diseño: acá se le sacan la navbar
y el hero (en Webflow los pone el sitio), se escopa todo el CSS bajo
#lb-estrategias para que no choque con los estilos de Webflow, y el markup pasa
a ser una constante del JS que se dibuja con los datos de /api/estrategias.json.

Correr después de tocar template.html:
    python landing/build_embed.py
"""

import json
import re
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
PLANTILLA = RAIZ / "landing" / "template.html"
DEST = RAIZ / "public" / "embed"
SALIDA_DCA = RAIZ / "public" / "inversion-programada-dca.html"

CONTENEDOR = "#lb-estrategias"

# Selectores que NO viajan al embed: los pone el sitio de Webflow.
GLOBALES = {"html", "body", "*", "a", ":focus-visible"}
PREFIJOS_FUERA = (".nav", ".hero", ".eyebrow")


def bloques(texto):
    """Parte CSS en (selector, cuerpo) respetando llaves anidadas."""
    out, i, n = [], 0, len(texto)
    while i < n:
        j = texto.find("{", i)
        if j == -1:
            break
        sel = texto[i:j].strip()
        prof, k = 1, j + 1
        while k < n and prof:
            prof += (texto[k] == "{") - (texto[k] == "}")
            k += 1
        out.append((sel, texto[j + 1:k - 1]))
        i = k
    return out


def descartar(sel):
    return any(
        s.strip() in GLOBALES or s.strip().startswith(PREFIJOS_FUERA)
        for s in sel.split(",")
    )


def escopar(sel):
    return ",".join(f"{CONTENEDOR} {s.strip()}" for s in sel.split(",") if s.strip())



def escudo_de_clases(reglas, contenedor):
    """
    Las clases del widget (card, cards, chip, wrap...) son genericas y colisionan
    con el sistema de diseno del sitio anfitrion. Nuestras reglas solo ganan en
    las propiedades que declaramos: si Webflow define `.card{display:none}` y
    nosotros nunca declaramos display, gana Webflow y la ficha desaparece.

    Este escudo neutraliza, para cada clase que usamos, las propiedades capaces
    de ocultar o descolocar un elemento. Va ANTES de las reglas propias, que son
    igual de especificas pero posteriores, asi que las pisan cuando corresponde.
    `display:revert` devuelve el valor del navegador (block para div, inline para
    span), no un valor fijo que romperia los inline.
    """
    clases = sorted(set(re.findall(r"\.([a-zA-Z][\w-]*)", "\n".join(reglas))))
    if not clases:
        return ""
    sel = ",".join(f"{contenedor} .{c}" for c in clases)
    # Solo las tres propiedades que realmente ocultan un elemento. Neutralizar
    # tambien width/height/position rompia las barras del termometro, que fijan
    # su ancho con estilo inline: un !important del CSS le gana al inline.
    return (sel + "{display:revert!important;visibility:visible!important;"
            "opacity:1!important}\n")


def marcar_importante(regla):
    """Refuerza las propiedades que el escudo neutraliza, para que la regla propia
    vuelva a imponerse sobre el escudo y sobre cualquier !important del anfitrion."""
    return re.sub(
        r"\b(display|visibility|opacity)\s*:\s*([^;}!]+)(?=[;}])",
        lambda m: f"{m.group(1)}:{m.group(2).strip()}!important",
        regla,
    )


def construir_css(css):
    css = re.sub(r"/\*.*?\*/", "", css, flags=re.S)
    out = []
    for sel, cuerpo in bloques(css):
        if sel.startswith("@media"):
            dentro = [
                f"{escopar(s)}{{{c.strip()}}}"
                for s, c in bloques(cuerpo)
                if not descartar(s)
            ]
            if dentro:
                out.append(sel + "{" + "".join(dentro) + "}")
        elif sel == ":root":
            out.append(CONTENEDOR + "{" + re.sub(r"\s+", " ", cuerpo).strip() + "}")
        elif not descartar(sel):
            out.append(f"{escopar(sel)}{{{cuerpo.replace(chr(10), '').strip()}}}")

    # Blindaje: el widget vive dentro de una pagina de Webflow, que trae sus
    # propios estilos sobre body, h2, p, td y demas. Reset universal escopado
    # primero; las reglas propias, mas especificas, repintan despues.
    base = (
        f"{CONTENEDOR},{CONTENEDOR} *,{CONTENEDOR} *::before,{CONTENEDOR} *::after{{"
        "box-sizing:border-box;margin:0;padding:0;border:0;"
        "font-family:'Plus Jakarta Sans',-apple-system,BlinkMacSystemFont,"
        '"Segoe UI",Arial,sans-serif;'
        "font-size:inherit;font-weight:inherit;font-style:normal;line-height:inherit;"
        "color:inherit;letter-spacing:normal;text-transform:none;text-decoration:none;"
        "text-shadow:none;box-shadow:none;background:transparent;float:none;"
        "list-style:none;vertical-align:baseline}\n"
        f"{CONTENEDOR}{{display:block;background:#f7f7f7;color:#2c2b2e;font-size:16px;"
        "font-weight:400;line-height:1.6;text-align:left;"
        "-webkit-font-smoothing:antialiased;padding-bottom:64px}\n"
        f"{CONTENEDOR} b,{CONTENEDOR} strong{{font-weight:700}}\n"
        f"{CONTENEDOR} em,{CONTENEDOR} i{{font-style:italic}}\n"
        f"{CONTENEDOR} img,{CONTENEDOR} svg{{max-width:100%;display:block}}\n"
        f"{CONTENEDOR} table{{border-collapse:collapse;border-spacing:0}}\n"
        f"{CONTENEDOR} button{{cursor:pointer;background:none}}\n"
        f"{CONTENEDOR} input,{CONTENEDOR} select,{CONTENEDOR} button{{font-family:inherit}}\n"
        f"{CONTENEDOR} a{{color:var(--violeta)}}\n"
        f"{CONTENEDOR} :focus-visible{{outline:3px solid var(--acento);"
        "outline-offset:3px;border-radius:6px}\n"
        "@media (prefers-reduced-motion:reduce){"
        + CONTENEDOR + " *{animation:none!important;transition:none!important}}\n"
    )
    escudo = escudo_de_clases(out, CONTENEDOR)
    out = [marcar_importante(r) for r in out]
    return ("/*! LB Finanzas — widget Estrategias de inversión. GENERADO: no editar. */\n"
            + base + escudo + "\n".join(out) + "\n")


PLANTILLA_JS = """/*!
 * LB Finanzas — widget "Estrategias de inversión"
 * GENERADO por landing/build_embed.py. No editar a mano: editar template.html.
 *
 * Se monta dentro de <div id="lb-estrategias"></div> y se dibuja con los datos
 * de /api/estrategias.json. Solo lee: no toca credenciales ni escribe nada.
 */
(function () {
  'use strict';

  var MARKUP = __MARKUP__;

  var ENDPOINT = (document.currentScript && document.currentScript.dataset.endpoint)
    || 'https://TU-PROYECTO.vercel.app/api/estrategias.json';

  function montar(R, payload) {
    var ESTRATEGIAS = payload.estrategias;
    R.innerHTML = MARKUP;

    var pie = R.querySelector('#termoPie');
    if (pie && payload.fechaLarga) {
      pie.textContent = 'Rendimiento total en dólares, punto a punto, con '
        + 'dividendos reinvertidos. Cierre del ' + payload.fechaLarga + '.';
    }

__CUERPO__
  }

  function fallar(R, err) {
    R.innerHTML = '<p style="padding:32px 24px;font-family:\\'Plus Jakarta Sans\\',Arial,'
      + 'sans-serif;font-size:14.5px;color:#6b6678;text-align:center">'
      + 'No pudimos cargar los rendimientos en este momento. Probá recargar la página.</p>';
    if (window.console) console.error('[lb-estrategias]', err);
  }

  function arrancar() {
    var R = document.getElementById('lb-estrategias');
    if (!R) return;
    R.setAttribute('aria-busy', 'true');
    fetch(ENDPOINT, { cache: 'no-cache' })
      .then(function (r) {
        if (!r.ok) throw new Error('HTTP ' + r.status);
        return r.json();
      })
      .then(function (d) {
        if (!d || !Array.isArray(d.estrategias) || !d.estrategias.length) {
          throw new Error('respuesta sin estrategias');
        }
        montar(R, d);
      })
      .catch(function (e) { fallar(R, e); })
      .then(function () { R.removeAttribute('aria-busy'); });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', arrancar);
  } else {
    arrancar();
  }
})();
"""


def construir_js(js, markup):
    js = re.sub(r"const ESTRATEGIAS = .*?;\n", "", js, flags=re.S)
    js = js.replace("document.getElementById('", "R.querySelector('#")
    js = js.replace("document.querySelectorAll('", "R.querySelectorAll('")
    cuerpo = "\n".join("    " + l if l.strip() else l for l in js.strip().split("\n"))
    return (PLANTILLA_JS
            .replace("__MARKUP__", json.dumps(markup, ensure_ascii=False))
            .replace("__CUERPO__", cuerpo))



# ── página de DCA ────────────────────────────────────────────────────────────
# Reusa la navbar y el hero de template.html para que las dos páginas queden
# siempre iguales. El contenido lo pone embed/dca.js.

SHELL_DCA = """<!DOCTYPE html>
<html lang="es-AR">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Inversión programada · LB Finanzas</title>
<meta name="description" content="Qué es el Dollar Cost Average, por qué funciona y una calculadora con los datos históricos reales del S&amp;P 500.">
<link rel="icon" type="image/png" sizes="64x64" href="/assets/favicon-64.png">
<link rel="apple-touch-icon" sizes="180x180" href="/assets/apple-touch-icon.png">
<meta name="theme-color" content="#522398">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&display=swap" rel="stylesheet">
<link rel="stylesheet" href="/embed/dca.css">
<style>
__SHELL__
body{margin:0;background:var(--fondo);color:var(--negro);font-family:'Plus Jakarta Sans',-apple-system,BlinkMacSystemFont,'Segoe UI',Arial,sans-serif;font-size:16px;line-height:1.6;-webkit-font-smoothing:antialiased}
html{scroll-behavior:smooth;scroll-padding-top:96px}
.wrap{max-width:1080px;margin:0 auto;padding:0 24px}
a{color:var(--violeta)}
</style>
</head>
<body>

__NAV__

<header class="hero">
  <div class="hero-in">
    <p class="eyebrow">CÓMO INVERTIR</p>
    <h1>Inversión programada</h1>
    <p>Poner siempre el mismo monto, siempre en la misma fecha, sin mirar el precio. Es la forma más simple de invertir sin tener que adivinar el momento — y acá podés ver cuánto habría dado con los datos reales del mercado.</p>
  </div>
</header>

<main>
  <div id="lb-dca"></div>
</main>

<script src="/embed/dca.js" data-endpoint="/api/sp500.json" defer></script>
</body>
</html>
"""


def construir_dca(plantilla, css):
    """Arma public/dca.html con la navbar y el hero de la plantilla."""
    nav = re.search(r'(<nav class="nav">.*?</nav>)', plantilla, re.S).group(1)
    nav = nav.replace(' aria-current="page"', '')
    nav = nav.replace('<a href="/inversion-programada-dca">',
                      '<a href="/inversion-programada-dca" aria-current="page">')

    css = re.sub(r"/\*.*?\*/", "", css, flags=re.S)
    partes = []
    for sel, cuerpo in bloques(css):
        if sel == ":root" or sel.startswith(PREFIJOS_FUERA) or sel in {"*", ":focus-visible"}:
            partes.append(f"{sel}{{{cuerpo.strip()}}}")
        elif sel.startswith("@media"):
            dentro = [f"{s}{{{c.strip()}}}" for s, c in bloques(cuerpo)
                      if s.startswith(PREFIJOS_FUERA) or ".wrap" in s or ".nav" in s]
            if dentro:
                partes.append(sel + "{" + "".join(dentro) + "}")
    return SHELL_DCA.replace("__SHELL__", "\n".join(partes)).replace("__NAV__", nav)


def main():
    h_plantilla = PLANTILLA.read_text(encoding="utf-8")
    css = re.search(r"<style>(.*?)</style>", h_plantilla, re.S).group(1)
    js = re.search(r"<script>(.*?)</script>", h_plantilla, re.S).group(1)
    markup = re.search(r"<main>(.*?)</main>", h_plantilla, re.S).group(1).strip()

    # La fecha del pie la escribe el JS con lo que venga del endpoint.
    markup = markup.replace('<p class="termo-pie">', '<p class="termo-pie" id="termoPie">')
    markup = re.sub(r"Cierre del __FECHA_LARGA__\.", "", markup)

    if "__DATOS__" in markup or "__FECHA_LARGA__" in markup:
        print("ERROR: quedaron tokens del build estático en el markup", file=sys.stderr)
        sys.exit(1)

    DEST.mkdir(parents=True, exist_ok=True)
    (DEST / "estrategias.css").write_text(construir_css(css), encoding="utf-8")
    (DEST / "estrategias.js").write_text(construir_js(js, markup), encoding="utf-8")

    SALIDA_DCA.write_text(construir_dca(h_plantilla, css), encoding="utf-8")

    for p in (DEST / "estrategias.css", DEST / "estrategias.js", SALIDA_DCA):
        print(f"OK · {p.relative_to(RAIZ)} ({p.stat().st_size:,} bytes)")


if __name__ == "__main__":
    main()
