/*
 * dash-shim.js — implementação mínima da API `dash` usada pelo painel.
 * Lê os JSON de ./data, calcula os indicadores derivados (dash.calc) e redesenha
 * os gráficos quando os dados chegam, quando a largura muda ou quando um filtro muda.
 */
(function () {
  const ARQUIVOS = {
    sistema: 'data/sistema.json',
    perfil_horario: 'data/perfil_horario.json',
    faixas_carga: 'data/faixas_carga.json',
    linhas: 'data/linhas.json',
    linhas_hora: 'data/linhas_hora.json',
    tipologia_perfil: 'data/tipologia_perfil.json',
    tipologia_resumo: 'data/tipologia_resumo.json',
    calendario: 'data/calendario.json',
    quarto_hora: 'data/quarto_hora.json',
    grade: 'data/grade.json',
    regionais: 'data/regionais.json',
    carga_hist: 'data/carga_hist.json',
    ocupacao_sistema: 'data/ocupacao_sistema.json'
  };
  const PARAMS_PADRAO = { linha: '9250' };

  const estado = {};
  const calcs = {};
  const ouvintes = [];
  let params = { ...PARAMS_PADRAO };
  let agendado = false;

  function agendar() {
    if (agendado) return;
    agendado = true;
    requestAnimationFrame(() => {
      agendado = false;
      ouvintes.forEach(fn => { try { fn(); } catch (e) { console.error(e); } });
    });
  }

  function carregar(id) {
    estado[id] = { status: 'loading', data: [] };
    fetch(ARQUIVOS[id])
      .then(r => { if (!r.ok) throw new Error(r.status + ' ' + r.statusText); return r.json(); })
      .then(d => { estado[id] = { status: 'ok', data: d, columns: Object.keys(d[0] || {}), meta: [] }; agendar(); })
      .catch(e => { console.error(id, e); estado[id] = { status: 'error', data: [], message: String(e) }; agendar(); });
  }

  function data(id) {
    if (ARQUIVOS[id]) {
      if (!estado[id]) carregar(id);
      return estado[id];
    }
    const c = calcs[id];
    if (!c) return { status: 'missing', data: [] };
    if (c.resultado) return c.resultado;
    const entradas = c.inputs.map(data);
    if (entradas.some(x => x.status === 'error' || x.status === 'missing')) return { status: 'error', data: [] };
    if (entradas.some(x => x.status !== 'ok')) return { status: 'loading', data: [] };
    try {
      c.resultado = { status: 'ok', data: c.fn(...entradas.map(x => x.data)), meta: [] };
    } catch (e) {
      console.error('calc', id, e);
      c.resultado = { status: 'error', data: [], message: String(e) };
    }
    return c.resultado;
  }

  window.dash = {
    data,
    onData(fn) { ouvintes.push(fn); try { fn(); } catch (e) { console.error(e); } },
    calc(id, def) { calcs[id] = { ...def }; },
    loader() {},
    refresh() {},
    params() { return { ...params }; },
    setParams(p) { params = { ...params, ...p }; agendar(); },
    resetParams() { params = { ...PARAMS_PADRAO }; agendar(); },
    setLink(nome) { try { history.replaceState(null, '', '#' + nome); } catch (e) { /* ignora */ } },
    colors: [1, 2, 3, 4, 5, 6, 7, 8].map(i => `var(--series-${i})`)
  };

  let larguraAnterior = 0;
  window.addEventListener('DOMContentLoaded', () => {
    const raiz = document.getElementById('dash-root');
    new ResizeObserver(() => {
      const w = raiz.clientWidth;
      if (Math.abs(w - larguraAnterior) > 4) { larguraAnterior = w; agendar(); }
    }).observe(raiz);
    if (window.matchMedia) matchMedia('(prefers-color-scheme: dark)').addEventListener('change', agendar);
  });
})();
