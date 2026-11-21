"""Builds the LESH? site (site/index.html) from sources/*.json, schedule.json and posted.json.
One page, two kinds of view: the home view and one sources view per reel (#reel-001). Only reels that are live
on Instagram are listed, so a held or unposted reel never shows.
python3 site.py                 build site/
python3 site.py --preview DIR   build into DIR and treat every approved reel as live (for a mock)
"""
import json, os, sys, shutil, html, datetime

HERE = os.path.dirname(os.path.abspath(__file__))
COL = {"sun": "#FFC23A", "sky": "#5B8CFF", "gulf": "#2EC4B6", "rose": "#FF7EB6", "lime": "#B8F05A"}
MONTHS = "January February March April May June July August September October November December".split()
DAYS = "Monday Tuesday Wednesday Thursday Friday Saturday Sunday".split()
IG = "https://www.instagram.com/leshexplained/"
E = html.escape

def load(name, default):
    p = os.path.join(HERE, name)
    return json.load(open(p, encoding="utf-8")) if os.path.exists(p) else default

def when(iso):
    d = datetime.datetime.fromisoformat(iso.replace("Z", "+00:00"))
    if d.tzinfo: d = d.astimezone(datetime.timezone(datetime.timedelta(hours=4)))  # UAE time
    return d

def short(iso):
    d = when(iso); return "%d %s %d" % (d.day, MONTHS[d.month - 1][:3], d.year)

def spoken(iso):
    d = when(iso); h = d.hour % 12 or 12
    return "%s %d %s, %d%s %s UAE time" % (DAYS[d.weekday()], d.day, MONTHS[d.month - 1], h, (":%02d" % d.minute) if d.minute else "", "pm" if d.hour >= 12 else "am")

def facts_of(src): return [f for f in src["facts"] if not f.get("hold")]
def count_sources(src): return len({s["name"].split(",")[0].strip() for f in facts_of(src) for s in f["sources"]})
def plural(n, word): return "%d %s%s" % (n, word, "" if n == 1 else "s")

def card(src, live):
    cover = '<img src="covers/%s.jpg" alt="" width="96" height="171" loading="lazy">' % src["n"] if src.get("_cover") else '<span class="nocover"></span>'
    return """<a class="card" href="#reel-%s" style="--c:%s">%s<span class="ct"><span class="num">%s</span><strong>%s</strong>
<span class="meta">%s. %s.<br>Posted %s.</span></span></a>""" % (src["n"], COL.get(src.get("colour"), COL["sun"]), cover, src["n"], E(src["title"]),
        plural(len(facts_of(src)), "fact"), plural(count_sources(src), "source"), short(live["published_at"]))

def view(src, live, older, newer):
    rows = ""
    for f in facts_of(src):
        links = "".join("<li>%s</li>" % (('<a href="%s" rel="noopener" target="_blank">%s</a>' % (E(s["url"]), E(s["name"]))) if s.get("url") else E(s["name"])) for s in f["sources"])
        note = '<p class="fn">%s</p>' % E(f["note"]) if f.get("note") else ""
        rows += '<li><p class="said">%s</p><ul class="src">%s</ul>%s</li>' % (E(f["said"]), links, note)
    n = len(facts_of(src))
    cover = '<img class="cover" src="covers/%s.jpg" alt="" width="180" height="320">' % src["n"] if src.get("_cover") else ""
    watch = '<a class="btn" href="%s" rel="noopener" target="_blank">Watch the reel</a>' % E(live["permalink"]) if live.get("permalink") else ""
    note = '<p class="reelnote">%s</p>' % E(src["note"]) if src.get("note") else ""
    nav = ""
    for other, label in ((newer, "Newer reel"), (older, "Older reel")):
        if other: nav += '<a class="hop" href="#reel-%s" style="--c:%s"><span>%s</span><strong>%s</strong></a>' % (other["n"], COL.get(other.get("colour"), COL["sun"]), label, E(other["title"]))
    heading = "The %d facts in this reel, and where each one comes from" % n if n != 1 else "The fact in this reel, and where it comes from"
    return """<article id="reel-%s" class="view reel" style="--c:%s" data-title="%s">
<div class="rhead"><div class="wrap"><div class="bar"><a class="brand" href="#home" aria-label="LESH? home"><img src="lesh.png" alt="LESH?" width="91" height="30"></a><a class="back" href="#home">All reels</a></div>
<div class="rtop">%s<div><p class="num">Reel %s</p><h1>%s</h1><p class="meta">Posted %s. Sources checked %s.</p><p class="acts">%s<button class="btn copy" type="button">Copy link</button></p></div></div></div></div>
<div class="wrap rbody"><h2>%s</h2><ol class="facts">%s</ol>%s<div class="hops">%s</div></div>
</article>""" % (src["n"], COL.get(src.get("colour"), COL["sun"]), E(src["title"]) + " Sources. LESH?", cover, src["n"], E(src["title"]), short(live["published_at"]), short(src["checked"]),
                 watch, heading, rows, note, nav)

def build(out, preview=False):
    sched = load("schedule.json", {"posts": []}); posts = sched["posts"] if isinstance(sched, dict) else sched
    posted = load("posted.json", {}); fixes = load("corrections.json", [])
    shutil.rmtree(out, ignore_errors=True)   # start clean, so nothing stale is ever served
    shutil.copytree(os.path.join(HERE, "site_src"), out)
    os.makedirs(os.path.join(out, "covers"), exist_ok=True)
    eps, upcoming = [], []
    for p in posts:
        if p.get("kind") == "story": continue
        live = posted.get(p["id"])
        if not live and preview and p.get("approved"): live = {"published_at": p["publish_at"], "permalink": IG}
        if not live:
            if p.get("approved"): upcoming.append(p["publish_at"])
            continue
        sp = os.path.join(HERE, "sources", p["id"] + ".json")
        if not os.path.exists(sp): continue
        src = json.load(open(sp, encoding="utf-8"))
        if not live.get("published_at"): live = dict(live, published_at=p["publish_at"])
        c = os.path.join(HERE, "media", p.get("cover", ""))
        if p.get("cover") and os.path.exists(c): shutil.copy(c, os.path.join(out, "covers", src["n"] + ".jpg")); src["_cover"] = True
        eps.append((live["published_at"], src, live))
    eps.sort(key=lambda e: e[0], reverse=True)   # newest first
    if eps:
        reels = '<div class="reels">%s</div>' % "".join(card(s, l) for _, s, l in eps)
        views = "".join(view(s, l, eps[i + 1][1] if i + 1 < len(eps) else None, eps[i - 1][1] if i > 0 else None) for i, (_, s, l) in enumerate(eps))
        nxt = '<p class="next">Next reel: %s.</p>' % spoken(sorted(upcoming)[0]) if upcoming else ""
    else:
        first = sorted(upcoming)
        reels = '<div class="soon"><strong>%s</strong><span>Its sources land here the minute it posts.</span></div>' % (("First reel: %s." % spoken(first[0])) if first else "First reel coming soon.")
        views, nxt = "", ""
    fx = "".join("<li><b>%s</b> %s</li>" % (E(x["date"]), E(x["text"])) for x in fixes)
    fixes_html = '<ul class="fix">%s</ul>' % fx if fx else ""
    page = (TEMPLATE.replace("%%REELS%%", reels).replace("%%NEXT%%", nxt).replace("%%VIEWS%%", views).replace("%%FIXES%%", fixes_html)
            .replace("%%PREVIEW%%", '<p class="preview">Preview. The two approved reels are shown as if they were already posted.</p>' if preview else "")
            .replace("%%NONE%%", "" if fx else "None so far. ").replace("%%IG%%", IG).replace("%%YEAR%%", str(datetime.date.today().year)))
    open(os.path.join(out, "index.html"), "w", encoding="utf-8").write(page)
    print("site ok:", len(eps), "reel(s) listed ->", out)

TEMPLATE = r"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>LESH? Says who. Every reel and its sources</title>
<meta name="description" content="Every LESH? reel, and where each fact in it comes from.">
<meta property="og:title" content="LESH? Says who"><meta property="og:description" content="Every LESH? reel, and where each fact in it comes from."><meta property="og:image" content="og.png">
<link rel="icon" href="icon.png"><meta name="theme-color" content="#FFC23A">
<style>
@font-face{font-family:Readex;src:url(fonts/readex-pro-latin-500-normal.woff2) format("woff2");font-weight:500;font-display:swap;unicode-range:U+0000-00FF,U+2000-206F}
@font-face{font-family:Readex;src:url(fonts/readex-pro-latin-700-normal.woff2) format("woff2");font-weight:700;font-display:swap;unicode-range:U+0000-00FF,U+2000-206F}
@font-face{font-family:Readex;src:url(fonts/readex-pro-arabic-700-normal.woff2) format("woff2");font-weight:700;font-display:swap;unicode-range:U+0600-06FF,U+FE70-FEFF}
/* one visual world: Sun poster, white reading pages, Night depth. Things you can press are built like the mark. */
:root{color-scheme:light;--sun:#FFC23A;--night:#0B0E13;--white:#fff;--ink2:#4C5361;--c:#FFC23A}
*{box-sizing:border-box}html{-webkit-text-size-adjust:100%}
body{margin:0;background:var(--white);color:var(--night);font:500 17px/1.5 Readex,system-ui,sans-serif;-webkit-font-smoothing:antialiased}
img{display:block;max-width:100%}a{color:inherit}h1,h2,p{margin:0}
.wrap{max-width:1040px;margin:0 auto;padding:0 20px}
.skip{position:absolute;left:-999px}.skip:focus{left:12px;top:12px;z-index:9;background:var(--white);padding:8px 12px;border:3px solid var(--night);border-radius:10px}
:focus-visible{outline:3px solid var(--night);outline-offset:3px}
[hidden]{display:none!important}

/* things you can press are built like the mark: a white face with Night depth */
.btn,.follow{display:inline-flex;align-items:center;font:700 16px/1 Readex,sans-serif;color:var(--night);background:var(--white);text-decoration:none;cursor:pointer;
  padding:13px 18px;border:3px solid var(--night);border-radius:14px;box-shadow:4px 4px 0 var(--night);transition:transform .08s,box-shadow .08s}
.btn:active,.follow:active{transform:translate(3px,3px);box-shadow:1px 1px 0 var(--night)}
.follow{font-size:14px;padding:10px 14px;border-radius:12px;box-shadow:3px 3px 0 var(--night)}

.bar{display:flex;align-items:center;justify-content:space-between;padding:16px 0}
.brand img{height:30px;width:auto}

/* home: the poster */
.hero{background:var(--sun);border-bottom:3px solid var(--night);overflow:hidden}
.stage{text-align:center;padding:10px 0 46px}
.stage h1{font:700 clamp(54px,17.6vw,176px)/1 Readex,sans-serif;white-space:nowrap;letter-spacing:-.045em;margin-top:8px;height:.98em;display:flex;align-items:center;justify-content:center;position:relative;z-index:1}
.stage h1 [lang=ar]{letter-spacing:0;font-size:.84em;line-height:1;padding-bottom:.1em}
.vh{position:absolute;width:1px;height:1px;overflow:hidden;clip-path:inset(50%)}
.mark{position:relative;width:min(66vw,360px);aspect-ratio:1;margin:-3vw auto 0;touch-action:pan-y;-webkit-user-select:none;user-select:none}
.mark-still{position:absolute;left:50%;top:50%;height:74%;width:auto;max-width:none;transform:translate(-46%,-50%);cursor:pointer}
.mark-canvas{position:absolute;inset:0;cursor:grab;outline-offset:-6px}.mark.held .mark-canvas{cursor:grabbing}
.mark.live .mark-still{visibility:hidden}
.hint{display:inline-block;font-weight:700;font-size:14px;background:var(--night);color:var(--white);padding:6px 12px;border-radius:99px;margin-top:-6px;transition:opacity .3s}
.hint.gone{opacity:0}
.lead{font-size:clamp(19px,2.4vw,24px);line-height:1.35;max-width:21em;margin:18px auto 0;text-wrap:balance}

.home h2,.rbody h2{font:700 clamp(28px,4.2vw,40px)/1.1 Readex,sans-serif;letter-spacing:-.025em}
.block{padding-top:44px;padding-bottom:8px}
.reels{display:grid;gap:22px;margin-top:22px;grid-template-columns:repeat(auto-fill,minmax(min(100%,400px),1fr))}
.card{display:grid;grid-template-columns:96px 1fr;gap:16px;align-items:center;padding:14px 18px 14px 14px;background:var(--c);text-decoration:none;
  border:3px solid var(--night);border-radius:22px;box-shadow:6px 6px 0 var(--night);transition:transform .08s,box-shadow .08s}
.card:active{transform:translate(4px,4px);box-shadow:2px 2px 0 var(--night)}
.card img,.nocover{width:96px;aspect-ratio:9/16;object-fit:cover;border:3px solid var(--night);border-radius:12px;background:var(--white)}
.ct{display:block}.num{font-weight:700;font-size:15px;letter-spacing:.04em}
.card strong{display:block;font:700 24px/1.12 Readex,sans-serif;letter-spacing:-.02em;margin:2px 0 10px;text-wrap:balance}
.meta{font-size:15px;line-height:1.4}
.next{color:var(--ink2);margin-top:26px}
.soon{margin-top:22px;padding:24px;border:3px solid var(--night);border-radius:22px;background:var(--sun);box-shadow:6px 6px 0 var(--night)}
.soon strong{display:block;font:700 26px/1.15 Readex,sans-serif;letter-spacing:-.02em}.soon span{display:block;margin-top:8px}

.how{background:var(--night);color:var(--white);margin-top:60px;padding:54px 0 58px}
.how :focus-visible{outline-color:var(--sun)}
.steps{display:grid;gap:26px 44px;margin-top:26px;grid-template-columns:repeat(auto-fit,minmax(min(100%,260px),1fr))}
.steps h3{font:700 22px/1.2 Readex,sans-serif;color:var(--sun);margin:0 0 6px}
.steps p{color:#D9D4C8}
.ask{padding-top:54px;padding-bottom:10px}.ask p{font-size:19px;max-width:26em;margin:10px 0 22px}
.fixes{padding-top:44px;padding-bottom:64px}.fixes p{max-width:34em;margin-top:10px}.fix{padding-left:20px}
.fixes a,.src a{text-decoration:underline;text-decoration-color:var(--sun);text-decoration-thickness:3px;text-underline-offset:4px;text-decoration-skip-ink:none}

/* a reel's own view takes the colour of its reel */
.rhead{background:var(--c);border-bottom:3px solid var(--night);padding-bottom:34px}
.back{font-weight:700;text-decoration:none;padding:8px 0 8px 22px;position:relative}
.back:before{content:"";position:absolute;left:4px;top:50%;width:9px;height:9px;border-left:3px solid var(--night);border-bottom:3px solid var(--night);transform:translateY(-50%) rotate(45deg)}
.rtop{display:grid;grid-template-columns:auto 1fr;gap:20px;align-items:start;margin-top:14px}
.rtop .cover{width:clamp(104px,22vw,180px);height:auto;aspect-ratio:9/16;object-fit:cover;border:3px solid var(--night);border-radius:14px;box-shadow:5px 5px 0 var(--night)}
.rtop h1{font:700 clamp(30px,6.4vw,64px)/1.02 Readex,sans-serif;letter-spacing:-.035em;margin:4px 0 12px;text-wrap:balance}
.acts{display:flex;flex-wrap:wrap;gap:12px;margin-top:18px}
.rbody{padding-top:40px;padding-bottom:56px}.rbody>*{max-width:760px}.rbody>.hops{max-width:none}
.facts{list-style:none;margin:18px 0 0;padding:0;counter-reset:f}
.facts>li{counter-increment:f;position:relative;padding:20px 0 20px 46px;border-top:3px solid var(--night)}
.facts>li:before{content:counter(f);position:absolute;left:0;top:19px;width:30px;height:30px;border-radius:50%;background:var(--night);color:var(--white);font-weight:700;font-size:14px;line-height:30px;text-align:center}
.said{font-weight:700;font-size:20px;line-height:1.3;text-wrap:pretty}
.src{list-style:none;margin:8px 0 0;padding:0;color:var(--ink2);font-size:16px}.src li{margin-top:4px}.src a{color:var(--night)}
.fn,.reelnote{color:var(--ink2);font-size:15px;margin-top:8px}
.reelnote{border-top:3px solid var(--night);padding-top:18px;margin-top:0}
.hops{display:grid;gap:18px;margin-top:40px;grid-template-columns:repeat(auto-fit,minmax(min(100%,300px),1fr))}
.hop{display:block;background:var(--c);padding:14px 18px;text-decoration:none;border:3px solid var(--night);border-radius:18px;box-shadow:5px 5px 0 var(--night);transition:transform .08s,box-shadow .08s}
.hop:active{transform:translate(3px,3px);box-shadow:2px 2px 0 var(--night)}
.hop span{font-size:14px;font-weight:700}.hop strong{display:block;font:700 20px/1.15 Readex,sans-serif;letter-spacing:-.02em}

.preview{background:var(--night);color:var(--white);font-size:13px;text-align:center;padding:7px 12px}
footer{background:var(--night);color:#B9B4A8;font-size:14px;padding:34px 0 56px}
footer img{height:26px;width:auto;margin-bottom:14px}footer p{max-width:44em}
footer nav{display:flex;gap:22px;margin-top:16px}footer nav a{color:var(--white);font-weight:700}footer :focus-visible{outline-color:var(--sun)}
.doc .rhead{background:var(--sun)}.doc h1{font:700 clamp(40px,9vw,84px)/1 Readex,sans-serif;letter-spacing:-.04em;margin:22px 0 8px}
.prose h2{font-size:24px;margin-top:34px}.prose h2:first-child{margin-top:0}.prose p{margin-top:10px;max-width:38em}.prose a{text-decoration:underline;text-decoration-color:var(--sun);text-decoration-thickness:3px;text-underline-offset:4px;text-decoration-skip-ink:none}
.prose .ar{margin-top:44px;padding-top:30px;border-top:3px solid var(--night);font-weight:700;line-height:1.9}.prose .ar h2{margin-top:0}.prose .ar p{font-weight:700;max-width:34em}
@media (min-width:760px){.stage{padding-bottom:64px}.mark{margin-top:-34px}.card{grid-template-columns:118px 1fr;padding:16px 22px 16px 16px}.card img,.nocover{width:118px}.card strong{font-size:28px}}
@media (prefers-reduced-motion:reduce){*{transition:none!important}}
</style></head>
<body class="nojs">
<a class="skip" href="#main">Skip to the reels</a>%%PREVIEW%%
<main id="main">
<section id="home" class="view home" data-title="LESH? Says who. Every reel and its sources">
  <div class="hero"><div class="wrap">
    <div class="bar"><a class="brand" href="#home" aria-label="LESH? home"><img src="lesh.png" alt="LESH?" width="91" height="30"></a><a class="follow" href="%%IG%%" rel="noopener" target="_blank">Follow on Instagram</a></div>
    <div class="stage">
      <h1 id="hl"><span class="en">Says who</span><span class="ar" lang="ar" dir="rtl" hidden>مين قال</span><span class="vh">?</span></h1>
      <div class="mark" id="mark"><img class="mark-still" id="still" src="mark-en.png" alt="" width="475" height="720"></div>
      <p class="hint" id="hint">Spin it</p>
      <p class="lead">Every LESH? reel, and where each fact in it comes from.</p>
    </div>
  </div></div>
  <div class="wrap block"><h2>The reels</h2>%%REELS%%%%NEXT%%</div>
  <div class="how"><div class="wrap"><h2>How a fact gets in</h2><div class="steps">
    <div><h3>The topic comes first</h3><p>We explain public things: roads, trains, buildings, bills. Politics, religion and anything to do with security stay out.</p></div>
    <div><h3>Then every number is traced</h3><p>Each one goes back to an official body or a named publication. When sources disagree, we say so. If we can't source it, it doesn't go in.</p></div>
    <div><h3>The pictures are drawn</h3><p>No real people and no real footage. Drawings show how a thing works, so they are not to scale.</p></div>
  </div></div></div>
  <div class="wrap ask"><h2>Got a lesh?</h2><p>Lesh means why. Comment yours on any reel, and the good ones become episodes.</p><a class="btn" href="%%IG%%" rel="noopener" target="_blank">Open Instagram</a></div>
  <div class="wrap fixes"><h2>Corrections</h2><p>%%NONE%%Spotted a mistake? Message <a href="%%IG%%" rel="noopener" target="_blank">@leshexplained</a> on Instagram. We fix it and list it here.</p>%%FIXES%%</div>
</section>
%%VIEWS%%
<article id="privacy" class="view doc" data-title="Privacy. LESH?">
<div class="rhead"><div class="wrap"><div class="bar"><a class="brand" href="#home" aria-label="LESH? home"><img src="lesh.png" alt="LESH?" width="91" height="30"></a><a class="back" href="#home">All reels</a></div>
<h1>Privacy</h1><p class="meta">Last updated 21 November 2026.</p></div></div>
<div class="wrap rbody prose">
<h2>The short version</h2>
<p>This site does not ask who you are and does not follow you around. There are no accounts, no forms, no cookies, no analytics, no ads and no tracking pixels. The fonts, pictures and scripts all come from this site itself.</p>
<h2>What the site collects</h2>
<p>Nothing that you type or submit, because there is nothing to submit here.</p>
<p>Like every website, the company that hosts this one receives your IP address and basic details of each request, such as the page asked for, the time and the type of browser. That is needed to deliver the page and keep it secure. We do not use it to identify you or to build a profile.</p>
<h2>Comments on Instagram</h2>
<p>We read the public comments on our own reels to find questions worth answering. We keep the text of a comment and when it was posted. We do not keep the username. If a comment becomes an episode, we do not name the person who wrote it unless they say we can.</p>
<h2>If you contact us</h2>
<p>If you message <a href="%%IG%%" rel="noopener" target="_blank">@leshexplained</a> or write to leshexplained@gmail.com, we see what you send and the account or address you sent it from. We use it to reply and to fix mistakes. We do not sell it or pass it on.</p>
<h2>Other sites</h2>
<p>Links to Instagram and to our sources take you to sites run by other people. Their own privacy rules apply there.</p>
<h2>Your choices</h2>
<p>You can ask what we hold that relates to you, and ask us to correct it or delete it. Message us and we will answer within 30 days.</p>
<h2>Changes</h2>
<p>If the site ever starts using anything that is not described here, this page changes first, and the date at the top changes with it.</p>
<div lang="ar" dir="rtl" class="ar"><h2>بالعربية</h2>
<p>هذا الموقع لا يطلب منك أي بيانات ولا يتتبعك. لا توجد حسابات ولا نماذج ولا ملفات تعريف الارتباط ولا أدوات تحليل ولا إعلانات. تستقبل شركة الاستضافة عنوان الإنترنت الخاص بك وبيانات الطلب الأساسية لعرض الصفحة وحمايتها فقط، ولا نستخدمها لتحديد هويتك.</p>
<p>نقرأ التعليقات العامة على مقاطعنا في إنستغرام لنختار الأسئلة، ونحتفظ بنص التعليق دون اسم صاحبه. إذا راسلتنا نستخدم رسالتك للرد وتصحيح الأخطاء فقط، ولا نبيعها ولا نشاركها. يمكنك أن تطلب معرفة ما نحتفظ به عنك أو تصحيحه أو حذفه في أي وقت.</p></div>
</div></article>
<article id="terms" class="view doc" data-title="Terms. LESH?">
<div class="rhead"><div class="wrap"><div class="bar"><a class="brand" href="#home" aria-label="LESH? home"><img src="lesh.png" alt="LESH?" width="91" height="30"></a><a class="back" href="#home">All reels</a></div>
<h1>Terms</h1><p class="meta">Last updated 21 November 2026.</p></div></div>
<div class="wrap rbody prose">
<h2>What LESH? is</h2>
<p>LESH? makes short explainers about how things in the UAE work. They are general information for curious people. They are not legal, financial, engineering or safety advice, so please do not make decisions that matter based on a one minute reel.</p>
<h2>Accuracy</h2>
<p>Every fact is checked against the sources listed on this site on the date shown. Things change, and sources sometimes disagree. When we get something wrong, we fix it and list the fix under Corrections.</p>
<h2>Independent</h2>
<p>LESH? is not affiliated with, endorsed by or speaking for any government body, authority or company. Names and trade marks belong to their owners and appear only to explain how something works.</p>
<h2>No advertising</h2>
<p>LESH? carries no advertising, sponsorship or paid placement. If that ever changes, it will be labelled clearly and this page will say so.</p>
<h2>Drawings and voice</h2>
<p>Everything on screen is drawn to show how a thing works. Drawings are not to scale, are not real footage and are not plans of real sites. The narration uses an AI voice, and every reel carries Instagram's AI label.</p>
<h2>Using our work</h2>
<p>The reels, drawings and words are ours. Share them freely with credit to @leshexplained. Please do not repost them as your own or use them to sell something without asking first. The sources we link to belong to their publishers.</p>
<h2>Concerns</h2>
<p>If you think something here is wrong, unfair to you or should not be shown, message <a href="%%IG%%" rel="noopener" target="_blank">@leshexplained</a> or write to leshexplained@gmail.com. We read everything and act quickly.</p>
<h2>Law</h2>
<p>LESH? is run from the United Arab Emirates and these terms follow UAE law.</p>
</div></article>
</main>
<footer><div class="wrap"><img src="lesh-night.png" alt="LESH?" width="80" height="26"><p>LESH? is an independent explainer page. It is not affiliated with any government body or company named here. Narration uses an AI voice, and every reel carries Instagram's AI label. © %%YEAR%% LESH?</p><nav aria-label="Legal"><a href="#privacy">Privacy</a><a href="#terms">Terms</a></nav></div></footer>
<script>
(function(){
  var b=document.body;b.className="js";
  var views=[].slice.call(document.querySelectorAll(".view")),home=document.getElementById("home"),first=true;
  function route(){
    var id=(location.hash||"").slice(1),el=id&&document.getElementById(id),act=el&&el.classList.contains("view")?el:home;
    views.forEach(function(v){v.hidden=v!==act});document.title=act.getAttribute("data-title");
    if(el&&act===home&&el!==home){el.scrollIntoView()}else if(!first){window.scrollTo(0,0)}
    first=false;
  }
  window.addEventListener("hashchange",route);route();
  [].forEach.call(document.querySelectorAll(".copy"),function(btn){btn.addEventListener("click",function(){
    var done=function(){btn.textContent="Link copied";setTimeout(function(){btn.textContent="Copy link"},1800)};
    try{navigator.clipboard.writeText(location.href).then(done,function(){btn.textContent="Copy it from the address bar"})}catch(e){btn.textContent="Copy it from the address bar"}
  })});
  // the mark: front is ?, back is the Arabic mark, and the headline follows it
  var host=document.getElementById("mark"),still=document.getElementById("still"),hint=document.getElementById("hint"),hl=document.getElementById("hl");
  function side(s){var ar=s==="back";hl.querySelector(".en").hidden=ar;hl.querySelector(".ar").hidden=!ar;hl.querySelector(".vh").textContent=ar?"؟":"?"}
  function used(){hint.className="hint gone"}
  var flat="front";still.addEventListener("click",function(){flat=flat==="front"?"back":"front";still.src=flat==="back"?"mark-ar.png":"mark-en.png";side(flat);used()});
  window.addEventListener("load",function(){var s=document.createElement("script");s.src="mark.js";s.onload=function(){
    try{var calm=window.matchMedia&&matchMedia("(prefers-reduced-motion: reduce)").matches;if(window.LeshMark&&LeshMark.mount(host,{calm:calm,onside:side,onuse:used}))host.className="mark live"}catch(e){}
  };document.head.appendChild(s)});
})();
</script>
</body></html>
"""

if __name__ == "__main__":
    if len(sys.argv) > 2 and sys.argv[1] == "--preview": build(sys.argv[2], preview=True)
    else: build(os.path.join(HERE, "site"))
