"""Генерация SVG-графиков без внешних библиотек (работает офлайн)."""

from __future__ import annotations

import html
import itertools
import math


_GRADIENT_IDS = itertools.count(1)


def _esc(value) -> str:
    return html.escape(str(value), quote=True)


def _num(value) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _nice_max(value: float) -> float:
    if value <= 0:
        return 1.0
    power = 10 ** math.floor(math.log10(value))
    for multiplier in (1, 1.2, 1.5, 2, 2.5, 3, 4, 5, 6, 8, 10):
        if value <= multiplier * power:
            return multiplier * power
    return 10 * power


def compact(value: float) -> str:
    value = _num(value)
    if abs(value) >= 1_000_000:
        return f"{value / 1_000_000:.1f} млн".replace(".", ",")
    if abs(value) >= 1_000:
        return f"{value / 1_000:.0f} тыс"
    return f"{value:.0f}"


def line_chart(
    points: list[tuple[str, float]],
    *,
    width: int = 760,
    height: int = 240,
    color: str = "var(--accent)",
    value_label: str = "",
) -> str:
    if not points:
        return _empty(width, height)

    pad_l, pad_r, pad_t, pad_b = 56, 16, 14, 28
    plot_w = width - pad_l - pad_r
    plot_h = height - pad_t - pad_b
    values = [_num(v) for _, v in points]
    top = _nice_max(max(values) * 1.05)

    def x_at(index: int) -> float:
        if len(points) == 1:
            return pad_l + plot_w / 2
        return pad_l + plot_w * index / (len(points) - 1)

    def y_at(value: float) -> float:
        return pad_t + plot_h * (1 - value / top)

    gradient_id = f"grad-{next(_GRADIENT_IDS)}"
    parts = [
        f'<svg viewBox="0 0 {width} {height}" class="chart" role="img" aria-label="{_esc(value_label or "график")}">',
        f'<defs><linearGradient id="{gradient_id}" x1="0" x2="0" y1="0" y2="1">'
        f'<stop offset="0%" style="stop-color:{color};stop-opacity:0.28"/>'
        f'<stop offset="100%" style="stop-color:{color};stop-opacity:0.02"/></linearGradient></defs>',
    ]

    for step in range(5):
        value = top * step / 4
        y = y_at(value)
        parts.append(f'<line x1="{pad_l}" x2="{width - pad_r}" y1="{y:.1f}" y2="{y:.1f}" class="grid"/>')
        parts.append(f'<text x="{pad_l - 8}" y="{y + 4:.1f}" text-anchor="end" class="axis">{_esc(compact(value))}</text>')

    coords = [(x_at(i), y_at(v)) for i, v in enumerate(values)]
    line = " ".join(f"{x:.1f},{y:.1f}" for x, y in coords)
    area = f"M {coords[0][0]:.1f},{pad_t + plot_h:.1f} L " + " L ".join(f"{x:.1f},{y:.1f}" for x, y in coords) + f" L {coords[-1][0]:.1f},{pad_t + plot_h:.1f} Z"
    parts.append(f'<path d="{area}" fill="url(#{gradient_id})" stroke="none"/>')
    parts.append(
        f'<polyline points="{line}" fill="none" style="stroke:{color}" '
        f'stroke-width="2.2" stroke-linejoin="round" stroke-linecap="round"/>'
    )

    for (label, value), (x, y) in zip(points, coords):
        parts.append(
            f'<circle class="dot" cx="{x:.1f}" cy="{y:.1f}" r="3.2" style="stroke:{color}" stroke-width="1.8">'
            f"<title>{_esc(label)}: {_esc(compact(_num(value)))}</title></circle>"
        )

    step = max(1, len(points) // 7)
    for index in range(0, len(points), step):
        label = points[index][0]
        parts.append(f'<text x="{x_at(index):.1f}" y="{height - 8}" text-anchor="middle" class="axis">{_esc(label[5:] if len(label) >= 10 else label)}</text>')

    parts.append("</svg>")
    return "".join(parts)


def bar_chart_h(
    items: list[tuple[str, float]],
    *,
    width: int = 560,
    row_height: int = 28,
    color: str = "var(--accent)",
    value_suffix: str = " ₽",
    label_width: int = 230,
) -> str:
    if not items:
        return _empty(width, 160)

    height = row_height * len(items) + 12
    bar_max = width - label_width - 90
    top = max(_num(v) for _, v in items) or 1
    parts = [f'<svg viewBox="0 0 {width} {height}" class="chart" role="img" aria-label="рейтинг">']
    for index, (label, value) in enumerate(items):
        value = _num(value)
        y = 6 + index * row_height
        bar_w = max(2.0, bar_max * value / top)
        text = label if len(label) <= 30 else label[:29] + "…"
        parts.append(f'<text x="0" y="{y + 15}" class="axis label">{_esc(text)}</text>')
        parts.append(f'<rect x="{label_width}" y="{y + 4}" width="{bar_w:.1f}" height="{row_height - 10}" rx="4" style="fill:{color}" opacity="0.85"><title>{_esc(label)}: {_esc(compact(value))}</title></rect>')
        parts.append(f'<text x="{label_width + bar_w + 6:.1f}" y="{y + 15}" class="axis value">{_esc(compact(value))}{_esc(value_suffix)}</text>')
    parts.append("</svg>")
    return "".join(parts)


def funnel(steps: list[tuple[str, float]], *, width: int = 480, row_height: int = 46) -> str:
    if not steps:
        return _empty(width, 160)
    height = row_height * len(steps) + 8
    top = _num(steps[0][1]) or 1
    available = width - 170
    parts = [f'<svg viewBox="0 0 {width} {height}" class="chart" role="img" aria-label="воронка">']
    for index, (label, value) in enumerate(steps):
        value = _num(value)
        y = 6 + index * row_height
        bar_w = max(3.0, available * value / top)
        share = value / top if top else 0
        parts.append(f'<rect x="0" y="{y}" width="{bar_w:.1f}" height="{row_height - 12}" rx="6" style="fill:var(--accent)" opacity="{0.92 - index * 0.14:.2f}"><title>{_esc(label)}: {_esc(compact(value))}</title></rect>')
        parts.append(f'<text x="{bar_w + 10:.1f}" y="{y + 16}" class="axis label">'
                     f'{_esc(label)} · {_esc(compact(value))} ({share * 100:.1f}%)</text>')
    parts.append("</svg>")
    return "".join(parts)


def _empty(width: int, height: int) -> str:
    return (
        f'<svg viewBox="0 0 {width} {height}" class="chart"><text x="{width / 2}" y="{height / 2}" '
        f'text-anchor="middle" class="axis">нет данных</text></svg>'
    )
