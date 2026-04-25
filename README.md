# Extractor de Datos de Instagram (Scraper)

Este proyecto es una herramienta para visitar un perfil público de Instagram y extraer la información de sus publicaciones.

## ⚙️ Requisitos

* **Python 3.11** Para garantizar la total compatibilidad del código y sus dependencias.
* Dependencias instaladas (Playwright y python-dotenv).

## 🧠 ¿Cómo funciona?

El proceso detrás de este script se enfoca en ser eficiente y, sobre todo, en pasar desapercibido ante los sistemas de seguridad de Instagram. El paso a paso de su funcionamiento es el siguiente:

1. El programa utiliza una herramienta llamada `Playwright`, mediante ella, tambien permite abrir un navegador Chromium. Esto le permite interactuar visualmente con la página (como localizar las casillas para escribir) de la misma manera que lo haría un humano.
2. **Inicio de Sesión Inteligente:** * Al ejecutarse, el programa primero verifica si ya tiene una sesión abierta guardada previamente mediante "cookies". Si es así, ingresa directamente.
   * Si es la primera vez que se ejecuta y no hay cookies guardadas, el sistema lee un archivo oculto llamado `.env` donde se encuentran guardados el usuario, la contraseña y el perfil que queremos investigar. Automáticamente, rellena los campos de texto en la pantalla de inicio de Instagram e ingresa.
3. **Manejo de Seguridad (Recaptcha):** Si durante el inicio de sesión Instagram lanza una alerta de seguridad o un *Recaptcha*, el programa está configurado para pausarse de inmediato. Esto te permite resolver el desafío manualmente en el navegador. Una vez que demuestras que eres humano, solo debes presionar "Enter" en la consola de comandos para que el programa retome su trabajo por sí solo.
4. **Navegación y Búsqueda:** * Tras entrar exitosamente, el navegador se dirige directamente al perfil objetivo.
   * Empieza a deslizar la pantalla hacia abajo (*scroll*) de forma automática para ir revelando y cargando más publicaciones.
5. **Extracción de la Información:** El programa hace clic y entra en cada publicación encontrada para recopilar los datos más importantes. Luego, organiza esa información en una estructura de datos `JSON` con el siguiente formato:
   ```
   {
     "post_url": "...",
     "caption": "...",
     "likes": "...",
     "image_url": "..."
   }
Toda esta información se guarda finalmente en un archivo con el mismo formato .json.<br>
6. **Camuflaje y Pausas (Anti-detección):** Para evitar que Instagram detecte que esto es un robot, se implementaron pausas de tiempo totalmente aleatorias (random) en todo el código. Así, el tiempo entre un clic, un scroll o la carga de una página siempre es distinto, imitando a la perfección el ritmo de una persona real.<br>
7. **Manejo de Errores y Capturas de Pantalla:** Si en cualquier parte del proceso ocurre un error inesperado que detenga la ejecución, se toma una captura de pantalla (screenshot) exacta de dónde y cómo se quedó atascado. Esto sirve como evidencia para saber qué falló. Finalmente, y de forma segura, cierra el navegador.

## 🚀 Instalación y Uso (Paso a Paso)

Para ejecutar este proyecto siguiendo las mejores prácticas de desarrollo, sigue estas instrucciones:

### 1. Clonar el repositorio

Abrir el  terminal y clonar este proyecto en su computadora:

```bash
git clone <URL_DEL_REPOSITORIO>
cd <NOMBRE_DE_TU_CARPETA>
```

### 2. Crear y activar un entorno virtual

Es una buena práctica aislar las dependencias del proyecto. Cree un entorno virtual ejecutando:

**En Windows:**

```bash
python -m venv venv
venv\Scripts\activate
```

### 3. Instalar las dependencias

Con el entorno virtual activado, instale las librerías necesarias ejecutando:

```bash
pip install -r requirements.txt
```

### 4. Instalar los navegadores de Playwright

Como Playwright utiliza navegadores internos para simular las acciones, es necesario descargar el motor de Chromium:

```bash
playwright install chromium
```

### 5. Configurar las variables de entorno

En el proyecto hay un archivo llamado `.env.example`. Crear un nuevo archivo llamado exactamente `.env` y copiar la estructura del ejemplo, rellenando con sus datos:

```env
IG_USERNAME=tu_usuario_aqui
IG_PASSWORD=tu_contraseña_aqui
IG_TARGET_PROFILE=perfil_a_investigar
```

### 6. Ejecutar el script

Finalmente, ejecutar el programa con:

```bash
python scraper.py
```

*(Verificar y en caso que sea necesario reemplazar `scraper.py` por el nombre exacto de tu archivo si es diferente).*
