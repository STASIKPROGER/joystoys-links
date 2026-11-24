#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Собирает таплинк Joys Toys в docs/ (его отдаёт GitHub Pages на go.joystoys.kz).

Стас, 29.10.2026: страница для шапки Instagram в стиле таплинка DR.JOYS, только
в цветах логотипа Joys Toys. Быстро на сайт, в WhatsApp и к адресам магазинов,
живые витрины акции (Хэллоуин и т. п.) и «Распродажи дня» — ровно как на сайте,
блоки собственного бренда DR.JOYS, опт и франшиза (WhatsApp Екатерины).

Витрины берутся с главной сайта (блоки JT-PROMOSHOW и JT-SALEDAY), цены DR.JOYS —
из карточек товаров. Сайт не отдаёт данные чужим страницам (нет CORS), поэтому
страница пересобирается: GitHub Actions раз в час (.github/workflows/build.yml).
Не удалось достать данные — docs/ не трогаем, остаётся прошлая сборка.

    python3 tools/build.py
Только стандартная библиотека Python.
"""
import datetime
import html
import json
import re
import shutil
import sys
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SITE_DIR, DOCS = ROOT / "site", ROOT / "docs"
BASE = "https://go.joystoys.kz"
SITE = "https://joystoys.kz"
UTM = "utm_source=taplink&utm_medium=social&utm_campaign="
UA = {"User-Agent": "Mozilla/5.0 (JoysToys taplink build)"}
MAX_CARDS = 20

WA_SHOP = "77011100066"
WA_KATYA = "77011244596"      # Екатерина, оптовый менеджер
DRJOYS = {                    # плейсхолдер цены -> карточка на сайте
    "P_NEON": "lubrikant-svetyaschiysya-neonovyy-100-ml-dr-joys",
    "P_CONDOMS": "prezervativy-drjoys-klassicheskie",
}


def get(url, timeout=60):
    return urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=timeout).read().decode("utf-8")


def wa(num, text):
    return f"https://wa.me/{num}?text=" + urllib.parse.quote(text)


def money(v):
    return f"{int(round(float(v))):,}".replace(",", " ") + " ₸"


def plural(n):
    a, b = n % 10, n % 100
    return "товар" if a == 1 and b != 11 else "товара" if 2 <= a <= 4 and not 12 <= b <= 14 else "товаров"


def text(s):
    return html.unescape(re.sub(r"<[^>]+>", "", s or "")).strip()


def iso_kz(s):
    """Срок акции для JS: без долей секунды и с часовым поясом Алматы (Safari иначе не разберёт)."""
    s = re.sub(r"\.\d+", "", s.strip())
    return s if re.search(r"[+-]\d\d:\d\d$|Z$", s) else s + "+05:00"


def cut(page, start, end):
    i, j = page.find(start), page.find(end)
    block = page[i:j] if 0 <= i < j else ""
    return unpack(block) or block


def unpack(block):
    """С 23.11.2026 сайт (JT-DEFER) отдаёт блоки главной не HTML, а скриптом jt_f_<блок>_N.js: внутри строка
    var H="<html блока>". Достаём её — витрины те же, что видит покупатель. Не вышло — пусто (блок пропустится)."""
    m = re.search(r'<script src="(https://[^"]+/jt_f_\w+\.js)"', block)
    if not m:
        return ""
    try:
        js = get(m.group(1))
        k = js.index('var H="') + len("var H=")
        return json.JSONDecoder().raw_decode(js, k)[0]
    except Exception as ex:
        print(f"  ! блок {m.group(1).rsplit('/', 1)[-1]}: {type(ex).__name__}", file=sys.stderr)
        return ""


def cards(block, prefix):
    """Карточки ленты: ссылка, скидка, значок акции, фото, название, цены — как на сайте."""
    out = []
    for m in re.finditer(r'<a class="jt-(?:nov|sale)__card" href="([^"]+)">(.*?)</a>', block, re.S):
        href, inner = m.group(1), m.group(2)
        # фото плитки: на сайте с 31.10.2026 почти везде ленивое (data-jt-bg — ставит JT-LAZYBG при прокрутке),
        # а где-то ещё прямым фоном — берём любое
        img = re.search(r"background-image:url\('([^']+)'\)", inner) or re.search(r'data-jt-bg="([^"]+)"', inner)
        new = re.search(rf'class="jt-{prefix}__new">(.*?)</span>', inner)
        old = re.search(rf'class="jt-{prefix}__old">(.*?)</span>', inner)
        out.append({
            "href": href,
            "badge": text((re.search(r'__badge">(.*?)</span>', inner) or [None, ""])[1]),
            "ic": text((re.search(r'jt-psec__mini">(.*?)</span>', inner) or [None, ""])[1]),
            "img": img.group(1) if img else "",
            "name": text((re.search(r'__name">(.*?)</span>', inner) or [None, ""])[1]),
            "new": text(new.group(1)) if new else "",
            "old": text(old.group(1)) if old else "",
        })
    return out


def link(href, camp):
    url = href if href.startswith("http") else SITE + href
    return url + ("&" if "?" in url else "?") + UTM + camp


def rail(items, more_href, more_text, camp):
    e = html.escape
    tiles = []
    for c in items[:MAX_CARDS]:
        tiles.append(
            f'<a class="pc" href="{e(link(c["href"], camp))}">'
            + (f'<span class="badge">{e(c["badge"])}</span>' if c["badge"] else "")
            + (f'<span class="ic">{e(c["ic"])}</span>' if c["ic"] else "")
            + f'<span class="img" style="background-image:url(\'{e(c["img"])}\')"></span>'
            f'<span class="nm">{e(c["name"])}</span>'
            f'<span class="pr"><span class="new">{e(c["new"])}</span>'
            + (f'<span class="old">{e(c["old"])}</span>' if c["old"] else "")
            + '</span><span class="buy">Купить</span></a>')
    tiles.append(f'<a class="pc more" href="{e(link(more_href, camp))}"><span class="go"><svg><use href="#arr"/></svg></span>{e(more_text)}</a>')
    return '<div class="rail">' + "".join(tiles) + "</div>"


def promo_sections(page):
    """Витрины календарных акций (может быть несколько) — блок JT-PROMOSHOW на главной."""
    block = cut(page, "<!-- JT-PROMOSHOW START -->", "<!-- JT-PROMOSHOW END -->")
    out = []
    for sec in re.split(r'(?=<div class="jt-nov jt-sale jt-psec)', block)[1:]:
        st = re.search(r'style="--pa:([^;"]+);--pb:([^;"]+)"', sec)
        end = re.search(r'data-promo-end="([^"]+)"', sec)
        title = re.search(r'<h2 class="jt-nov__title">(.*?)</h2>', sec, re.S)
        sub = re.search(r'<p class="jt-psec__sub">(.*?)</p>', sec, re.S)
        allm = re.search(r'<a class="jt-nov__all" href="([^"]+)">(.*?)</a>', sec, re.S)
        items = cards(sec, "psec")
        if not (title and items):
            continue
        e = html.escape
        all_href, all_text = (allm.group(1), text(allm.group(2)).rstrip(" →")) if allm else ("/", "Все товары акции")
        out.append(
            f'  <section class="show promo" style="--pa:{e(st.group(1)) if st else "#ff8a00"};--pb:{e(st.group(2)) if st else "#ff4d1a"}">\n'
            f'    <div class="head"><h2>{e(text(title.group(1)))}</h2>'
            + (f'<span class="timer" data-end="{e(iso_kz(end.group(1)))}"></span>' if end else "") + "</div>\n"
            + (f'    <p class="sub">{e(text(sub.group(1)))}</p>\n' if sub else "")
            + "    " + rail(items, all_href, all_text, "promo") + "\n"
            f'    <a class="all" href="{e(link(all_href, "promo"))}">{e(all_text)} <svg><use href="#arr"/></svg></a>\n'
            "  </section>")
    return "\n".join(out)


def sale_section(page):
    """«Распродажа дня» — блок JT-SALEDAY на главной, таймер до того же момента, что на сайте."""
    block = cut(page, "<!-- JT-SALEDAY START -->", "<!-- JT-SALEDAY END -->")
    items = cards(block, "sale")
    if not items:
        return ""
    end = re.search(r'data-sale-end="([^"]+)"', block)
    allm = re.search(r'<a class="jt-sale__all" href="([^"]+)"', block)
    all_href = allm.group(1) if allm else "/collection/rasprodazha-dnya"
    e = html.escape
    return ('  <section class="show sale">\n'
            '    <div class="head"><h2>🔥 Распродажа дня</h2>'
            + (f'<span class="timer" data-end="{e(iso_kz(end.group(1)))}"></span>' if end else "") + "</div>\n"
            '    <p class="sub">Новые скидки каждый день — только сутки.</p>\n'
            "    " + rail(items, all_href, "Все товары распродажи", "sale") + "\n"
            f'    <a class="all" href="{e(link(all_href, "sale"))}">Все товары распродажи <svg><use href="#arr"/></svg></a>\n'
            "  </section>")


def extra_section(page):
    """«Ещё акции» в конце страницы: карусель «Акции» (JT-PROMO) и «Бренд месяца» (JT-BRANDPROMO) с главной.
    Сменились акции на сайте — сменятся и здесь; нет ни одной — раздела нет."""
    e = html.escape
    parts = []
    block = cut(page, "<!-- JT-PROMO START -->", "<!-- JT-PROMO END -->")
    tiles = []
    for m in re.finditer(r'<a class="jt-promo__card" href="([^"]+)">(.*?)</a>', block, re.S):
        inner = m.group(2)
        img = re.search(r'<source[^>]+srcset="([^"]+)"', inner) or re.search(r'<img[^>]+src="([^"]+)"', inner)
        cap = text((re.search(r'jt-promo__cap">(.*?)</span>', inner) or [None, ""])[1])
        if img and cap:
            tiles.append(f'<a class="pb" href="{e(link(m.group(1), "akcii"))}"><img src="{e(img.group(1))}" alt="" loading="lazy">'
                         f'<span>{e(cap)}</span></a>')
    if tiles:
        parts.append('  <div class="prom-rail">' + "".join(tiles) + "</div>")
    b = cut(page, "<!-- JT-BRANDPROMO START -->", "<!-- JT-BRANDPROMO END -->")
    items = cards(b, "bsale")
    title = re.search(r'<h2 class="jt-nov__title">(.*?)</h2>', b, re.S)
    if items and title:
        chip = re.search(r'jt-bsale__chip">(.*?)</span>', b)
        sub = re.search(r'<p class="jt-bsale__sub">(.*?)</p>', b, re.S)
        allm = re.search(r'<a class="jt-nov__all" href="([^"]+)">(.*?)</a>', b, re.S)
        all_href, all_text = (allm.group(1), text(allm.group(2)).rstrip(" →")) if allm else ("/page/akcii", "Все товары")
        parts.append(
            '  <section class="show brandm">\n'
            f'    <div class="head"><h2>{e(text(title.group(1)))}</h2>'
            + (f'<span class="chipx">{e(text(chip.group(1)))}</span>' if chip else "") + "</div>\n"
            + (f'    <p class="sub">{e(text(sub.group(1)))}</p>\n' if sub else "")
            + "    " + rail(items, all_href, all_text, "brand") + "\n"
            f'    <a class="all" href="{e(link(all_href, "brand"))}">{e(all_text)} <svg><use href="#arr"/></svg></a>\n'
            "  </section>")
    if not parts:
        return ""
    return ('  <div class="sec"><h2 class="st">Ещё акции</h2><span class="tag pink tilt-r">для тех, кто долистал</span></div>\n'
            + "\n".join(parts) + "\n"
            f'  <a class="all-akcii btn line" href="{e(link("/page/akcii", "akcii"))}">Все акции и условия <svg><use href="#arr"/></svg></a>\n')


# Чёрная пятница (Штаб 24.11.2026): первая кнопка, выше «В магазин», только 24–30.11 по Алматы.
# N в «до −N%» — 70, как во всех материалах ЧП; если в разделе в наличии нет скидки ≥70% — самая большая, что есть (проверка при каждой сборке).
ALMATY = datetime.timezone(datetime.timedelta(hours=5))
BF_FROM = datetime.datetime(2026, 11, 24, tzinfo=ALMATY)
BF_TO = datetime.datetime(2026, 12, 1, tzinfo=ALMATY)
BF_PROMISE = 70   # Штаб 24.11: «до −70%», как баннер и пост в Google Картах; −79% у кабеля Gvibe — не обещание. Меньше в наличии — пишем сколько есть
BF_URL = SITE + "/collection/black-friday?utm_source=instagram&utm_medium=bio&utm_campaign=bf_carousel"


def bf_max_discount():
    best, page = 0, 1
    while page <= 30:
        d = json.loads(get(f"{SITE}/collection/black-friday.json?page={page}&page_size=100"))
        ps = d.get("products") or []
        if not ps:
            break
        for pr in ps:
            for v in pr.get("variants") or []:
                cur, old = float(v.get("price") or 0), float(v.get("old_price") or 0)
                if (v.get("quantity") or 0) > 0 and old > cur > 0:
                    best = max(best, int((1 - cur / old) * 100))
        page += 1
    return best


def bf_button(now=None):
    now = now or datetime.datetime.now(ALMATY)
    if not BF_FROM <= now < BF_TO:
        return "", "нет (не 24–30.11)"
    try:
        n = bf_max_discount()
    except Exception as ex:
        print(f"  ! скидки Чёрной пятницы: {type(ex).__name__}", file=sys.stderr)
        n = 0
    n = min(n, BF_PROMISE)
    title = f"Чёрная пятница — до −{n}%" if n >= 10 else "Чёрная пятница"
    e = html.escape
    out = (f'  <a class="bf" href="{e(BF_URL)}" data-from="{BF_FROM.isoformat()}" data-to="{BF_TO.isoformat()}">\n'
           '    <span class="shine" aria-hidden="true"></span>\n'
           f'    <span class="pct">{"−" + str(n) + "%" if n >= 10 else "BF"}</span>\n'
           f'    <span><b>{e(title)}</b><small>только до 30 ноября</small></span>\n'
           '    <span class="go"><svg><use href="#arr"/></svg></span>\n'
           '  </a>\n')
    return out, f"есть, до −{n}%" if n >= 10 else "есть, без цифры"


def price(perm):
    try:
        d = json.loads(get(f"{SITE}/product/{perm}.json"))
        p = d.get("product", d)
        v = (p.get("variants") or [{}])[0]
        return money(v.get("price") or p.get("price"))
    except Exception as ex:
        print(f"  ! цена {perm}: {ex}", file=sys.stderr)
        return "На сайте"


def main():
    page = get(SITE + "/")
    if "JT-SALEDAY" not in page and "JT-PROMOSHOW" not in page:
        sys.exit("ABORT: на главной нет витрин — docs/ не трогаю")
    promo, sale, extra = promo_sections(page), sale_section(page), extra_section(page)
    bf, bf_note = bf_button()
    total = re.search(r'"total":(\d+)', page)
    n = int(total.group(1)) if total else 0
    vals = {
        "BASE": BASE, "SITE": SITE, "UTM": UTM, "BF": bf, "PROMO": promo, "SALE": sale, "EXTRA": extra,
        "TOTAL": f"{n:,}".replace(",", " ") + " " + plural(n) if n else "тысячи товаров",
        "WA_SHOP": wa(WA_SHOP, "Здравствуйте! Пишу из инстаграма Joys Toys. Хочу заказать "),
        "WA_NEON": wa(WA_SHOP, "Здравствуйте! Хочу заказать неоновый лубрикант DR.JOYS"),
        "WA_KATYA": wa(WA_KATYA, "Здравствуйте, Екатерина! Пишу по поводу опта / франшизы Joys Toys."),
    }
    vals.update({k: price(perm) for k, perm in DRJOYS.items()})
    out = (SITE_DIR / "index.html").read_text(encoding="utf-8")
    for k, v in vals.items():
        out = out.replace("{{" + k + "}}", v)
    left = re.findall(r"\{\{\w+\}\}", out)
    if left:
        sys.exit(f"ABORT: не заполнены {left}")
    DOCS.mkdir(exist_ok=True)
    shutil.copytree(SITE_DIR / "assets", DOCS / "assets", dirs_exist_ok=True)
    (DOCS / "index.html").write_text(out, encoding="utf-8")
    (DOCS / "CNAME").write_text(BASE.split("//")[1] + "\n")
    (DOCS / ".nojekyll").write_text("")
    promos, tiles = promo.count('class="show promo'), out.count('class="pc"')
    pbs = extra.count('class="pb"')
    print(f"собрано: чёрная пятница {bf_note}, акций {promos}, распродажа {'есть' if sale else 'нет'}, ещё акций {pbs} + "
          f"бренд месяца {'есть' if 'brandm' in extra else 'нет'}, карточек {tiles}, "
          f"товаров в наличии {n}; " + ", ".join(f"{k}={vals[k]}" for k in DRJOYS))


if __name__ == "__main__":
    main()
