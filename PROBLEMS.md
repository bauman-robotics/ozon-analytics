# Проблемы и разбор

Документ фиксирует проблемы, с которыми пришёл пользователь, их причины,
внесённые исправления и оставшиеся ограничения. Логи приведены как есть.

## 1. `PermissionError` при записи `out\sku.csv`

### Лог пользователя

```text
Traceback (most recent call last):
  File "C:\Users\kfani\Desktop\ozon-analytics\run.py", line 300, in <module>
    sys.exit(main())
  File "C:\Users\kfani\Desktop\ozon-analytics\run.py", line 296, in main
    return args.func(args)
  File "C:\Users\kfani\Desktop\ozon-analytics\run.py", line 178, in cmd_report
    out = _build_report(snapshot, args)
  File "C:\Users\kfani\Desktop\ozon-analytics\run.py", line 43, in _build_report
    for csv_path in report.write_csvs(data, store.OUT_DIR, suffix):
  File "C:\Users\kfani\Desktop\ozon-analytics\ozon\report.py", line 500, in write_csvs
    with sku_path.open("w", encoding="utf-8-sig", newline="") as handle:
  File "C:\Users\kfani\AppData\Local\Python\pythoncore-3.15-64\Lib\pathlib\__init__.py", line 970, in open
    return io.open(self, mode, buffering, encoding, errors, newline)
PermissionError: [Errno 13] Permission denied: 'C:\Users\kfani\Desktop\ozon-analytics\out\sku.csv'
```

### Причина

На Windows файл `out\sku.csv` был занят другой программой — чаще всего
он открыт в Excel, — либо имел атрибут «только чтение». Старый
`write_csvs()` открывал целевой файл напрямую и не перехватывал `OSError`.
Из-за этого падал весь `report`, хотя дашборд к этому моменту уже был
сохранён.

### Что сделано

- Запись CSV и HTML переведена на атомарную: временный файл рядом,
  затем `os.replace()` (`ozon/store.py`).
- `write_csvs()` пишет каждый файл отдельно и возвращает список ошибок,
  не прерывая отчёт (`ozon/report.py`).
- В консоль выводится сообщение с подсказкой: закрыть файл и выполнить
  `py run.py report` (`run.py`).
- На Windows при `PermissionError` проект пытается снять атрибут
  «только чтение» и повторить замену.
- Если не удалось сохранить сам дашборд, выводится понятная ошибка,
  а не traceback.

### Как проверить

1. Закрыть `out\sku.csv` в Excel.
2. Выполнить `py run.py report` — команда пересоберёт отчёт из готового
   снимка без запросов к API.
3. Убедиться, что в консоли нет traceback, а `sku.csv`, `daily.csv`
   и `dashboard.html` обновились.

## 2. `deprecated metrics used` (HTTP 400)

### Лог пользователя

```text
deprecatad metrics used (HTTP 400)
```

В исходном сообщении пользователя слово написано как `deprecatad`;
фактическое сообщение Ozon — `deprecated metrics used`.

### Причина

Ozon пометил метрики воронки `session_view`, `hits_view`, `hits_tocart`
(а также `position_category`) как deprecated и отклоняет **весь** запрос
`POST /v1/analytics/data`, если в нём есть хотя бы одна из них.
Старый код при ошибке повторял запрос с `session_view`, которая тоже
deprecated, поэтому воронка не загружалась вообще.

Дополнительно: расширенные метрики `returns`, `cancellations`,
`delivered_units` и метрики воронки требуют подписки **Premium Plus**.
У пользователя есть **Premium**, но не Premium Plus, поэтому эти данные
недоступны и по тарифу.

### Что сделано

- Воронка больше не запрашивается в live-сборе — HTTP 400 исчезает
  (`ozon/api.py`, `ozon/collect.py`).
- В live-отчёте сессии и конверсия показываются как «—», в блоке воронки
  написано, что Ozon отключил эти метрики. В демо-отчёте воронка осталась.
- Если Ozon отклоняет расширенный набор метрик продаж, проект повторяет
  запрос с `revenue` + `ordered_units` и предупреждает, что возвраты,
  отмены и доставка недоступны без Premium Plus.
- «Доля возвратов» и колонка «Возвр.» показывают «—», а не `0.0%`,
  чтобы отсутствие данных не выглядело как нулевые возвраты.
- В CSV добавлены признаки `returns_known` и `stock_known`.

### Оставшееся ограничение

- Вернуть воронку через `/v1/analytics/data` нельзя: метрики deprecated.
  Альтернатива для поисковых показов — `/v1/analytics/product-queries`
  (требует Premium), но она в дашборд пока не включена.
- Без Premium Plus недоступны `returns`, `cancellations`,
  `delivered_units`. Возвраты можно попробовать получать отдельно через
  `/v1/returns/list` — это возможная следующая доработка, но она требует
  отдельной проверки ролей ключа и маппинга возвратов на SKU/день.

## 3. Дополнительные проблемы, найденные при разборе

### 3.1. Ложные алерты «Нет в наличии»

Если остатки не загрузились (нет роли «Товары», `--no-stocks` или сбой
запроса), `stock` оставался нулём, и проект показывал «Нет в наличии»
почти по каждому товару. Теперь остаток и «хватит на» показываются как
«—», а алерт создаётся только при известных остатках.

### 3.2. Лимит `/v1/analytics/data` — 1 запрос в минуту

Ozon ограничивает метод одним запросом в минуту (и 50 запросами в сутки
без Premium Plus). Старый клиент делал паузы только для оборачиваемости,
поэтому при пагинации мог получить 429 и потерять данные. Теперь клиент
выдерживает 60 секунд между запросами, учитывает `Retry-After` и делает
более длинные паузы при 429.

### 3.3. Потеря уже загруженных данных при сбое пагинации

Если первая страница аналитики или первая порция остатков получена,
а следующая упала, старый код выбрасывал всё. Теперь загруженные строки
сохраняются с предупреждением о частичной загрузке.

### 3.4. GUI открывал не тот дашборд

Кнопка «Демо-дашборд» вызывала общий `open_dashboard()`, который
предпочитал `out/dashboard.html`. Если live-отчёт уже существовал,
открывался он, а не демо. Теперь для демо всегда открывается
`out/dashboard-demo.html`.

## 4. Как проверялось

- `python3 -m unittest discover -s tests` — **49 тестов, OK**.
- Демо-сборка `python3 run.py demo` — успешно.
- Занятый `sku.csv` и недоступный `dashboard.html` воспроизведены:
  отчёт продолжает работу, выводит предупреждение, traceback отсутствует.
- Живой запрос к Ozon Seller API не выполнялся: в среде разработки нет
  `.env` с ключом. Для проверки API-части нужно выполнить
  `py run.py all --days 30` на машине с ключом.
