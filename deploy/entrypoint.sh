#!/bin/bash
# Starts Odoo from environment variables, on any PostgreSQL 13+ (managed or self-hosted):
#   first boot  -> creates the tables, keeps every attachment in the database, installs the modules in pt_BR
#   new release -> upgrades the modules when the addons fingerprint changed
set -euo pipefail

# Most providers hand out one URL (postgres://user:password@host:port/database?sslmode=require).
# It fills the DB_* variables that are not set one by one.
if [ -n "${DATABASE_URL:-}" ]; then
    eval "$(python3 - <<'PY'
import os
import shlex
from urllib.parse import parse_qs, unquote, urlsplit

url = urlsplit(os.environ["DATABASE_URL"])
values = {
    "DB_HOST": url.hostname,
    "DB_PORT": url.port,
    "DB_USER": unquote(url.username or ""),
    "DB_PASSWORD": unquote(url.password or ""),
    "DB_NAME": url.path.lstrip("/"),
    "DB_SSLMODE": (parse_qs(url.query).get("sslmode") or [""])[0],
}
for key, value in values.items():
    if value and not os.environ.get(key):
        print(f"export {key}={shlex.quote(str(value))}")
PY
)"
fi

: "${DB_HOST:?set DB_HOST, or DATABASE_URL}"
: "${DB_USER:?set DB_USER, or DATABASE_URL}"
: "${DB_PASSWORD:?set DB_PASSWORD, or DATABASE_URL}"
if [ "$DB_USER" = "postgres" ]; then
    echo "[deploy] Odoo refuses to run as the 'postgres' superuser: create a role for it, e.g." >&2
    echo "         CREATE ROLE odoo LOGIN CREATEDB PASSWORD '...';" >&2
    exit 1
fi
# The database manager is disabled (list_db = False); without a given master password, use a random one.
: "${ADMIN_PASSWD:=$(head -c 48 /dev/urandom | base64 | tr -dc 'A-Za-z0-9')}"
: "${DB_PORT:=5432}"
: "${DB_NAME:=odoo}"
# "prefer" uses TLS when the server offers it (managed providers) and still works with a local PostgreSQL.
: "${DB_SSLMODE:=prefer}"
: "${PORT:=8069}"
: "${MODULES:=workshop_os,workshop_os_nfse}"
: "${LOAD_DEMO:=false}"

CONF=/tmp/odoo.conf
umask 077
cat > "$CONF" <<CONF
[options]
addons_path = /opt/oficina/addons,/usr/lib/python3/dist-packages/odoo/addons
data_dir = /var/lib/odoo
db_host = ${DB_HOST}
db_port = ${DB_PORT}
db_user = ${DB_USER}
db_password = ${DB_PASSWORD}
db_name = ${DB_NAME}
db_sslmode = ${DB_SSLMODE}
db_maxconn = 8
dbfilter = ^${DB_NAME}\$
list_db = False
admin_passwd = ${ADMIN_PASSWD}
proxy_mode = True
http_port = ${PORT}
workers = 0
max_cron_threads = 1
CONF

export PGPASSWORD="$DB_PASSWORD" PGSSLMODE="$DB_SSLMODE"
sql() { psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -v ON_ERROR_STOP=1 -tAqc "$1"; }
set_param() {
    sql "insert into ir_config_parameter (key, value, create_uid, write_uid, create_date, write_date)
         values ('$1', '$2', 1, 1, now(), now()) on conflict (key) do update set value = excluded.value, write_date = now()"
}

wait-for-psql.py --db_host "$DB_HOST" --db_port "$DB_PORT" --db_user "$DB_USER" --db_password "$DB_PASSWORD" --timeout=60

fingerprint=$(cat /deploy/addons.sha)
installed=$(sql "select 1 from ir_module_module where name = 'workshop_os' and state = 'installed'" 2>/dev/null || true)

if [ "$installed" != "1" ]; then
    # Never leave a public instance with admin/admin: the first boot needs the real credentials.
    : "${ODOO_ADMIN_EMAIL:?set ODOO_ADMIN_EMAIL (login of the administrator) for the first boot}"
    : "${ODOO_ADMIN_PASSWORD:?set ODOO_ADMIN_PASSWORD for the first boot}"
    if [ "${#ODOO_ADMIN_PASSWORD}" -lt 10 ]; then
        echo "[deploy] ODOO_ADMIN_PASSWORD must have at least 10 characters" >&2
        exit 1
    fi
    # Odoo decides on sample data when the database is created, so the flag goes on the base install too.
    demo=()
    if [ "$LOAD_DEMO" = "true" ]; then demo=(--with-demo); fi
    echo "[deploy] first boot: installing base"
    odoo -c "$CONF" -i base "${demo[@]}" --load-language=pt_BR --stop-after-init --no-http
    # Attachments (assets, photos, PDFs) live in the database: containers may lose their disk on a redeploy,
    # and one database dump then holds everything.
    set_param ir_attachment.location db
    echo "env['ir.attachment'].force_storage(); env.cr.commit()" | odoo shell -c "$CONF" --no-http >/dev/null
    echo "[deploy] installing ${MODULES}"
    odoo -c "$CONF" -i "$MODULES" "${demo[@]}" --stop-after-init --no-http
    # The credentials reach Python through the environment, never through a command line.
    odoo shell -c "$CONF" --no-http >/dev/null <<'PY'
import os
email = os.environ["ODOO_ADMIN_EMAIL"]
env.ref("base.user_admin").write({"login": email, "email": email, "password": os.environ["ODOO_ADMIN_PASSWORD"]})
env.cr.commit()
PY
    set_param deploy.addons_fingerprint "$fingerprint"
elif [ "$(sql "select value from ir_config_parameter where key = 'deploy.addons_fingerprint'")" != "$fingerprint" ]; then
    echo "[deploy] new release: upgrading ${MODULES}"
    odoo -c "$CONF" -u "$MODULES" --stop-after-init --no-http
    set_param deploy.addons_fingerprint "$fingerprint"
fi

exec odoo -c "$CONF"
