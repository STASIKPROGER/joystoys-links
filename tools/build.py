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
    "P_BERRY": "lubrikant-dr-joys-200-ml-klubnika",
    "P_AQUA": "lubrikant-dr-joys-200-ml-klassika",
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
    return page[i:j] if 0 <= i < j else ""


def cards(block, prefix):
    """Карточки ленты: ссылка, скидка, значок акции, фото, название, цены — как на сайте."""
    out = []
    for m in re.finditer(r'<a class="jt-(?:nov|sale)__card" href="([^"]+)">(.*?)</a>', block, re.S):
        href, inner = m.group(1), m.group(2)
        img = re.search(r"background-image:url\('([^']+)'\)", inner)
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
            f'  <section class="show promo eared" style="--pa:{e(st.group(1)) if st else "#ff8a00"};--pb:{e(st.group(2)) if st else "#ff4d1a"}">\n'
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
    return ('  <section class="show sale eared">\n'
            '    <div class="head"><h2>🔥 Распродажа дня</h2>'
            + (f'<span class="timer" data-end="{e(iso_kz(end.group(1)))}"></span>' if end else "") + "</div>\n"
            '    <p class="sub">Каждый день новые товары со скидкой до 50% — только сутки.</p>\n'
            "    " + rail(items, all_href, "Все товары распродажи", "sale") + "\n"
            f'    <a class="all" href="{e(link(all_href, "sale"))}">Все товары распродажи <svg><use href="#arr"/></svg></a>\n'
            "  </section>")


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
    promo, sale = promo_sections(page), sale_section(page)
    total = re.search(r'"total":(\d+)', page)
    n = int(total.group(1)) if total else 0
    vals = {
        "BASE": BASE, "SITE": SITE, "UTM": UTM, "PROMO": promo, "SALE": sale,
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
    print(f"собрано: акций {promos}, распродажа {'есть' if sale else 'нет'}, карточек {tiles}, "
          f"товаров в наличии {n}; " + ", ".join(f"{k}={vals[k]}" for k in DRJOYS))


if __name__ == "__main__":
    main()
