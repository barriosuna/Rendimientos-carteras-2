/*!
 * LB Finanzas — widget "Estrategias de inversión"
 * GENERADO por landing/build_embed.py. No editar a mano: editar template.html.
 *
 * Se monta dentro de <div id="lb-estrategias"></div> y se dibuja con los datos
 * de /api/estrategias.json. Solo lee: no toca credenciales ni escribe nada.
 */
(function () {
  'use strict';

  var MARKUP = "<section class=\"wrap\" id=\"comparar\">\n  <h2 class=\"sec-h\">Cómo viene cada una</h2>\n  <p class=\"sec-b\">Elegí una ventana de tiempo y mirá las nueve ordenadas de mejor a peor. Tocá cualquiera para ir a su ficha.</p>\n  <div class=\"termo\">\n    <div class=\"termo-top\">\n      <div>\n        <h3>El termómetro</h3>\n        <p id=\"termoSub\">Rendimiento en los últimos 12 meses</p>\n      </div>\n      <div class=\"ventanas\" role=\"tablist\" aria-label=\"Ventana de tiempo\">\n        <button role=\"tab\" data-v=\"0\">En el día</button>\n        <button role=\"tab\" data-v=\"1\">En el mes</button>\n        <button role=\"tab\" data-v=\"2\">3 meses</button>\n        <button role=\"tab\" data-v=\"3\">En el año</button>\n        <button role=\"tab\" data-v=\"4\" aria-selected=\"true\">12 meses</button>\n      </div>\n    </div>\n    <div class=\"barras\" id=\"barras\"></div>\n    <p class=\"termo-pie\" id=\"termoPie\">Rendimiento total en dólares, punto a punto, con dividendos reinvertidos. </p>\n  </div>\n</section>\n\n<section class=\"wrap\" id=\"tabla\">\n  <h2 class=\"sec-h\">Todas las ventanas, todas las carteras</h2>\n  <p class=\"sec-b\">Tocá el encabezado de cualquier columna para reordenar.</p>\n  <div class=\"tabla-caja\">\n    <table id=\"tablaComp\">\n      <thead>\n        <tr>\n          <th class=\"ord\" data-c=\"-1\" scope=\"col\">Estrategia</th>\n          <th class=\"ord\" data-c=\"0\" scope=\"col\">En el día</th>\n          <th class=\"ord\" data-c=\"1\" scope=\"col\">En el mes</th>\n          <th class=\"ord\" data-c=\"2\" scope=\"col\">3 meses</th>\n          <th class=\"ord\" data-c=\"3\" scope=\"col\">En el año</th>\n          <th class=\"ord\" data-c=\"4\" aria-sort=\"descending\" scope=\"col\">12 meses</th>\n        </tr>\n      </thead>\n      <tbody id=\"tablaBody\"></tbody>\n    </table>\n  </div>\n</section>\n\n<section class=\"wrap\" id=\"estrategias\">\n  <h2 class=\"sec-h\">Las nueve estrategias</h2>\n  <p class=\"sec-b\">Cada ficha tiene el rendimiento en las cinco ventanas, el gráfico de los últimos doce meses, los cinco activos de mayor peso y para quién está pensada. En todas podés invertir de una vez o programar un monto fijo que entre solo.</p>\n  <div class=\"filtros\" id=\"filtros\">\n    <button data-f=\"todas\" aria-pressed=\"true\">Todas</button>\n    <button data-f=\"conservative\" aria-pressed=\"false\">Conservadoras</button>\n    <button data-f=\"moderate\" aria-pressed=\"false\">Moderadas</button>\n    <button data-f=\"aggressive\" aria-pressed=\"false\">Agresivas</button>\n  </div>\n  <div class=\"cards\" id=\"cards\"></div>\n</section>\n\n<section class=\"wrap\">\n  <div class=\"cierre\">\n    <h3>¿Cuál va con vos?</h3>\n    <p>La estrategia que más rindió no es necesariamente la que te conviene. Depende de en cuánto tiempo vas a necesitar la plata y de cuánto podés ver caer tu cartera sin vender. Y una vez elegida, no hace falta que estés encima: programás un monto fijo por día, por semana o por mes y listo.</p>\n      <a class=\"btn\" href=\"/inversion-programada-dca\">Cómo funciona la inversión programada</a>\n  </div>\n</section>\n\n<section class=\"wrap\" id=\"metodologia\" style=\"padding-top:26px\">\n  <div class=\"metodo\">\n    <h4>Cómo calculamos estos números</h4>\n    <p>Precios ajustados por dividendos y splits. El rendimiento de cada cartera es el promedio ponderado del rendimiento de sus activos, con los pesos normalizados al inicio de cada ventana — es decir, asumiendo rebalanceo. Todo expresado en dólares.</p>\n    <p><strong>“En el día” es la variación de la última rueda cerrada contra la anterior</strong>, no la jornada en curso. Las carteras modelo son ejemplos de asignación construidos por el equipo de Research de LB Finanzas: no son un producto administrado y no incluyen comisiones, impuestos ni costos de transacción.</p>\n    <p>Los rendimientos pasados no garantizan rendimientos futuros.</p>\n  </div>\n</section>";

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

    const VENTANAS = ['En el día','En el mes','Últimos 3 meses','En el año (YTD)','Últimos 12 meses'];
    const VENT_CORTA = ['Día','Mes','3M','Año','12M'];

    const fmt = n => (n>0?'+':'') + n.toFixed(2).replace('.',',') + '%';
    const cls = n => n>0?'pos':(n<0?'neg':'');
    const clsT = n => n>0?'v-pos':(n<0?'v-neg':'v-cero');

    /* ---------- TERMÓMETRO ---------- */
    let ventanaActiva = 4;

    function pintarBarras(){
      const cont = R.querySelector('#barras');
      const orden = [...ESTRATEGIAS].sort((a,b)=>b.ret[ventanaActiva]-a.ret[ventanaActiva]);
      const vals = orden.map(e=>e.ret[ventanaActiva]);
      const min = Math.min(0,...vals), max = Math.max(0,...vals);
      const span = (max-min) || 1;
      const cero = (0-min)/span*100;

      cont.innerHTML = orden.map(e=>{
        const v = e.ret[ventanaActiva];
        const x = (v-min)/span*100;
        const left = Math.min(cero,x), w = Math.max(Math.abs(x-cero),0.6);
        const color = v>=0 ? 'var(--verde)' : '#ff8fa8';
        return `<a class="barra" href="#${e.id}">
          <span class="barra-n">${e.nombre}</span>
          <span class="barra-riel">
            <span class="barra-cero" style="left:${cero}%"></span>
            <span class="barra-f" style="left:${left}%;width:${w}%;background:${color}"></span>
          </span>
          <span class="barra-v num ${cls(v)}">${fmt(v)}</span>
        </a>`;
      }).join('');

      R.querySelector('#termoSub').textContent = 'Rendimiento ' +
        (ventanaActiva===0?'en el día':ventanaActiva===1?'en el mes':ventanaActiva===2?'en los últimos 3 meses':ventanaActiva===3?'en lo que va del año':'en los últimos 12 meses');
    }

    R.querySelectorAll('.ventanas button').forEach(b=>{
      b.addEventListener('click',()=>{
        R.querySelectorAll('.ventanas button').forEach(x=>x.setAttribute('aria-selected','false'));
        b.setAttribute('aria-selected','true');
        ventanaActiva = +b.dataset.v;
        pintarBarras();
      });
    });
    pintarBarras();

    /* ---------- TABLA ---------- */
    let ordCol = 4, ordDesc = true;

    function pintarTabla(){
      const orden = [...ESTRATEGIAS].sort((a,b)=>{
        if(ordCol===-1) return ordDesc ? b.nombre.localeCompare(a.nombre) : a.nombre.localeCompare(b.nombre);
        return ordDesc ? b.ret[ordCol]-a.ret[ordCol] : a.ret[ordCol]-b.ret[ordCol];
      });
      R.querySelector('#tablaBody').innerHTML = orden.map(e=>
        `<tr><td class="nom"><a href="#${e.id}">${e.nombre}</a><small>${e.riesgo} · ${e.plazo.toLowerCase()}</small></td>` +
        e.ret.map(v=>`<td class="num ${clsT(v)}">${fmt(v)}</td>`).join('') + '</tr>'
      ).join('');
    }

    R.querySelectorAll('#tablaComp th.ord').forEach(th=>{
      th.addEventListener('click',()=>{
        const c = +th.dataset.c;
        if(c===ordCol){ ordDesc = !ordDesc; } else { ordCol = c; ordDesc = true; }
        R.querySelectorAll('#tablaComp th.ord').forEach(x=>x.removeAttribute('aria-sort'));
        th.setAttribute('aria-sort', ordDesc?'descending':'ascending');
        pintarTabla();
      });
    });
    pintarTabla();

    /* ---------- GRÁFICO ----------
       Si la estrategia trae `serie` (array de {f:'YYYY-MM-DD', v:<base 100>}),
       dibuja la curva de 12 meses. Si no, cae al gráfico de las cinco ventanas.
       Cargar `serie` no requiere ningún otro cambio en la página.            */

    function grafSerie(e){
      const W=420,H=200,P={t:14,r:10,b:24,l:38};
      const vs=e.serie.map(p=>p.v), min=Math.min(...vs), max=Math.max(...vs);
      const pad=(max-min)*0.12||1, lo=min-pad, hi=max+pad;
      const X=i=>P.l+i/(e.serie.length-1)*(W-P.l-P.r);
      const Y=v=>P.t+(hi-v)/(hi-lo)*(H-P.t-P.b);
      const d=e.serie.map((p,i)=>(i?'L':'M')+X(i).toFixed(1)+' '+Y(p.v).toFixed(1)).join(' ');
      const area=d+` L${X(e.serie.length-1).toFixed(1)} ${H-P.b} L${P.l} ${H-P.b} Z`;
      const sube=vs[vs.length-1]>=vs[0], col=sube?'#12855a':'#e0466b';
      return `<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="Evolución de ${e.nombre} en los últimos 12 meses">
        <defs><linearGradient id="g-${e.id}" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stop-color="${col}" stop-opacity=".22"/><stop offset="100%" stop-color="${col}" stop-opacity="0"/>
        </linearGradient></defs>
        <line x1="${P.l}" y1="${Y(100)}" x2="${W-P.r}" y2="${Y(100)}" stroke="#e7e3ee" stroke-dasharray="3 3"/>
        <path d="${area}" fill="url(#g-${e.id})"/>
        <path d="${d}" fill="none" stroke="${col}" stroke-width="2.2" stroke-linejoin="round" stroke-linecap="round"/>
        <text x="4" y="${Y(hi).toFixed(1)+8}" font-size="10" fill="#9990a8">${hi.toFixed(0)}</text>
        <text x="4" y="${Y(lo).toFixed(1)}" font-size="10" fill="#9990a8">${lo.toFixed(0)}</text>
      </svg>`;
    }

    function grafVentanas(e){
      const W=420,H=214,P={t:18,r:8,b:48,l:8};
      const vs=e.ret, min=Math.min(0,...vs), max=Math.max(0,...vs), span=(max-min)||1;
      const bw=(W-P.l-P.r)/vs.length, gap=bw*0.32;
      const Y=v=>P.t+(max-v)/span*(H-P.t-P.b);
      const y0=Y(0);
      return `<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="Rendimiento de ${e.nombre} por ventana de tiempo">
        <line x1="${P.l}" y1="${y0.toFixed(1)}" x2="${W-P.r}" y2="${y0.toFixed(1)}" stroke="#d8d3e2"/>
        ${vs.map((v,i)=>{
          const x=P.l+i*bw+gap/2, w=bw-gap;
          const y=Math.min(y0,Y(v)), h=Math.max(Math.abs(Y(v)-y0),1.5);
          const col = i===4 ? '#8555ff' : (v>=0?'#c9b8ee':'#f2b9c8');
          const ty = v>=0 ? y-7 : y+h+14;
          return `<rect x="${x.toFixed(1)}" y="${y.toFixed(1)}" width="${w.toFixed(1)}" height="${h.toFixed(1)}" rx="3" fill="${col}"/>
            <text x="${(x+w/2).toFixed(1)}" y="${ty.toFixed(1)}" text-anchor="middle" font-size="11" font-weight="800" fill="${i===4?'#522398':'#6b6678'}">${fmt(v)}</text>
            <text x="${(x+w/2).toFixed(1)}" y="${H-10}" text-anchor="middle" font-size="11" font-weight="${i===4?700:500}" fill="#9990a8">${VENT_CORTA[i]}</text>`;
        }).join('')}
      </svg>`;
    }

    /* ---------- CARDS ---------- */
    R.querySelector('#cards').innerHTML = ESTRATEGIAS.map(e=>{
      const kpis = e.ret.map((v,i)=>
        `<div class="kpi${i===4?' destacado':''}">
           <span class="kpi-l">${VENT_CORTA[i]}</span>
           <span class="kpi-v num ${clsT(v)}">${fmt(v)}</span>
         </div>`).join('');

      const filas = e.activos.map(a=>
        `<tr>
          <td class="tk"><b>${a.t}</b>${a.nombre?`<small>${a.nombre}</small>`:''}</td>
          <td class="num">${a.peso.toString().replace('.',',')}%</td>
          <td class="num ${a.r12m===null?'sd':clsT(a.r12m)}">${a.r12m===null?'s/d':fmt(a.r12m)}</td>
        </tr>`).join('');

      const resto = e.totalActivos>5 ? `Se muestran los 5 activos de mayor peso de un total de ${e.totalActivos}.` : `La cartera tiene ${e.totalActivos} activos: están todos.`;

      const [primero,...siguientes] = e.descripcion;
      const desc = `<p>${primero}</p>` + (siguientes.length
        ? `<details><summary>Seguir leyendo</summary>${siguientes.map(p=>`<p>${p}</p>`).join('')}</details>`
        : '');

      const tieneSerie = Array.isArray(e.serie) && e.serie.length>1;

      return `<article class="card" id="${e.id}" data-riesgo="${e.riesgoKey}">
        <div class="card-h">
          <div class="card-ico">${e.icono?`<img src="${e.icono}" alt="" loading="lazy">`:''}</div>
          <div class="card-tit">
            <h3>${e.nombre}</h3>
            <p>${e.subtitulo}</p>
            <div class="chips">
              <span class="chip r-${e.riesgoKey}">Riesgo ${e.riesgo.toLowerCase()}</span>
              <span class="chip">${e.plazo}</span>
              <span class="chip">${e.totalActivos} activos</span>
            </div>
          </div>
        </div>
        <div class="kpis">${kpis}</div>
        <div class="card-b">
          <div class="graf">
            <p class="bloque-t">Últimos 12 meses</p>
            <p class="bloque-s">${tieneSerie ? 'Base 100 al inicio del período.' : 'Rendimiento acumulado en cada ventana. La barra violeta son los 12 meses.'}</p>
            ${tieneSerie ? grafSerie(e) : grafVentanas(e)}
          </div>
          <div class="act">
            <p class="bloque-t">Top 5 activos</p>
            <p class="bloque-s">Por peso dentro de la cartera.</p>
            <table>
              <thead><tr><th scope="col">Activo</th><th scope="col">Peso</th><th scope="col">12M</th></tr></thead>
              <tbody>${filas}</tbody>
            </table>
            <p class="act-pie">${resto}</p>
          </div>
        </div>
        <div class="desc">${desc}</div>
        <div class="prog">
          <div class="prog-txt">
            <p>🔁 En LB podés poner un monto fijo en <b>${e.nombre}</b> y que se invierta solo, sin que tengas que acordarte. <a href="/inversion-programada-dca">Por qué conviene invertir así</a></p>
          </div>
          <div class="frec"><span>Todos los días</span><span>Todas las semanas</span><span>Todos los meses</span></div>
        </div>
      </article>`;
    }).join('');

    /* ---------- FILTROS ---------- */
    R.querySelectorAll('#filtros button').forEach(b=>{
      b.addEventListener('click',()=>{
        R.querySelectorAll('#filtros button').forEach(x=>x.setAttribute('aria-pressed','false'));
        b.setAttribute('aria-pressed','true');
        const f = b.dataset.f;
        R.querySelectorAll('.card').forEach(c=>{
          c.hidden = !(f==='todas' || c.dataset.riesgo===f);
        });
      });
    });
  }

  function fallar(R, err) {
    R.innerHTML = '<p style="padding:32px 24px;font-family:\'Plus Jakarta Sans\',Arial,'
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
