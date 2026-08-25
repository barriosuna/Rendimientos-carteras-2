# Landing "Estrategias de inversión"

Página estática que se regenera sola cada mañana con los rendimientos de las
carteras modelo. Vive en Vercel, se construye desde este repo privado.

## Cómo funciona

```
GitHub Actions (9:20 AR, L-V)
  └─ calcula rendimientos  ──► escribe el Google Sheet   (esto ya existía)
  └─ landing/build.py      ──► escribe public/index.html (esto es nuevo)
  └─ git commit + push
        └─ Vercel detecta el push ──► publica
```

`build.py` cruza dos fuentes:

| Fuente | Qué aporta | Se actualiza |
|---|---|---|
| Google Sheet, hojas `carteras`, `aportes`, `control` | los números | solo, todas las mañanas |
| `landing/estrategias.json` | nombre, subtítulo, descripción, ícono, riesgo, plazo, orden | a mano, cuando cambie |
| `landing/activos.json` | nombre legible de cada ticker | a mano, al sumar un ticker |

## Archivos

```
landing/
  build.py           genera la página
  template.html      el HTML con los tokens __DATOS__ y __FECHA_LARGA__
  estrategias.json   metadata de las 9 carteras (editable a mano)
  activos.json       ticker → nombre legible
  requirements.txt
public/
  index.html         GENERADO — no editar a mano, se pisa en cada corrida
  assets/            logo y favicons
vercel.json
```

**Para cambiar el diseño se edita `template.html`, nunca `public/index.html`.**

## Secrets que necesita el workflow

| Secret | Valor |
|---|---|
| `SHEET_ID` | `11VeiUwK0cHVCH8lBM5pudPuMNNGjBlHfoiOVgDUbh0o` |
| `GOOGLE_SERVICE_ACCOUNT_JSON` | el JSON del service account, completo. Probablemente ya exista con otro nombre: reusalo y cambiá la referencia en el workflow. |

El service account solo necesita **lectura** sobre el Sheet.

## Freno de mano

Antes de escribir nada, `build.py` mira `Ultima rueda` en la hoja `control`:

- más de 5 días de atraso → sale con código 1, el job se corta, **no se publica**
- entre 3 y 5 días → publica, pero deja un aviso en el log del workflow

Es a propósito: si el cálculo se rompe, preferimos que la página se quede con
los números de ayer antes que publicar algo viejo sin decirlo. La fecha del dato
sale impresa en la página, abajo del termómetro.

## Correrlo a mano

```bash
pip install -r landing/requirements.txt
export SHEET_ID='11VeiUwK0cHVCH8lBM5pudPuMNNGjBlHfoiOVgDUbh0o'
export GOOGLE_SERVICE_ACCOUNT_JSON="$(cat ~/ruta/al/service-account.json)"
python landing/build.py
python -m http.server 8000 --directory public   # http://localhost:8000
```

## Pendiente: el gráfico de 12 meses

Hoy los nueve gráficos son barras por ventana, porque el Sheet no guarda serie
temporal. Si el workflow escribe una hoja `series` con el valor semanal base 100
de cada cartera, cargá ese array en el campo `serie` de cada estrategia dentro de
`build.py` y **la página dibuja la curva sola** — el código del gráfico de línea
ya está escrito en `template.html` y detecta el campo.
