# New demo database

[![English](https://img.shields.io/badge/lang-English-1f6feb.svg)](demo-database.md)
[![Português](https://img.shields.io/badge/lang-Portugu%C3%AAs-2ea043.svg)](demo-database.pt-BR.md)

The public demo runs on Render (free web service) with its database on Supabase (free project). Follow
these steps when the demo needs a new database:

- a new Supabase account or project;
- a project deleted, or paused for too long to restore;
- a clean demo.

Supabase is only one option. Any PostgreSQL 13+ works: set `DATABASE_URL` to the URL your provider gives you and skip steps 1 and 2. See [Database](../README.md#database-any-postgresql-13-or-newer) for what the database must allow.

The Odoo side is automatic. On its first boot the container creates the database, installs the modules in
Portuguese with sample data, and sets the administrator. There is nothing to run by hand in Odoo.

## 1. Create the Supabase project

1. **New project**, region **East US (North Virginia)**, the same region as the Render service (Virginia).
   Odoo runs many queries per page, so the database must sit next to the web service.
2. Click **Generate a password** and save it in your password manager. Supabase never shows it again.
3. The free plan allows two active projects per organization.

## 2. Copy the connection details

In the project, open **Connect → Direct → Session pooler** and note:

| Field | Example |
|---|---|
| host | `aws-0-<region>.pooler.supabase.com` |
| port | `5432` |
| user | `postgres.<project-ref>` |

Use the **session pooler** only:

- **Direct connection** is IPv6, and Render cannot reach it.
- **Transaction pooler** breaks the `LISTEN` that Odoo's scheduled jobs need.

## 3. Point Render to it

In **Render → oficina-os → Environment**, set these variables, then click **Save, rebuild, and deploy**:

| Variable | Value |
|---|---|
| `DB_HOST` | pooler host |
| `DB_PORT` | `5432` |
| `DB_USER` | `postgres.<project-ref>` |
| `DB_PASSWORD` | the project password |
| `DB_NAME` | `odoo` (any name; it is created on first boot) |
| `LOAD_DEMO` | `true` |
| `ODOO_ADMIN_EMAIL` | administrator login |
| `ODOO_ADMIN_PASSWORD` | at least 10 characters |

The administrator variables count only on the first boot of each database. To change the administrator
later, do it inside Odoo.

**On a new Render account:** use **New → Blueprint** and pick the repository. [`render.yaml`](../render.yaml)
creates the service and asks for the same secrets.

**With the Render CLI from Git Bash on Windows:** prefix the command with `MSYS_NO_PATHCONV=1`. Otherwise
Git Bash rewrites `/web/health` into a Windows path, and the deploy never passes the health check.

## 4. Watch the first boot

It takes two to three minutes. In **Logs**, look for these lines:

```
[deploy] first boot: installing base
[deploy] installing workshop_os,workshop_os_nfse
HTTP service (werkzeug) running on ...:10000
```

Then open `https://<service>.onrender.com/web/health?db_server_status=1`. It should answer
`{"status": "pass", "db_server_status": true}`.

## 5. Demo logins

| Login | Password | Lands in |
|---|---|---|
| `escritorio` | `escritorio` | the office dashboard |
| `mecanico` | `mecanico` | the mechanic app (open it on a phone) |

The administrator is the one from `ODOO_ADMIN_EMAIL` and `ODOO_ADMIN_PASSWORD`. Do not publish it.

## 6. Keep it awake

Set the repository variable `KEEPALIVE_URL` to the service URL, for example
`https://oficina-os.onrender.com`. It lives under **Settings → Secrets and variables → Actions → Variables**.

The [keep-alive workflow](../.github/workflows/keepalive.yml) then calls the health check with the database
check. It runs every 10 minutes from 07:00 to 21:00 (Brazil), Monday to Saturday. That prevents both
Render's sleep and Supabase's pause after a week without activity.

GitHub disables scheduled workflows after 60 days without commits. If the demo starts pausing again,
re-enable the workflow under **Actions → Keep alive**.

## Starting the demo over without deleting anything

Set `DB_NAME` to a new name, for example `demo_2026_10`, and deploy. The first boot builds a fresh demo in
that database, and the old one stays untouched. When you are sure you no longer need the old database,
delete it in Supabase: the free plan holds 500 MB.

## If Supabase paused the project

Open the project in the dashboard and click **Restore**. Paused free projects can be restored for 90 days.
After that, start again from step 1.
