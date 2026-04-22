"""
Scrapear instagram con el uso de cookies
"""

import json
import os
import random
import re
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from playwright.sync_api import Browser, BrowserContext, Page, sync_playwright, TimeoutError as PlaywrightTimeoutError

# ---------------------------------------------------------------------------
# Configuración global
# ---------------------------------------------------------------------------
load_dotenv()

INSTAGRAM_URL: str = "https://www.instagram.com"
SESSION_FILE: Path = Path("session.json")
OUTPUT_FILE: Path = Path("posts.json")
TARGET_PROFILE: str = os.getenv("IG_TARGET_PROFILE", "ldu_oficial")
MIN_POSTS: int = 5

def human_delay(min_s: float = 1.5, max_s: float = 3.5) -> None:
    """Pausa aleatoria para evadir detección heurística."""
    time.sleep(random.uniform(min_s, max_s))

def apply_stealth(context: BrowserContext) -> None:
    """Inyecta un script para ocultar el rastro de automatización (WebDriver)."""
    context.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")

# ---------------------------------------------------------------------------
# Módulo de autenticación
# ---------------------------------------------------------------------------
def login(page: Page, username: str, password: str) -> None:
    """Realiza el inicio de sesión usando la estrategia de 'Enter'."""
    if not username or not password:
        raise ValueError("Las credenciales deben estar definidas en .env")

    print("[AUTH] Navegando al login…")
    page.goto(f"{INSTAGRAM_URL}/accounts/login/", timeout=30000)
    human_delay(2, 4)
    
    print("[AUTH] Rellenando credenciales...")
    page.locator('input[name="username"]').first.fill(username)
    human_delay(1, 2)
    
    pass_input = page.locator('input[name="password"]').first
    pass_input.fill(password)
    human_delay(1, 2)
    
    print("[AUTH] Presionando Enter para loguearse...")
    pass_input.press("Enter")
    
    # Pausa larga para asentar la carga inicial
    human_delay(5, 8)
    
    # Manejo de Captcha si aparece
    if "recaptcha" in page.url or "challenge" in page.url:
        print("\n" + "="*60)
        print("⚠️  COMPLETA EL CAPTCHA MANUALMENTE ⚠️")
        print("="*60)
        input("Presiona ENTER en consola cuando estés en el feed de Instagram...")
        print("="*60 + "\n")
    
    # Verificar éxito (si sigue en la página de login, falló)
    if "accounts/login" in page.url:
        page.screenshot(path="login_failed.png")
        raise Exception("Login fallido. Revisa login_failed.png")
    
    print("[AUTH] ¡Login aparentemente exitoso!")
    human_delay(3, 5) # Asentando cookies

def get_or_create_session(browser: Browser, username: str, password: str) -> BrowserContext:
    """Gestiona el contexto, aplicando stealth nativo y cargando sesión."""
    context = browser.new_context(
        viewport={"width": 1280, "height": 900},
        user_agent=(
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        )
    )
    apply_stealth(context) # <- Clave para que no detecte el bot

    if SESSION_FILE.exists():
        print(f"[SESSION] Sesión encontrada en '{SESSION_FILE}'. Validando…")
        # Cerramos este contexto temporal e iniciamos uno con las cookies guardadas
        context.close()
        context = browser.new_context(
            storage_state=str(SESSION_FILE),
            viewport={"width": 1280, "height": 900},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
        )
        apply_stealth(context)
        
        page = context.new_page()
        try:
            page.goto(INSTAGRAM_URL, timeout=20000)
            human_delay(3, 5)
            # Si aparece el input de usuario, es porque la sesión expiró
            if page.locator('input[name="username"]').is_visible(timeout=4000):
                print("[WARN] Sesión expirada. Relogueando...")
                SESSION_FILE.unlink()
            else:
                print("[SESSION] Sesión activa.")
                page.close()
                return context
        except Exception:
            pass
        page.close()
    
    # No hay sesion o expiró.
    print("[SESSION] Iniciando login desde cero…")
    page = context.new_page()
    login(page, username, password)
    context.storage_state(path=str(SESSION_FILE))
    print(f"[SESSION] Nueva sesión guardada en '{SESSION_FILE}'.")
    page.close()
    
    return context

# ---------------------------------------------------------------------------
# Módulo de extracción
# ---------------------------------------------------------------------------
def get_post_urls(page: Page, profile: str, count: int) -> list[str]:
    """Recolecta las URLs de la grilla del perfil."""
    profile_url = f"{INSTAGRAM_URL}/{profile}/"
    print(f"[SCRAPER] Visitando perfil: {profile_url}")
    page.goto(profile_url, timeout=30000)
    human_delay(3, 5)

    post_urls = set()
    print(f"[SCRAPER] Recolectando URLs (objetivo: {count})...")

    while len(post_urls) < count:
        anchors = page.locator('a[href*="/p/"], a[href*="/reel/"]').all()
        for a in anchors:
            href = a.get_attribute("href")
            if href:
                url_limpia = f"{INSTAGRAM_URL}{href.split('?')[0]}"
                post_urls.add(url_limpia)

        if len(post_urls) >= count:
            break
            
        page.evaluate("window.scrollBy(0, window.innerHeight)")
        human_delay(2, 4)

    return list(post_urls)[:count]

def scrape_single_post(page: Page, post_url: str, index: int) -> dict:
    """Extrae datos usando la etiqueta SEO meta (Método infalible)."""
    data = {
        "post_url": post_url,
        "caption": None,
        "likes": None,
        "image_url": None
    }
    try:
        page.goto(post_url, wait_until="domcontentloaded", timeout=30000)
        human_delay(2, 3)
        page.evaluate("window.scrollBy(0, 200)") # Fuerza renderizado de imágenes

        # 1. Extracción vía Meta Tag SEO (La magia)
        meta_locator = page.locator('meta[property="og:description"], meta[name="description"]').first
        content = meta_locator.get_attribute("content", timeout=3000)
        
        if content:
            # Separar el caption de la info ("100 likes, 2 comments - cuenta: Caption aquí")
            if ":" in content:
                data["caption"] = content.split(":", 1)[1].strip().strip('"')
            else:
                data["caption"] = content
                
            # Extraer likes usando Regex
            likes_match = re.search(r'([\d,.]+)\s*(likes|Me gusta)', content, re.IGNORECASE)
            if likes_match:
                data["likes"] = likes_match.group(1).replace(',', '')

        # 2. Extraer Imagen
        imgs = page.locator('img[style*="object-fit: cover"]').all()
        for img in imgs:
            src = img.get_attribute("src")
            if src and ("scontent" in src or "fbcdn" in src or "instagram" in src):
                data["image_url"] = src
                break # Tomar la primera imagen válida

    except Exception as e:
        print(f"  [ERROR] Falla en {post_url}: {e}")
        data["error"] = str(e)

    return data

# ---------------------------------------------------------------------------
# Punto de entrada principal
# ---------------------------------------------------------------------------
def main() -> None:
    username: str = os.getenv("IG_USERNAME", "")
    password: str = os.getenv("IG_PASSWORD", "")

    with sync_playwright() as playwright:
        # Desactivamos AutomationControlled desde el lanzamiento
        browser: Browser = playwright.chromium.launch(
            headless=False,
            args=["--disable-blink-features=AutomationControlled"]
        )
        context: Optional[BrowserContext] = None

        try:
            context = get_or_create_session(browser, username, password)
            page = context.new_page()
            
            # 1. Obtener URLs
            urls = get_post_urls(page, TARGET_PROFILE, MIN_POSTS)
            
            # 2. Iterar y extraer datos
            print(f"\n[SCRAPER] Extrayendo datos de {len(urls)} publicaciones...")
            posts_data = []
            
            for index, url in enumerate(urls):
                print(f"  [{index + 1}/{len(urls)}] Analizando: {url}")
                post_info = scrape_single_post(page, url, index)
                posts_data.append(post_info)
                
                print(f"        ✓ Likes: {post_info.get('likes', 'N/A')}")
                print(f"        ✓ Caption: {repr(post_info.get('caption', '')[:40])}...")
                
                # Pausa humana entre posteos para no saturar
                human_delay(4, 7)
            
            # 3. Guardar Data
            with open(OUTPUT_FILE, "w", encoding="utf-8") as fh:
                json.dump(posts_data, fh, ensure_ascii=False, indent=4)
            print(f"\n[OUTPUT] Datos guardados en '{OUTPUT_FILE}'.")

        except ValueError as exc:
            print(f"[FATAL] Error de configuración: {exc}")
        except Exception as exc:
            print(f"[FATAL] Error inesperado: {exc}")
            raise
        finally:
            if context:
                context.close()
            browser.close()
            print("[CLEANUP] Navegador cerrado correctamente.")

if __name__ == "__main__":
    main()