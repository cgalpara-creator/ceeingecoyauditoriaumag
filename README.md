# 🏦 Contabilidad — Centro de Alumnos

Software contable **web, local y simple** para una sola organización
(el Centro de Alumnos). Inspirado en Odoo / Nubox pero reducido a lo esencial.
Trabaja en **pesos chilenos (CLP), redondeados y sin decimales**
(formato `$1.234.567`).

## ✨ Funcionalidades

- **Panel (dashboard)**: KPIs de ingresos, egresos, saldo en caja y saldo del
  mes; gráfico de evolución mensual y dona de egresos por categoría.
- **Transacciones**: registrar, editar y eliminar ingresos/egresos con
  **folio / n° de comprobante**, fecha, categoría, descripción, monto y método
  de pago. Filtros por tipo, categoría y **rango de fechas (desde/hasta)**.
- **Categorías personalizables** desde la interfaz (añadir / eliminar).
- **Reportes**: Estado de resultados (ingresos y egresos por categoría) con
  resultado del período (superávit / déficit), filtrable por mes.
- **Comprobante PDF** imprimible por transacción (folio, monto en CLP, firma).
- **Login multiusuario**: una cuenta por persona (hash seguro), gestión de
  usuarios y cambio de contraseña.
- **Exportación a Excel** (`.xlsx`) de todo el libro de transacciones.

> 🌐 ¿Quieres que tus colegas accedan por internet? Mira **[DEPLOYMENT.md](DEPLOYMENT.md)**.

## 🧱 Stack

- **Python + Flask** (servidor web que entrega HTML)
- **Bootstrap 5 + Chart.js** (servidos localmente, funciona **100% offline**)
- **SQLite** (base de datos local `contabilidad.db`)
- **pandas + openpyxl** (exportación a Excel)

## 📁 Estructura

```
centro-alumnos-contabilidad/
├── app.py              # Servidor Flask + rutas
├── database.py         # Capa de datos (SQLite, montos enteros CLP)
├── templates/          # Plantillas HTML (Jinja2)
│   ├── base.html
│   ├── dashboard.html
│   ├── transacciones.html
│   └── reportes.html
├── static/style.css
├── requirements.txt
├── README.md
└── contabilidad.db     # Se crea solo al primer uso
```

## 🚀 Instalación y ejecución

Requiere **Python 3.9+**.

```bash
cd centro-alumnos-contabilidad
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python app.py
```

Abre en el navegador: **http://127.0.0.1:5000**

**Acceso inicial:** usuario `admin`, contraseña `admin123`.
> 🔐 Cámbiala apenas entres, desde "Cambiar contraseña" en la barra lateral.

> ℹ️ Bootstrap, los iconos y Chart.js están incluidos en `static/vendor/`, así
> que la app funciona **sin conexión a internet**. Todo es 100% local.

## 💾 Respaldo

Toda la información vive en `contabilidad.db`. Para hacer una copia de
seguridad, simplemente copia ese archivo.

## 🎨 Personalización

- Nombre de la organización: variable `EMPRESA` al inicio de `app.py`.
- Categorías y métodos de pago iniciales: listas al inicio de `database.py`
  (las categorías luego se editan desde la propia app).
