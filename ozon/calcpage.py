"""HTML-страница калькулятора прибыли (переиспользует тему дашборда)."""

from __future__ import annotations

import html
import json

from . import report
from .util import fmt_int, fmt_money, to_float

CALC_CSS = """
.controls{display:grid;grid-template-columns:repeat(auto-fit,minmax(250px,1fr));gap:16px}
.control{background:var(--soft);border:1px solid var(--border);border-radius:12px;padding:12px 14px}
.control .name{font-size:12px;color:var(--muted);text-transform:uppercase;letter-spacing:.03em;margin-bottom:8px}
.control .row{display:flex;gap:10px;align-items:center}
.control input[type=range]{flex:1;accent-color:var(--accent);min-width:80px}
.control input[type=number]{width:88px;border:1px solid var(--border);background:var(--card);color:var(--text);
  border-radius:8px;padding:6px 8px;font:inherit;font-size:13.5px;text-align:right}
.control .out{font-weight:700;font-variant-numeric:tabular-nums;min-width:64px;text-align:right}
.control .hintline{margin-top:8px}
.check{display:flex;gap:8px;align-items:center;font-size:13px;color:var(--muted);margin-top:8px}
.check input{accent-color:var(--accent)}
.calc-table{min-width:0}
.calc-table td.name{max-width:420px}
.calc-table tbody tr{cursor:default}
.neg{color:var(--bad)}
.pos{color:var(--good)}
.sens{cursor:pointer}
.sens.active td{background:var(--hover)}
.btn{border:1px solid var(--border);background:var(--card);color:var(--text);border-radius:10px;
  padding:7px 12px;font:inherit;font-size:13px;cursor:pointer}
.btn:hover{border-color:var(--accent);color:var(--accent)}
.bar{height:6px;border-radius:3px;background:var(--border);overflow:hidden;margin-top:6px}
.bar i{display:block;height:100%;background:var(--accent)}
"""

CALC_JS = r"""
(function(){
  const SKUS = window.__SKUS__ || [];
  const BASE = window.__BASE__ || {ad_rate:0, has_costs:false};
  const state = {price:0, cost:0, overrideCost:false, adRate:BASE.ad_rate*100, elasticity:-1.5, sort:'revenue'};

  const money = v => new Intl.NumberFormat('ru-RU',{maximumFractionDigits:0}).format(Math.round(v))+' ₽';
  const int = v => new Intl.NumberFormat('ru-RU',{maximumFractionDigits:0}).format(Math.round(v));
  const pct = v => (v*100).toFixed(1).replace('.',',')+'%';

  function costFor(s){
    if(state.overrideCost && state.cost>0) return state.cost;
    return s.has_cost ? s.cost : state.cost;
  }

  function compute(delta){
    const k = 1 + delta/100;
    const ad = state.adRate/100;
    let revenue=0, units=0, profit=0;
    const rows = SKUS.map(function(s){
      const price = s.price*k;
      const u = Math.max(0, s.units*(1 + (delta/100)*state.elasticity));
      const cost = costFor(s);
      const unitProfit = price*(1 - s.commission - ad) - s.fee_fixed - cost;
      const total = unitProfit*u;
      revenue += price*u; units += u; profit += total;
      return {s:s, price:price, units:u, unitProfit:unitProfit, profit:total};
    });
    return {rows:rows, revenue:revenue, units:units, profit:profit, margin: revenue? profit/revenue : 0};
  }

  const base = compute(0);
  const baseBySku = {};
  base.rows.forEach(function(r){ baseBySku[r.s.sku] = r; });

  function setKpi(id, value, baseValue, fmt){
    const el = document.getElementById(id);
    if(!el) return;
    el.querySelector('.value').textContent = fmt(value);
    const d = el.querySelector('.delta');
    if(!baseValue){ d.textContent=''; d.className='delta flat'; return; }
    const diff = (value-baseValue)/Math.abs(baseValue);
    d.textContent = (diff>=0?'+':'')+(diff*100).toFixed(1).replace('.',',')+'% к базе';
    d.className = 'delta ' + (Math.abs(diff)<0.0005 ? 'flat' : (diff>0?'good':'bad'));
  }

  function renderSensitivity(cur){
    const body = document.getElementById('sens');
    if(!body) return;
    let out = '';
    [-10,-5,0,5,10].forEach(function(d){
      const r = compute(d);
      const diff = base.profit ? (r.profit-base.profit)/Math.abs(base.profit)*100 : 0;
      const active = Math.abs(d-state.price)<0.01 ? ' active' : '';
      out += '<tr class="sens'+active+'" data-d="'+d+'"><td>'+d+'%</td>'
        + '<td class="num">'+money(r.profit)+'</td>'
        + '<td class="num '+(diff>=0?'pos':'neg')+'">'+(diff>=0?'+':'')+diff.toFixed(1).replace('.',',')+'%</td>'
        + '<td class="num">'+int(r.units)+'</td></tr>';
    });
    body.innerHTML = out;
    body.querySelectorAll('tr.sens').forEach(function(tr){
      tr.addEventListener('click', function(){ applyDelta(parseFloat(tr.dataset.d)); });
    });
  }

  function renderTable(cur){
    const body = document.getElementById('rows');
    if(!body) return;
    let rows = cur.rows.slice();
    if(state.sort==='profit') rows.sort(function(a,b){ return b.profit-a.profit; });
    else if(state.sort==='unit') rows.sort(function(a,b){ return b.unitProfit-a.unitProfit; });
    else rows.sort(function(a,b){ return b.s.revenue-a.s.revenue; });

    let html = '';
    rows.forEach(function(r){
      const b = baseBySku[r.s.sku];
      const diff = (b && b.profit) ? (r.profit-b.profit)/Math.abs(b.profit)*100 : 0;
      const margin = r.price ? r.unitProfit/r.price : 0;
      html += '<tr>'
        + "<td class='name'><a href='https://www.ozon.ru/product/"+r.s.sku+"/' target='_blank' rel='noopener'>"
        + r.s.name + '</a>' + (r.s.offer_id ? "<div class='tiny'>"+r.s.offer_id+'</div>' : '') + '</td>'
        + '<td class="num">'+money(r.price)+'</td>'
        + '<td class="num">'+int(r.units)+'</td>'
        + '<td class="num">'+money(r.s.cost)+'</td>'
        + '<td class="num '+(r.unitProfit<0?'neg':'')+'">'+money(r.unitProfit)+'</td>'
        + '<td class="num '+(r.profit<0?'neg':'')+'">'+money(r.profit)+'</td>'
        + '<td class="num">'+pct(margin)+'</td>'
        + '<td class="num '+(diff>=0?'pos':'neg')+'">'+(diff>=0?'+':'')+diff.toFixed(1).replace('.',',')+'%</td>'
        + '</tr>';
    });
    body.innerHTML = html;
  }

  function render(){
    const cur = compute(state.price);
    setKpi('kpi-revenue', cur.revenue, base.revenue, money);
    setKpi('kpi-profit', cur.profit, base.profit, money);
    setKpi('kpi-margin', cur.margin, base.margin, pct);
    setKpi('kpi-units', cur.units, base.units, int);
    renderSensitivity(cur);
    renderTable(cur);
  }

  function applyDelta(d){
    state.price = d;
    const range = document.getElementById('price');
    const num = document.getElementById('price-num');
    if(range) range.value = d;
    if(num) num.value = d;
    const out = document.getElementById('price-out');
    if(out) out.textContent = (d>0?'+':'')+d+'%';
    render();
  }

  function bindRange(id, numId, outId, onChange, format){
    const range = document.getElementById(id);
    const num = numId ? document.getElementById(numId) : null;
    const out = outId ? document.getElementById(outId) : null;
    function update(value, from){
      if(isNaN(value)) return;
      if(range) range.value = value;
      if(num && from!=='num') num.value = value;
      if(out) out.textContent = format ? format(value) : value;
      onChange(value);
      render();
    }
    if(range) range.addEventListener('input', function(){ update(parseFloat(range.value),'range'); });
    if(num) num.addEventListener('input', function(){ update(parseFloat(num.value),'num'); });
    return update;
  }

  bindRange('price','price-num','price-out', v=>{state.price=v;}, v=>(v>0?'+':'')+v+'%');
  bindRange('elasticity','elasticity-num','elasticity-out', v=>{state.elasticity=v;}, v=>v.toFixed(1).replace('.',','));
  bindRange('ad','ad-num','ad-out', v=>{state.adRate=v;}, v=>v.toFixed(1).replace('.',',')+'%');
  bindRange('cost','cost-num',null, v=>{state.cost=v;});

  const override = document.getElementById('override');
  if(override) override.addEventListener('change', function(){ state.overrideCost = override.checked; render(); });

  const sort = document.getElementById('sort');
  if(sort) sort.addEventListener('change', function(){ state.sort = sort.value; render(); });

  const reset = document.getElementById('reset');
  if(reset) reset.addEventListener('click', function(){
    state.price=0; state.cost=0; state.overrideCost=false;
    state.adRate = BASE.ad_rate*100; state.elasticity=-1.5; state.sort='revenue';
    if(override) override.checked=false;
    if(sort) sort.value='revenue';
    applyDelta(0);
    const e=document.getElementById('elasticity'); if(e) e.value=-1.5;
    const en=document.getElementById('elasticity-num'); if(en) en.value=-1.5;
    const eo=document.getElementById('elasticity-out'); if(eo) eo.textContent='-1,5';
    const a=document.getElementById('ad'); if(a) a.value=state.adRate;
    const an=document.getElementById('ad-num'); if(an) an.value=state.adRate.toFixed(1);
    const ao=document.getElementById('ad-out'); if(ao) ao.textContent=state.adRate.toFixed(1).replace('.',',')+'%';
    const c=document.getElementById('cost'); if(c) c.value=0;
    const cn=document.getElementById('cost-num'); if(cn) cn.value=0;
    render();
  });

  render();
})();
"""

PRELOAD_JS = (
    "<script>try{if(localStorage.getItem('ozon-theme')==='light')"
    "{document.documentElement.setAttribute('data-theme','light');}}catch(e){}</script>"
)


def _esc(value) -> str:
    return html.escape(str(value if value is not None else ""))


def render(model: dict) -> str:
    meta = model.get("meta") or {}
    period = model.get("period") or {}
    totals = model.get("totals") or {}
    mode = "live" if meta.get("mode") == "live" else "demo"
    badge = (
        '<span class="badge live">live</span>'
        if mode == "live"
        else '<span class="badge">демо-данные</span>'
    )
    ad_default = round(to_float(model.get("ad_rate")) * 100, 1)

    data_js = (
        "<script>"
        f"window.__SKUS__={json.dumps(model.get('skus') or [], ensure_ascii=False).replace('</', '<\\/')};"
        f"window.__BASE__={json.dumps({'ad_rate': model.get('ad_rate', 0), 'has_costs': model.get('has_costs', False)}, ensure_ascii=False)};"
        "</script>"
    )

    parts = [
        '<!doctype html><html lang="ru" data-theme="dark"><head><meta charset="utf-8">',
        '<meta name="viewport" content="width=device-width,initial-scale=1">',
        PRELOAD_JS,
        f"<title>Калькулятор прибыли — Ozon</title>",
        f"<style>{report.STYLE}{CALC_CSS}</style></head><body><div class='wrap'>",
        "<header class='top'><div>"
        f"<h1>Калькулятор прибыли {badge}</h1>"
        f"<div class='sub'>База: {_esc(period.get('from', ''))} — {_esc(period.get('to', ''))} · "
        f"{len(model.get('skus') or [])} товаров с продажами</div>"
        "</div>"
        "<div class='top-right'>"
        "<button id='theme-toggle' class='theme-toggle' type='button'>☀️ Светлая</button>"
        f"<div class='sub'>Сформировано {_esc(meta.get('generated_at', ''))}</div>"
        "</div></header>",
    ]

    if mode != "live":
        parts.append(
            "<div class='warnbox'><b>Демонстрационные данные.</b> "
            "Для расчёта на своих продажах выполните <code>py run.py calc</code> "
            "после сбора данных (<code>py run.py all --days 30</code>).</div>"
        )

    parts.append(
        "<div class='panel'><h2>Параметры <span class='hint'>двигайте — таблица и KPI пересчитаются</span></h2>"
        "<div class='controls'>"
        "<div class='control'><div class='name'>Цена, %</div><div class='row'>"
        "<input id='price' type='range' min='-30' max='30' step='0.5' value='0'>"
        "<input id='price-num' type='number' min='-30' max='30' step='0.5' value='0'>"
        "<span class='out' id='price-out'>0%</span></div>"
        "<div class='hintline'>сдвиг цены ко всем товарам</div></div>"
        "<div class='control'><div class='name'>Себестоимость, ₽/шт</div><div class='row'>"
        "<input id='cost' type='range' min='0' max='3000' step='10' value='0'>"
        "<input id='cost-num' type='number' min='0' step='10' value='0'>"
        "</div><label class='check'><input id='override' type='checkbox'> применить ко всем товарам</label>"
        "<div class='hintline'>пусто — берём из costs.csv, если он есть</div></div>"
        f"<div class='control'><div class='name'>Реклама, % от выручки</div><div class='row'>"
        f"<input id='ad' type='range' min='0' max='30' step='0.5' value='{ad_default}'>"
        f"<input id='ad-num' type='number' min='0' max='30' step='0.5' value='{ad_default}'>"
        f"<span class='out' id='ad-out'>{str(ad_default).replace('.', ',')}%</span></div>"
        "<div class='hintline'>базовое значение — из фактических начислений</div></div>"
        "<div class='control'><div class='name'>Эластичность спроса</div><div class='row'>"
        "<input id='elasticity' type='range' min='-3' max='0' step='0.1' value='-1.5'>"
        "<input id='elasticity-num' type='number' min='-3' max='0' step='0.1' value='-1.5'>"
        "<span class='out' id='elasticity-out'>-1,5</span></div>"
        "<div class='hintline'>−1,5 = при росте цены на 10% заказы падают на 15%</div></div>"
        "</div></div>"
    )

    parts.append(
        "<div class='cards'>"
        "<div class='card' id='kpi-revenue'><div class='label'>Выручка</div>"
        f"<div class='value'>{fmt_money(totals.get('revenue', 0))}</div><div class='delta flat'></div></div>"
        "<div class='card' id='kpi-profit'><div class='label'>Прибыль</div>"
        f"<div class='value'>{fmt_money(totals.get('profit', 0))}</div><div class='delta flat'></div></div>"
        "<div class='card' id='kpi-margin'><div class='label'>Маржа</div>"
        f"<div class='value'>{round((totals.get('profit', 0) / totals.get('revenue', 1)) * 100, 1)}%</div>"
        "<div class='delta flat'></div></div>"
        "<div class='card' id='kpi-units'><div class='label'>Заказы, шт</div>"
        f"<div class='value'>{fmt_int(totals.get('units', 0))}</div><div class='delta flat'></div></div>"
        "</div>"
    )

    parts.append(
        "<div class='panel'><h2>Чувствительность к цене <span class='hint'>нажмите на строку, чтобы применить</span></h2>"
        "<div class='table-scroll'><table class='calc-table'><thead><tr>"
        "<th>Цена</th><th>Прибыль</th><th>Δ к базе</th><th>Заказы</th>"
        "</tr></thead><tbody id='sens'></tbody></table></div></div>"
    )

    parts.append(
        "<div class='panel'><h2>Товары</h2>"
        "<div class='toolbar'>"
        "<div class='tiny'>Колонки: цена, заказы, себестоимость, прибыль на единицу, прибыль за период, маржа. "
        "Красным — убыточные.</div>"
        "<select id='sort' class='btn'><option value='revenue'>по выручке</option>"
        "<option value='profit'>по прибыли</option><option value='unit'>по прибыли на единицу</option></select>"
        "</div>"
        "<div class='table-scroll'><table class='calc-table'><thead><tr>"
        "<th>Товар</th><th>Цена</th><th>Заказы</th><th>Себест.</th>"
        "<th>Прибыль/шт</th><th>Прибыль</th><th>Маржа</th><th>Δ к базе</th>"
        "</tr></thead><tbody id='rows'></tbody></table></div></div>"
    )

    parts.append(
        "<footer>Модель: прибыль = заказы × (цена × (1 − комиссия − реклама) − фикс. издержки − себестоимость). "
        "Комиссия и фиксированные издержки взяты из фактических начислений Ozon; "
        "реклама — отдельным параметром.</footer>"
    )

    parts.append(
        "</div>"
        + data_js
        + f"<script>{report.SCRIPT}</script>"
        + f"<script>{CALC_JS}</script>"
        + "</body></html>"
    )
    return "".join(parts)
