"""Сборка HTML-дашборда и CSV-выгрузок."""

from __future__ import annotations

import csv
import html
from pathlib import Path

from . import store, svgchart
from .util import fmt_int, fmt_money, fmt_pct, to_float, to_int

STYLE = """
:root{
  color-scheme: dark;
  --bg:#0a0e17; --card:#121827; --soft:#0e1421; --border:#232c3d; --border-strong:#33405a;
  --text:#e8ecf4; --text-strong:#f4f7fc; --muted:#8a94a9;
  --accent:#5ea0ff; --good:#34d399; --bad:#f87171; --warn:#fbbf24;
  --grid:#1e2739; --axis:#7b869c; --hover:#172032;
  --radius:14px; --shadow:0 1px 2px rgba(0,0,0,.5),0 1px 3px rgba(0,0,0,.35);
  --red-bg:#3a1618; --red-fg:#fca5a5;
  --green-bg:#0e2f25; --green-fg:#6ee7b7;
  --blue-bg:#12233f; --blue-fg:#93c5fd;
  --yellow-bg:#33260a; --yellow-fg:#fcd34d;
  --gray-bg:#1b2231; --gray-fg:#9aa4b8;
  --badge-bg:#33260a; --badge-fg:#fcd34d;
  --badge-live-bg:#0e2f25; --badge-live-fg:#6ee7b7;
  --warnbox-bg:#2a2007; --warnbox-border:#6b4e0a; --warnbox-fg:#fcd34d;
}
html[data-theme="light"]{
  color-scheme: light;
  --bg:#f6f7fb; --card:#ffffff; --soft:#f9fafb; --border:#e6e8f0; --border-strong:#cbd5e1;
  --text:#111827; --text-strong:#111827; --muted:#6b7280;
  --accent:#2563eb; --good:#059669; --bad:#dc2626; --warn:#d97706;
  --grid:#eef0f6; --axis:#6b7280; --hover:#f8fafc;
  --shadow:0 1px 2px rgba(16,24,40,.06),0 1px 3px rgba(16,24,40,.08);
  --red-bg:#fee2e2; --red-fg:#991b1b;
  --green-bg:#dcfce7; --green-fg:#166534;
  --blue-bg:#dbeafe; --blue-fg:#1e40af;
  --yellow-bg:#fef3c7; --yellow-fg:#92400e;
  --gray-bg:#f3f4f6; --gray-fg:#6b7280;
  --badge-bg:#fef3c7; --badge-fg:#92400e;
  --badge-live-bg:#dcfce7; --badge-live-fg:#166534;
  --warnbox-bg:#fffbeb; --warnbox-border:#fde68a; --warnbox-fg:#92400e;
}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--text);
  font:15px/1.45 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,"Helvetica Neue",Arial,sans-serif;
  transition:background .15s ease,color .15s ease}
.wrap{max-width:1240px;margin:0 auto;padding:28px 20px 60px}
header.top{display:flex;flex-wrap:wrap;gap:12px;align-items:flex-end;justify-content:space-between;margin-bottom:22px}
.top-right{display:flex;flex-direction:column;align-items:flex-end;gap:8px;text-align:right}
h1{font-size:26px;margin:0 0 4px;letter-spacing:-.02em}
.sub{color:var(--muted);font-size:13px}
.badge{display:inline-block;padding:3px 9px;border-radius:999px;font-size:11px;font-weight:700;
  letter-spacing:.04em;text-transform:uppercase;background:var(--badge-bg);color:var(--badge-fg);vertical-align:middle}
.badge.live{background:var(--badge-live-bg);color:var(--badge-live-fg)}
.theme-toggle{display:inline-flex;align-items:center;gap:6px;border:1px solid var(--border);
  background:var(--card);color:var(--text);border-radius:10px;padding:7px 11px;font-size:13px;
  cursor:pointer;font-family:inherit}
.theme-toggle:hover{border-color:var(--accent);color:var(--accent)}
.cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(172px,1fr));gap:12px;margin-bottom:18px}
.card{background:var(--card);border:1px solid var(--border);border-radius:var(--radius);padding:14px 16px;box-shadow:var(--shadow)}
.card .label{font-size:12px;color:var(--muted);text-transform:uppercase;letter-spacing:.03em}
.card .value{font-size:22px;font-weight:700;margin-top:4px;letter-spacing:-.02em;font-variant-numeric:tabular-nums}
.card .delta{font-size:12.5px;margin-top:4px;font-weight:600}
.card .delta.good{color:var(--good)} .card .delta.bad{color:var(--bad)} .card .delta.flat{color:var(--muted)}
.panel{background:var(--card);border:1px solid var(--border);border-radius:var(--radius);padding:18px;margin-bottom:18px;box-shadow:var(--shadow)}
.panel h2{font-size:16px;margin:0 0 14px;letter-spacing:-.01em}
.panel h2 .hint{font-weight:400;color:var(--muted);font-size:13px;margin-left:8px}
.grid2{display:grid;grid-template-columns:1.45fr 1fr;gap:18px}
@media (max-width:900px){.grid2{grid-template-columns:1fr}}
.chart{width:100%;height:auto;display:block;overflow:visible}
.grid{stroke:var(--grid);stroke-width:1}
.axis{fill:var(--axis);font-size:11px;font-variant-numeric:tabular-nums}
.axis.label{fill:var(--text);font-size:12px}
.axis.value{fill:var(--text-strong);font-size:11.5px;font-weight:600}
.dot{fill:var(--card)}
.alerts{display:flex;flex-direction:column;gap:8px;max-height:340px;overflow:auto;padding-right:4px}
.alert{display:flex;gap:10px;align-items:flex-start;border:1px solid var(--border);border-left-width:4px;
  border-radius:10px;padding:9px 12px;background:var(--soft)}
.alert.red{border-left-color:var(--bad)} .alert.yellow{border-left-color:var(--warn)} .alert.blue{border-left-color:var(--accent)}
.alert .t{font-weight:600;font-size:13.5px}
.alert .d{color:var(--muted);font-size:12.5px}
.toolbar{display:flex;gap:10px;align-items:center;justify-content:space-between;flex-wrap:wrap;margin-bottom:12px}
input[type=search]{border:1px solid var(--border);border-radius:10px;padding:9px 12px;font-size:14px;
  min-width:260px;background:var(--card);color:var(--text);outline:none;font-family:inherit}
input[type=search]::placeholder{color:var(--muted)}
input[type=search]:focus{border-color:var(--accent);box-shadow:0 0 0 3px rgba(94,160,255,.18)}
.table-scroll{overflow:auto;border:1px solid var(--border);border-radius:12px}
table{border-collapse:separate;border-spacing:0;width:100%;font-size:13.5px;min-width:1000px}
th,td{padding:9px 10px;text-align:right;white-space:nowrap;border-bottom:1px solid var(--border)}
th{position:sticky;top:0;background:var(--soft);z-index:1;font-size:12px;color:var(--muted);
  text-transform:uppercase;letter-spacing:.03em;cursor:pointer;user-select:none}
th:hover{color:var(--text)}
th:first-child,td:first-child{text-align:left}
td.name{text-align:left;max-width:340px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
td.name a{color:var(--text);text-decoration:none;border-bottom:1px dotted var(--border-strong)}
td.name a:hover{color:var(--accent)}
tr:hover td{background:var(--hover)}
.num{font-variant-numeric:tabular-nums}
.abc{display:inline-block;width:20px;height:20px;line-height:20px;text-align:center;border-radius:6px;font-weight:700;font-size:11px}
.abc.A{background:var(--green-bg);color:var(--green-fg)}
.abc.B{background:var(--blue-bg);color:var(--blue-fg)}
.abc.C{background:var(--gray-bg);color:var(--gray-fg)}
.pill{display:inline-block;padding:2px 8px;border-radius:999px;font-size:11.5px;font-weight:600}
.pill.red{background:var(--red-bg);color:var(--red-fg)}
.pill.yellow{background:var(--yellow-bg);color:var(--yellow-fg)}
.pill.green{background:var(--green-bg);color:var(--green-fg)}
.pill.blue{background:var(--blue-bg);color:var(--blue-fg)}
.pill.gray{background:var(--gray-bg);color:var(--gray-fg)}
.warnbox{border:1px solid var(--warnbox-border);background:var(--warnbox-bg);color:var(--warnbox-fg);
  border-radius:12px;padding:12px 14px;margin-bottom:16px;font-size:13.5px}
.warnbox ul{margin:6px 0 0;padding-left:18px}
footer{color:var(--muted);font-size:12px;text-align:center;margin-top:26px}
.tiny{color:var(--muted);font-size:12px}
details summary{cursor:pointer;color:var(--muted);font-size:13px}
::-webkit-scrollbar{width:10px;height:10px}
::-webkit-scrollbar-track{background:var(--soft)}
::-webkit-scrollbar-thumb{background:var(--border-strong);border-radius:6px}
@media print{
  :root{
    color-scheme:light; --bg:#fff; --card:#fff; --soft:#fff; --border:#ddd; --border-strong:#bbb;
    --text:#111; --text-strong:#000; --muted:#555; --grid:#e5e5e5; --axis:#666; --hover:#fff;
    --shadow:none;
  }
  .theme-toggle{display:none}
  body{background:#fff}
}
"""

SCRIPT = """
(function(){
  var root=document.documentElement;
  var toggle=document.getElementById('theme-toggle');
  function applyTheme(theme){
    root.setAttribute('data-theme',theme);
    if(toggle){toggle.textContent=theme==='dark'?'☀️ Светлая':'🌙 Тёмная';}
    try{localStorage.setItem('ozon-theme',theme);}catch(e){}
  }
  var saved=null;
  try{saved=localStorage.getItem('ozon-theme');}catch(e){}
  applyTheme(saved||'dark');
  if(toggle){
    toggle.addEventListener('click',function(){
      applyTheme(root.getAttribute('data-theme')==='dark'?'light':'dark');
    });
  }
  var search=document.getElementById('search');
  if(search){
    search.addEventListener('input',function(){
      var q=this.value.toLowerCase().trim();
      document.querySelectorAll('#sku-table tbody tr').forEach(function(tr){
        tr.style.display=tr.textContent.toLowerCase().indexOf(q)>=0?'':'none';
      });
    });
  }
  var table=document.getElementById('sku-table');
  if(table){
    table.querySelectorAll('th').forEach(function(th,idx){
      th.addEventListener('click',function(){
        var tbody=table.querySelector('tbody');
        var rows=Array.prototype.slice.call(tbody.querySelectorAll('tr'));
        var asc=th.dataset.asc!=='1';
        table.querySelectorAll('th').forEach(function(h){delete h.dataset.asc;});
        th.dataset.asc=asc?'1':'0';
        rows.sort(function(a,b){
          var av=a.children[idx].dataset.v, bv=b.children[idx].dataset.v;
          var an=parseFloat(av), bn=parseFloat(bv);
          if(!isNaN(an)&&!isNaN(bn)) return asc?an-bn:bn-an;
          return asc?String(av).localeCompare(String(bv)):String(bv).localeCompare(String(av));
        });
        rows.forEach(function(r){tbody.appendChild(r);});
      });
    });
  }
})();
"""


def _esc(value) -> str:
    return html.escape(str(value if value is not None else ""))


def render(data: dict) -> str:
    meta = data.get("meta") or {}
    kpi = data.get("kpi") or {}
    prev = data.get("prev") or {}
    period = data.get("period") or {}
    finance = data.get("finance") or {}
    alerts = data.get("alerts") or []
    skus = data.get("sku") or []
    daily = data.get("daily") or []

    mode = "live" if meta.get("mode") == "live" else "demo"
    badge = (
        '<span class="badge live">live</span>'
        if mode == "live"
        else '<span class="badge">демо-данные</span>'
    )

    parts: list[str] = [
        '<!doctype html><html lang="ru" data-theme="dark"><head><meta charset="utf-8">',
        '<meta name="viewport" content="width=device-width,initial-scale=1">',
        "<script>try{if(localStorage.getItem('ozon-theme')==='light'){document.documentElement.setAttribute('data-theme','light');}}catch(e){}</script>",
        f"<title>Ozon — аналитика {_esc(period.get('from', ''))} … {_esc(period.get('to', ''))}</title>",
        f"<style>{STYLE}</style></head><body><div class='wrap'>",
    ]

    parts.append(
        "<header class='top'><div>"
        f"<h1>Аналитика Ozon {badge}</h1>"
        f"<div class='sub'>Период {_esc(period.get('from', ''))} — {_esc(period.get('to', ''))} "
        f"· сравнение с {_esc((data.get('prev_period') or {}).get('from', ''))} — {_esc((data.get('prev_period') or {}).get('to', ''))}</div>"
        "</div>"
        "<div class='top-right'>"
        "<button id='theme-toggle' class='theme-toggle' type='button'>☀️ Светлая</button>"
        f"<div class='sub'>Сформировано {_esc(meta.get('generated_at', ''))}"
        f"<br>Client-Id {_esc(meta.get('client_id_masked', '—'))} · запросов к API: {_esc(meta.get('api_calls', 0))}</div>"
        "</div></header>"
    )

    if mode != "live":
        parts.append(
            "<div class='warnbox'><b>Это демонстрационные данные.</b> "
            "К вашим продажам они отношения не имеют. Реальные цифры появятся после "
            "<code>py run.py all --days 30</code> (нужен ключ в <code>.env</code>) — "
            "файл <code>out/dashboard.html</code>.</div>"
        )

    warnings = meta.get("warnings") or []
    if warnings:
        items = "".join(f"<li>{_esc(w)}</li>" for w in warnings)
        parts.append(f"<div class='warnbox'><b>Часть данных не загружена</b><ul>{items}</ul></div>")

    parts.append(_kpi_cards(kpi, prev, data))
    parts.append(_charts(data, daily, skus))
    if finance.get("has_data"):
        parts.append(_finance_panel(finance))
    if alerts:
        parts.append(_alerts_panel(alerts))
    parts.append(
        _sku_panel(
            skus,
            data.get("has_costs"),
            data.get("has_settlement"),
            data.get("has_funnel"),
            data.get("has_returns", True),
        )
    )
    parts.append(
        "<footer>Данные: Ozon Seller API (/v1/analytics/data, /v1/analytics/stocks, "
        "/v1/finance/accrual/by-day). Маржа считается по фактическим начислениям на SKU; "
        "для полной картины добавьте себестоимость в costs.csv.</footer>"
    )
    parts.append(f"</div><script>{SCRIPT}</script></body></html>")
    return "".join(parts)


def _delta(cur, prev_value, *, invert: bool = False, currency: bool = False, points: bool = False) -> str:
    cur_f, prev_f = to_float(cur), to_float(prev_value)
    if prev_f == 0:
        return "<div class='delta flat'>—</div>"
    if points:
        diff = cur_f - prev_f
        text = f"{'+' if diff > 0 else ''}{diff * 100:.1f} п.п."
        good = diff <= 0 if invert else diff >= 0
    else:
        diff = (cur_f - prev_f) / abs(prev_f)
        text = f"{'+' if diff > 0 else ''}{diff * 100:.1f}%"
        good = diff <= 0 if invert else diff >= 0
    cls = "flat" if diff == 0 else ("good" if good else "bad")
    return f"<div class='delta {cls}'>{text} к пред. периоду</div>"


def _card(label: str, value: str, delta_html: str = "") -> str:
    return f"<div class='card'><div class='label'>{_esc(label)}</div><div class='value'>{value}</div>{delta_html}</div>"


def _kpi_cards(kpi: dict, prev: dict, data: dict) -> str:
    has_funnel = data.get("has_funnel")
    has_returns = data.get("has_returns", True)
    cards = [
        _card("Выручка", fmt_money(kpi.get("revenue", 0)), _delta(kpi.get("revenue"), prev.get("revenue"))),
        _card("Заказано, шт", fmt_int(kpi.get("units", 0)), _delta(kpi.get("units"), prev.get("units"))),
        _card("Средний чек", fmt_money(kpi.get("avg_price", 0)), _delta(kpi.get("avg_price"), prev.get("avg_price"))),
        _card(
            "Сессии",
            fmt_int(kpi.get("sessions", 0)) if has_funnel else "—",
            _delta(kpi.get("sessions"), prev.get("sessions")) if has_funnel else "",
        ),
        _card(
            "Конверсия в корзину",
            fmt_pct(kpi.get("conv", 0)) if has_funnel else "—",
            _delta(kpi.get("conv"), prev.get("conv"), points=True) if has_funnel else "",
        ),
        _card(
            "Доля возвратов",
            fmt_pct(kpi.get("return_rate", 0)) if has_returns else "—",
            _delta(kpi.get("return_rate"), prev.get("return_rate"), invert=True, points=True)
            if has_returns
            else "",
        ),
    ]
    return "<div class='cards'>" + "".join(cards) + "</div>"


def _charts(data: dict, daily: list[dict], skus: list[dict]) -> str:
    revenue_points = [(str(d.get("day", "")), to_float(d.get("revenue"))) for d in daily]
    units_points = [(str(d.get("day", "")), to_float(d.get("units"))) for d in daily]
    top = sorted(skus, key=lambda r: r["revenue"], reverse=True)[:10]
    top_items = [(str(r["name"]), r["revenue"]) for r in top]

    kpi = data.get("kpi") or {}
    funnel_steps = [
        ("Сессии", to_float(kpi.get("sessions"))),
        ("В корзину", to_float(kpi.get("tocarts"))),
        ("Заказы, шт", to_float(kpi.get("units"))),
    ]

    if data.get("has_funnel"):
        funnel_html = svgchart.funnel(funnel_steps)
    else:
        funnel_html = (
            "<div class='tiny'>Ozon отключил метрики воронки "
            "(<code>session_view</code>, <code>hits_view</code>, <code>hits_tocart</code>) — "
            "сессии и конверсия в корзину больше не отдаются через API. "
            "В демо-отчёте воронка остаётся для примера.</div>"
        )

    return (
        "<div class='panel'><h2>Выручка по дням <span class='hint'>₽</span></h2>"
        + svgchart.line_chart(revenue_points, value_label="выручка по дням")
        + "</div>"
        "<div class='grid2'>"
        "<div class='panel'><h2>Товары-локомотивы <span class='hint'>топ-10 по выручке</span></h2>"
        + svgchart.bar_chart_h(top_items)
        + "</div>"
        "<div class='panel'><h2>Воронка <span class='hint'>сессии → корзина → заказ</span></h2>"
        + funnel_html
        + "</div></div>"
        "<div class='panel'><h2>Заказы по дням <span class='hint'>шт</span></h2>"
        + svgchart.line_chart(units_points, height=180, color="var(--good)", value_label="заказы по дням")
        + "</div>"
    )


def _finance_panel(finance: dict) -> str:
    values = finance.get("values") or {}
    order = [
        ("accruals_for_sale", "Начислено за продажи"),
        ("sale_commission", "Комиссия Ozon"),
        ("processing_and_delivery", "Обработка и доставка"),
        ("refunds_and_cancellations", "Возвраты и отмены"),
        ("services_amount", "Доп. услуги"),
        ("compensation_amount", "Компенсации"),
    ]
    cards = []
    for key, label in order:
        value = values.get(key, 0)
        cls = "good" if value > 0 else ("bad" if value < 0 else "flat")
        cards.append(
            f"<div class='card'><div class='label'>{_esc(label)}</div>"
            f"<div class='value' style='color:var(--{'good' if value > 0 else 'bad' if value < 0 else 'muted'})'>"
            f"{fmt_money(value)}</div>"
            f"<div class='delta {cls}'>по транзакциям за период</div></div>"
        )
    payout = finance.get("payout", 0)
    cards.append(
        f"<div class='card'><div class='label'>К выплате (оценка)</div>"
        f"<div class='value'>{fmt_money(payout)}</div>"
        f"<div class='delta'>сумма всех начислений и удержаний</div></div>"
    )
    commission = fmt_pct(finance.get("commission_rate", 0))
    delivery = fmt_money(finance.get("delivery_per_unit", 0))
    return (
        "<div class='panel'><h2>Финансы <span class='hint'>"
        f"средняя комиссия {commission} · доставка ≈ {delivery} на единицу</span></h2>"
        "<div class='cards'>" + "".join(cards) + "</div></div>"
    )


def _alerts_panel(alerts: list[dict]) -> str:
    counts = {"red": 0, "yellow": 0, "blue": 0}
    for alert in alerts:
        counts[alert.get("level", "blue")] = counts.get(alert.get("level", "blue"), 0) + 1
    rows = []
    for alert in alerts[:25]:
        level = alert.get("level", "blue")
        rows.append(
            f"<div class='alert {level}'>"
            f"<div style='flex:1'><div class='t'>{_esc(alert.get('name'))} — {_esc(alert.get('title'))}</div>"
            f"<div class='d'>SKU {_esc(alert.get('sku'))} · {_esc(alert.get('detail'))}</div></div></div>"
        )
    more = ""
    if len(alerts) > 25:
        more = f"<div class='tiny'>…и ещё {len(alerts) - 25} сигналов</div>"
    title = (
        f"Требует внимания <span class='hint'>"
        f"критичных: {counts.get('red', 0)} · предупреждений: {counts.get('yellow', 0)} · заметок: {counts.get('blue', 0)}</span>"
    )
    return f"<div class='panel'><h2>{title}</h2><div class='alerts'>{''.join(rows)}{more}</div></div>"


def _grade_pill(grade: str) -> str:
    grade = (grade or "").upper()
    mapping = {
        "DEFICIT": ("red", "дефицит"),
        "SURPLUS": ("yellow", "избыток"),
        "POPULAR": ("green", "популярный"),
        "ACTUAL": ("blue", "актуальный"),
        "NO_SALES": ("gray", "без продаж"),
        "GRADES_GREEN": ("green", "ок"),
        "GRADES_YELLOW": ("yellow", "средне"),
        "GRADES_RED": ("red", "плохо"),
        "GRADES_CRITICAL": ("red", "критично"),
        "GRADES_NOSALES": ("gray", "без продаж"),
    }
    cls, text = mapping.get(grade, ("gray", grade.lower() or "—"))
    return f"<span class='pill {cls}'>{_esc(text)}</span>"


def _sku_panel(
    skus: list[dict],
    has_costs: bool,
    has_settlement: bool = False,
    has_funnel: bool = True,
    has_returns: bool = True,
) -> str:
    head = [
        "<th>ABC</th>", "<th>Товар</th>", "<th>SKU</th>", "<th>Выручка</th>",
        "<th>Доля</th>", "<th>Шт</th>", "<th>Ср. цена</th>", "<th>Возвр.</th>",
        "<th>Сессии</th>", "<th>Конв.</th>", "<th>Остаток</th>", "<th>Хватит</th>",
        "<th>Статус</th>",
    ]
    if has_settlement:
        head.append("<th>После Ozon</th>")
    if has_costs:
        head.append("<th>Маржа</th>")

    rows = []
    for row in skus:
        name = _esc(row["name"])
        offer = _esc(row.get("offer_id") or "")
        link = f"https://www.ozon.ru/product/{to_int(row['sku'])}/"
        stock_known = bool(row.get("stock_known", True))
        stock_value = to_int(row["stock"])
        stock_text = fmt_int(stock_value) if stock_known else "—"
        idc_value = to_float(row["idc"])
        idc_text = f"{idc_value:.0f} дн." if stock_known and idc_value > 0 else "—"
        grade = row.get("grade") if stock_known else ""
        cells = [
            f"<td data-v='{_esc(row.get('abc'))}'><span class='abc {_esc(row.get('abc'))}'>{_esc(row.get('abc'))}</span></td>",
            f"<td class='name' data-v='{name}'><a href='{link}' target='_blank' rel='noopener'>{name}</a>"
            + (f"<div class='tiny'>{offer}</div>" if offer else "")
            + "</td>",
            f"<td class='num' data-v='{to_int(row['sku'])}'>{to_int(row['sku'])}</td>",
            f"<td class='num' data-v='{to_float(row['revenue']):.2f}'>{fmt_money(row['revenue'])}</td>",
            f"<td class='num' data-v='{to_float(row['share']):.4f}'>{row['share'] * 100:.1f}%</td>",
            f"<td class='num' data-v='{to_float(row['units']):.2f}'>{fmt_int(row['units'])}</td>",
            f"<td class='num' data-v='{to_float(row['avg_price']):.2f}'>{fmt_money(row['avg_price'])}</td>",
            f"<td class='num' data-v='{to_float(row['return_rate']):.4f}'>"
            + (f"{row['return_rate'] * 100:.1f}%" if has_returns and to_float(row["units"]) else "—")
            + "</td>",
            f"<td class='num' data-v='{to_float(row['sessions']):.2f}'>"
            + (fmt_int(row["sessions"]) if has_funnel else "—")
            + "</td>",
            f"<td class='num' data-v='{to_float(row['conv']):.4f}'>"
            + (f"{row['conv'] * 100:.2f}%" if has_funnel and to_float(row["sessions"]) else "—")
            + "</td>",
            f"<td class='num' data-v='{stock_value if stock_known else -1}'>{stock_text}</td>",
            f"<td class='num' data-v='{idc_value if stock_known else -1:.2f}'>{idc_text}</td>",
            f"<td data-v='{_esc(grade)}'>{_grade_pill(grade)}</td>",
        ]
        if has_settlement:
            net = row.get("net_before_cost")
            if net is None:
                cells.append("<td class='num' data-v='0'>—</td>")
            else:
                net_pct = net / row["revenue"] * 100 if row["revenue"] else 0
                color = "var(--good)" if net >= 0 else "var(--bad)"
                cells.append(
                    f"<td class='num' data-v='{net:.2f}' style='color:{color}'>{fmt_money(net)}"
                    f"<div class='tiny'>{net_pct:.1f}% от выручки</div></td>"
                )
        if has_costs:
            margin = row.get("margin")
            if margin is None:
                cells.append("<td class='num' data-v='0'>—</td>")
            else:
                pct = (row.get("margin_pct") or 0) * 100
                color = "var(--good)" if margin >= 0 else "var(--bad)"
                cells.append(
                    f"<td class='num' data-v='{margin:.2f}' style='color:{color}'>{fmt_money(margin)}"
                    f"<div class='tiny'>{pct:.1f}%</div></td>"
                )
        rows.append("<tr>" + "".join(cells) + "</tr>")

    toolbar = (
        "<div class='toolbar'><input id='search' type='search' placeholder='Поиск по названию, SKU или артикулу…'>"
        f"<div class='tiny'>{len(skus)} товаров · клик по заголовку сортирует</div></div>"
    )
    return (
        "<div class='panel'><h2>Товары</h2>"
        + toolbar
        + "<div class='table-scroll'><table id='sku-table'><thead><tr>"
        + "".join(head)
        + "</tr></thead><tbody>"
        + "".join(rows)
        + "</tbody></table></div></div>"
    )


def write_csvs(
    data: dict,
    out_dir: Path,
    suffix: str = "",
) -> tuple[list[Path], list[tuple[Path, OSError]]]:
    """Пишет sku.csv и daily.csv, не прерывая отчёт из-за одного занятого файла.

    Возвращает (сохранённые файлы, ошибки). Ошибка обычно означает, что файл
    открыт в Excel или защищён от записи; дашборд при этом всё равно собирается.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    errors: list[tuple[Path, OSError]] = []

    tables = [
        (
            out_dir / f"sku{suffix}.csv",
            [
                "sku", "offer_id", "name", "abc", "revenue", "share", "units", "avg_price",
                "returns", "returns_known", "return_rate", "sessions", "conv", "stock",
                "stock_known", "idc", "grade", "turnover", "margin", "margin_pct",
            ],
            data.get("sku") or [],
        ),
        (
            out_dir / f"daily{suffix}.csv",
            ["day", "revenue", "units", "returns", "returns_known", "sessions", "tocarts", "conv"],
            data.get("daily") or [],
        ),
    ]

    for path, fields, rows in tables:
        try:
            with store.atomic_open(path, encoding="utf-8-sig", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
                writer.writeheader()
                writer.writerows(rows)
        except OSError as exc:
            errors.append((path, exc))
        else:
            written.append(path)
    return written, errors
