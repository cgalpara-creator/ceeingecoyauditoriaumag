# 🚀 Publicar la app en internet (acceso para tus colegas)

Guía para dejar la contabilidad del Centro de Alumnos **online 24/7**, accesible
desde cualquier computador o celular, sin depender de tu PC.

Recomendación: **PythonAnywhere** (plan gratuito). Razón clave: su disco es
**permanente**, así que la base de datos SQLite (`contabilidad.db`) **no se borra**
al reiniciar. Otros hosts gratuitos (Render free, Railway) borran el disco al
reiniciar y perderías los datos, salvo que pagues un disco persistente.

---

## Opción A — PythonAnywhere (recomendada, gratis)

### 1. Crear la cuenta
1. Entra a **https://www.pythonanywhere.com** y crea una cuenta **Beginner (gratis)**.
2. Tu app quedará en una dirección tipo `https://TUUSUARIO.pythonanywhere.com`.

### 2. Subir el código
**Forma fácil (sin Git):**
1. Comprime la carpeta del proyecto en un `.zip` (sin la carpeta `.venv`).
2. En PythonAnywhere: pestaña **Files** → sube el `.zip`.
3. Abre una consola **Bash** (pestaña *Consoles → Bash*) y descomprime:
   ```bash
   unzip centro-alumnos-contabilidad.zip
   ```

**Forma con Git (si lo subes a GitHub):**
```bash
git clone https://github.com/TU_USUARIO/centro-alumnos-contabilidad.git
```

### 3. Instalar dependencias (en la consola Bash)
```bash
cd centro-alumnos-contabilidad
python3.10 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 4. Crear la Web App
1. Pestaña **Web** → **Add a new web app**.
2. Elige **Manual configuration** (¡no "Flask"!) → **Python 3.10**.

### 5. Apuntar al entorno virtual
En la pestaña **Web**, sección *Virtualenv*, escribe la ruta:
```
/home/TUUSUARIO/centro-alumnos-contabilidad/.venv
```

### 6. Configurar el archivo WSGI
En la pestaña **Web**, haz clic en el enlace del *WSGI configuration file*,
**borra todo** y déjalo así (cambia `TUUSUARIO`):
```python
import sys

ruta = "/home/TUUSUARIO/centro-alumnos-contabilidad"
if ruta not in sys.path:
    sys.path.insert(0, ruta)

# (Opcional pero recomendado) clave secreta propia:
import os
os.environ["SECRET_KEY"] = "pega-aqui-una-clave-larga-y-aleatoria"

from app import app as application   # 'application' es el nombre que espera PythonAnywhere
```
> Si no defines `SECRET_KEY`, la app igual funciona: genera y guarda una sola vez
> en el archivo `.secret_key` (que persiste en el disco de PythonAnywhere).

### 7. Recargar y entrar
1. Pulsa el botón verde **Reload** en la pestaña Web.
2. Abre `https://TUUSUARIO.pythonanywhere.com`.
3. Entra con **admin / admin123**.

### 8. ⚠️ Pasos de seguridad (¡importantes!)
1. **Cambia la contraseña de admin** (barra lateral → *Cambiar contraseña*).
2. Crea una cuenta para cada colega en la sección **Usuarios** y entrégales su
   usuario y contraseña.

> Nota del plan gratuito: PythonAnywhere pide entrar a tu cuenta cada ~3 meses
> para mantener la web activa (un solo clic en un botón "Run until 3 months from today").

---

## Opción B — Render / Railway (si prefieres)

Funciona, pero el disco gratuito es **efímero**: cada reinicio borra
`contabilidad.db`. Para usarlo en serio necesitarías:
- un **disco persistente** (de pago), o
- migrar de SQLite a **PostgreSQL** (cambio mayor de código).

Si igual quieres probarlo para una demo, se usa un servidor de producción:
```bash
pip install gunicorn
gunicorn app:app
```
(Render detecta el `Procfile`/comando `gunicorn app:app`.)

---

## 🔒 Recordatorios de seguridad para multiusuario

- La app **ya guarda las contraseñas cifradas** (hash), nunca en texto plano.
- Cambia la contraseña de `admin` apenas publiques.
- Crea **una cuenta por persona** (así sabes quién entra y puedes quitar accesos).
- El archivo `contabilidad.db` es tu información: haz **respaldos** periódicos
  (en PythonAnywhere puedes descargarlo desde la pestaña *Files*).
