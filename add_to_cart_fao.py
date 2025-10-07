from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout
import time, sys, re

PRODUCT_URL = sys.argv[1] if len(sys.argv) > 1 else "https://www.faoschwarz.it/"
USER_DATA_DIR = r"C:\Users\%USERNAME%\AppData\Local\FAOProfile"  # profilo separato consigliato

CANDIDATES_ADD = [
    "button:has-text('Aggiungi al carrello')",
    "button:has-text('Aggiungi al Carrello')",
    "button:has-text('Aggiungi')",
    "text=Aggiungi al carrello",
    "[data-action='add-to-cart']",
    "button#add-to-cart, #add-to-cart",
]
CANDIDATES_CHECKOUT = [
    "a:has-text('Checkout')",
    "button:has-text('Checkout')",
    "text=Vai al checkout",
    "a[href*='checkout']",
    "button[href*='checkout']",
]

def click_first(page, selectors, timeout=4000):
    for sel in selectors:
        try:
            page.locator(sel).first.wait_for(state="visible", timeout=timeout)
            page.locator(sel).first.click()
            return sel
        except Exception:
            continue
    return None

def run():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        # Profilo separato dedicato a FAO (così rimani loggato e salvi indirizzo/pagamento se possibile)
        ctx = browser.new_context()
        page = ctx.new_page()
        page.set_default_timeout(15000)

        print("🔗 Aprendo:", PRODUCT_URL)
        page.goto(PRODUCT_URL, wait_until="domcontentloaded")

        # chiudi cookie banner se presente
        try:
            for sel in ["button:has-text('Accetta')", "button:has-text('Accept')", "text=Accetta tutti"]:
                if page.locator(sel).first.is_visible():
                    page.locator(sel).first.click()
                    break
        except Exception:
            pass

        # se è pagina variante, assicurati di essere su prodotto (no listing)
        # (best effort, fai click su prima variante se necessario)
        try:
            # eventuali select di variante
            if page.locator("select").count() > 0:
                first_sel = page.locator("select").first
                first_sel.select_option(index=1)
        except Exception:
            pass

        # Aggiungi al carrello
        sel_used = click_first(page, CANDIDATES_ADD)
        if sel_used:
            print("🛒 Clic eseguito su:", sel_used)
        else:
            print("⚠️ Non ho trovato il bottone 'Aggiungi al carrello' con i selettori standard.")
            input("Controlla manualmente, poi premi Invio per chiudere...")
            browser.close()
            return

        # Attendi mini-cart/cart
        try:
            page.wait_for_timeout(600)  # piccolo respiro
            # prova ad andare al checkout
            sel_checkout = click_first(page, CANDIDATES_CHECKOUT, timeout=6000)
            if sel_checkout:
                print("➡️  Checkout aperto con:", sel_checkout)
            else:
                print("ℹ️  Non ho trovato 'Checkout'. Rimani sul carrello e procedi tu.")
        except PWTimeout:
            pass

        print("✅ Fermato prima del pagamento. Completa tu manualmente.")
        input("Premi Invio per chiudere il browser...")
        browser.close()

if __name__ == "__main__":
    run()
