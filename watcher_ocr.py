# watcher_ocr.py
# Requisiti: pip install pillow pyautogui pytesseract
# (opzionale per auto-checkout) pip install playwright && playwright install chromium

import time, re, json, os, subprocess, shlex, webbrowser
import pyautogui, pytesseract
from PIL import Image
from urllib.parse import quote_plus

# Percorso Tesseract (TUO)
pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

# Config opzionale
CFG = {
    "whitelist": ["faoschwarz.it", "popsplanet.it"],  # aggiungi qui i domini
    "poll_ms": 400,
    "max_seen": 80,
    "profile_dir": r"%LOCALAPPDATA%\ResellProfile"
}
if os.path.exists("config.json"):
    try:
        CFG.update(json.load(open("config.json", "r", encoding="utf-8")))
    except Exception as e:
        print("⚠️ Errore nel leggere config.json:", e)

# Pattern
URL_RE = re.compile(r"https?://[^\s)>\]]+", re.I)
DOMAIN_ONLY_RE = re.compile(r"^https?://[^/]+/?$", re.I)
PATHLIKE_RE = re.compile(r"^(?:/?[a-z0-9-]+)+(?:/[a-z0-9-]+)*/?$", re.I)  # /shop/.../statuina/
IS_PRODUCT = re.compile(r"/(shop|prodotto|product|products)/", re.I)
IS_SEARCH = re.compile(r"[?&]s=.+", re.I)

STOPWORDS = {"Reason","Price","Sizes","Useful Links","StockX","Google","Ebay","Kaufland","Goatify","APP"}
EXIT_MODAL_MARKERS = ("Stai uscendo da Discord", "Visita il sito")  # IT popup

# TUA REGIONE (full screen)
REGION = (0, 0, 1907, 1079)

seen = set()

def is_whitelisted(u_or_dom: str) -> bool:
    lo = u_or_dom.lower()
    return any(dom.lower() in lo for dom in CFG["whitelist"])

def normalize_domain(u: str) -> str:
    dom = u.split("//",1)[-1].split("/",1)[0].lower()
    return dom.replace("www.","")

def is_full_product_url(url: str) -> bool:
    return bool(IS_PRODUCT.search(url))

def prefer_product_url(urls: list[str]) -> str | None:
    """Sceglie la URL 'prodotto' più lunga. Evita le ?s=... se esiste una product URL."""
    prods = [u for u in urls if is_full_product_url(u)]
    if prods:
        return max(prods, key=len)
    return None

def extract_title_near_domain(lines: list[str], domain: str) -> str | None:
    idx = next((i for i, ln in enumerate(lines) if domain in ln.lower()), -1)
    candidates = []
    around = lines[idx+1: idx+7] if idx >= 0 else lines
    def good(s: str) -> bool:
        return s and "http" not in s and all(sw.lower() not in s.lower() for sw in STOPWORDS) and len(s) >= 16
    for ln in around:
        s = ln.strip()
        if good(s): candidates.append(s)
    if not candidates:
        for ln in lines:
            s = ln.strip()
            if good(s): candidates.append(s)
    return max(candidates, key=len) if candidates else None

def reconstruct_wrapped_url(lines: list[str], start_idx: int, base_url: str) -> str | None:
    parts = []
    for j in range(start_idx+1, min(start_idx+8, len(lines))):
        raw = lines[j].strip().rstrip(".,);]")
        raw = raw.replace("…","").replace("\u200b","").replace(" ", "")
        if PATHLIKE_RE.match(raw):
            parts.append(raw)
        else:
            break
    if not parts:
        return None
    path = "/".join(p.strip("/") for p in parts if p)
    if not path.startswith("/"): path = "/" + path
    if not path.endswith("/"): path += "/"
    return base_url.rstrip("/") + path

def launch_auto_checkout_product(url: str):
    profile = os.path.expandvars(CFG.get("profile_dir", r"%LOCALAPPDATA%\ResellProfile"))
    cmd = f'python auto_checkout.py --product-url "{url}" --profile "{profile}"'
    print("🧭 auto-checkout (product):", cmd)
    subprocess.Popen(shlex.split(cmd), cwd=os.path.dirname(__file__) or ".")

def launch_auto_checkout_query(domain: str, title: str):
    profile = os.path.expandvars(CFG.get("profile_dir", r"%LOCALAPPDATA%\ResellProfile"))
    cmd = f'python auto_checkout.py --domain "{domain}" --query "{title}" --profile "{profile}"'
    print("🧭 auto-checkout (query):", cmd)
    subprocess.Popen(shlex.split(cmd), cwd=os.path.dirname(__file__) or ".")

def contains_exit_modal(text: str) -> bool:
    t = text.lower()
    return all(m.lower() in t for m in (EXIT_MODAL_MARKERS[0].lower(), EXIT_MODAL_MARKERS[1].lower()))

# --- sostituisci/aggiorna nel watcher ---

FORCE_WWW = {"popsplanet.it", "faoschwarz.it"}

def normalize_domain(u: str) -> str:
    raw = u.split("//",1)[-1].split("/",1)[0]
    raw = raw.replace("_", ".").replace("—","-").replace("–","-").replace(" ", "")
    raw = raw.replace("www_", "www.").replace("www-", "www.")
    cleaned = "".join(ch for ch in raw if ch.isalnum() or ch in ".-").lower()
    if cleaned.startswith("www."): cleaned = cleaned[4:]
    return cleaned

def host_for(dom: str) -> str:
    d = normalize_domain(dom)
    return "www." + d if d in FORCE_WWW else d

def launch_auto_checkout_with_query(domain: str, title: str):
    exe = "python"
    profile = os.path.expandvars(CFG.get("profile_dir", r"%LOCALAPPDATA%\ResellProfile"))
    dom = normalize_domain(domain)
    cmd = f'{exe} auto_checkout.py --domain "{dom}" --query "{title}" --profile "{profile}"'
    print("🧭 Avvio auto-checkout (query):", cmd)
    subprocess.Popen(shlex.split(cmd), cwd=os.path.dirname(__file__) or ".")


print("🔍 OCR watcher attivo. Mantieni Discord visibile nella REGIONE impostata.")
print("Whitelist domini:", ", ".join(CFG["whitelist"]) or "(vuota)")

while True:
    img = pyautogui.screenshot(region=REGION)
    text = pytesseract.image_to_string(img)
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]

    # Caso 1: popup "Stai uscendo da Discord" → l'URL completa è nel riquadro
    if contains_exit_modal(text):
        modal_urls = URL_RE.findall(text)
        modal_urls = [u.rstrip(".,);]") for u in modal_urls if is_whitelisted(u)]
        prod = prefer_product_url(modal_urls)
        if prod and prod not in seen:
            seen.add(prod)
            print("🔓 URL dal popup Discord:", prod)
            if os.path.exists(os.path.join(os.path.dirname(__file__) or ".", "auto_checkout.py")):
                launch_auto_checkout_product(prod)
            else:
                webbrowser.open(prod)
            # chiudi il popup per riprendere la chat
            try: pyautogui.press("esc")
            except: pass
        time.sleep(max(0.05, CFG["poll_ms"]/1000))
        continue

    # Caso 2: URL "normali" nel testo catturato
    urls = [u.rstrip(".,);]") for u in URL_RE.findall(text)]
    # Se c'è una product URL whitelisted, preferiscila rispetto a ?s=
    prod = prefer_product_url([u for u in urls if is_whitelisted(u)])
    if prod and prod not in seen:
        seen.add(prod)
        print("➡️ URL prodotto:", prod)
        if os.path.exists(os.path.join(os.path.dirname(__file__) or ".", "auto_checkout.py")):
            launch_auto_checkout_product(prod)
        else:
            webbrowser.open(prod)
        time.sleep(max(0.05, CFG["poll_ms"]/1000))
        continue

    # Filtra solo le URL whitelisted rimaste (spesso SERP ?s=…)
    urls = [u for u in urls if is_whitelisted(u) and not IS_SEARCH.search(u)]
    for url in urls:
        if url in seen:
            continue
        seen.add(url)
        if DOMAIN_ONLY_RE.match(url):
            dom = normalize_domain(url)
            if not is_whitelisted(dom): 
                continue
            idx = next((i for i, ln in enumerate(lines) if dom in ln.lower()), -1)
            if idx >= 0:
                full = reconstruct_wrapped_url(lines, idx, f"https://{host_for(dom)}")
                if full and is_full_product_url(full):
                    print("🔗 URL ricostruita:", full)
                    if os.path.exists(os.path.join(os.path.dirname(__file__) or ".", "auto_checkout.py")):
                        launch_auto_checkout_product(full)
                    else:
                        webbrowser.open(full)
                    break
            title = extract_title_near_domain(lines, dom)
            if title:
                print(f"🔎 Nessun deep-link visibile. Titolo: {title}")
                if os.path.exists(os.path.join(os.path.dirname(__file__) or ".", "auto_checkout.py")):
                    launch_auto_checkout_query(dom, title)
                else:
                    search_url = f"https://{host_for(dom)}/?s={quote_plus(title)}&post_type=product"
                    print("➡️ Apro ricerca:", search_url)
                    webbrowser.open(search_url)
            else:
                print("ℹ️ Dominio visto ma niente path/titolo. Apro home:", url)
                webbrowser.open(url)
        else:
            print("➡️ URL whitelisted:", url)
            webbrowser.open(url)

    time.sleep(max(0.05, CFG["poll_ms"]/1000))
