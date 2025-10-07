# pip install pyautogui pillow
import json, time
import pyautogui
from PIL import Image

print("== Seleziona la REGIONE per la chat Discord ==")
print("1) Porta il mouse sull'ANGOLO IN ALTO A SINISTRA dell'area chat.")
input("   Quando sei posizionato correttamente, premi INVIO qui nella console...")
x1, y1 = pyautogui.position()
print(f"   Preso top-left: ({x1}, {y1})")

print("\n2) Porta il mouse sull'ANGOLO IN BASSO A DESTRA dell'area chat.")
input("   Quando sei posizionato correttamente, premi INVIO...")
x2, y2 = pyautogui.position()
print(f"   Preso bottom-right: ({x2}, {y2})")

left, top = x1, y1
width, height = max(1, x2 - x1), max(1, y2 - y1)
region = (left, top, width, height)

print(f"\n✅ REGIONE calcolata: {region}")
print("   Copiala dentro watcher_ocr.py al posto di REGION = (...)\n")

# Salva anche un file di appoggio
with open("region.json", "w", encoding="utf-8") as f:
    json.dump({"REGION": region}, f, ensure_ascii=False, indent=2)

# Screenshot di prova
img = pyautogui.screenshot(region=region)
img.save("region_test.png")
print("🖼️ Creato screenshot 'region_test.png' per verifica visiva.")
