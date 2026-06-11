"""
app.py
------
Software contable web (Flask) del Centro de Alumnos.

Estilo ERP simple (Odoo/Nubox) para una sola organización, en CLP sin decimales.

Ejecutar con:
    python app.py
Luego abrir http://127.0.0.1:5000 en el navegador.
"""

from __future__ import annotations

import os
import secrets
from datetime import date
from functools import wraps
from io import BytesIO
from pathlib import Path

import pandas as pd
from flask import (Flask, flash, redirect, render_template, request,
                   send_file, session, url_for)
from reportlab.lib.pagesizes import A5
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas

import database as db

# Datos de la organización (monoempresa).
# Para cambiar el nombre visible en toda la app, edita "nombre" aquí.
EMPRESA = {
    "nombre": "CEE Inge Eco y Auditoría UMAG",
    "moneda": "CLP",
}

# Meses en español (valor de 2 dígitos → nombre) para los filtros desplegables.
MESES = [
    ("01", "Enero"), ("02", "Febrero"), ("03", "Marzo"), ("04", "Abril"),
    ("05", "Mayo"), ("06", "Junio"), ("07", "Julio"), ("08", "Agosto"),
    ("09", "Septiembre"), ("10", "Octubre"), ("11", "Noviembre"),
    ("12", "Diciembre"),
]

def _obtener_secret_key() -> str:
    """
    Clave para firmar las sesiones (login). Orden de prioridad:
      1. Variable de entorno SECRET_KEY (recomendado en producción).
      2. Archivo local '.secret_key' (se genera solo la 1ª vez y persiste,
         así las sesiones no se invalidan al reiniciar el servidor).
    """
    if os.environ.get("SECRET_KEY"):
        return os.environ["SECRET_KEY"]
    archivo = Path(__file__).parent / ".secret_key"
    if archivo.exists():
        return archivo.read_text().strip()
    clave = secrets.token_hex(32)
    archivo.write_text(clave)
    return clave


app = Flask(__name__)
app.secret_key = _obtener_secret_key()

# Crea las tablas al arrancar.
db.init_db()

# Expone helpers/datos a TODAS las plantillas (formato CLP, empresa, fecha hoy).
app.jinja_env.globals.update(clp=db.format_clp, empresa=EMPRESA)


@app.context_processor
def inyectar_comunes():
    """Variables disponibles en todas las plantillas (ej. el mes actual)."""
    usuario = session.get("usuario")
    return {"mes_actual": date.today().strftime("%Y-%m"),
            "hoy": date.today().isoformat(),
            "usuario_actual": usuario,
            "es_admin": bool(usuario) and db.es_usuario_admin(usuario)}


def admin_required(f):
    """Decorador: restringe una ruta solo a usuarios administradores."""
    @wraps(f)
    def envoltura(*args, **kwargs):
        usuario = session.get("usuario")
        if not usuario or not db.es_usuario_admin(usuario):
            flash("Solo un administrador puede gestionar usuarios.", "danger")
            return redirect(url_for("index"))
        return f(*args, **kwargs)
    return envoltura


# ---------------------------------------------------------------------------
# Autenticación
# ---------------------------------------------------------------------------
# Endpoints accesibles sin haber iniciado sesión.
RUTAS_PUBLICAS = {"login", "static"}


@app.before_request
def requerir_login():
    """Bloquea el acceso a toda la app si no hay sesión iniciada."""
    if request.endpoint not in RUTAS_PUBLICAS and not session.get("usuario"):
        return redirect(url_for("login"))


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        usuario = request.form.get("usuario", "")
        clave = request.form.get("clave", "")
        if db.verificar_credenciales(usuario, clave):
            session["usuario"] = usuario.strip()
            flash(f"Bienvenido/a, {usuario.strip()}.", "success")
            return redirect(url_for("index"))
        flash("Usuario o contraseña incorrectos.", "danger")
    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    flash("Sesión cerrada.", "info")
    return redirect(url_for("login"))


@app.route("/usuarios")
@admin_required
def usuarios():
    return render_template("usuarios.html", usuarios=db.listar_usuarios())


@app.route("/usuarios/nuevo", methods=["POST"])
@admin_required
def nuevo_usuario():
    usuario = request.form.get("usuario", "").strip()
    clave = request.form.get("clave", "")
    if not usuario or len(clave) < 4:
        flash("Usuario obligatorio y contraseña de al menos 4 caracteres.", "danger")
    elif db.crear_usuario(usuario, clave):  # colegas: rol normal (no admin)
        flash(f"Usuario «{usuario}» creado.", "success")
    else:
        flash(f"El usuario «{usuario}» ya existe.", "danger")
    return redirect(url_for("usuarios"))


@app.route("/usuarios/<int:uid>/renombrar", methods=["POST"])
@admin_required
def renombrar_usuario(uid: int):
    nuevo = request.form.get("nuevo_nombre", "").strip()
    if not nuevo:
        flash("Escribe el nuevo nombre de usuario.", "danger")
        return redirect(url_for("usuarios"))
    ok, anterior = db.renombrar_usuario(uid, nuevo)
    if ok:
        # Si renombras tu propia cuenta, actualiza la sesión para no quedar colgado.
        if session.get("usuario") == anterior:
            session["usuario"] = nuevo
        flash(f"Usuario «{anterior}» renombrado a «{nuevo}».", "success")
    else:
        flash(f"No se pudo renombrar (¿«{nuevo}» ya existe?).", "danger")
    return redirect(url_for("usuarios"))


@app.route("/usuarios/<int:uid>/eliminar", methods=["POST"])
@admin_required
def borrar_usuario(uid: int):
    # No permitir quedarse sin ningún usuario (te dejaría fuera de la app).
    if db.contar_usuarios() <= 1:
        flash("No puedes eliminar el último usuario.", "danger")
    else:
        db.eliminar_usuario(uid)
        flash("Usuario eliminado.", "warning")
    return redirect(url_for("usuarios"))


@app.route("/cambiar-clave", methods=["POST"])
def cambiar_clave():
    actual = request.form.get("actual", "")
    nueva = request.form.get("nueva", "")
    usuario = session.get("usuario", "")
    if not db.verificar_credenciales(usuario, actual):
        flash("La contraseña actual no es correcta.", "danger")
    elif len(nueva) < 4:
        flash("La nueva contraseña debe tener al menos 4 caracteres.", "danger")
    else:
        db.cambiar_clave(usuario, nueva)
        flash("Contraseña actualizada correctamente.", "success")
    return redirect(request.referrer or url_for("index"))


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------
@app.route("/")
def index():
    balance = db.calcular_balance()
    balance_mes = db.calcular_balance(mes=date.today().strftime("%Y-%m"))
    mensual = db.resumen_mensual()
    recientes = db.obtener_transacciones()[:8]
    egresos_cat = db.resumen_por_categoria("Egreso")

    return render_template(
        "dashboard.html",
        balance=balance,
        balance_mes=balance_mes,
        # Series para Chart.js (listas simples).
        chart_labels=[m["mes"] for m in mensual],
        chart_ingresos=[m["ingresos"] for m in mensual],
        chart_egresos=[m["egresos"] for m in mensual],
        cat_labels=[c["categoria"] for c in egresos_cat],
        cat_valores=[c["total"] for c in egresos_cat],
        recientes=recientes,
    )


# ---------------------------------------------------------------------------
# Transacciones
# ---------------------------------------------------------------------------
@app.route("/transacciones")
def transacciones():
    # Filtros vía query string (?tipo=&categoria=&desde=&hasta=).
    tipo = request.args.get("tipo") or None
    categoria = request.args.get("categoria") or None
    desde = request.args.get("desde") or None
    hasta = request.args.get("hasta") or None

    items = db.obtener_transacciones(tipo=tipo, categoria=categoria,
                                     desde=desde, hasta=hasta)
    total = sum(t["monto"] if t["tipo"] == "Ingreso" else -t["monto"]
                for t in items)

    return render_template(
        "transacciones.html",
        items=items,
        total_filtrado=total,
        categorias=db.obtener_categorias(),
        cat_ingreso=db.obtener_categorias("Ingreso"),
        cat_egreso=db.obtener_categorias("Egreso"),
        metodos=db.METODOS_PAGO,
        f_tipo=tipo or "", f_categoria=categoria or "",
        f_desde=desde or "", f_hasta=hasta or "",
    )


@app.route("/transacciones/nueva", methods=["POST"])
def nueva_transaccion():
    f = request.form
    try:
        monto = int(round(float(f.get("monto", 0))))
    except ValueError:
        monto = 0
    if monto <= 0:
        flash("El monto debe ser un número mayor que cero.", "danger")
    else:
        db.agregar_transaccion(
            f["fecha"], f["tipo"], f["categoria"],
            f.get("descripcion", ""), monto, f["metodo_pago"],
            folio=f.get("folio", ""),
        )
        flash("Transacción registrada correctamente.", "success")
    return redirect(request.referrer or url_for("transacciones"))


@app.route("/transacciones/<int:tid>/editar", methods=["POST"])
def editar_transaccion(tid: int):
    f = request.form
    try:
        monto = int(round(float(f.get("monto", 0))))
    except ValueError:
        monto = 0
    if monto <= 0:
        flash("El monto debe ser un número mayor que cero.", "danger")
    else:
        db.actualizar_transaccion(
            tid, f["fecha"], f["tipo"], f["categoria"],
            f.get("descripcion", ""), monto, f["metodo_pago"],
            folio=f.get("folio", ""),
        )
        flash(f"Transacción #{tid} actualizada.", "success")
    return redirect(url_for("transacciones"))


@app.route("/transacciones/<int:tid>/eliminar", methods=["POST"])
def eliminar_transaccion(tid: int):
    db.eliminar_transaccion(tid)
    flash(f"Transacción #{tid} eliminada.", "warning")
    return redirect(request.referrer or url_for("transacciones"))


# ---------------------------------------------------------------------------
# Categorías
# ---------------------------------------------------------------------------
@app.route("/categorias/nueva", methods=["POST"])
def nueva_categoria():
    nombre = request.form.get("nombre", "").strip()
    tipo = request.form.get("tipo", "Ingreso")
    if nombre:
        db.agregar_categoria(nombre, tipo)
        flash(f"Categoría «{nombre}» añadida a {tipo}.", "success")
    else:
        flash("Escribe un nombre de categoría.", "danger")
    return redirect(request.referrer or url_for("transacciones"))


@app.route("/categorias/<int:cid>/eliminar", methods=["POST"])
def eliminar_categoria(cid: int):
    db.eliminar_categoria(cid)
    flash("Categoría eliminada.", "warning")
    return redirect(request.referrer or url_for("transacciones"))


# ---------------------------------------------------------------------------
# Reportes
# ---------------------------------------------------------------------------
@app.route("/reportes")
def reportes():
    # Filtros por listas desplegables: mes ("01".."12") y año ("YYYY").
    mes = request.args.get("mes") or ""
    anio = request.args.get("anio") or ""

    # Construye un prefijo de fecha para el filtro LIKE 'prefijo%':
    #   año + mes  -> "2026-06"   (mes exacto)
    #   solo año   -> "2026-"     (todo el año)
    #   solo mes   -> "____-06"   ('_' es comodín en LIKE: ese mes en cualquier año)
    #   nada       -> None        (todo el histórico)
    if anio and mes:
        prefijo = f"{anio}-{mes}"
    elif anio:
        prefijo = f"{anio}-"
    elif mes:
        prefijo = f"____-{mes}"
    else:
        prefijo = None

    ingresos = db.resumen_por_categoria("Ingreso", mes=prefijo)
    egresos = db.resumen_por_categoria("Egreso", mes=prefijo)
    balance = db.calcular_balance(mes=prefijo)
    return render_template(
        "reportes.html",
        ingresos=ingresos, egresos=egresos, balance=balance,
        meses=MESES, anios=db.anios_disponibles(),
        f_mes=mes, f_anio=anio,
    )


# ---------------------------------------------------------------------------
# Exportar a Excel
# ---------------------------------------------------------------------------
@app.route("/exportar")
def exportar():
    """Genera y descarga un .xlsx con todo el libro de transacciones."""
    items = db.obtener_transacciones()
    df = pd.DataFrame(items)
    if not df.empty:
        df = df.rename(columns={
            "id": "ID", "folio": "Folio", "fecha": "Fecha", "tipo": "Tipo",
            "categoria": "Categoría", "descripcion": "Descripción",
            "monto": "Monto (CLP)", "metodo_pago": "Método de pago",
        })

    buffer = BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Libro")
        hoja = writer.sheets["Libro"]
        for columna in hoja.columns:
            ancho = max((len(str(c.value)) for c in columna if c.value),
                        default=12)
            hoja.column_dimensions[columna[0].column_letter].width = ancho + 2
    buffer.seek(0)

    return send_file(
        buffer, as_attachment=True,
        download_name=f"contabilidad_{date.today().isoformat()}.xlsx",
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


# ---------------------------------------------------------------------------
# Comprobante PDF por transacción
# ---------------------------------------------------------------------------
def _ruta_logo() -> str | None:
    """Devuelve la ruta del logo si existe en static/ (logo.png/.jpg), si no None."""
    base = Path(__file__).parent / "static"
    for nombre in ("logo.png", "logo.jpg", "logo.jpeg"):
        p = base / nombre
        if p.exists():
            return str(p)
    return None


def _generar_comprobante_pdf(t: dict) -> BytesIO:
    """Construye un comprobante PDF (tamaño A5) para una transacción."""
    buffer = BytesIO()
    c = canvas.Canvas(buffer, pagesize=A5)
    ancho, alto = A5

    y = alto - 15 * mm

    # Encabezado: logo si existe; si no, el nombre en texto (respaldo).
    logo = _ruta_logo()
    if logo:
        img = ImageReader(logo)
        iw, ih = img.getSize()
        w = 110 * mm
        h = w * ih / iw
        if h > 42 * mm:          # limita la altura para no comerse la página
            h = 42 * mm
            w = h * iw / ih
        c.drawImage(logo, (ancho - w) / 2, y - h, width=w, height=h,
                    mask="auto", preserveAspectRatio=True)
        y = y - h - 8 * mm
    else:
        c.setFont("Helvetica-Bold", 15)
        c.drawCentredString(ancho / 2, y - 6 * mm, EMPRESA["nombre"])
        y -= 16 * mm

    # Título del comprobante (centrado).
    titulo = "INGRESO" if t["tipo"] == "Ingreso" else "EGRESO"
    c.setFont("Helvetica-Bold", 13)
    c.drawCentredString(ancho / 2, y, f"COMPROBANTE DE {titulo}")
    y -= 7 * mm
    c.setFont("Helvetica", 10)
    c.drawCentredString(ancho / 2, y,
                        f"N° {t.get('folio') or t['id']}   ·   {t['fecha']}")
    y -= 6 * mm

    # Línea separadora.
    c.line(18 * mm, y, ancho - 18 * mm, y)
    y -= 10 * mm

    # Detalle (etiqueta: valor).
    filas = [
        ("Tipo", t["tipo"]),
        ("Categoría", t["categoria"]),
        ("Descripción", t.get("descripcion") or "—"),
        ("Método de pago", t["metodo_pago"]),
    ]
    for etiqueta, valor in filas:
        c.setFont("Helvetica-Bold", 11)
        c.drawString(20 * mm, y, f"{etiqueta}:")
        c.setFont("Helvetica", 11)
        c.drawString(62 * mm, y, str(valor))
        y -= 9 * mm

    # Monto destacado.
    y -= 4 * mm
    c.setFont("Helvetica-Bold", 12)
    c.drawString(20 * mm, y, "MONTO:")
    c.setFont("Helvetica-Bold", 20)
    c.drawString(62 * mm, y - 1 * mm, db.format_clp(t["monto"]) + " CLP")

    # Firma.
    c.line(20 * mm, 22 * mm, 80 * mm, 22 * mm)
    c.setFont("Helvetica", 9)
    c.drawString(20 * mm, 18 * mm, "Firma de Secretario de Finanzas")
    c.drawRightString(ancho - 18 * mm, 12 * mm,
                      f"Emitido: {date.today().isoformat()}")

    c.showPage()
    c.save()
    buffer.seek(0)
    return buffer


@app.route("/transacciones/<int:tid>/comprobante")
def comprobante(tid: int):
    t = db.obtener_transaccion(tid)
    if not t:
        flash("La transacción no existe.", "danger")
        return redirect(url_for("transacciones"))
    pdf = _generar_comprobante_pdf(t)
    return send_file(
        pdf, as_attachment=False,  # se abre en el navegador para imprimir
        download_name=f"comprobante_{t.get('folio') or tid}.pdf",
        mimetype="application/pdf",
    )


if __name__ == "__main__":
    # Ejecución LOCAL. En producción (PythonAnywhere/Render) el servidor importa
    # el objeto 'app' y NO ejecuta este bloque, por lo que 'debug' no aplica allá.
    # Para uso en la misma red local: host="0.0.0.0".
    app.run(host=os.environ.get("HOST", "127.0.0.1"),
            port=int(os.environ.get("PORT", 5000)),
            debug=os.environ.get("FLASK_DEBUG", "1") == "1")
