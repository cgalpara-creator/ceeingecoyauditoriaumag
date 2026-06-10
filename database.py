"""
database.py
-----------
Capa de acceso a datos (SQLite local) del software contable del Centro de Alumnos.

Reglas del dominio:
  - Moneda: Peso chileno (CLP). Los montos se guardan como ENTEROS (sin decimales).
  - Cada transacción es un Ingreso o un Egreso con monto siempre positivo;
    el signo se deriva del tipo al calcular saldos.

Toda la app (app.py) habla con la base de datos únicamente a través de
estas funciones, manteniendo el código modular.
"""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from datetime import date
from pathlib import Path

from werkzeug.security import check_password_hash, generate_password_hash

DB_PATH = Path(__file__).parent / "contabilidad.db"

# Categorías por defecto (semilla inicial). Luego se editan desde la interfaz.
CATEGORIAS_INGRESO = ["Cuotas socios", "Eventos", "Rifas", "Kiosco",
                      "Aportes", "Otros ingresos"]
CATEGORIAS_EGRESO = ["Actividades", "Materiales", "Premios", "Transporte",
                     "Donaciones", "Otros gastos"]

METODOS_PAGO = ["Efectivo", "Transferencia", "Tarjeta", "Otro"]


# ---------------------------------------------------------------------------
# Utilidades
# ---------------------------------------------------------------------------
def format_clp(monto: float | int) -> str:
    """
    Formatea un monto como CLP redondeado, con separador de miles chileno.
    Ejemplo: 1234567 -> '$1.234.567'
    """
    entero = int(round(monto or 0))
    # f-string con coma como separador, luego se cambia a punto (estilo CL).
    return "$" + f"{entero:,}".replace(",", ".")


@contextmanager
def _get_connection():
    """Entrega una conexión SQLite y garantiza commit/cierre."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Inicialización
# ---------------------------------------------------------------------------
def init_db() -> None:
    """Crea las tablas si no existen y siembra categorías por defecto."""
    with _get_connection() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS transacciones (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                folio       TEXT,                     -- nº comprobante (opcional)
                fecha       TEXT    NOT NULL,         -- ISO 'YYYY-MM-DD'
                tipo        TEXT    NOT NULL,         -- 'Ingreso' / 'Egreso'
                categoria   TEXT    NOT NULL,
                descripcion TEXT,
                monto       INTEGER NOT NULL,         -- CLP, entero, positivo
                metodo_pago TEXT    NOT NULL
            )
            """
        )
        # Migración: añade la columna 'folio' a bases de datos ya existentes.
        columnas = {c["name"] for c in
                    conn.execute("PRAGMA table_info(transacciones)").fetchall()}
        if "folio" not in columnas:
            conn.execute("ALTER TABLE transacciones ADD COLUMN folio TEXT")
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS categorias (
                id     INTEGER PRIMARY KEY AUTOINCREMENT,
                nombre TEXT NOT NULL,
                tipo   TEXT NOT NULL,
                UNIQUE(nombre, tipo)
            )
            """
        )
        if conn.execute("SELECT COUNT(*) FROM categorias").fetchone()[0] == 0:
            semillas = (
                [(n, "Ingreso") for n in CATEGORIAS_INGRESO]
                + [(n, "Egreso") for n in CATEGORIAS_EGRESO]
            )
            conn.executemany(
                "INSERT INTO categorias (nombre, tipo) VALUES (?, ?)", semillas
            )

        # Tabla de usuarios para el login.
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS usuarios (
                id       INTEGER PRIMARY KEY AUTOINCREMENT,
                usuario  TEXT NOT NULL UNIQUE,
                clave    TEXT NOT NULL,         -- hash, nunca texto plano
                es_admin INTEGER NOT NULL DEFAULT 0
            )
            """
        )
        # Migración: añade 'es_admin' a bases de datos ya existentes.
        cols_u = {c["name"] for c in
                  conn.execute("PRAGMA table_info(usuarios)").fetchall()}
        if "es_admin" not in cols_u:
            conn.execute(
                "ALTER TABLE usuarios ADD COLUMN es_admin INTEGER NOT NULL DEFAULT 0"
            )

        # Siembra inicial (instalación nueva): crea al administrador 'Cristopher'.
        if conn.execute("SELECT COUNT(*) FROM usuarios").fetchone()[0] == 0:
            conn.execute(
                "INSERT INTO usuarios (usuario, clave, es_admin) VALUES (?, ?, 1)",
                ("Cristopher", generate_password_hash("admin123")),
            )

        # Garantiza que SIEMPRE exista al menos un administrador. En bases ya
        # creadas (que tenían 'admin'), promueve esa cuenta —o la más antigua—
        # para que no te quedes sin quién gestione usuarios.
        if conn.execute("SELECT COUNT(*) FROM usuarios WHERE es_admin=1").fetchone()[0] == 0:
            fila = conn.execute(
                "SELECT id FROM usuarios WHERE usuario='admin' "
                "UNION ALL SELECT id FROM usuarios ORDER BY id LIMIT 1"
            ).fetchone()
            if fila:
                conn.execute("UPDATE usuarios SET es_admin=1 WHERE id=?", (fila["id"],))


# ---------------------------------------------------------------------------
# Usuarios / autenticación
# ---------------------------------------------------------------------------
def verificar_credenciales(usuario: str, clave: str) -> bool:
    """Devuelve True si usuario y contraseña coinciden con un registro válido."""
    with _get_connection() as conn:
        fila = conn.execute(
            "SELECT clave FROM usuarios WHERE usuario = ?", (usuario.strip(),)
        ).fetchone()
    return bool(fila) and check_password_hash(fila["clave"], clave)


def cambiar_clave(usuario: str, nueva_clave: str) -> bool:
    """Actualiza la contraseña de un usuario existente. Devuelve True si existía."""
    with _get_connection() as conn:
        cur = conn.execute(
            "UPDATE usuarios SET clave = ? WHERE usuario = ?",
            (generate_password_hash(nueva_clave), usuario.strip()),
        )
    return cur.rowcount > 0


def listar_usuarios() -> list[dict]:
    """Lista de usuarios (sin exponer el hash de la contraseña)."""
    with _get_connection() as conn:
        filas = conn.execute(
            "SELECT id, usuario, es_admin FROM usuarios ORDER BY es_admin DESC, usuario"
        ).fetchall()
    return [dict(f) for f in filas]


def es_usuario_admin(usuario: str) -> bool:
    """Devuelve True si el usuario tiene rol de administrador."""
    with _get_connection() as conn:
        fila = conn.execute(
            "SELECT es_admin FROM usuarios WHERE usuario = ?", (usuario.strip(),)
        ).fetchone()
    return bool(fila) and bool(fila["es_admin"])


def crear_usuario(usuario: str, clave: str, es_admin: bool = False) -> bool:
    """Crea un usuario nuevo. Devuelve False si el nombre ya existe."""
    try:
        with _get_connection() as conn:
            conn.execute(
                "INSERT INTO usuarios (usuario, clave, es_admin) VALUES (?, ?, ?)",
                (usuario.strip(), generate_password_hash(clave), 1 if es_admin else 0),
            )
        return True
    except sqlite3.IntegrityError:
        return False


def renombrar_usuario(usuario_id: int, nuevo_nombre: str) -> tuple[bool, str]:
    """
    Renombra un usuario. Devuelve (ok, nombre_anterior).
    Si el nuevo nombre ya existe, devuelve (False, "").
    """
    nuevo = nuevo_nombre.strip()
    with _get_connection() as conn:
        fila = conn.execute(
            "SELECT usuario FROM usuarios WHERE id = ?", (usuario_id,)
        ).fetchone()
        if not fila:
            return False, ""
        anterior = fila["usuario"]
        try:
            conn.execute(
                "UPDATE usuarios SET usuario = ? WHERE id = ?", (nuevo, usuario_id)
            )
        except sqlite3.IntegrityError:
            return False, ""
    return True, anterior


def eliminar_usuario(usuario_id: int) -> None:
    """Elimina un usuario por id."""
    with _get_connection() as conn:
        conn.execute("DELETE FROM usuarios WHERE id = ?", (usuario_id,))


def contar_usuarios() -> int:
    with _get_connection() as conn:
        return conn.execute("SELECT COUNT(*) FROM usuarios").fetchone()[0]


# ---------------------------------------------------------------------------
# Categorías
# ---------------------------------------------------------------------------
def obtener_categorias(tipo: str | None = None) -> list[dict]:
    """Devuelve categorías (todas, o filtradas por tipo) como lista de dicts."""
    with _get_connection() as conn:
        if tipo:
            filas = conn.execute(
                "SELECT * FROM categorias WHERE tipo = ? ORDER BY nombre", (tipo,)
            ).fetchall()
        else:
            filas = conn.execute(
                "SELECT * FROM categorias ORDER BY tipo, nombre"
            ).fetchall()
    return [dict(f) for f in filas]


def agregar_categoria(nombre: str, tipo: str) -> None:
    """Añade una categoría (ignora duplicados gracias a UNIQUE)."""
    with _get_connection() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO categorias (nombre, tipo) VALUES (?, ?)",
            (nombre.strip(), tipo),
        )


def eliminar_categoria(categoria_id: int) -> None:
    """Elimina una categoría por id (no afecta transacciones ya registradas)."""
    with _get_connection() as conn:
        conn.execute("DELETE FROM categorias WHERE id = ?", (categoria_id,))


# ---------------------------------------------------------------------------
# Transacciones (CRUD)
# ---------------------------------------------------------------------------
def agregar_transaccion(fecha: str, tipo: str, categoria: str,
                        descripcion: str, monto: float, metodo_pago: str,
                        folio: str = "") -> None:
    """Inserta una transacción. El monto se guarda redondeado y positivo."""
    with _get_connection() as conn:
        conn.execute(
            """
            INSERT INTO transacciones
                (folio, fecha, tipo, categoria, descripcion, monto, metodo_pago)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (folio.strip() or None, fecha, tipo, categoria, descripcion,
             abs(int(round(float(monto)))), metodo_pago),
        )


def actualizar_transaccion(tid: int, fecha: str, tipo: str, categoria: str,
                           descripcion: str, monto: float, metodo_pago: str,
                           folio: str = "") -> None:
    """Actualiza todos los campos de una transacción existente."""
    with _get_connection() as conn:
        conn.execute(
            """
            UPDATE transacciones
               SET folio=?, fecha=?, tipo=?, categoria=?, descripcion=?,
                   monto=?, metodo_pago=?
             WHERE id=?
            """,
            (folio.strip() or None, fecha, tipo, categoria, descripcion,
             abs(int(round(float(monto)))), metodo_pago, tid),
        )


def eliminar_transaccion(tid: int) -> None:
    with _get_connection() as conn:
        conn.execute("DELETE FROM transacciones WHERE id = ?", (tid,))


def obtener_transaccion(tid: int) -> dict | None:
    with _get_connection() as conn:
        fila = conn.execute(
            "SELECT * FROM transacciones WHERE id = ?", (tid,)
        ).fetchone()
    return dict(fila) if fila else None


def obtener_transacciones(tipo: str | None = None, categoria: str | None = None,
                          mes: str | None = None, desde: str | None = None,
                          hasta: str | None = None) -> list[dict]:
    """
    Lista de transacciones (más recientes primero) con filtros opcionales.
    'desde'/'hasta' son fechas ISO inclusivas y tienen prioridad sobre 'mes'.
    """
    consulta = "SELECT * FROM transacciones"
    cond, params = [], []
    if tipo:
        cond.append("tipo = ?"); params.append(tipo)
    if categoria:
        cond.append("categoria = ?"); params.append(categoria)
    if desde:
        cond.append("fecha >= ?"); params.append(desde)
    if hasta:
        cond.append("fecha <= ?"); params.append(hasta)
    # 'mes' solo se aplica si no se especificó un rango de fechas explícito.
    if mes and not (desde or hasta):
        cond.append("fecha LIKE ?"); params.append(f"{mes}%")
    if cond:
        consulta += " WHERE " + " AND ".join(cond)
    consulta += " ORDER BY fecha DESC, id DESC"
    with _get_connection() as conn:
        filas = conn.execute(consulta, params).fetchall()
    return [dict(f) for f in filas]


# ---------------------------------------------------------------------------
# Reportes / agregados
# ---------------------------------------------------------------------------
def calcular_balance(mes: str | None = None) -> dict[str, int]:
    """Totales de ingresos, egresos y saldo (opcionalmente filtrado por mes)."""
    consulta = """
        SELECT
            COALESCE(SUM(CASE WHEN tipo='Ingreso' THEN monto END), 0) AS ingresos,
            COALESCE(SUM(CASE WHEN tipo='Egreso'  THEN monto END), 0) AS egresos
        FROM transacciones
    """
    params: list[str] = []
    if mes:
        consulta += " WHERE fecha LIKE ?"; params.append(f"{mes}%")
    with _get_connection() as conn:
        fila = conn.execute(consulta, params).fetchone()
    ingresos, egresos = int(fila["ingresos"]), int(fila["egresos"])
    return {"ingresos": ingresos, "egresos": egresos,
            "saldo": ingresos - egresos}


def resumen_por_categoria(tipo: str, mes: str | None = None) -> list[dict]:
    """Suma de montos por categoría para un tipo dado (para el estado de resultados)."""
    consulta = """
        SELECT categoria, SUM(monto) AS total
        FROM transacciones WHERE tipo = ?
    """
    params: list[str] = [tipo]
    if mes:
        consulta += " AND fecha LIKE ?"; params.append(f"{mes}%")
    consulta += " GROUP BY categoria ORDER BY total DESC"
    with _get_connection() as conn:
        filas = conn.execute(consulta, params).fetchall()
    return [dict(f) for f in filas]


def resumen_mensual() -> list[dict]:
    """
    Devuelve, por mes ('YYYY-MM'), los totales de ingresos y egresos.
    Pensado para alimentar el gráfico de evolución del dashboard.
    """
    with _get_connection() as conn:
        filas = conn.execute(
            """
            SELECT substr(fecha, 1, 7) AS mes,
                   COALESCE(SUM(CASE WHEN tipo='Ingreso' THEN monto END), 0) AS ingresos,
                   COALESCE(SUM(CASE WHEN tipo='Egreso'  THEN monto END), 0) AS egresos
            FROM transacciones
            GROUP BY mes ORDER BY mes
            """
        ).fetchall()
    return [dict(f) for f in filas]
