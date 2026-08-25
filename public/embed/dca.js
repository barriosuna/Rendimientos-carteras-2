/*!
 * LB Finanzas — widget "Dollar Cost Average"
 * Se monta dentro de <div id="lb-dca"></div>.
 * La calculadora corre sobre la serie mensual real de /api/sp500.json.
 * Solo lee: no toca credenciales ni escribe nada.
 */
(function () {
  'use strict';

  var ENDPOINT = (document.currentScript && document.currentScript.dataset.endpoint)
    || 'https://TU-PROYECTO.vercel.app/api/sp500.json';

  // Aportes por mes según frecuencia. Ruedas hábiles ≈ 21/mes, semanas ≈ 4,33.
  var FREC = {
    diaria:  { etiqueta: 'Todos los días',   porMes: 21,   corta: 'por día' },
    semanal: { etiqueta: 'Todas las semanas', porMes: 4.33, corta: 'por semana' },
    mensual: { etiqueta: 'Todos los meses',  porMes: 1,    corta: 'por mes' }
  };

  var estado = { monto: 100, frecuencia: 'mensual', anios: 15 };
  var SERIE = null;
  var R = null;

  // ── formato ──────────────────────────────────────────────────────────────
  function usd(n) {
    return '$' + Math.round(n).toLocaleString('es-AR');
  }
  // Los montos del eje se abrevian para que no se corten contra el borde.
  function usdCorto(n) {
    if (n >= 1e6) return '$' + (n / 1e6).toFixed(n >= 1e7 ? 0 : 1).replace('.', ',') + 'M';
    if (n >= 1e3) return '$' + Math.round(n / 1e3) + 'k';
    return '$' + Math.round(n);
  }
  function pct(n) {
    return (n > 0 ? '+' : '') + n.toFixed(1).replace('.', ',') + '%';
  }

  // ── simulación ───────────────────────────────────────────────────────────
  // Compra un monto fijo el primer día de cada mes y lo mantiene hasta el final.
  // Precios reales: el retorno entre dos meses es el cociente de sus cierres.
  function simular(serie, montoMensual, meses) {
    var tramo = serie.slice(-(meses + 1));
    if (tramo.length < 2) return null;

    var unidades = 0, aportado = 0, puntos = [];
    for (var i = 0; i < tramo.length - 1; i++) {
      var precio = tramo[i].c;
      unidades += montoMensual / precio;
      aportado += montoMensual;
      puntos.push({
        f: tramo[i].f,
        aportado: aportado,
        valor: unidades * tramo[i + 1].c
      });
    }
    var ultimo = puntos[puntos.length - 1];
    var n = puntos.length;
    return {
      aportado: ultimo.aportado,
      valor: ultimo.valor,
      ganancia: ultimo.valor - ultimo.aportado,
      retorno: (ultimo.valor / ultimo.aportado - 1) * 100,
      anualizado: tirAnual(montoMensual, n, ultimo.valor),
      desde: tramo[0].f,
      hasta: tramo[tramo.length - 1].f,
      puntos: puntos
    };
  }

  // Rendimiento anualizado real de la plata aportada (TIR).
  // En DCA no sirve elevar valor/aportado a 1/años: cada aporte estuvo invertido
  // un tiempo distinto. Se resuelve la tasa mensual por biseccion y se anualiza.
  function tirAnual(cuota, n, valorFinal) {
    function vpn(r) {
      var v = -valorFinal / Math.pow(1 + r, n), t;
      for (t = 0; t < n; t++) v += cuota / Math.pow(1 + r, t);
      return v;
    }
    // Bracket acotado: fuera de este rango los terminos (1+r)^-n desbordan
    // y vpn() devuelve NaN, que rompia la biseccion.
    var lo = -0.25, hi = 0.25, flo = vpn(lo), fhi = vpn(hi), mid, fm, i;
    if (!isFinite(flo) || !isFinite(fhi) || flo * fhi > 0) return null;
    for (i = 0; i < 120; i++) {
      mid = (lo + hi) / 2;
      fm = vpn(mid);
      if (!isFinite(fm)) return null;
      if (flo * fm <= 0) { hi = mid; fhi = fm; } else { lo = mid; flo = fm; }
    }
    return (Math.pow(1 + mid, 12) - 1) * 100;
  }

  // ── gráficos ─────────────────────────────────────────────────────────────
  function grafEvolucion(r) {
    var W = 860, H = 300, P = { t: 16, r: 34, b: 30, l: 56 };
    var max = 0, i;
    for (i = 0; i < r.puntos.length; i++) max = Math.max(max, r.puntos[i].valor, r.puntos[i].aportado);
    max = max * 1.06 || 1;
    var n = r.puntos.length;
    var X = function (k) { return P.l + (n > 1 ? k / (n - 1) : 0) * (W - P.l - P.r); };
    var Y = function (v) { return P.t + (1 - v / max) * (H - P.t - P.b); };

    function linea(campo) {
      var d = '';
      for (var k = 0; k < n; k++) d += (k ? 'L' : 'M') + X(k).toFixed(1) + ' ' + Y(r.puntos[k][campo]).toFixed(1);
      return d;
    }
    var area = linea('valor') + 'L' + X(n - 1).toFixed(1) + ' ' + Y(0).toFixed(1) +
               'L' + X(0).toFixed(1) + ' ' + Y(0).toFixed(1) + 'Z';

    var ejes = '', pasos = 4;
    for (i = 0; i <= pasos; i++) {
      var v = max * i / pasos, y = Y(v);
      ejes += '<line x1="' + P.l + '" y1="' + y.toFixed(1) + '" x2="' + (W - P.r) +
              '" y2="' + y.toFixed(1) + '" stroke="#eeebf4"/>' +
              '<text x="' + (P.l - 10) + '" y="' + (y + 4).toFixed(1) +
              '" text-anchor="end" font-size="11" fill="#9990a8">' + usdCorto(v) + '</text>';
    }
    var etiq = '';
    [0, Math.floor((n - 1) / 2), n - 1].forEach(function (k) {
      if (k < 0 || k >= n) return;
      etiq += '<text x="' + X(k).toFixed(1) + '" y="' + (H - 8) +
              '" text-anchor="middle" font-size="11" fill="#9990a8">' +
              r.puntos[k].f.replace('-', '/') + '</text>';
    });

    return '<svg viewBox="0 0 ' + W + ' ' + H + '" role="img" aria-label="Evolución del valor de la cartera contra el total aportado">' +
      '<defs><linearGradient id="lbdca-g" x1="0" y1="0" x2="0" y2="1">' +
      '<stop offset="0%" stop-color="#8555ff" stop-opacity=".24"/>' +
      '<stop offset="100%" stop-color="#8555ff" stop-opacity="0"/></linearGradient></defs>' +
      ejes +
      '<path d="' + area + '" fill="url(#lbdca-g)"/>' +
      '<path d="' + linea('aportado') + '" fill="none" stroke="#9990a8" stroke-width="2" stroke-dasharray="5 4"/>' +
      '<path d="' + linea('valor') + '" fill="none" stroke="#522398" stroke-width="2.6" stroke-linejoin="round"/>' +
      etiq + '</svg>';
  }

  // Ilustra por qué el precio promedio de compra queda por debajo del promedio simple.
  function grafMecanismo() {
    var precios = [100, 80, 60, 80, 100];
    var aporte = 300;
    var W = 440, H = 210, P = { t: 22, r: 10, b: 42, l: 10 };
    var maxU = 0, i;
    for (i = 0; i < precios.length; i++) maxU = Math.max(maxU, aporte / precios[i]);
    var bw = (W - P.l - P.r) / precios.length, gap = bw * 0.34;
    var base = H - P.b;
    var barras = '';
    for (i = 0; i < precios.length; i++) {
      var u = aporte / precios[i];
      var h = (u / maxU) * (base - P.t);
      var x = P.l + i * bw + gap / 2;
      barras += '<rect x="' + x.toFixed(1) + '" y="' + (base - h).toFixed(1) +
        '" width="' + (bw - gap).toFixed(1) + '" height="' + h.toFixed(1) +
        '" rx="3" fill="' + (precios[i] < 100 ? '#8555ff' : '#c9b8ee') + '"/>' +
        '<text x="' + (x + (bw - gap) / 2).toFixed(1) + '" y="' + (base - h - 7).toFixed(1) +
        '" text-anchor="middle" font-size="11.5" font-weight="800" fill="#522398">' +
        u.toFixed(1) + '</text>' +
        '<text x="' + (x + (bw - gap) / 2).toFixed(1) + '" y="' + (base + 16) +
        '" text-anchor="middle" font-size="11" fill="#6b6678">$' + precios[i] + '</text>';
    }
    return '<svg viewBox="0 0 ' + W + ' ' + H + '" role="img" ' +
      'aria-label="Con el mismo aporte se compran más unidades cuando el precio baja">' +
      '<line x1="' + P.l + '" y1="' + base + '" x2="' + (W - P.r) + '" y2="' + base + '" stroke="#d8d3e2"/>' +
      barras +
      '<text x="' + (W / 2) + '" y="' + (H - 8) + '" text-anchor="middle" font-size="11" fill="#9990a8">' +
      'Precio del activo en cada aporte</text></svg>';
  }

  // ── render ───────────────────────────────────────────────────────────────
  function pintarResultado() {
    var f = FREC[estado.frecuencia];
    var mensual = estado.monto * f.porMes;
    var r = simular(SERIE, mensual, estado.anios * 12);
    if (!r) return;

    R.querySelector('#dcaAportado').textContent = usd(r.aportado);
    R.querySelector('#dcaValor').textContent = usd(r.valor);

    var g = R.querySelector('#dcaGanancia');
    g.textContent = usd(r.ganancia);
    g.className = 'kpi-v num ' + (r.ganancia >= 0 ? 'pos' : 'neg');
    R.querySelector('#dcaRetorno').textContent = pct(r.retorno) + ' sobre lo aportado';
    R.querySelector('#dcaEquiv').textContent =
      usd(mensual) + ' por mes · ' + r.desde.replace('-', '/') + ' a ' + r.hasta.replace('-', '/');

    R.querySelector('#dcaGraf').innerHTML = grafEvolucion(r);
  }

  function pintarEscenarios() {
    var filas = '';
    [5, 10, 15, 20, 25, 30].forEach(function (a) {
      var r = simular(SERIE, 100, a * 12);
      if (!r) return;
      filas += '<tr><td>' + a + ' años</td>' +
        '<td class="num">' + usd(r.aportado) + '</td>' +
        '<td class="num">' + usd(r.valor) + '</td>' +
        '<td class="num ' + (r.ganancia >= 0 ? 'pos' : 'neg') + '">' + usd(r.ganancia) + '</td>' +
        '<td class="num">' + (r.anualizado === null ? '—' : r.anualizado.toFixed(1).replace('.', ',') + '%') + '</td></tr>';
    });
    R.querySelector('#dcaEscenarios').innerHTML = filas;
    R.querySelector('#dcaEscHasta').textContent = SERIE[SERIE.length - 1].f.replace('-', '/');
  }

  function conectar() {
    var input = R.querySelector('#dcaMonto');
    input.addEventListener('input', function () {
      var v = parseFloat(input.value);
      estado.monto = (isFinite(v) && v > 0) ? Math.min(v, 1000000) : 0;
      pintarResultado();
    });

    R.querySelectorAll('.segm button').forEach(function (b) {
      b.addEventListener('click', function () {
        R.querySelectorAll('.segm button').forEach(function (x) { x.setAttribute('aria-pressed', 'false'); });
        b.setAttribute('aria-pressed', 'true');
        estado.frecuencia = b.dataset.f;
        pintarResultado();
      });
    });

    var rango = R.querySelector('#dcaAnios');
    rango.addEventListener('input', function () {
      estado.anios = parseInt(rango.value, 10);
      R.querySelector('#dcaAniosTxt').textContent = estado.anios;
      pintarResultado();
    });
  }

  // El contenido explicativo no depende de datos, asi que se dibuja siempre.
  // Solo la calculadora y la tabla de escenarios esperan al endpoint.
  function dibujarEstructura() {
    R.innerHTML = MARKUP
      .replace('__MAX_ANIOS__', 30)
      .replace('__ANIOS__', estado.anios)
      .replace('__ANIOS_TXT__', estado.anios)
      .replace(/__DESDE__/g, '…')
      .replace(/__HASTA__/g, '…');
    R.querySelector('#dcaMecGraf').innerHTML = grafMecanismo();
  }

  function conDatos(payload) {
    SERIE = payload.serie;
    var maxAnios = Math.min(30, Math.floor((SERIE.length - 1) / 12));
    if (estado.anios > maxAnios) estado.anios = maxAnios;

    var rango = R.querySelector('#dcaAnios');
    rango.max = maxAnios;
    rango.value = estado.anios;
    R.querySelector('#dcaAniosTxt').textContent = estado.anios;

    var desde = SERIE[0].f.replace('-', '/');
    var hasta = SERIE[SERIE.length - 1].f.replace('-', '/');
    R.querySelectorAll('.periodo').forEach(function (e) {
      e.textContent = desde + ' y ' + hasta;
    });

    conectar();
    pintarResultado();
    pintarEscenarios();
  }

  function sinDatos(err) {
    var c = R.querySelector('#dcaCalc');
    if (c) {
      c.innerHTML = '<p class="calc-cargando">La calculadora no está disponible en este ' +
        'momento. Probá recargar la página en un rato.</p>';
    }
    var t = R.querySelector('#dcaEscenarios');
    if (t) {
      t.innerHTML = '<tr><td colspan="5" style="text-align:center;color:#9990a8;' +
        'font-weight:500;padding:26px 16px">Sin datos disponibles por ahora.</td></tr>';
    }
    if (window.console) console.error('[lb-dca]', err);
  }

  function arrancar() {
    R = document.getElementById('lb-dca');
    if (!R) return;
    dibujarEstructura();
    R.setAttribute('aria-busy', 'true');
    fetch(ENDPOINT, { cache: 'no-cache' })
      .then(function (r) {
        if (!r.ok) throw new Error('HTTP ' + r.status);
        return r.json();
      })
      .then(function (d) {
        if (!d || !Array.isArray(d.serie) || d.serie.length < 24) {
          throw new Error('serie insuficiente');
        }
        conDatos(d);
      })
      .catch(sinDatos)
      .then(function () { R.removeAttribute('aria-busy'); });
  }

  var MARKUP = [
'<section class="wrap">',
'  <p class="eyebrow">ESTRATEGIA · DCA</p>',
'  <h2 class="sec-h">Invertir siempre lo mismo, pase lo que pase</h2>',
'  <p class="sec-b">El Dollar Cost Average — también llamado compra programada o aporte periódico — consiste en poner un monto fijo en el mismo activo cada tanto, sin mirar el precio. Es la forma más simple de sacarte de encima la pregunta de cuándo entrar.</p>',
'  <div class="prosa">',
'    <p>La lógica es la que ya conocés de cualquier ahorro automático: todos los meses sale la misma plata de tu cuenta y compra. Si ese mes el activo está barato, tu aporte compra más; si está caro, compra menos. <strong>No tenés que acertar el piso del mercado, porque comprás en todos los precios, incluidos los mínimos.</strong></p>',
'    <p>Lo que resuelve no es solamente matemático. La razón más frecuente por la que alguien termina con menos plata de la que podría no es haber elegido mal el activo: es haber esperado el momento ideal, haber entrado tarde y haber vendido en la peor semana. <strong>Automatizar la compra saca la decisión emocional del medio.</strong></p>',
'    <p>La alternativa es el <em>lump sum</em>: poner todo de una. En un mercado con tendencia alcista de largo plazo, el lump sum gana en la mayoría de los períodos, y eso hay que decirlo. Pero es una comparación que solo tiene sentido si ya tenés el capital junto. <strong>Si tus aportes salen del sueldo y no de un capital que ya está, la comparación no aplica: no estás eligiendo entre DCA y lump sum, estás eligiendo entre DCA y no invertir.</strong></p>',
'  </div>',
'</section>',

'<section class="wrap">',
'  <h2 class="sec-h">Probá con datos reales</h2>',
'  <p class="sec-b">Cuánto habrías tenido si hubieras aportado un monto fijo al S&amp;P 500. Corre sobre los precios mensuales reales del índice, con dividendos reinvertidos, entre <span class=\"periodo\">…</span>.</p>',
'  <div class="calc" id="dcaCalc">',
'    <div class="calc-ctrl">',
'      <div class="campo"><label for="dcaMonto">Monto de cada aporte (USD)</label>',
'        <div class="monto"><span>$</span><input type="number" id="dcaMonto" value="100" min="1" step="10" inputmode="decimal"></div></div>',
'      <div class="campo"><label id="dcaFrecLabel">Cada cuánto</label>',
'        <div class="segm" role="group" aria-labelledby="dcaFrecLabel">',
'          <button type="button" data-f="diaria" aria-pressed="false">Día</button>',
'          <button type="button" data-f="semanal" aria-pressed="false">Semana</button>',
'          <button type="button" data-f="mensual" aria-pressed="true">Mes</button>',
'        </div></div>',
'      <div class="campo"><label for="dcaAnios">Durante cuánto tiempo</label>',
'        <div class="anios"><b id="dcaAniosTxt">__ANIOS_TXT__</b><span>años</span></div>',
'        <input type="range" id="dcaAnios" min="1" max="__MAX_ANIOS__" value="__ANIOS__"></div>',
'    </div>',
'    <div class="kpis">',
'      <div class="kpi"><span class="kpi-l">Pusiste</span><span class="kpi-v num" id="dcaAportado">—</span>',
'        <span class="kpi-s" id="dcaEquiv">—</span></div>',
'      <div class="kpi"><span class="kpi-l">Terminabas con</span><span class="kpi-v num" id="dcaValor">—</span>',
'        <span class="kpi-s">valor de la cartera</span></div>',
'      <div class="kpi destacado"><span class="kpi-l">Diferencia</span><span class="kpi-v num" id="dcaGanancia">—</span>',
'        <span class="kpi-s" id="dcaRetorno">—</span></div>',
'    </div>',
'    <div class="calc-graf">',
'      <div id="dcaGraf"></div>',
'      <div class="leyenda">',
'        <span><i style="background:#522398"></i>Valor de la cartera</span>',
'        <span><i style="background:#9990a8"></i>Total aportado</span>',
'      </div>',
'    </div>',
'    <p class="calc-pie"><strong>Cómo está calculado.</strong> La simulación compra al cierre de cada mes con los precios reales del índice, ajustados por dividendos y splits, y mantiene todo hasta el final del período. Los aportes diarios y semanales se agregan al equivalente mensual (21 ruedas y 4,33 semanas por mes): en el largo plazo la frecuencia casi no mueve el resultado, lo que manda es cuánto ponés por mes y durante cuánto tiempo. No se descuentan comisiones, impuestos ni inflación. Los rendimientos pasados no garantizan rendimientos futuros.</p>',
'  </div>',
'</section>',

'<section class="wrap">',
'  <h2 class="sec-h">Los números de referencia</h2>',
'  <p class="sec-b">Aportando USD 100 por mes al S&amp;P 500, con corte en <span id="dcaEscHasta">—</span>.</p>',
'  <div class="tabla-caja"><table>',
'    <thead><tr><th scope="col">Si hubieras empezado hace</th><th scope="col">Pusiste</th>',
'      <th scope="col">Terminabas con</th><th scope="col">Diferencia</th><th scope="col">Anualizado</th></tr></thead>',
'    <tbody id="dcaEscenarios"></tbody>',
'  </table></div>',
'</section>',

'<section class="wrap">',
'  <h2 class="sec-h">Por qué el promedio te queda a favor</h2>',
'  <p class="sec-b">El efecto no es una intuición: es aritmética. Comprás más unidades justo cuando el activo está barato, así que los precios bajos pesan más en tu promedio.</p>',
'  <div class="mec">',
'    <div class="mec-txt">',
'      <p>Mirá qué pasa con un aporte fijo de $300 sobre un activo que baja y vuelve a subir hasta el mismo precio del principio. El promedio simple de los cinco precios es $84, pero vos pagaste $80,4 por unidad.</p>',
'      <p>La diferencia no es un truco: comprás más cantidad justo cuando está barato, así que los precios bajos pesan más en tu promedio. Es el efecto del promedio armónico, y juega siempre a favor del que aporta parejo.</p>',
'      <p><strong>Ojo con lo que esto sí significa: reduce el costo promedio, no el riesgo del activo.</strong></p>',
'    </div>',
'    <div class="mec-graf">',
'      <div id="dcaMecGraf"></div>',
'      <p class="mec-pie">Unidades compradas con un aporte fijo de $300 en cada momento. Las barras violetas son los meses en que el precio estaba por debajo del inicial.</p>',
'    </div>',
'  </div>',
'</section>',

'<section class="wrap">',
'  <h2 class="sec-h">Qué resuelve y qué no</h2>',
'  <p class="sec-b">Cuatro cosas para tener claras antes de automatizar nada.</p>',
'  <div class="props">',
'    <div class="prop"><span class="prop-n">01</span><h3>Diversifica el momento de entrada</h3>',
'      <p>Repartís la compra en decenas de precios distintos en vez de jugarte a uno. Dejás de necesitar una respuesta a la pregunta de si hoy está caro.</p></div>',
'    <div class="prop"><span class="prop-n">02</span><h3>Baja el costo promedio</h3>',
'      <p>El precio promedio al que comprás tiende a quedar por debajo del promedio simple del activo en el período, porque comprás más unidades cuando está barato.</p></div>',
'    <div class="prop"><span class="prop-n">03</span><h3>Convierte el ahorro en costumbre</h3>',
'      <p>Una orden automática no se saltea un mes porque el noticiero está feo. Y quedarse invertido durante las caídas es, en los hechos, la parte más difícil de invertir.</p></div>',
'    <div class="prop ojo"><span class="prop-n">04</span><h3>No te salva de un activo malo</h3>',
'      <p>Si lo que comprás cae y no se recupera, aportar todos los meses solo te hace perder más ordenadamente. El DCA es una técnica sobre <em>cuándo</em> comprar, no sobre <em>qué</em> comprar.</p></div>',
'  </div>',
'</section>',

'<section class="wrap">',
'  <h2 class="sec-h">Cómo lo automatizás en LB</h2>',
'  <p class="sec-b">Cuatro pasos, una sola vez. Después corre solo.</p>',
'  <div class="pasos">',
'    <div class="paso"><div class="paso-n">1</div><div><h3>Elegí qué comprar</h3>',
'      <p>Puede ser una de nuestras estrategias de inversión o un activo suelto. Para seguir al S&amp;P 500, los más usados son <code>SPY</code>, <code>VOO</code> e <code>IVV</code>.</p></div></div>',
'    <div class="paso"><div class="paso-n">2</div><div><h3>Entrá a Automatizaciones</h3>',
'      <p>En la pantalla del activo o de la cartera, tocá <code>Automatizar compra</code>. Ahí definís monto, frecuencia y de dónde sale la plata.</p></div></div>',
'    <div class="paso"><div class="paso-n">3</div><div><h3>Poné monto y frecuencia</h3>',
'      <p>Diaria, semanal, quincenal o mensual. Elegí la que se acomode a cuándo cobrás: es más importante que el aporte no te falte a que la frecuencia sea la óptima.</p></div></div>',
'    <div class="paso"><div class="paso-n">4</div><div><h3>Confirmá y olvidate</h3>',
'      <p>La orden se ejecuta sola. Revisala una o dos veces al año para subir el monto si te subió el ingreso; tocarla más seguido suele salir peor que no tocarla.</p></div></div>',
'  </div>',
'</section>',

'<section class="wrap">',
'  <div class="cierre">',
'    <h3>¿Sobre cuál lo aplicás?</h3>',
'    <p>El DCA resuelve el cuándo. El qué sigue siendo la decisión importante, y depende de en cuánto tiempo vas a necesitar la plata y de cuánta caída aguantás sin vender.</p>',
'    <a class="btn" href="/estrategias-de-inversion">Ver las estrategias</a>',
'  </div>',
'</section>',

'<section class="wrap" style="padding-top:26px">',
'  <div class="nota">',
'    <h4>Sobre estos números</h4>',
'    <p>Los datos son los cierres mensuales del S&amp;P 500 a través de su ETF de referencia, ajustados por dividendos y splits. La serie se actualiza sola todos los días hábiles junto con el resto de nuestros datos de mercado.</p>',
'    <p>Las simulaciones son ejercicios históricos, no proyecciones. El período que cubren incluye la crisis de 2008 y la caída de 2020, pero también uno de los tramos alcistas más largos de la historia del índice: un período distinto habría dado otro resultado. <strong>Los rendimientos pasados no garantizan rendimientos futuros.</strong></p>',
'  </div>',
'</section>'
  ].join('\n');

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', arrancar);
  } else {
    arrancar();
  }
})();
