#!/data/data/com.termux/files/usr/bin/python
"""
COSMO server: the part of COSMO that lives on the phone.

Runs in Termux with the Python standard library only (no pip installs).
Listens on 127.0.0.1:8080, so only apps on this phone can reach it.

    Browser (JARVIS page) ──► this server ──► AI engine: laptop Ollama, else phone Ollama
                                   │
                                   ├── data/*.json   brain, memories, chat, monitor (on the phone)
                                   ├── internet      news feeds, weather, Gumroad, GitHub
                                   ├── termux-api    notifications, torch, volume, voice …
                                   └── scheduler     morning briefing, nudge, evening recap

Settings live in config.json next to this file (created on first run).
"""
import datetime as dt
import html
import socket
import json
import os
import re
import shutil
import subprocess
import sys
import threading
import time
import urllib.parse
import urllib.request
import uuid
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor
from email.utils import parsedate_to_datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")
CONFIG_PATH = os.path.join(HERE, "config.json")
TZ = dt.timezone(dt.timedelta(hours=8))  # Malaysia time, no daylight saving
UA = "Mozilla/5.0 (Linux; Android) COSMO/1.0"
os.makedirs(DATA, exist_ok=True)

# Mobile networks often advertise IPv6 that doesn't actually work, so every
# request waits for an IPv6 timeout before trying IPv4. Try IPv4 first.
_getaddrinfo = socket.getaddrinfo


def _ipv4_first(*args, **kw):
    res = _getaddrinfo(*args, **kw)
    return sorted(res, key=lambda r: r[0] != socket.AF_INET)


socket.getaddrinfo = _ipv4_first

DEFAULT_CONFIG = {
    "port": 8080,
    # Tried in order. The first one that answers with at least one model wins.
    "engines": [
        {"name": "Laptop", "url": "", "model": "qwen2.5:7b"},
        {"name": "Phone", "url": "http://127.0.0.1:11434", "model": "auto"},
    ],
    "city": {"name": "Alor Setar", "lat": 6.1248, "lon": 100.3678},
    # Named outlets only. COSMO may summarise these headlines but never invents news.
    "feeds": [
        {"source": "BBC World", "cat": "world", "url": "https://feeds.bbci.co.uk/news/world/rss.xml"},
        {"source": "Al Jazeera", "cat": "world", "url": "https://www.aljazeera.com/xml/rss/all.xml"},
        {"source": "Free Malaysia Today", "cat": "malaysia", "url": "https://www.freemalaysiatoday.com/feed/"},
        {"source": "Malay Mail", "cat": "malaysia", "url": "https://www.malaymail.com/feed/rss/malaysia"},
        {"source": "BBC Technology", "cat": "tech", "url": "https://feeds.bbci.co.uk/news/technology/rss.xml"},
        {"source": "The Verge", "cat": "tech", "url": "https://www.theverge.com/rss/index.xml"},
        {"source": "TechCrunch", "cat": "tech", "url": "https://techcrunch.com/feed/"},
        {"source": "Hacker News", "cat": "tech", "url": "https://hnrss.org/frontpage"},
    ],
    "gumroad_token": "",          # optional: Gumroad → Settings → Advanced → Applications → access token
    "github_user": "mrvenkham",   # public activity only, no token needed
    "notifications": True,
    "schedule": {"briefing": "06:45", "nudge": "16:30", "recap": "21:30",
                 "quiet_start": "22:30", "quiet_end": "06:30"},
    "chat_turns": 16,
}


# ───────────────────────── storage ─────────────────────────
_lock = threading.RLock()


def read_json(path, default):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return default


def write_json(path, value):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(value, f, ensure_ascii=False, indent=1)
    os.replace(tmp, path)  # atomic: a crash never leaves half a file


def data_path(name):
    return os.path.join(DATA, name + ".json")


def load(name, default):
    with _lock:
        return read_json(data_path(name), default)


def save(name, value):
    with _lock:
        write_json(data_path(name), value)


def merge(base, extra):
    out = dict(base)
    for k, v in (extra or {}).items():
        out[k] = merge(base[k], v) if isinstance(v, dict) and isinstance(base.get(k), dict) else v
    return out


def load_config():
    cfg = merge(DEFAULT_CONFIG, read_json(CONFIG_PATH, {}))
    if not os.path.exists(CONFIG_PATH):
        write_json(CONFIG_PATH, cfg)
    return cfg


CFG = load_config()


def now():
    return dt.datetime.now(TZ)


def log(*a):
    print(now().strftime("%H:%M:%S"), *a, flush=True)


# ───────────────────────── http helpers ─────────────────────────
def http_get(url, timeout=8):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def http_json(url, body=None, timeout=8):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, headers={"User-Agent": UA, "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read() or b"{}")


class Cache:
    """Remembers a value for `ttl` seconds so the internet isn't hit on every request.
    `peek` never makes the page wait once there is any value: it returns what it has
    (even if old) and refreshes in the background. Values can be kept on disk."""

    def __init__(self, ttl, disk=None):
        self.ttl, self.t, self.v, self.lock, self.disk, self.busy = ttl, 0, None, threading.Lock(), disk, False
        if disk:
            saved = load(disk, None)
            if saved:
                self.v, self.t = saved.get("v"), saved.get("t", 0)

    def get(self, fn, force=False):
        with self.lock:
            if force or self.v is None or time.time() - self.t > self.ttl:
                self.v, self.t = fn(), time.time()
                if self.disk:
                    save(self.disk, {"v": self.v, "t": self.t})
            return self.v

    def peek(self, fn):
        if self.v is None:
            return self.get(fn)
        if time.time() - self.t > self.ttl and not self.busy:
            self.busy = True

            def refresh():
                try:
                    self.get(fn, force=True)
                finally:
                    self.busy = False
            threading.Thread(target=refresh, daemon=True).start()
        return self.v


# ───────────────────────── AI engine ─────────────────────────
_engine = {"t": 0, "e": None, "warm": None}


def pick_engine(force=False):
    if not force and time.time() - _engine["t"] < 20:
        return _engine["e"]
    found, status = None, []
    for e in CFG["engines"]:
        if not e.get("url"):
            status.append({"name": e["name"], "url": "", "up": False})
            continue
        try:
            names = [m["name"] for m in http_json(e["url"].rstrip("/") + "/api/tags", timeout=2.5).get("models", [])]
        except Exception:
            names = []
        status.append({"name": e["name"], "url": e["url"], "up": bool(names)})
        if names and not found:
            model = e["model"] if e["model"] in names else names[0]
            found = {"name": e["name"], "url": e["url"].rstrip("/"), "model": model, "models": names}
    _engine.update(t=time.time(), e=found, status=status)
    if found and _engine["warm"] != (found["url"], found["model"]):
        _engine["warm"] = (found["url"], found["model"])
        threading.Thread(target=warm, args=(found,), daemon=True).start()
    return found


def warm(e):
    """Load the model into memory now and keep it there, so the first question isn't slow."""
    try:
        http_json(e["url"] + "/api/generate", {"model": e["model"], "keep_alive": "30m"}, timeout=180)
        log("model ready:", e["name"], e["model"])
    except Exception as ex:
        log("warm failed:", ex)


def ollama_chat(messages, stream=False, num_predict=260, timeout=300):
    e = pick_engine()
    if not e:
        raise RuntimeError("No AI engine is running. Start it with: cosmo")
    body = {"model": e["model"], "messages": messages, "stream": stream, "keep_alive": "30m",
            "options": {"temperature": 0.7, "num_ctx": 4096 if e["name"] == "Laptop" else 2048,
                        "num_predict": num_predict}}
    req = urllib.request.Request(e["url"] + "/api/chat", data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"})
    return e, urllib.request.urlopen(req, timeout=timeout)


def ollama_once(messages, num_predict=400):
    e, r = ollama_chat(messages, stream=False, num_predict=num_predict)
    with r:
        return json.loads(r.read()).get("message", {}).get("content", "").strip()


# ───────────────────────── world: news, weather, pulse ─────────────────────────
def _text(el, tag):
    x = el.find(tag)
    return (x.text or "").strip() if x is not None and x.text else ""


def _clean(s):
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", s or ""))).strip()


def parse_feed(raw, source, cat):
    root = ET.fromstring(raw)
    items = []
    atom = "{http://www.w3.org/2005/Atom}"
    nodes = root.findall(".//item") or root.findall(f".//{atom}entry")
    for n in nodes[:8]:
        title = _clean(_text(n, "title") or _text(n, f"{atom}title"))
        link = _text(n, "link")
        if not link:
            le = n.find(f"{atom}link")
            link = le.get("href", "") if le is not None else ""
        when = _text(n, "pubDate") or _text(n, f"{atom}updated") or _text(n, f"{atom}published")
        ts = None
        try:
            ts = parsedate_to_datetime(when).timestamp()
        except Exception:
            try:
                ts = dt.datetime.fromisoformat(when.replace("Z", "+00:00")).timestamp()
            except Exception:
                pass
        if title and link.startswith("http"):
            items.append({"source": source, "cat": cat, "title": title[:220], "link": link, "ts": ts})
    return items


def fetch_news():
    def one(f):
        try:
            return parse_feed(http_get(f["url"], timeout=6), f["source"], f["cat"]), None
        except Exception as ex:
            return [], f"{f['source']}: {type(ex).__name__}"

    t0 = time.time()
    with ThreadPoolExecutor(max_workers=max(1, len(CFG["feeds"]))) as pool:
        results = list(pool.map(one, CFG["feeds"]))
    log(f"news: {sum(len(r) for r, _ in results)} headlines in {time.time() - t0:.1f}s", *[e for _, e in results if e])
    items = [i for r, _ in results for i in r]
    cutoff = time.time() - 3 * 86400  # nothing older than 3 days
    items = [i for i in items if not i["ts"] or i["ts"] > cutoff]
    items.sort(key=lambda i: i["ts"] or 0, reverse=True)
    return {"items": items, "errors": [e for _, e in results if e], "fetched": time.time()}


WMO = {0: "clear", 1: "mostly clear", 2: "partly cloudy", 3: "overcast", 45: "fog", 48: "fog",
       51: "light drizzle", 53: "drizzle", 55: "heavy drizzle", 61: "light rain", 63: "rain", 65: "heavy rain",
       80: "rain showers", 81: "heavy showers", 82: "violent showers", 95: "thunderstorm",
       96: "thunderstorm with hail", 99: "thunderstorm with hail"}


def fetch_weather():
    c = CFG["city"]
    q = urllib.parse.urlencode({
        "latitude": c["lat"], "longitude": c["lon"], "timezone": "Asia/Kuala_Lumpur", "forecast_days": 1,
        "current": "temperature_2m,apparent_temperature,weather_code,precipitation",
        "daily": "temperature_2m_max,temperature_2m_min,precipitation_probability_max,weather_code"})
    try:
        j = json.loads(http_get("https://api.open-meteo.com/v1/forecast?" + q, timeout=8))
        cur, day = j["current"], j["daily"]
        return {"ok": True, "city": c["name"], "temp": round(cur["temperature_2m"]),
                "feels": round(cur["apparent_temperature"]), "now": WMO.get(cur["weather_code"], "mixed"),
                "high": round(day["temperature_2m_max"][0]), "low": round(day["temperature_2m_min"][0]),
                "rain_chance": day["precipitation_probability_max"][0], "source": "Open-Meteo"}
    except Exception as ex:
        return {"ok": False, "city": c["name"], "error": type(ex).__name__}


def fetch_pulse():
    out = {"gumroad": {"connected": bool(CFG.get("gumroad_token"))}, "github": {}}
    today = now().date()
    if CFG.get("gumroad_token"):
        try:
            after = (today - dt.timedelta(days=7)).isoformat()
            j = http_json("https://api.gumroad.com/v2/sales?" + urllib.parse.urlencode(
                {"access_token": CFG["gumroad_token"], "after": after}), timeout=10)
            sales = j.get("sales", [])

            def day_of(s):
                return dt.datetime.fromisoformat(s["created_at"].replace("Z", "+00:00")).astimezone(TZ).date()

            t = [s for s in sales if day_of(s) == today]
            out["gumroad"].update(ok=True, today=len(t), week=len(sales),
                                  today_rev=sum(s.get("price", 0) for s in t) / 100,
                                  week_rev=sum(s.get("price", 0) for s in sales) / 100,
                                  last=sales[0].get("product_name") if sales else None)
        except Exception as ex:
            out["gumroad"].update(ok=False, error=type(ex).__name__)
    if CFG.get("github_user"):
        try:
            ev = json.loads(http_get(f"https://api.github.com/users/{CFG['github_user']}/events/public", timeout=8))
            pushes = [e for e in ev if e.get("type") == "PushEvent"]
            last = dt.datetime.fromisoformat(pushes[0]["created_at"].replace("Z", "+00:00")).astimezone(TZ) if pushes else None
            out["github"] = {"ok": True, "pushes_today": sum(
                1 for e in pushes if dt.datetime.fromisoformat(e["created_at"].replace("Z", "+00:00")).astimezone(TZ).date() == today),
                "last_push": last.isoformat() if last else None,
                "days_since": (today - last.date()).days if last else None}
        except Exception as ex:
            out["github"] = {"ok": False, "error": type(ex).__name__}
    return out


NEWS, WEATHER, PULSE = Cache(20 * 60, disk="news_cache"), Cache(30 * 60, disk="weather_cache"), Cache(15 * 60)


def news_cached_only():
    """Headlines without waiting on the network; refreshes in the background if stale."""
    if NEWS.v is None:
        threading.Thread(target=NEWS.get, args=(fetch_news,), daemon=True).start()
        return []
    return NEWS.peek(fetch_news).get("items", [])


# ───────────────────────── country news (globe) ─────────────────────────
# Google News search RSS gathers recent headlines from many outlets and names
# each outlet; links go through news.google.com to the original article.
_country_cache, _country_lock = {}, threading.Lock()


def fetch_country(name, force=False):
    name = re.sub(r"[^\w .,'()-]", "", name)[:60].strip()
    if not name:
        return {"name": "", "items": [], "error": "No country given."}
    key = name.lower()
    with _country_lock:
        hit = _country_cache.get(key)
        if hit and not force and time.time() - hit["fetched"] < 15 * 60:
            return hit
    items, err = [], None
    try:
        q = urllib.parse.urlencode({"q": f'"{name}" when:2d', "hl": "en-US", "gl": "US", "ceid": "US:en"})
        root = ET.fromstring(http_get("https://news.google.com/rss/search?" + q, timeout=6))
        for n in root.findall(".//item")[:12]:
            src_el = n.find("source")
            source = (src_el.text or "").strip() if src_el is not None else "Unknown outlet"
            title = _clean(_text(n, "title"))
            if source and title.endswith(" - " + source):
                title = title[: -len(source) - 3]
            ts = None
            try:
                ts = parsedate_to_datetime(_text(n, "pubDate")).timestamp()
            except Exception:
                pass
            link = _text(n, "link")
            if title and link.startswith("http"):
                items.append({"source": source, "title": title[:220], "link": link, "ts": ts})
    except Exception as ex:
        err = f"Google News: {type(ex).__name__}"
    if not items:  # fall back to the main feeds, matching the country by name
        pat = re.compile(r"\b" + re.escape(name.split(" (")[0]) + r"\b", re.I)
        items = [{k: i[k] for k in ("source", "title", "link", "ts")} for i in news_cached_only() if pat.search(i["title"])][:10]
    items.sort(key=lambda i: i["ts"] or 0, reverse=True)
    out = {"name": name, "items": items, "error": err if not items else None, "fetched": time.time()}
    with _country_lock:
        _country_cache[key] = out
        if len(_country_cache) > 60:
            _country_cache.pop(next(iter(_country_cache)))
    return out


def country_brief(name):
    data = fetch_country(name)
    if data.get("brief") and time.time() - data.get("brief_at", 0) < 30 * 60:
        return data
    if not data["items"]:
        data["brief"] = f"I couldn't find recent headlines about {data['name']}. Quiet news day, or no internet."
        return data
    heads = "\n".join(f"- ({i['source']}) {i['title']}" for i in data["items"][:10])
    prompt = (f"HEADLINES about {data['name']} from the last two days (the only facts you may use):\n{heads}\n\n"
              f"In plain text, under 90 words: what is happening in {data['name']} right now? "
              "Give 3 short bullets, each ending with its outlet in brackets. "
              "If the headlines disagree or are thin, say so. Do not add anything that is not in the headlines. "
              "No TASK, MEMORY or ACTION lines.")
    try:
        data["brief"] = ollama_once([{"role": "user", "content": prompt}], num_predict=220)
        data["brief_at"] = time.time()
    except Exception as ex:
        data["brief"] = f"The AI couldn't summarise right now ({type(ex).__name__}). The headlines below are live."
    return data


# ───────────────────────── brain, memory, monitor ─────────────────────────
def brain():
    return load("brain", [])


def brain_add(text, typ="task"):
    text = str(text).strip()[:280]
    if not text:
        return None
    with _lock:
        b = brain()
        n = {"id": uuid.uuid4().hex[:10], "text": text, "type": typ if typ in ("task", "note", "idea") else "task",
             "done": False, "at": time.time() * 1000}
        b.insert(0, n)
        save("brain", b)
    return n


def open_tasks():
    return [n for n in brain() if n["type"] == "task" and not n["done"]]


def memories():
    return load("memory", [])


def memory_add(fact):
    fact = str(fact).strip()[:200]
    if not fact:
        return False
    with _lock:
        m = memories()
        if any(fact.lower() == x["fact"].lower() for x in m):
            return False
        m.append({"fact": fact, "at": time.time()})
        save("memory", m[-60:])  # keep the newest 60
    return True


def monitor():
    return load("monitor", {"layout": 85, "recall": 12, "packs": 2, "devlog": 20})


# ───────────────────────── phone actions (safe list only) ─────────────────────────
APPS = {"tiktok": "https://www.tiktok.com/", "youtube": "https://www.youtube.com/",
        "instagram": "https://www.instagram.com/", "gumroad": "https://gumroad.com/dashboard",
        "github": "https://github.com/", "spotify": "https://open.spotify.com/",
        "gmail": "https://mail.google.com/", "maps": "https://maps.google.com/",
        "jarvis": "http://127.0.0.1:8080/"}


def has_api():
    return shutil.which("termux-torch") is not None


def run(cmd, inp=None, timeout=15):
    try:
        r = subprocess.run(cmd, input=inp, capture_output=True, text=True, timeout=timeout)
        return r.returncode == 0, (r.stdout or r.stderr).strip()
    except Exception as ex:
        return False, str(ex)


def act(raw):
    """Run one phone action. Anything not on this list is refused. No texts, calls or file deletion."""
    c = raw.strip().lower()
    if not has_api():
        return "Phone control needs Termux:API (F-Droid) and: pkg install termux-api"
    if m := re.match(r"^torch (on|off)$", c):
        run(["termux-torch", m[1]]); return f"Torch {m[1]}."
    if m := re.match(r"^volume (\d{1,2})$", c):
        v = max(0, min(15, int(m[1]))); run(["termux-volume", "music", str(v)]); return f"Media volume {v}/15."
    if m := re.match(r"^brightness (\d{1,3})%?$", c):
        p = max(0, min(100, int(m[1]))); run(["termux-brightness", str(round(p * 2.55))]); return f"Brightness {p}%."
    if c == "brightness auto":
        run(["termux-brightness", "auto"]); return "Brightness on auto."
    if c == "vibrate":
        run(["termux-vibrate", "-d", "300"]); return "Buzzed."
    if c == "battery":
        ok, out = run(["termux-battery-status"])
        try:
            b = json.loads(out); return f"Battery {b['percentage']}%, {b['status'].lower()}."
        except Exception:
            return "Couldn't read the battery."
    if m := re.match(r"^open (\w+)$", c):
        url = APPS.get(m[1])
        if not url:
            return f"I can open: {', '.join(APPS)}."
        run(["termux-open-url", url]); return f"Opening {m[1]}."
    if m := re.match(r"^say (.{1,300})$", raw.strip(), re.I):
        threading.Thread(target=run, args=(["termux-tts-speak", m[1]],), daemon=True).start(); return "Speaking."
    if m := re.match(r"^copy (.{1,1000})$", raw.strip(), re.I | re.S):
        run(["termux-clipboard-set"], inp=m[1]); return "Copied to clipboard."
    return "Not on my allowed list. I can do: torch on/off, volume 0-15, brightness 0-100, vibrate, battery, open <app>, say <text>, copy <text>."


def notify(title, content, path="/"):
    if not CFG.get("notifications") or not has_api():
        return
    run(["termux-notification", "--id", "cosmo", "--title", title, "--content", content[:400],
         "--action", f"termux-open-url http://127.0.0.1:{CFG['port']}{path}", "--priority", "high"])
    log("notified:", title)


# ───────────────────────── COSMO's mind ─────────────────────────
SYSTEM = """You are COSMO, a sharp, direct, slightly witty personal coach, like Jarvis, living on the user's phone.
The user is a 16-year-old developer and creator in Malaysia who builds HyDeck, an Android widget app sold on Gumroad with theme packs (MIDAS, GYM). Call them "boss". Casual Malaysian words like "bro" and "steady" are fine sometimes.
Rules:
- Keep replies short: under 110 words, plain text, no markdown.
- No generic motivational quotes. Give concrete actions. Call out slacking directly but kindly.
- Sleep, school and health are part of performance. Never push all-nighters.
- Prefer actions that get HyDeck in front of buyers over building new prototypes.
- NEWS: only mention news that appears in the HEADLINES of the context, and name the source in brackets, e.g. [BBC World]. If there are no headlines, say you have no fresh news. Never invent or guess news.
- Use the context (time, weather, tasks, sales, commits). Don't repeat it back word for word.
Special lines (each on its own line, exactly as shown; the phone acts on them):
- TASK: <task>    when you give steps for an open goal, exactly 3, each doable within the hour.
- MEMORY: <fact>  when the user tells you something lasting about themselves, their goals or preferences.
- ACTION: <cmd>   only when the user asks you to do something on the phone. Allowed: torch on, torch off, volume <0-15>, brightness <0-100>, brightness auto, vibrate, battery, open <tiktok|youtube|instagram|gumroad|github|spotify|gmail|maps>, copy <text>.
End with a short status line in square brackets."""

NEWS_WORDS = re.compile(r"news|happening|headline|berita|world|today|current|update|trend", re.I)


def context(message=""):
    t = now()
    lines = [f"Time: {t.strftime('%A %d %b, %H:%M')} (Malaysia)"]
    w = WEATHER.v
    if w and w.get("ok"):
        lines.append(f"Weather in {w['city']}: {w['temp']}°C, {w['now']}, high {w['high']}°C, rain chance {w['rain_chance']}%")
    ot = open_tasks()[:8]
    lines.append("Open tasks: " + ("; ".join(n["text"] for n in ot) if ot else "none"))
    m = monitor()
    lines.append(f"HyDeck: layout {m['layout']}%, Recall {m['recall']}/20, packs {m['packs']}/4, devlog {m['devlog']}%")
    p = PULSE.v or {}
    g = p.get("gumroad", {})
    if g.get("ok"):
        lines.append(f"Gumroad: {g['today']} sales today (${g['today_rev']:.2f}), {g['week']} in 7 days")
    gh = p.get("github", {})
    if gh.get("ok") and gh.get("days_since") is not None:
        lines.append(f"GitHub: last push {gh['days_since']} day(s) ago, {gh['pushes_today']} today")
    if NEWS_WORDS.search(message):
        items = news_cached_only()[:8]
        lines.append("HEADLINES:\n" + ("\n".join(f"- [{i['source']}] {i['title']}" for i in items) if items else "(none fetched yet)"))
    return "[Context]\n" + "\n".join(lines)


def system_prompt():
    mem = memories()[-20:]
    return SYSTEM + ("\nWhat you remember about the boss:\n" + "\n".join("- " + x["fact"] for x in mem) if mem else "")


DIRECTIVE = re.compile(r"^\s*(?:[-*•\d.)]\s*)*(TASK|MEMORY|ACTION)\s*:\s*(.+?)\s*$", re.I | re.M)


def apply_directives(text, allow_actions=True):
    events = []
    tasks = []
    for kind, val in DIRECTIVE.findall(text):
        kind = kind.upper()
        if kind == "TASK" and len(tasks) < 5:
            tasks.append(val)
        elif kind == "MEMORY":
            if memory_add(val):
                events.append({"kind": "memory", "text": val})
        elif kind == "ACTION" and allow_actions:
            events.append({"kind": "action", "text": val, "result": act(val)})
    for t in reversed(tasks):  # newest-first list: add in reverse so step 1 sits on top
        brain_add(t, "task")
    events[:0] = [{"kind": "task", "text": t} for t in tasks]
    return events


def chat_history():
    return load("chat", [])


def remember_turn(user, assistant):
    with _lock:
        h = chat_history() + [{"role": "user", "content": user}, {"role": "assistant", "content": assistant}]
        n = CFG["chat_turns"]
        if len(h) > n + 6:  # trim in chunks so the engine's cache survives most turns
            h = h[-n:]
        save("chat", h)


def build_messages(message):
    """Returns (messages, user_turn). The same user_turn is saved to history so the
    engine sees an identical prefix next time and can reuse its cache."""
    user_turn = f"{message}\n\n{context(message)}"
    return [{"role": "system", "content": system_prompt()}, *chat_history(),
            {"role": "user", "content": user_turn}], user_turn


# ───────────────────────── briefing & greeting ─────────────────────────
_brief_lock = threading.Lock()


def briefing(force=False, ai=False):
    """Without `ai`, returns at once: today's saved plan (if written) plus live weather,
    sales and headlines. With `ai`, the engine writes the plan, which is slow on a phone."""
    today = now().date().isoformat()
    cached = load("briefing", {})
    if not ai:
        news = NEWS.peek(fetch_news)
        out = {"date": today, "weather": WEATHER.peek(fetch_weather), "pulse": PULSE.peek(fetch_pulse),
               "headlines": pick_headlines(news["items"]), "news_errors": news["errors"], "text": "", "engine": None}
        if cached.get("date") == today and cached.get("text"):
            out.update(text=cached["text"], engine=cached.get("engine"), generated=cached.get("generated"))
        return out
    if cached.get("date") == today and cached.get("text") and not force:
        return cached
    with _brief_lock:
        news = NEWS.get(fetch_news, force=force)
        w = WEATHER.get(fetch_weather, force=force)
        p = PULSE.get(fetch_pulse, force=force)
        top = pick_headlines(news["items"])
        out = {"date": today, "generated": time.time(), "weather": w, "pulse": p, "headlines": top,
               "news_errors": news["errors"], "text": "", "engine": None}
        e = pick_engine()
        if e:
            heads = "\n".join(f"[{i + 1}] ({h['source']}) {h['title']}" for i, h in enumerate(top)) or "(no headlines available)"
            prompt = (f"Write the boss's daily briefing for {now().strftime('%A %d %B')}.\n\n"
                      f"HEADLINES (the only news you may use):\n{heads}\n\n{context()}\n\n"
                      "Format exactly, plain text, under 170 words:\n"
                      "NEWS: 3 short bullets, each ending with its source in brackets, e.g. [BBC World].\n"
                      "WEATHER: one line with advice.\n"
                      "TODAY: the 3 most important things to do today, numbered, based on open tasks, sales and commits.\n"
                      "COSMO: one sharp coaching line.")
            try:
                out["text"] = ollama_once([{"role": "system", "content": system_prompt()},
                                           {"role": "user", "content": prompt}], num_predict=420)
                out["engine"] = f"{e['name']} · {e['model']}"
            except Exception as ex:
                out["text"] = ""
                out["error"] = f"The AI couldn't write the briefing ({type(ex).__name__})."
        save("briefing", out)
        return out


def pick_headlines(items, per_cat=(("malaysia", 3), ("world", 3), ("tech", 3))):
    out, seen = [], set()
    for cat, n in per_cat:
        for i in [x for x in items if x["cat"] == cat]:
            key = i["title"].lower()[:60]
            if key in seen:
                continue
            seen.add(key)
            out.append(i)
            n -= 1
            if not n:
                break
    return out


def greeting():
    """Instant, no AI call: COSMO speaks first when the page opens."""
    t = now()
    h = t.hour
    part = "It's late" if h >= 22 or h < 5 else "Morning" if h < 12 else "Afternoon" if h < 17 else "Evening"
    bits = [f"{part}, boss."]
    if h >= 23 or h < 5:
        bits.append("Past 11. Whatever it is, it ships better after sleep.")
    ot = open_tasks()
    if ot:
        oldest = min(ot, key=lambda n: n["at"])
        days = int((time.time() * 1000 - oldest["at"]) / 86400000)
        bits.append(f"'{oldest['text']}' has been open {days} days. Today?" if days >= 2 else f"{len(ot)} open task{'s' if len(ot) > 1 else ''}. Top one: '{ot[0]['text']}'.")
    else:
        bits.append("No open tasks. Tell me today's mission.")
    g = (PULSE.v or {}).get("gumroad", {})
    if g.get("ok") and g.get("today"):
        bits.append(f"{g['today']} Gumroad sale{'s' if g['today'] > 1 else ''} today. Steady.")
    gh = (PULSE.v or {}).get("github", {})
    if gh.get("ok") and (gh.get("days_since") or 0) >= 3:
        bits.append(f"No commits in {gh['days_since']} days.")
    return " ".join(bits)


# ───────────────────────── scheduler ─────────────────────────
def hhmm(s):
    h, m = s.split(":")
    return int(h) * 60 + int(m)


def quiet(t):
    s = CFG["schedule"]
    m, a, b = t.hour * 60 + t.minute, hhmm(s["quiet_start"]), hhmm(s["quiet_end"])
    return (m >= a or m < b) if a > b else (a <= m < b)


def scheduler():
    while True:
        try:
            t = now()
            today, cur = t.date().isoformat(), t.strftime("%H:%M")
            sent = load("sent", {})
            for job in ("briefing", "nudge", "recap"):
                due = CFG["schedule"][job]
                if sent.get(job) == today or not (hhmm(due) <= t.hour * 60 + t.minute < hhmm(due) + 20):
                    continue
                sent[job] = today
                save("sent", sent)
                if quiet(t):
                    continue
                if job == "briefing":
                    b = briefing(force=True, ai=True)
                    first = next((l for l in b.get("text", "").splitlines() if re.match(r"\s*1[.)]", l)), "")
                    notify("COSMO · Morning briefing", (first.strip() or "Your news, weather and plan for today are ready.") + " Tap to open.", "/#briefing")
                elif job == "nudge":
                    ot = open_tasks()
                    if ot:
                        oldest = min(ot, key=lambda n: n["at"])
                        notify("COSMO · Check-in", f"Still open: '{oldest['text']}'. 25 minutes on it now?", "/")
                elif job == "recap":
                    start = dt.datetime.combine(t.date(), dt.time(0), TZ).timestamp() * 1000
                    done = [n for n in brain() if n.get("done") and n.get("doneAt", 0) >= start]
                    notify("COSMO · Evening recap", f"{len(done)} task{'s' if len(done) != 1 else ''} done today. Pick tomorrow's first move, then sleep.", "/")
        except Exception as ex:
            log("scheduler:", ex)
        time.sleep(30)


# ───────────────────────── web server ─────────────────────────
# Files the page needs, served as-is. Only these paths; nothing else on the phone is reachable.
STATIC = {
    "/countries.json": "application/json",
    "/manifest.webmanifest": "application/manifest+json",
    "/sw.js": "text/javascript",
    "/icons/icon-192.png": "image/png",
    "/icons/icon-512.png": "image/png",
    "/icons/icon-maskable-512.png": "image/png",
}


class Handler(BaseHTTPRequestHandler):
    server_version = "COSMO/1.0"

    def log_message(self, *a):
        pass

    def send(self, code, body, ctype="application/json"):
        raw = body if isinstance(body, bytes) else json.dumps(body, ensure_ascii=False).encode()
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(raw)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(raw)

    def body(self):
        n = int(self.headers.get("Content-Length") or 0)
        try:
            return json.loads(self.rfile.read(n) or b"{}") if n else {}
        except ValueError:
            return {}

    def do_GET(self):
        u = urllib.parse.urlparse(self.path)
        q = urllib.parse.parse_qs(u.query)
        force = q.get("refresh") == ["1"]
        p = u.path
        try:
            if p in ("/", "/index.html"):
                with open(os.path.join(HERE, "index.html"), "rb") as f:
                    return self.send(200, f.read(), "text/html; charset=utf-8")
            if p == "/api/status":
                e = pick_engine(force=force)
                return self.send(200, {"engine": e, "engines": _engine.get("status", []), "phone_api": has_api(),
                                       "city": CFG["city"]["name"], "time": now().isoformat(),
                                       "gumroad": bool(CFG.get("gumroad_token"))})
            if p == "/api/brain":
                return self.send(200, brain())
            if p == "/api/memory":
                return self.send(200, memories())
            if p == "/api/monitor":
                return self.send(200, monitor())
            if p == "/api/news":
                return self.send(200, NEWS.get(fetch_news, force=True) if force else NEWS.peek(fetch_news))
            if p == "/api/weather":
                return self.send(200, WEATHER.get(fetch_weather, force=True) if force else WEATHER.peek(fetch_weather))
            if p == "/api/pulse":
                return self.send(200, PULSE.get(fetch_pulse, force=True) if force else PULSE.peek(fetch_pulse))
            if p == "/api/briefing":
                return self.send(200, briefing(force=force, ai=q.get("ai") == ["1"]))
            if p == "/api/greet":
                return self.send(200, {"text": greeting()})
            if p in STATIC:
                with open(os.path.join(HERE, p.lstrip("/")), "rb") as f:
                    return self.send(200, f.read(), STATIC[p])
            if p == "/api/country":
                return self.send(200, fetch_country(q.get("name", [""])[0], force=force))
            if p == "/api/country/brief":
                return self.send(200, country_brief(q.get("name", [""])[0]))
            self.send(404, {"error": "not found"})
        except Exception as ex:
            log("GET", p, ex)
            self.send(500, {"error": str(ex)})

    def do_POST(self):
        p = urllib.parse.urlparse(self.path).path
        b = self.body()
        try:
            if p == "/api/chat":
                return self.chat_stream(str(b.get("message", ""))[:2000])
            if p == "/api/ask":  # non-streaming, used by `cosmo talk`
                msg = str(b.get("message", ""))[:2000]
                msgs, user_turn = build_messages(msg)
                text = ollama_once(msgs, num_predict=260)
                remember_turn(user_turn, text)
                return self.send(200, {"text": text, "events": apply_directives(text)})
            if p == "/api/brain/add":
                n = brain_add(b.get("text", ""), b.get("type", "task"))
                return self.send(200 if n else 400, brain())
            if p in ("/api/brain/toggle", "/api/brain/delete"):
                with _lock:
                    items = brain()
                    if p.endswith("toggle"):
                        for n in items:
                            if n["id"] == b.get("id"):
                                n["done"] = not n["done"]
                                n["doneAt"] = time.time() * 1000 if n["done"] else None
                    else:
                        items = [n for n in items if n["id"] != b.get("id")]
                    save("brain", items)
                return self.send(200, items)
            if p == "/api/brain/import":
                with _lock:
                    items = brain()
                    have = {n["id"] for n in items}
                    for n in b.get("items", [])[:500]:
                        if isinstance(n, dict) and n.get("id") not in have and n.get("text"):
                            items.append({"id": str(n["id"])[:24], "text": str(n["text"])[:280],
                                          "type": n.get("type", "task"), "done": bool(n.get("done")),
                                          "at": n.get("at") or time.time() * 1000})
                    items.sort(key=lambda n: n["at"], reverse=True)
                    save("brain", items)
                return self.send(200, items)
            if p == "/api/monitor":
                m = monitor()
                for k in m:
                    if isinstance(b.get(k), (int, float)):
                        m[k] = b[k]
                save("monitor", m)
                return self.send(200, m)
            if p == "/api/memory/delete":
                with _lock:
                    m = [x for x in memories() if x["fact"] != b.get("fact")]
                    save("memory", m)
                return self.send(200, m)
            if p == "/api/forget":
                save("chat", [])
                return self.send(200, {"ok": True})
            if p == "/api/model":
                e = pick_engine(force=True)
                if not e or b.get("model") not in e["models"]:
                    return self.send(400, {"error": "That model isn't installed on the active engine."})
                for x in CFG["engines"]:
                    if x["name"] == e["name"]:
                        x["model"] = b["model"]
                write_json(CONFIG_PATH, CFG)
                return self.send(200, pick_engine(force=True))
            if p == "/api/act":
                return self.send(200, {"result": act(str(b.get("cmd", "")))})
            self.send(404, {"error": "not found"})
        except Exception as ex:
            log("POST", p, ex)
            self.send(500, {"error": str(ex)})

    def chat_stream(self, message):
        """Streams COSMO's reply as NDJSON lines: {"t": text}… then {"done": true, "events": […]}."""
        self.send_response(200)
        self.send_header("Content-Type", "application/x-ndjson")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()

        def out(obj):
            self.wfile.write((json.dumps(obj, ensure_ascii=False) + "\n").encode())
            self.wfile.flush()

        full, stats = "", {}
        try:
            msgs, user_turn = build_messages(message)
            e, r = ollama_chat(msgs, stream=True)
            out({"engine": f"{e['name']} · {e['model']}"})
            with r:
                for line in r:
                    if not line.strip():
                        continue
                    j = json.loads(line)
                    if j.get("error"):
                        raise RuntimeError(j["error"])
                    piece = j.get("message", {}).get("content", "")
                    if piece:
                        full += piece
                        out({"t": piece})
                    if j.get("done"):
                        stats = {k: j.get(k) for k in ("eval_count", "eval_duration", "prompt_eval_duration", "load_duration")}
            remember_turn(user_turn, full)
            out({"done": True, "stats": stats, "events": apply_directives(full)})
        except (BrokenPipeError, ConnectionResetError):
            log("chat: client stopped")  # the Stop button; closing `r` stops the engine
        except Exception as ex:
            try:
                out({"error": str(ex)})
            except Exception:
                pass


def main():
    port = CFG["port"]
    srv = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    threading.Thread(target=scheduler, daemon=True).start()
    # Prefetch the world in the background so the first briefing is quick.
    for c, fn in ((NEWS, fetch_news), (WEATHER, fetch_weather), (PULSE, fetch_pulse)):
        threading.Thread(target=c.get, args=(fn,), daemon=True).start()
    threading.Thread(target=pick_engine, daemon=True).start()
    log(f"COSMO server on http://127.0.0.1:{port}  (Ctrl+C to stop)")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    sys.exit(main())
