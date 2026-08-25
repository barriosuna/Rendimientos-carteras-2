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

    base = (
        f"{CONTENEDOR}{{font-family:'Plus Jakarta Sans',-apple-system,"
        'BlinkMacSystemFont,"Segoe UI",Arial,sans-serif;font-size:16px;'
        "line-height:1.6;color:#2c2b2e;-webkit-font-smoothing:antialiased}\n"
        f"{CONTENEDOR} *{{box-sizing:border-box}}\n"
        f"{CONTENEDOR} a{{color:var(--violeta)}}\n"
        f"{CONTENEDOR} :focus-visible{{outline:3px solid var(--acento);"
        "outline-offset:3px;border-radius:6px}\n"
        "@media (prefers-reduced-motion:reduce){"
        + CONTENEDOR + " *{animation:none!important;transition:none!important}}\n"
    )
    return "/*! LB Finanzas — widget Estrategias de inversión. GENERADO: no editar. */\n" + base + "\n".join(out) + "\n"


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


def main():
    h = PLANTILLA.read_text(encoding="utf-8")
    css = re.search(r"<style>(.*?)</style>", h, re.S).group(1)
    js = re.search(r"<script>(.*?)</script>", h, re.S).group(1)
    markup = re.search(r"<main>(.*?)</main>", h, re.S).group(1).strip()

    # La fecha del pie la escribe el JS con lo que venga del endpoint.
    markup = markup.replace('<p class="termo-pie">', '<p class="termo-pie" id="termoPie">')
    markup = re.sub(r"Cierre del __FECHA_LARGA__\.", "", markup)

    if "__DATOS__" in markup or "__FECHA_LARGA__" in markup:
        print("ERROR: quedaron tokens del build estático en el markup", file=sys.stderr)
        sys.exit(1)

    DEST.mkdir(parents=True, exist_ok=True)
    (DEST / "estrategias.css").write_text(construir_css(css), encoding="utf-8")
    (DEST / "estrategias.js").write_text(construir_js(js, markup), encoding="utf-8")

    for f in ("estrategias.css", "estrategias.js"):
        p = DEST / f
        print(f"OK · {p.relative_to(RAIZ)} ({p.stat().st_size:,} bytes)")


if __name__ == "__main__":
    main()
