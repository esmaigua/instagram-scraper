"""
instagram_scraper/scraper.py
============================
Scraper de Instagram usando Playwright (modo síncrono).

Arquitectura:
    - Gestión de sesión con storage_state para evitar logins repetidos.
    - Credenciales cargadas exclusivamente desde variables de entorno (.env).
    - Navegación humana simulada (ArrowRight) para iterar publicaciones.
    - Persistencia de datos en JSON formateado.
    - Sin time.sleep(); únicamente auto-esperas de Playwright.

Autor: Proyecto Final — Ingeniería de Sistemas
"""

import json
import os
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from playwright.sync_api import Browser, BrowserContext, Page, Playwright, sync_playwright

# ---------------------------------------------------------------------------
# Configuración global
# ---------------------------------------------------------------------------
load_dotenv()

INSTAGRAM_URL: str = "https://www.instagram.com"
SESSION_FILE: Path = Path("session.json")
OUTPUT_FILE: Path = Path("posts.json")
TARGET_PROFILE: str = os.getenv("IG_TARGET_PROFILE", "nike")
MIN_POSTS: int = 10


# ---------------------------------------------------------------------------
# Módulo de autenticación
# ---------------------------------------------------------------------------
def login(page: Page, username: str, password: str) -> None:
    """Realiza el inicio de sesión en Instagram"""
    if not username or not password:
        raise ValueError("Las credenciales IG_USERNAME e IG_PASSWORD deben estar definidas en .env")

    print("[AUTH] Navegando al formulario de login…")
    page.goto(f"{INSTAGRAM_URL}/accounts/login/", wait_until="networkidle")
    
    # Esperar que el formulario esté listo
    page.wait_for_selector("form", timeout=10000)
    
    # Llenar campos de usuario y contraseña
    print("[AUTH] Rellenando credenciales...")
    
    # Campo de usuario/email
    page.fill("input[type='text']", username)
    # Campo de contraseña  
    page.fill("input[type='password']", password)
    
    print("[AUTH] Credenciales ingresadas")
    
    # Pequeña pausa para evitar detección
    page.wait_for_timeout(1000)
    
    # Hacer click en el botón "Iniciar sesión" usando el aria-label
    print("[AUTH] Haciendo click en Iniciar sesión...")
    page.locator('div[aria-label="Iniciar sesión"]').click()
    
    # Esperar la redirección
    page.wait_for_timeout(5000)
    
    # Verificar resultado
    current_url = page.url
    print(f"[AUTH] URL actual: {current_url}")
    
    if "accounts/login" in current_url:
        print("[ERROR] Login fallido - aún en página de login")
        page.screenshot(path="login_failed.png")
        raise Exception("No se pudo hacer login - verifica tus credenciales")
    
    print("[AUTH] Login exitoso!")
    
    # Cerrar modales si aparecen
    try:
        modal = page.get_by_role("button", name="Ahora no")
        if modal.is_visible(timeout=3000):
            modal.click()
    except:
        pass
    
    try:
        modal = page.get_by_role("button", name="Not now")
        if modal.is_visible(timeout=3000):
            modal.click()
    except:
        pass

def get_or_create_session(browser: Browser, username: str, password: str) -> BrowserContext:
    """
    Devuelve un BrowserContext autenticado.
    """
    context = None
    
    if SESSION_FILE.exists():
        print(f"[SESSION] Sesión encontrada en '{SESSION_FILE}'. Verificando...")
        context = browser.new_context(storage_state=str(SESSION_FILE))
        
        # Verificar si la sesión es válida
        test_page = context.new_page()
        test_page.goto(f"{INSTAGRAM_URL}/", wait_until="domcontentloaded")
        test_page.wait_for_timeout(3000)
        
        # Verificar si estamos logueados (buscando el avatar o feed)
        is_logged_in = False
        try:
            # Buscar el avatar del usuario o el feed
            avatar = test_page.locator("svg[aria-label='Perfil'], img[alt*='perfil']")
            if avatar.count() > 0:
                is_logged_in = True
                print("[SESSION] Sesión válida encontrada.")
            else:
                print("[SESSION] Sesión inválida o expirada.")
        except:
            print("[SESSION] Error verificando sesión.")
        
        test_page.close()
        
        if not is_logged_in:
            print("[SESSION] Sesión inválida, eliminando archivo...")
            SESSION_FILE.unlink()  # Eliminar sesión inválida
            context.close()
            context = None
    
    if context is None:
        print("[SESSION] No se encontró sesión válida. Iniciando login…")
        context = browser.new_context(
            viewport={"width": 1280, "height": 900},
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
        )
        page = context.new_page()
        login(page, username, password)
        
        # Esperar a que el login se complete y el feed cargue
        page.wait_for_timeout(5000)
        
        # Verificar login exitoso
        if "accounts/login" in page.url:
            print("[ERROR] El login falló")
            page.screenshot(path="login_failed.png")
            raise Exception("No se pudo iniciar sesión")
        
        page.close()
        context.storage_state(path=str(SESSION_FILE))
        print(f"[SESSION] Sesión guardada en '{SESSION_FILE}'.")
    
    return context


# ---------------------------------------------------------------------------
# Módulo de extracción
# ---------------------------------------------------------------------------

def extract_post_data(page: Page) -> dict:
    """
    Extrae los datos de la publicación actualmente abierta en el modal.

    Usa selectores basados en roles y atributos ARIA/semánticos para
    mayor resiliencia ante cambios en las clases CSS de Instagram.

    Args:
        page: Instancia de página con el modal de post abierto.

    Returns:
        Diccionario con las claves:
            - ``post_url``   (str): URL canónica del post.
            - ``image_url``  (str | None): src de la imagen principal.
            - ``description``(str | None): Texto de la descripción/caption.
    """
    post_url: str = page.url

    # --- Imagen principal ---
    # El <img> dentro del article del modal que tiene un src de CDN
    image_url: Optional[str] = None
    try:
        img_locator = page.locator("article img[src*='cdninstagram'], article img[src*='fbcdn']").first
        img_locator.wait_for(state="visible", timeout=8_000)
        image_url = img_locator.get_attribute("src")
    except Exception as exc:
        print(f"  [WARN] No se pudo extraer imagen: {exc}")

    # --- Descripción ---
    description: Optional[str] = None
    try:
        # El caption suele estar en un <h1> o en un <span> dentro de un
        # elemento con rol "dialog" (el modal de post).
        caption_locator = page.locator(
            "article [role='dialog'] h1, "
            "div[role='dialog'] h1, "
            "article span[dir='auto']"
        ).first
        caption_locator.wait_for(state="visible", timeout=6_000)
        description = caption_locator.inner_text()
    except Exception as exc:
        print(f"  [WARN] No se pudo extraer descripción: {exc}")

    return {
        "post_url": post_url,
        "image_url": image_url,
        "description": description,
    }


def scrape_profile_posts(context: BrowserContext, profile: str, count: int) -> list[dict]:
    """
    Navega al perfil indicado y extrae datos de ``count`` publicaciones.
    """
    page: Page = context.new_page()
    posts: list[dict] = []

    try:
        profile_url = f"{INSTAGRAM_URL}/{profile}/"
        print(f"[SCRAPER] Navegando al perfil: {profile_url}")
        page.goto(profile_url, wait_until="domcontentloaded")

        # Esperar a que la grilla de posts cargue
        page.wait_for_selector("main article", timeout=20000)
        
        # --- CERRAR CUALQUIER MODAL/POPUP ---
        print("[SCRAPER] Cerrando modales...")
        
        # Presionar Escape varias veces para cerrar modales
        for _ in range(3):
            page.keyboard.press("Escape")
            page.wait_for_timeout(500)
        
        # Buscar y cerrar botones comunes de modales
        modal_buttons = [
            "button:has-text('Ahora no')",
            "button:has-text('Not now')", 
            "button:has-text('Cancel')",
            "button:has-text('Cerrar')",
            "button:has-text('Close')",
            "div[aria-label='Close']",
            "svg[aria-label='Close']",
            "button:has-text('Guardar información')",
            "button:has-text('Save Info')",
        ]
        
        for selector in modal_buttons:
            try:
                modal = page.locator(selector)
                if modal.count() > 0 and modal.first.is_visible(timeout=2000):
                    modal.first.click()
                    print(f"[SCRAPER] Modal cerrado: {selector}")
                    page.wait_for_timeout(1000)
            except:
                pass
        
        # --- Hacer click en el primer post con JavaScript (evita el overlay) ---
        print("[SCRAPER] Abriendo primer post...")
        
        # Método 1: Click con JavaScript directamente
        try:
            page.evaluate("""
                const firstPost = document.querySelector('main article a');
                if (firstPost) {
                    firstPost.click();
                    return true;
                }
                return false;
            """)
            print("[SCRAPER] Click con JavaScript ejecutado")
        except Exception as e:
            print(f"[SCRAPER] Error en JavaScript click: {e}")
        
        # Esperar que el modal del post se abra
        page.wait_for_timeout(3000)
        
        # Verificar que estamos en un post (URL contiene /p/ o /reel/)
        current_url = page.url
        if "/p/" not in current_url and "/reel/" not in current_url:
            print(f"[WARNING] No se abrió un post. URL actual: {current_url}")
            # Intentar click normal como fallback
            first_post = page.locator("main article a").first
            first_post.click()
            page.wait_for_timeout(3000)
        
        print(f"[SCRAPER] Extrayendo {count} publicaciones…\n")

        for index in range(count):
            # Esperar a que el modal del post esté activo
            page.wait_for_selector("article img", timeout=15000)

            print(f"  [{index + 1}/{count}] Extrayendo post: {page.url}")
            try:
                data = extract_post_data(page)
                posts.append(data)
                print(f"        ✓ image_url: {'OK' if data['image_url'] else 'N/A'}")
                print(f"        ✓ description: {repr(data['description'][:60]) if data['description'] else 'N/A'}")
            except Exception as exc:
                print(f"  [ERROR] Falló extracción del post {index + 1}: {exc}")
                posts.append({"post_url": page.url, "image_url": None, "description": None, "error": str(exc)})

            # Navegar al siguiente post
            if index < count - 1:
                page.keyboard.press("ArrowRight")
                page.wait_for_timeout(3000)  # Esperar a que cargue el siguiente

    except Exception as e:
        print(f"[SCRAPER] Error general: {e}")
        page.screenshot(path="error_screenshot.png")
        print("[SCRAPER] Screenshot guardado: error_screenshot.png")
    finally:
        page.close()

    return posts


# ---------------------------------------------------------------------------
# Módulo de persistencia
# ---------------------------------------------------------------------------

def save_to_json(data: list[dict], filepath: Path) -> None:
    """
    Serializa y escribe la lista de posts en un archivo JSON formateado.

    Args:
        data:     Lista de diccionarios con los datos extraídos.
        filepath: Ruta destino del archivo .json.
    """
    with open(filepath, "w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=2)
    print(f"\n[OUTPUT] {len(data)} posts guardados en '{filepath}'.")


# ---------------------------------------------------------------------------
# Punto de entrada principal
# ---------------------------------------------------------------------------

def main() -> None:
    """
    Orquesta el flujo completo del scraper:
        1. Lee credenciales desde .env.
        2. Lanza Playwright y obtiene/crea sesión autenticada.
        3. Extrae posts del perfil objetivo.
        4. Persiste resultados en JSON.
    """
    username: str = os.getenv("IG_USERNAME", "")
    password: str = os.getenv("IG_PASSWORD", "")

    with sync_playwright() as playwright:
        browser: Browser = playwright.chromium.launch(
            headless=False,          # headless=True para entornos CI/CD
            slow_mo=350,             # Humaniza las interacciones (ms)
        )
        context: Optional[BrowserContext] = None

        try:
            context = get_or_create_session(browser, username, password)
            posts = scrape_profile_posts(context, TARGET_PROFILE, MIN_POSTS)
            save_to_json(posts, OUTPUT_FILE)

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