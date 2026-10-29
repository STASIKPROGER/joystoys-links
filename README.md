# Joys Toys — ссылки для шапки Instagram (go.joystoys.kz)

Одна страница: в магазин, WhatsApp, адреса, живые витрины акции и «Распродажи дня» с joystoys.kz,
собственный бренд DR.JOYS, опт и франшиза. Раскладка — как у таплинка DR.JOYS (go.dr-joys.com),
цвета и «ушки» — из логотипа Joys Toys (#FF0066, #000066).

- `site/` — шаблон страницы и картинки, `tools/build.py` — сборка в `docs/` (её отдаёт GitHub Pages)
- витрины и цены берутся с сайта при каждой сборке; GitHub Actions собирает раз в час (`.github/workflows/build.yml`)
- `tools/og.html` — обложка для превью ссылки (assets/og.jpg)

Сборка вручную: `python3 tools/build.py` (только стандартная библиотека).
