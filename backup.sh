#!/usr/bin/env bash
#
# backup.sh — Respaldo de la base de datos del CEE Inge Eco y Auditoría UMAG.
#
# Copia 'contabilidad.db' a la carpeta 'backups/' con fecha y hora, y conserva
# solo los 30 respaldos más recientes.
#
# Uso manual:        ./backup.sh
# Uso programado:    ver instrucciones al final de DEPLOYMENT.md (cron / tarea PA)

set -euo pipefail

# Carpeta donde está este script (funciona aunque se llame desde otro lugar).
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DB="$DIR/contabilidad.db"
DEST="$DIR/backups"

mkdir -p "$DEST"

if [ ! -f "$DB" ]; then
  echo "Aún no existe $DB (no hay datos que respaldar todavía)."
  exit 0
fi

STAMP="$(date +%Y%m%d_%H%M%S)"
DESTINO="$DEST/contabilidad_$STAMP.db"
cp "$DB" "$DESTINO"

# Conserva solo los 30 respaldos más recientes (borra los más antiguos).
ls -1t "$DEST"/contabilidad_*.db 2>/dev/null | tail -n +31 | xargs -r rm --

echo "Respaldo creado: $DESTINO"
