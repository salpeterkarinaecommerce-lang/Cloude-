"""Map (envíos a todo el país) + end card for 770 Import hilo3d — 1080x1920, 7.4 s."""
import os
HERE = os.path.dirname(os.path.abspath(__file__))
gen, cities = {}, []
for line in open("/tmp/claude-0/-home-user-Cloude-/336cd61f-d42e-512d-9e7d-628674a53f2f/scratchpad/reel/graficos/gen.txt"):
    k, _, v = line.strip().partition(" ")
    if k == "CITY":
        n, x, y, d = v.split(" ", 3); cities.append((n, float(x), float(y), d))
    else:
        gen[k] = v
bax, bay = map(float, gen["BA"].split())
MX, MY = 318, 650                      # map origin on screen (scale 1)
DUR = 7.4

routes = "".join(f'<path class="route" id="r-{n}" d="{d}" pathLength="1"/>' for n, x, y, d in cities)
dots = "".join(f'<g class="city" id="c-{n}" transform="translate({x},{y})"><circle r="15" class="ring"/><circle r="6.5"/></g>' for n, x, y, d in cities)
pk = "".join(f'<g class="pk" id="k-{n}"><rect x="-9" y="-9" width="18" height="18" rx="2.5"/><rect class="tp" x="-2" y="-9" width="4" height="18"/></g>' for n, x, y, d in cities)
extr = "".join(f'<path d="{gen["OUTLINE"]}" transform="translate(0,{i * 2.2})" fill="{c}"/><path d="{gen["TDF"]}" transform="translate(0,{i * 2.2})" fill="{c}"/>'
               for i, c in reversed(list(enumerate(["#c49a45", "#a88234", "#94712a", "#7f5f22", "#6c501c", "#5a4218"], 1))))
js = []
for i, (n, x, y, d) in enumerate(cities):
    t = 1.05 + i * 0.09
    js.append(f'tl.fromTo("#r-{n}", {{strokeDashoffset: 1}}, {{strokeDashoffset: 0, duration: 0.55, ease: "power2.inOut"}}, {t:.3f});')
    js.append(f'tl.fromTo("#k-{n}", {{opacity: 0}}, {{opacity: 1, duration: 0.1}}, {t + 0.1:.3f});')
    js.append(f'tl.to("#k-{n}", {{motionPath: {{path: "#r-{n}", align: "#r-{n}", alignOrigin: [0.5, 0.5], autoRotate: false}}, duration: 0.9, ease: "power1.inOut", immediateRender: true}}, {t + 0.1:.3f});')
    js.append(f'tl.to("#k-{n}", {{opacity: 0, scale: 0.3, svgOrigin: "{x} {y}", duration: 0.15}}, {t + 0.98:.3f});')
    js.append(f'tl.fromTo("#c-{n}", {{scale: 0, opacity: 0, svgOrigin: "{x} {y}"}}, {{scale: 1, opacity: 1, duration: 0.45, ease: "back.out(3)"}}, {t + 0.95:.3f});')
js = "\n  ".join(js)

labels = {"sal": "Salta", "mza": "Mendoza", "brc": "Bariloche", "ush": "Ushuaia", "pos": "Posadas"}
lab_html, lab_js = "", []
for i, (n, x, y, d) in enumerate(cities):
    if n in labels:
        sx, sy = MX + x, MY + y
        side = "r" if n == "pos" else "l"
        style = f"left:{sx + 26:.0f}px" if side == "r" else f"right:{1080 - sx + 26:.0f}px"
        lab_html += f'<div class="cl" id="cl-{n}" style="{style};top:{sy - 20:.0f}px">{labels[n]}</div>'
        lab_js.append(f'tl.fromTo("#cl-{n}", {{opacity: 0, y: 12}}, {{opacity: 1, y: 0, duration: 0.3, ease: "power3.out"}}, {1.05 + i * 0.09 + 1.0:.2f});')
lab_js = "\n  ".join(lab_js)
ox, oy = MX + bax, MY + bay

html = f"""<!doctype html>
<html lang="es" data-resolution="portrait">
<head>
<meta charset="UTF-8" />
<meta name="viewport" content="width=1080, height=1920" />
<script src="assets/gsap.min.js"></script>
<script src="assets/MotionPathPlugin.min.js"></script>
<style>
  @font-face {{ font-family: "Lora"; src: url("assets/fonts/lora-latin-700-italic.woff2") format("woff2"); font-weight: 700; font-style: italic; }}
  @font-face {{ font-family: "Inter"; src: url("assets/fonts/inter-latin-500-normal.woff2") format("woff2"); font-weight: 500; }}
  @font-face {{ font-family: "Inter"; src: url("assets/fonts/inter-latin-600-normal.woff2") format("woff2"); font-weight: 600; }}
  @font-face {{ font-family: "Inter"; src: url("assets/fonts/inter-latin-700-normal.woff2") format("woff2"); font-weight: 700; }}
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  html, body {{ width: 1080px; height: 1920px; overflow: hidden; background: #0b1330; }}
  #root {{ position: relative; width: 1080px; height: 1920px; overflow: hidden; font-family: "Inter", sans-serif; color: #f4efe3; }}
  .L {{ position: absolute; inset: 0; }}
  #bg {{ background: radial-gradient(ellipse 80% 55% at 50% 58%, #1b2656 0%, #111a40 55%, #0a1230 100%); }}
  #halo {{ position: absolute; left: {ox:.0f}px; top: {oy:.0f}px; width: 900px; height: 900px; margin: -450px 0 0 -450px; border-radius: 50%;
           background: radial-gradient(closest-side, rgba(241,212,143,.22), rgba(241,212,143,0)); }}
  #map {{ position: absolute; left: {MX}px; top: {MY}px; width: 445px; height: 920px; overflow: visible; }}
  #map .top {{ fill: url(#gg); stroke: #fff0c4; stroke-width: 1.6; stroke-linejoin: round; }}
  #map .edge {{ fill: none; stroke: #fff4d2; stroke-width: 3; stroke-dasharray: 1; stroke-linejoin: round; }}
  #map .route {{ fill: none; stroke: #ffffff; stroke-width: 3.2; stroke-dasharray: 1; stroke-linecap: round; filter: drop-shadow(0 0 5px rgba(255,255,255,.85)); }}
  #map .city circle {{ fill: #0d1638; stroke: #fff; stroke-width: 3; }}
  #map .city .ring {{ fill: none; stroke: #fff; stroke-width: 2; opacity: .55; }}
  #map .pk rect {{ fill: #f6dc9c; stroke: #6c501c; stroke-width: 1.5; }}
  #map .pk .tp {{ fill: #b88a3a; stroke: none; }}
  #orb {{ position: absolute; left: {ox:.0f}px; top: {oy:.0f}px; width: 64px; height: 64px; margin: -32px 0 0 -32px; border-radius: 50%;
          background: radial-gradient(circle at 38% 30%, #fff6d6 0%, #f3d589 16%, #d4ab55 45%, #a8802f 75%, #6e4f17 100%);
          box-shadow: 0 10px 30px rgba(0,0,0,.5), 0 0 40px rgba(241,212,143,.6); }}
  .pr {{ position: absolute; left: {ox:.0f}px; top: {oy:.0f}px; width: 64px; height: 64px; margin: -32px 0 0 -32px; border-radius: 50%; border: 3px solid rgba(241,212,143,.8); }}
  #onceLbl {{ position: absolute; left: {ox + 50:.0f}px; top: {oy - 34:.0f}px; font-weight: 700; font-size: 34px; color: #fff; text-shadow: 0 3px 14px rgba(0,0,0,.8); }}
  #onceLbl small {{ display: block; font-weight: 600; font-size: 26px; letter-spacing: .14em; color: #f1d48f; }}
  .cl {{ position: absolute; font-weight: 600; font-size: 30px; color: #fff; text-shadow: 0 2px 12px rgba(0,0,0,.95), 0 0 4px rgba(0,0,0,.9); white-space: nowrap; }}
  #h1 {{ position: absolute; left: 0; right: 0; top: 252px; text-align: center; font-weight: 600; font-size: 76px; letter-spacing: -.01em; }}
  #h2 {{ position: absolute; left: 0; right: 0; top: 330px; text-align: center; font-family: "Lora", serif; font-style: italic; font-weight: 700; font-size: 124px; color: #e3c27a; }}
  #h3 {{ position: absolute; left: 0; right: 0; top: 500px; text-align: center; }}
  #h3 span {{ display: inline-flex; align-items: center; gap: 16px; padding: 14px 30px; border-radius: 40px; border: 2px solid rgba(227,194,122,.6);
              background: rgba(13,22,56,.6); font-weight: 600; font-size: 38px; color: #f4efe3; }}
  #h3 i {{ width: 14px; height: 14px; border-radius: 50%; background: #f1d48f; box-shadow: 0 0 12px #f1d48f; display: inline-block; }}
  #cover {{ position: absolute; inset: 0; width: 100%; height: 100%; }}
  /* end card */
  #end {{ background: radial-gradient(ellipse 120% 70% at 50% 40%, #121c46 0%, #0b1330 70%); }}
  #warm {{ position: absolute; left: 540px; top: 1820px; width: 1100px; height: 700px; margin: -350px 0 0 -550px; border-radius: 50%;
           background: radial-gradient(closest-side, rgba(255,196,120,.28), rgba(255,196,120,0)); }}
  #eLogo {{ position: absolute; left: 260px; top: 300px; width: 560px; height: 290px; }}
  #e770 {{ position: absolute; left: 0; top: 20px; width: 340px; }}
  #eBox {{ position: absolute; left: 372px; top: 8px; width: 170px; height: 176px; }}
  #eImp {{ position: absolute; left: 120px; top: 222px; width: 330px; }}
  #eC {{ position: absolute; left: 0; right: 0; top: 700px; text-align: center; font-weight: 600; font-size: 62px; }}
  #eL {{ position: absolute; left: 0; right: 0; top: 790px; text-align: center; font-family: "Lora", serif; font-style: italic; font-weight: 700; font-size: 138px; color: #e3c27a; }}
  #eBtn {{ position: absolute; left: 140px; width: 800px; top: 1110px; height: 132px; border-radius: 70px; overflow: hidden;
           background: linear-gradient(180deg, #ffad3b, #f08a1c); box-shadow: 0 0 0 4px rgba(255,170,70,.25), 0 24px 60px -10px rgba(255,150,40,.6);
           display: flex; align-items: center; justify-content: center; gap: 22px; font-weight: 700; font-size: 50px; color: #0d1638; }}
  #eBtn svg {{ width: 62px; height: 62px; }}
  #eRing {{ position: absolute; left: 140px; width: 800px; top: 1110px; height: 132px; border-radius: 70px; border: 4px solid #ffad3b; opacity: 0; }}
  #eSw {{ position: absolute; top: -20%; bottom: -20%; left: -30%; width: 160px; transform: skewX(-18deg); background: linear-gradient(100deg, transparent, rgba(255,255,255,.55), transparent); }}
  #eTel {{ position: absolute; left: 0; right: 0; top: 1320px; text-align: center; font-weight: 700; font-size: 64px; }}
  #eEnv {{ position: absolute; left: 0; right: 0; top: 1420px; text-align: center; font-weight: 600; font-size: 30px; letter-spacing: .22em; color: rgba(244,239,227,.75); }}
</style>
</head>
<body>
<div id="root" data-composition-id="main" data-start="0" data-duration="{DUR}" data-width="1080" data-height="1920">
 <div class="L clip" data-start="0" data-duration="{DUR}" data-track-index="0">
  <div id="scene" class="L">
    <div id="bg" class="L"></div>
    <div id="halo"></div>
    <svg id="map" viewBox="0 0 445 920">
      <defs><linearGradient id="gg" x1="0" y1="0" x2="0.4" y2="1"><stop offset="0" stop-color="#f6dfa4"/><stop offset=".55" stop-color="#e0bb6c"/><stop offset="1" stop-color="#c79c4a"/></linearGradient></defs>
      <g id="extr">{extr}</g>
      <g id="topf"><path class="top" d="{gen['OUTLINE']}"/><path class="top" d="{gen['TDF']}"/></g>
      <path class="edge" id="edge1" d="{gen['OUTLINE']}" pathLength="1"/>
      {routes}
      {pk}
      {dots}
    </svg>
    <div class="pr" id="pr1"></div><div class="pr" id="pr2"></div>
    <div id="orb"></div>
    <div id="onceLbl"><small>DESDE</small>Once, CABA</div>
    {lab_html}
    <div id="h1">Hacemos envíos</div>
    <div id="h2">a todo el país</div>
    <div id="h3"><span><i></i>Directo desde nuestro local en Once</span></div>
  </div>

  <div id="end" class="L">
    <div id="warm"></div>
    <div id="eLogo"><img id="e770" src="assets/l770.png"/>
      <svg id="eBox" viewBox="0 0 52 54"><g fill="none" stroke="#c9a45c" stroke-width="2.6" stroke-linejoin="round"><path d="M26 3 L49 14 L49 40 L26 51 L3 40 L3 14 Z"/><path d="M3 14 L26 25 L49 14 M26 25 L26 51"/><path d="M14 8.5 L37 19.5 L37 30"/></g></svg>
      <img id="eImp" src="assets/limport.png"/></div>
    <div id="eC">Conocenos en Once</div>
    <div id="eL">Lavalle 2042</div>
    <div id="eRing"></div>
    <div id="eBtn"><svg viewBox="0 0 32 32"><path fill="#0d1638" d="M16 3C8.8 3 3 8.6 3 15.6c0 2.5.7 4.8 2 6.8L3.4 29l6.8-1.8c1.8 1 3.8 1.5 5.8 1.5 7.2 0 13-5.6 13-12.6S23.2 3 16 3zm0 23.2c-1.9 0-3.7-.5-5.2-1.4l-.4-.2-4 1 1.1-3.8-.3-.4c-1.1-1.6-1.6-3.4-1.6-5.3C5.6 10 10.3 5.4 16 5.4s10.4 4.6 10.4 10.4S21.7 26.2 16 26.2zm5.7-7.7c-.3-.2-1.9-.9-2.2-1s-.5-.2-.7.2-.8 1-1 1.2-.4.2-.7.1c-.3-.2-1.3-.5-2.5-1.5-.9-.8-1.5-1.8-1.7-2.1s0-.5.1-.6l.5-.6c.2-.2.2-.3.3-.6.1-.2 0-.4 0-.6l-1-2.3c-.3-.6-.5-.5-.7-.5h-.6c-.2 0-.6.1-.9.4s-1.2 1.1-1.2 2.7 1.2 3.1 1.4 3.4c.2.2 2.4 3.6 5.8 5 2.9 1.1 3.4.9 4.1.8.6-.1 1.9-.8 2.2-1.5.3-.7.3-1.4.2-1.5-.1-.2-.3-.3-.6-.4z"/></svg>Escribinos por WhatsApp<i id="eSw"></i></div>
    <div id="eTel">11 2614-5001</div>
    <div id="eEnv">ENVÍOS A TODO EL PAÍS</div>
  </div>

  <img id="cover" src="assets/f396.png"/>
 </div>
</div>
<script>
  gsap.registerPlugin(MotionPathPlugin);
  const tl = gsap.timeline({{ paused: true }});
  gsap.set("#end", {{ opacity: 0 }});
  gsap.set(["#orb", "#pr1", "#pr2"], {{ opacity: 0 }});

  // gold screen shrinks into the Once pin
  tl.fromTo("#cover", {{ clipPath: "circle(160% at {ox:.0f}px {oy:.0f}px)" }}, {{ clipPath: "circle(32px at {ox:.0f}px {oy:.0f}px)", duration: 0.6, ease: "power3.inOut" }}, 0.0);
  tl.set("#orb", {{ opacity: 1 }}, 0.58);
  tl.set("#cover", {{ opacity: 0 }}, 0.6);
  tl.fromTo("#orb", {{ scale: 1 }}, {{ scale: 0.75, duration: 0.5, ease: "back.out(3)" }}, 0.6);

  // map builds (extruded gold)
  tl.fromTo("#map", {{ scale: 1.08, transformOrigin: "{bax}px {bay}px" }}, {{ scale: 1, duration: 1.0, ease: "power3.out" }}, 0.1);
  tl.fromTo("#edge1", {{ strokeDashoffset: 1 }}, {{ strokeDashoffset: 0, duration: 0.8, ease: "power2.inOut" }}, 0.2);
  tl.fromTo(["#topf", "#extr"], {{ opacity: 0 }}, {{ opacity: 1, duration: 0.5, ease: "power2.out" }}, 0.45);
  tl.fromTo("#extr", {{ y: -12 }}, {{ y: 0, duration: 0.6, ease: "power3.out" }}, 0.45);
  tl.fromTo("#pr1", {{ opacity: 0.9, scale: 0.8 }}, {{ opacity: 0, scale: 4, duration: 1.0, ease: "power2.out", repeat: 2, immediateRender: false }}, 0.7);
  tl.fromTo("#pr2", {{ opacity: 0.9, scale: 0.8 }}, {{ opacity: 0, scale: 4, duration: 1.0, ease: "power2.out", repeat: 2, immediateRender: false }}, 1.2);
  tl.fromTo("#onceLbl", {{ opacity: 0, x: -16 }}, {{ opacity: 1, x: 0, duration: 0.35, ease: "power3.out" }}, 0.8);

  // headline (clear: hacemos envíos a todo el país, directo)
  tl.fromTo("#h1", {{ opacity: 0, y: 30 }}, {{ opacity: 1, y: 0, duration: 0.4, ease: "power3.out" }}, 0.45);
  tl.fromTo("#h2", {{ opacity: 0, y: 30 }}, {{ opacity: 1, y: 0, duration: 0.45, ease: "power3.out" }}, 0.65);
  tl.fromTo("#h3", {{ opacity: 0, y: 20 }}, {{ opacity: 1, y: 0, duration: 0.4, ease: "power3.out" }}, 1.0);

  // routes + packages from Once
  {js}
  {lab_js}

  // to end card
  tl.to("#scene", {{ opacity: 0, scale: 0.94, filter: "blur(10px)", duration: 0.35, ease: "power2.in" }}, 3.75);
  tl.to("#end", {{ opacity: 1, duration: 0.3 }}, 3.9);
  tl.fromTo("#eLogo", {{ opacity: 0, y: 40, scale: 0.92 }}, {{ opacity: 1, y: 0, scale: 1, duration: 0.6, ease: "back.out(1.6)" }}, 3.95);
  tl.fromTo("#eC", {{ opacity: 0, y: 24 }}, {{ opacity: 1, y: 0, duration: 0.4, ease: "power3.out" }}, 4.25);
  tl.fromTo("#eL", {{ opacity: 0, y: 30 }}, {{ opacity: 1, y: 0, duration: 0.45, ease: "power3.out" }}, 4.4);
  tl.fromTo("#eBtn", {{ opacity: 0, scale: 0.7 }}, {{ opacity: 1, scale: 1, duration: 0.55, ease: "back.out(2)" }}, 4.65);
  tl.fromTo("#eTel", {{ opacity: 0, y: 20 }}, {{ opacity: 1, y: 0, duration: 0.4, ease: "power3.out" }}, 4.85);
  tl.fromTo("#eEnv", {{ opacity: 0 }}, {{ opacity: 1, duration: 0.4 }}, 5.0);
  tl.fromTo("#eRing", {{ opacity: 0.9, scale: 1 }}, {{ opacity: 0, scale: 1.18, duration: 0.8, ease: "power2.out", repeat: 2, immediateRender: false }}, 5.2);
  tl.fromTo("#eSw", {{ x: 0 }}, {{ x: 1200, duration: 0.8, ease: "power2.inOut" }}, 5.4);

  window.__timelines = window.__timelines || {{}};
  window.__timelines["main"] = tl;
</script>
</body>
</html>
"""
open(os.path.join(HERE, "index.html"), "w", encoding="utf-8").write(html)
print("ok")
