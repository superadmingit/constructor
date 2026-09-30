"""Собирает страницу сбора данных в один HTML-файл (рисунки, стили, логика внутри)."""
import json, sys
from pathlib import Path
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import figs

CAPTIONS = {
    "press": "Пресс сбоку. Оператор стоит справа.",
    "plate": "Шильдик: где искать нужные строки.",
    "table": "Стол сверху: как считать «слева направо» и «спереди назад».",
    "ram": "Ползун снизу: где отверстие под хвостовик.",
    "caliper": "Штангенциркуль: какими губками что мерить.",
    "vernier": "Как читать показание штангенциркуля.",
    "radius": "Радиус гиба и радиусомер.",
    "die": "Штамп в разрезе. Нажмите на строку списка, чтобы подсветить деталь.",
}
DIE_LEGEND = [list(x) for x in figs.DIE_LEGEND] + [
    [17, "t-dshut", "Закрытая высота штампа",
     "расстояние от нижней плоскости нижней плиты до верхней плоскости верхней плиты, когда штамп сомкнут"]]

PAGE_FIGS = ["press", "plate", "table", "ram", "caliper", "vernier", "radius", "die"]


def figure_html():
    out = []
    for key in PAGE_FIGS:
        fn, _title = figs.FIGURES[key]
        svg = fn().replace('id="', f'id="{key}__')
        extra = ""
        if key == "die":
            items = "".join(
                f'<li><button type="button" data-id="{i}"><span class="num">{n if n <= 16 else "•"}</span> {t}</button></li>'
                for n, i, t, _ in DIE_LEGEND)
            extra = f'<ol class="legend">{items}</ol>'
        out.append(f'<figure data-fig="{key}" hidden><figcaption>{CAPTIONS[key]}</figcaption>'
                   f'<div class="fig">{svg}</div>{extra}</figure>')
    return "".join(out)

ICONS = {
    "machines": {k: figs.machine_icon(k) for k in
                 ["lathe", "mill", "drill", "jig", "grinder", "edm", "guillotine", "brake"]},
    "press": {k: figs.press_type_icon(k) for k in ["crank_open", "crank_closed", "hydraulic", "unknown"]},
}
SPRITE = ('<svg width="0" height="0" style="position:absolute" aria-hidden="true" focusable="false"><defs>'
          '<marker id="arr" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="9" markerHeight="9" '
          'markerUnits="userSpaceOnUse" orient="auto-start-reverse"><path d="M0,1 L9,5 L0,9 z" '
          'style="fill:var(--fig-dim)"/></marker></defs></svg>')

css = open(HERE / "style.css", encoding="utf-8").read()
js = open(HERE / "app.js", encoding="utf-8").read()
data = json.dumps({"ICONS": ICONS, "DIE_LEGEND": DIE_LEGEND}, ensure_ascii=False)

html = f"""<!doctype html>
<html lang="ru">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>Данные цеха для расчёта штампов</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Golos+Text:wght@400;500;600;700&display=swap" rel="stylesheet">
<style>{css}</style>
</head>
<body>
{SPRITE}
<div class="wrap">
<header class="top">
  <h1>Данные цеха для расчёта штампов</h1>
  <p class="lede">Здесь мы собираем то, что нужно программе, чтобы считать штампы под ваши прессы и станки: параметры прессов и станки цеха. Это делается один раз для цеха.</p>
  <p class="need"><b>Понадобятся:</b> рулетка, штангенциркуль, телефон для фото, паспорта прессов (если есть). Около часа, можно частями: всё сохраняется в этом браузере.</p>
  <p class="need"><b>Не знаете?</b> Нажмите «Не знаю». Это нормальный ответ: программа пометит такое место и не будет считать его проверенным.</p>
  <div class="prog"><div class="bar"><div class="fill" id="progfill"></div></div><p id="progtxt"></p></div>
</header>
<nav class="tabs" id="tabs" role="tablist" aria-label="Разделы"></nav>
<div class="layout" id="layout">
  <main class="main">
    <section id="sec-presses" role="tabpanel" aria-labelledby="tab-presses"></section>
    <section id="sec-machines" role="tabpanel" aria-labelledby="tab-machines" hidden></section>
    <section id="sec-part" role="tabpanel" aria-labelledby="tab-part" hidden></section>
    <section id="sec-glossary" role="tabpanel" aria-labelledby="tab-glossary" hidden></section>
    <section id="sec-send" role="tabpanel" aria-labelledby="tab-send" hidden></section>
    <noscript><p class="warn">Для работы страницы нужен включённый JavaScript.</p></noscript>
  </main>
  <aside class="figpanel" id="figpanel" aria-label="Рисунок">
    <div class="fphead"><b>Жёлтым выделено то, что вы сейчас заполняете</b><button type="button" class="sheetclose" id="sheetclose">Закрыть</button></div>
    {figure_html()}
  </aside>
</div>
</div>
<div class="scrim" id="scrim"></div>
<script>window.DATA = {data};</script>
<script>{js}</script>
</body>
</html>
"""
out = sys.argv[1] if len(sys.argv) > 1 else str(HERE / "data_collection.html")
open(out, "w", encoding="utf-8").write(html)
print(out, f"{len(html)/1024:.0f} KB")
