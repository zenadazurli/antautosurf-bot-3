#!/usr/bin/env python3
# bot.py - AntAutoSurf Bot con ricerca proxy automatica

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
from concurrent.futures import ThreadPoolExecutor, as_completed

# ============================================================
# CONFIGURAZIONE DA VARIABILI D'AMBIENTE
# ============================================================
EMAIL = os.environ.get("EMAIL", "kavonobenna@gmail.com")
PASSWORD = os.environ.get("PASSWORD", "DF45$!sada")
HEADLESS = os.environ.get("HEADLESS", "True").lower() == "true"

# Proxy (opzionale - se impostato manualmente)
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
# PROXY FINDER - CERCA PROXY PUBBLICI GRATUITI
# ============================================================
PROXY_SOURCES = [
    "https://free-proxy-list.net/",
    "https://api.proxyscrape.com/?request=displayproxies&proxytype=http",
]

def scarica_proxy_da_url(url):
    """Scarica lista proxy da URL"""
    try:
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            proxies = []
            for line in response.text.splitlines():
                line = line.strip()
                if line and not line.startswith('#') and not line.startswith('<!'):
                    if ':' in line:
                        parts = line.split(':')
                        if len(parts) == 2:
                            try:
                                port = int(parts[1])
                                proxies.append({"host": parts[0], "port": port})
                            except:
                                pass
            return proxies
    except Exception as e:
        log(f"   ⚠️ Errore scaricamento: {e}")
    return []

def ottieni_proxy_pubblici():
    """Ottiene lista di proxy pubblici da tutte le fonti"""
    all_proxies = []
    log("📥 Scarico proxy pubblici...")
    
    for url in PROXY_SOURCES:
        proxies = scarica_proxy_da_url(url)
        if proxies:
            log(f"   ✅ Trovati: {len(proxies)} proxy")
            all_proxies.extend(proxies)
    
    # Rimuovi duplicati
    unique = []
    seen = set()
    for p in all_proxies:
        key = f"{p['host']}:{p['port']}"
        if key not in seen:
            seen.add(key)
            unique.append(p)
    
    log(f"✅ Proxy unici: {len(unique)}")
    return unique

def verifica_proxy(proxy, timeout=5):
    """Verifica se un proxy è raggiungibile"""
    try:
        host = proxy["host"]
        port = proxy["port"]
        
        proxies = {
            "http": f"http://{host}:{port}",
            "https": f"http://{host}:{port}"
        }
        
        response = requests.get(
            "http://httpbin.org/ip",
            proxies=proxies,
            timeout=timeout
        )
        
        if response.status_code == 200:
            return proxy, True
    except:
        pass
    return proxy, False

def trova_proxy_funzionante(proxy_list, max_workers=30):
    """Trova il primo proxy funzionante"""
    if not proxy_list:
        return None
    
    log(f"🔍 Cerco proxy funzionante tra {len(proxy_list)}...")
    
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(verifica_proxy, p): p for p in proxy_list[:200]}
        
        for future in as_completed(futures):
            proxy, ok = future.result()
            if ok:
                log(f"✅ Proxy trovato: {proxy['host']}:{proxy['port']}")
                return proxy
    
    log("❌ Nessun proxy funzionante trovato!")
    return None

def ottieni_proxy_automatico():
    """Ottiene un proxy funzionante automaticamente"""
    
    # Se è già configurato un proxy manuale, verificalo
    if PROXY_HOST and PROXY_USER:
        proxy = {
            "host": PROXY_HOST,
            "port": int(PROXY_PORT) if PROXY_PORT else 3128,
            "user": PROXY_USER,
            "pass": PROXY_PASS
        }
        log(f"🔍 Verifico proxy manuale: {PROXY_HOST}:{PROXY_PORT}")
        ok, _ = verifica_proxy(proxy)
        if ok:
            log(f"✅ Proxy manuale funzionante!")
            return proxy
        else:
            log("⚠️ Proxy manuale non funzionante, cerco alternativo...")
    
    # Cerca proxy pubblici
    proxy_list = ottieni_proxy_pubblici()
    if proxy_list:
        proxy = trova_proxy_funzionante(proxy_list)
        if proxy:
            return proxy
    
    log("⚠️ Nessun proxy trovato, procedo senza proxy")
    return None

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
    
    # Ottieni proxy automaticamente
    proxy = ottieni_proxy_automatico()
    
    proxy_config = None
    if proxy:
        host = proxy.get("host")
        port = proxy.get("port")
        user = proxy.get("user", "")
        pwd = proxy.get("pass", "")
        
        if user and pwd:
            log(f"🌐 Proxy: {host}:{port} (con autenticazione)")
            proxy_config = {
                "server": f"http://{host}:{port}",
                "username": user,
                "password": pwd
            }
        else:
            log(f"🌐 Proxy: {host}:{port} (senza autenticazione)")
            proxy_config = {
                "server": f"http://{host}:{port}"
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
            
            # Contatori
            csrf_invalidi = 0
            MAX_CSRF_INVALIDI = 5
            MAX_CYCLES = 5000
            proxy_morto = 0
            
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
                
                try:
                    page.goto(url, wait_until="domcontentloaded", timeout=30000)
                except Exception as e:
                    if "ERR_TUNNEL_CONNECTION_FAILED" in str(e) or "proxy" in str(e).lower():
                        log("⚠️ Proxy morto! Cerco nuovo proxy...")
                        proxy_morto += 1
                        if proxy_morto >= 3:
                            log("🔄 Troppi proxy morti, riavvio il bot...")
                            return
                        # Ricerca nuovo proxy
                        nuovo_proxy = ottieni_proxy_automatico()
                        if nuovo_proxy:
                            log("✅ Nuovo proxy trovato, riavvio il bot...")
                            return
                    continue
                
                page_text = page.content()
                
                # Gestisci CSRF invalido
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
            if "proxy" in str(e).lower() or "tunnel" in str(e).lower():
                log("🔄 Errore proxy, riavvio per nuovo proxy...")
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
