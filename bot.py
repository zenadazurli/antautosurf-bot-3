#!/usr/bin/env python3
# bot.py - AntAutoSurf Bot per Render con riavvio automatico

import os
import time
import sys
import json
import re
import requests
from playwright.sync_api import sync_playwright
from urllib.parse import unquote
from datetime import datetime
import imagehash
from PIL import Image
import io

# ============================================================
# CONFIGURAZIONE DA VARIABILI D'AMBIENTE
# ============================================================
EMAIL = os.environ.get("EMAIL", "kavonobenna@gmail.com")
PASSWORD = os.environ.get("PASSWORD", "DF45$!sada")
HEADLESS = os.environ.get("HEADLESS", "True").lower() == "true"

# Proxy (opzionale)
PROXY_HOST = os.environ.get("PROXY_HOST")
PROXY_PORT = os.environ.get("PROXY_PORT")
PROXY_USER = os.environ.get("PROXY_USER")
PROXY_PASS = os.environ.get("PROXY_PASS")

# ============================================================
# LOGGING
# ============================================================
def log(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}", flush=True)

# ============================================================
# CARICA DATABASE PHASH
# ============================================================
def carica_database():
    try:
        with open("hash_phash_db.json", "r") as f:
            return json.load(f)
    except FileNotFoundError:
        log("ℹ️ Database phash non trovato, uso database vuoto")
        return {}
    except Exception as e:
        log(f"⚠️ Errore caricamento database: {e}")
        return {}

phash_db = carica_database()
log(f"📊 Database phash: {len(phash_db)} hash")

# ============================================================
# VERIFICA PROXY
# ============================================================
def verifica_proxy(host, port, user, pwd):
    """Verifica che il proxy sia raggiungibile"""
    if not host or not user:
        return True
    
    try:
        response = requests.get(
            "http://httpbin.org/ip",
            proxies={
                "http": f"http://{user}:{pwd}@{host}:{port}",
                "https": f"http://{user}:{pwd}@{host}:{port}"
            },
            timeout=10
        )
        if response.status_code == 200:
            log(f"✅ Proxy raggiungibile! IP: {response.json()['origin']}")
            return True
    except Exception as e:
        log(f"⚠️ Proxy non raggiungibile: {e}")
        return False
    
    return False

# ============================================================
# FUNZIONI DI PULIZIA
# ============================================================
def pulisci_url(url):
    url = re.sub(r'<[^>]+>', '', url)
    url = url.strip()
    url = unquote(url)
    url = re.sub(r'[<>\'"]', '', url)
    return url

def pulisci_ad_id(ad_id):
    ad_id = unquote(ad_id)
    ad_id = re.sub(r'<[^>]+>', '', ad_id)
    ad_id = re.sub(r'[<>\'"]', '', ad_id)
    match = re.search(r'(\d+)', ad_id)
    if match:
        return match.group(1)
    return ad_id

# ============================================================
# RISOLUZIONE CAPTCHA
# ============================================================
def risolvi_captcha(page, phash_db):
    html = page.content()
    cap_match = re.search(r'capimg\.php\?id=(\d+)', html)
    if not cap_match:
        return False
    
    cap_id = cap_match.group(1)
    cids = [int(x) for x in re.findall(r'cid=(\d+)', html)]
    cids_unici = list(set(cids))
    
    log(f"   🖼️ Captcha ID: {cap_id}")
    log(f"   📌 CID disponibili: {cids_unici}")
    
    # Screenshot del captcha
    img_element = page.locator('img[src*="capimg.php"]')
    img_data = img_element.screenshot()
    
    # Calcola phash
    img_pil = Image.open(io.BytesIO(img_data))
    phash = imagehash.phash(img_pil)
    phash_str = str(phash)
    log(f"   🔑 PHASH: {phash_str}")
    
    # Cerca nel database
    for stored_phash, cid in phash_db.items():
        try:
            diff = imagehash.hex_to_hash(phash_str) - imagehash.hex_to_hash(stored_phash)
            if diff <= 10:
                page.goto(f"https://antautosurf.com/index.php?cid={cid}")
                time.sleep(2)
                log(f"   ✅ CAPTCHA RISOLTO! CID: {cid}")
                return True
        except:
            pass
    
    # Prova tutti i CID
    for cid in cids_unici:
        page.goto(f"https://antautosurf.com/index.php?cid={cid}")
        time.sleep(2)
        html_test = page.content()
        if "Please Click Similar" not in html_test:
            phash_db[phash_str] = cid
            with open("hash_phash_db.json", "w") as f:
                json.dump(phash_db, f, indent=2)
            log(f"   ✅ CAPTCHA RISOLTO! CID: {cid} (nuovo)")
            return True
    
    log(f"   ❌ CAPTCHA NON RISOLTO!")
    return False

# ============================================================
# MAIN BOT
# ============================================================
def esegui_bot():
    log("="*60)
    log(f"🤖 AntAutoSurf Bot - {EMAIL}")
    log(f"🔇 Headless: {HEADLESS}")
    
    # Configura proxy
    proxy_config = None
    if PROXY_HOST and PROXY_USER:
        log(f"🌐 Proxy: {PROXY_HOST}:{PROXY_PORT}")
        log(f"   👤 User: {PROXY_USER}")
        
        # Verifica proxy
        if not verifica_proxy(PROXY_HOST, PROXY_PORT, PROXY_USER, PROXY_PASS):
            log("⚠️ Proxy non raggiungibile, procedo senza proxy")
        else:
            proxy_config = {
                "server": f"http://{PROXY_HOST}:{PROXY_PORT}",
                "username": PROXY_USER,
                "password": PROXY_PASS
            }
    else:
        log("⚠️ Proxy non configurato, procedo senza proxy")
    
    log("="*60)
    
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=HEADLESS,
            proxy=proxy_config,
            args=['--disable-blink-features=AutomationControlled']
        )
        
        context = browser.new_context()
        page = context.new_page()
        
        try:
            # ============================================================
            # LOGIN
            # ============================================================
            log("📧 Login...")
            page.goto("https://antautosurf.com/", wait_until="domcontentloaded", timeout=30000)
            time.sleep(2)
            
            page.fill('input[name="bitcoinwallet"]', EMAIL)
            page.click('input[type="submit"][value*="Enter"]')
            time.sleep(3)
            
            html = page.content()
            if "Please enter Password" in html:
                log("🔑 Password...")
                page.fill('input[name="password"]', PASSWORD)
                page.click('input[value="Enter"]')
                time.sleep(3)
            
            log("✅ Login completato!")
            
            # ============================================================
            # DASHBOARD
            # ============================================================
            log("📊 Dashboard...")
            page.goto(f"https://antautosurf.com/index.php?bitcoinwallet={EMAIL}&ref=", wait_until="networkidle", timeout=30000)
            time.sleep(3)
            html = page.content()
            
            # Captcha
            if "Please Click Similar" in html:
                log("⚠️ CAPTCHA RILEVATO!")
                if not risolvi_captcha(page, phash_db):
                    log("❌ Captcha non risolto!")
                    return
            
            # Balance
            balance_match = re.search(r'btoday["\']?\s*[=:]\s*([\d.]+)', html)
            if balance_match:
                log(f"💰 Balance: {balance_match.group(1)}")
            
            # CSRF
            csrf_match = re.search(r'csrf_token=([a-f0-9]+)', html)
            if not csrf_match:
                log("❌ CSRF non trovato!")
                return
            
            csrf = csrf_match.group(1)
            log(f"🎫 CSRF: {csrf[:16]}...")
            
            # ============================================================
            # SURF CON RIAVVIO AUTOMATICO
            # ============================================================
            log("🚀 Avvio surf...")
            
            key = ""
            time_val = 12
            ad_id = ""
            cycle = 0
            
            # 🔥 CONTATORI
            csrf_invalidi = 0
            MAX_CSRF_INVALIDI = 5
            MAX_CYCLES = 5000  # 5000 cicli = ~16-20 ore
            
            while cycle < MAX_CYCLES:
                cycle += 1
                log(f"🔄 CICLO {cycle}")
                
                if ad_id:
                    ad_id_pulito = pulisci_ad_id(ad_id)
                else:
                    ad_id_pulito = ""
                
                params = {
                    "wallet": EMAIL,
                    "key": key,
                    "time": time_val,
                    "ad_id": ad_id_pulito,
                    "isitbad": 0,
                    "csrf_token": csrf
                }
                
                url = "https://antautosurf.com/surf.php?" + "&".join([f"{k}={v}" for k, v in params.items()])
                
                page.goto(url, wait_until="domcontentloaded", timeout=30000)
                page_text = page.content()
                
                # 🔥 GESTISCI CSRF INVALIDO
                if "Invalid CSRF token" in page_text:
                    csrf_invalidi += 1
                    log(f"❌ CSRF invalido! ({csrf_invalidi}/{MAX_CSRF_INVALIDI})")
                    
                    if csrf_invalidi >= MAX_CSRF_INVALIDI:
                        log("🔄 Troppi CSRF invalidi! Riavvio il bot...")
                        return
                    
                    page.goto(f"https://antautosurf.com/index.php?bitcoinwallet={EMAIL}&ref=", wait_until="networkidle", timeout=30000)
                    time.sleep(2)
                    html = page.content()
                    csrf_match = re.search(r'csrf_token=([a-f0-9]+)', html)
                    if csrf_match:
                        csrf = csrf_match.group(1)
                        csrf_invalidi = 0
                        log(f"🎫 Nuovo CSRF: {csrf[:16]}...")
                    continue
                else:
                    csrf_invalidi = 0
                
                if "--_--" not in page_text:
                    time.sleep(5)
                    continue
                
                parts = page_text.split("--_--")
                if len(parts) < 4:
                    continue
                
                ad_url = pulisci_url(parts[0])
                time_val = int(parts[1])
                key = parts[2]
                ad_id = parts[3]
                
                if "connection.php" in ad_url:
                    log("   📂 Test anti-bot...")
                    page.goto(ad_url, wait_until="domcontentloaded", timeout=30000)
                    for i in range(time_val, 0, -1):
                        print(f"   ⏳ {i}s", end="\r")
                        time.sleep(1)
                    print("   " * 20, end="\r")
                    continue
                
                log(f"   📢 Annuncio reale! Timer: {time_val}s")
                
                try:
                    new_page = context.new_page()
                    new_page.goto(ad_url, wait_until="domcontentloaded", timeout=10000)
                except:
                    pass
                
                for i in range(time_val, 0, -1):
                    print(f"   ⏳ {i}s", end="\r")
                    time.sleep(1)
                print("   " * 20, end="\r")
                log(f"   ✅ Timer completato!")
                
                try:
                    new_page.close()
                except:
                    pass
                
                if cycle % 3 == 0:
                    page.goto(f"https://antautosurf.com/index.php?bitcoinwallet={EMAIL}&ref=", wait_until="networkidle", timeout=30000)
                    time.sleep(2)
                    html = page.content()
                    csrf_match = re.search(r'csrf_token=([a-f0-9]+)', html)
                    if csrf_match:
                        csrf = csrf_match.group(1)
                        log(f"   🎫 CSRF aggiornato: {csrf[:16]}...")
            
            log(f"🔄 Raggiunti {MAX_CYCLES} cicli, riavvio programmato...")
            return
            
        except Exception as e:
            log(f"❌ Errore: {e}")
        finally:
            browser.close()

# ============================================================
# MAIN LOOP CON RIAVVIO
# ============================================================
if __name__ == "__main__":
    log("="*60)
    log("🚀 AVVIO BOT - RIAVVIO AUTOMATICO")
    log("="*60)
    
    try:
        while True:
            try:
                esegui_bot()
            except Exception as e:
                log(f"❌ Errore nel bot: {e}")
            
            log("⏳ Attesa 60 secondi prima di riavviare...")
            time.sleep(60)
    except KeyboardInterrupt:
        log("\n⏹️ Arresto...")
        sys.exit(0)