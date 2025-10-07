# auto_checkout.py  — versione robusta con sanificazione dominio + fallback profilo
# pip install playwright
# playwright install chromium

from playwright.sync_api import sync_playwright
from urllib.parse import quote_plus, urlparse
import argparse, sys, re, os

# ---------- Helpers dominio ----------
FORCE_WWW = {"popsplanet.it", "faoschwarz.it"}  # domini che preferiscono www

def sanitize_domain(d: str) -> str:
    if not d:
        return ""
    d = d.strip()
    d = d.replace("_", ".").replace("—", "-").replace("–", "-").replace(" ", "")
    d = d.replace("www_", "www.").replace("www-", "www.")
    # lascia solo [a-z0-9.-]
    d = "".join(ch for ch in d if ch.isalnum() or ch in ".-")
    d = d.replace("..", ".")
    d = d.lower()
    # togli prefisso www. per uniformare (lo rimetto dopo se serve)
    if d.startswith("www."):
        d = d[4:]
    return d

def host_for(d: str) -> str:
    d = sanitize_domain(d)
    return ("www." + d) if d in FORCE_WWW else d

def detect_domain(url: str | None, domain_arg: str | None) -> str | None:
    if domain_arg:
        return sanitize_domain(domain_arg)
    if url:
        netloc = urlparse(url).netloc
        if netloc:
            return sanitize_domain(netloc)
    return None

# ---------- Selettori ----------
GENERIC_RESULT = [
    "ul.products li.product a.woocommerce-LoopProduct-link",
    "ul.products li.product a[href*='/prodotto/']",
    "ul.products li.product a[href*='/product/']",
    "article.product a.woocommerce-LoopProduct-link",
    ".products .product a[href*='/product/']",
    "a[href*='/products/']",  # Shopify
]
GENERIC_ADD = [
    "button.single_add_to_cart_button",
    "button[name='add-to-cart']",
    "button:has-text('Aggiungi al carrello')",
    "button:has-text('Aggiungi al Carrello')",
    "form.cart button[type='submit']",
    "button[name='add']"
]
GENERIC_CHECKOUT = [
    "a:has-text('Checkout')",
    "a[href*='checkout']",
    "button:has-text('Vai al checkout')",
    "a:has-text('Procedi')",
    "a:has-text('Concludi ordine')",
    "a:has-text('Completa acquisto')",
]
COOKIE_BUTTONS = [
    "#onetrust-accept-btn-handler",
    "button:has-text('Accetta tutti')",
    "button:has-text('Accetta')",
    "button:has-text('Ho capito')",
    "button:has-text('Accept')",
    "[aria-label*='accept']",
]

DOMAIN_SPECIFIC = {
    "faoschwarz.it": {
        "result": GENERIC_RESULT,
        "add": GENERIC_ADD,
        "checkout": GENERIC_CHECKOUT,
        "cookie": COOKIE_BUTTONS,
        "search_builder": lambda q, host: f"https://{host}/?s={quote_plus(q)}&post_type=product",
    },
    "popsplanet.it": {
        "result": GENERIC_RESULT + [
            ".product a.woocommerce-LoopProduct-link",
            ".products.grid li.product a",
        ],
        "add": GENERIC_ADD,
        "checkout": GENERIC_CHECKOUT,
        "cookie": COOKIE_BUTTONS,
        "search_builder": lambda q, host: f"https://{host}/?s={quote_plus(q)}&post_type=product",
    },
}

# ---------- Utility ----------
def click_first(page, selectors, timeout=7000):
    for sel in selectors:
        try:
            page.locator(sel).first.wait_for(state="visible", timeout=timeout)
            page.locator(sel).first.click()
            return sel
        except Exception:
            continue
    return None

def close_cookie_banner(page, selectors):
    for sel in selectors:
        try:
            if page.locator(sel).first.is_visible():
                page.locator(sel).first.click()
                return True
        except Exception:
            pass
    return False

def ensure_results_rendered(page):
    for _ in range(6):
        page.wait_for_timeout(250)
        page.mouse.wheel(0, 900)
    page.wait_for_timeout(400)

# ---------- Main ----------
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--query")
    ap.add_argument("--domain")
    ap.add_argument("--search-url")
    ap.add_argument("--product-url")
    ap.add_argument("--profile")
    args = ap.parse_args()

    if not (args.product_url or args.search_url or (args.query and args.domain)):
        print("Usa: --product-url OR --search-url OR (--query + --domain)")
        sys.exit(1)

    domain = detect_domain(args.search_url or args.product_url, args.domain)
    if not domain:
        print("Impossibile determinare il dominio.")
        sys.exit(1)
    host = host_for(domain)
    cfg = DOMAIN_SPECIFIC.get(domain, {
        "result": GENERIC_RESULT,
        "add": GENERIC_ADD,
        "checkout": GENERIC_CHECKOUT,
        "cookie": COOKIE_BUTTONS,
        "search_builder": lambda q, host: f"https://{host}/?s={quote_plus(q)}&post_type=product",
    })

    target_url = args.product_url or args.search_url or cfg["search_builder"](args.query, host)

    with sync_playwright() as p:
        page = None
        ctx = None
        browser = None
        # --- tenta profilo persistente, con fallback sicuro ---
        try:
            if args.profile:
                os.makedirs(args.profile, exist_ok=True)
                ctx = p.chromium.launch_persistent_context(args.profile, headless=False)
                page = ctx.new_page()
            else:
                raise RuntimeError("No persistent profile requested")
        except Exception as e:
            print("⚠️ Profilo persistente fallito, passo al profilo volatile:", e)
            browser = p.chromium.launch(headless=False)
            ctx = browser.new_context()
            page = ctx.new_page()

        page.set_default_timeout(15000)

        print("🔗 Apro:", target_url)
        page.goto(target_url, wait_until="domcontentloaded")
        close_cookie_banner(page, cfg["cookie"])

        # se è una SERP → apri primo risultato
        if re.search(r"[?&]s=", target_url) and "post_type=product" in target_url:
            print("🔎 SERP rilevata: seleziono il primo prodotto…")
            ensure_results_rendered(page)
            sel = click_first(page, cfg["result"], timeout=9000)
            if not sel:
                ensure_results_rendered(page)
                sel = click_first(page, cfg["result"], timeout=9000)
            if not sel:
                print("❌ Nessun risultato cliccabile trovato.")
                input("Controlla a mano e premi Invio per chiudere…")
                ctx.close()
                return
            print("➡️  Aperto primo prodotto con:", sel)
            page.wait_for_load_state("domcontentloaded")
            close_cookie_banner(page, cfg["cookie"])

        print("🛒 Provo 'Aggiungi al carrello'…")
        sel_add = click_first(page, cfg["add"], timeout=9000)
        if not sel_add:
            print("⚠️ Bottone 'Aggiungi al carrello' non trovato. Rimani sulla pagina e procedi manualmente.")
            input("Premi Invio per chiudere…")
            ctx.close()
            return
        print("✅ Add-to-cart con:", sel_add)

        page.wait_for_timeout(900)
        sel_chk = click_first(page, cfg["checkout"], timeout=9000)
        if sel_chk:
            print("➡️  Checkout aperto con:", sel_chk)
        else:
            print("ℹ️  Checkout non trovato (minicart): procedi manualmente.")

        print("\n⏸️  Mi fermo prima del pagamento. Completa manualmente.")
        input("Premi Invio per chiudere…")
        ctx.close()

if __name__ == "__main__":
    main()
