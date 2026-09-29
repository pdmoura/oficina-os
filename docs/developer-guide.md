# Developer guide

[![English](https://img.shields.io/badge/lang-English-1f6feb.svg)](developer-guide.md)
[![Português](https://img.shields.io/badge/lang-Portugu%C3%AAs-2ea043.svg)](developer-guide.pt-BR.md)

How Oficina OS is built, tested, translated, deployed and run. For using the system, see the
[user manual](user-manual.md).

## Contents

1. [Overview](#1-overview)
2. [Repository layout](#2-repository-layout)
3. [Data model](#3-data-model)
4. [Security](#4-security)
5. [Front end](#5-front-end)
6. [Public pages and routes](#6-public-pages-and-routes)
7. [Reports](#7-reports)
8. [NFS-e](#8-nfs-e)
9. [Translations](#9-translations)
10. [Local development and tests](#10-local-development-and-tests)
11. [Environments and deployment](#11-environments-and-deployment)
12. [Operations](#12-operations)
13. [Conventions](#13-conventions)
14. [Customising for a client](#14-customising-for-a-client)
15. [Troubleshooting](#15-troubleshooting)

## 1. Overview

Oficina OS is three Odoo 19 Community modules, under the OPL-1 licence:

| Module | Depends on | Role |
|---|---|---|
| `workshop_os` | `base`, `web`, `mail`, `mail_bot`, `auth_signup` | Vehicles, work orders, stages, checklists, photos, the mechanic app, the customer approval page, the office dashboard, the monthly closing, PDFs, white-label theming, the guided tour. |
| `l10n_br_nfse_nacional` | `base`, `mail`, `certificate` | Brazilian service invoices through the national system: assisted and direct modes, XSD validation, XMLDSig, mTLS, cancellation, DANFSe. Works without the workshop module. |
| `workshop_os_nfse` | both above | Glue, installed automatically: the note of a work order or a monthly closing. |

Source strings are English; the shipped translation is `pt_BR`. Everything shop-specific (name, logos, colours,
texts, services, users) is data, not code, so one code base serves any number of shops.

## 2. Repository layout

```
workshop_os/
  controllers/        workshop_os.py (public page, brand images), web.py (PWA manifest)
  models/             one file per model; res_company.py holds the brand/theme helpers
  wizard/             workshop.order.print (the "Include photos" question)
  views/              <model>_views.xml, workshop_os_menus.xml, public/webclient templates
  report/             <report>_reports.xml (actions) and _templates.xml (QWeb)
  security/           groups, ir.model.access.csv, record rules per model
  data/               stages, locations, sectors, checklists, sequence, theme asset (English, translated)
  demo/               demo company, users and orders
  static/src/
    app/              mechanic app (OWL client action): mechanic_app.*, screens.js, utils.js
    backend/          dashboard, field widgets, view patches (notebook, status bar, save buttons), customer link
    tour/             guided tour (service, overlay component, steps)
    public/           customer approval page
    scss/tokens.scss  design tokens shared by the app, the dashboard and the public page
  i18n/pt_BR.po       module translation; i18n_extra/pt_BR.po fills gaps in Odoo core's own pt_BR
  migrations/<version>/ pre-/post-migrate scripts
  tests/
l10n_br_nfse_nacional/  models/, tools/nfse_xml.py (XML, signature, text rules), wizard/ (cancel), data/xsd, report/
workshop_os_nfse/       models/ (mixin workshop.nfse.source, extensions), views/, tests/
deploy/                 entrypoint.sh, docker-compose.yml, placeholder.py, sample_data.py
Dockerfile, docker-compose.yml (local), render.yaml (demo), .github/workflows (CI, keep-alive)
docs/                   manuals, runbooks, screenshots
```

## 3. Data model

| Model | What it is | Notes |
|---|---|---|
| `workshop.vehicle` | A truck, by plate | Plate normalised (Mercosul and old format) and unique per company; open order and history computed. |
| `workshop.order` | A work order | Number from the `workshop.order` sequence on create ("New" until then). `state`: draft → approved → done → delivered (and rejected, cancel). `stage_id` is the yard position, independent from `state`. Public `access_token`, computed `public_url`. |
| `workshop.order.line` | A service or part on an order | `approval` pending/approved/rejected; `is_part` (copied from the catalogue) splits the order into `amount_services` and `amount_parts`; `_service_rows(parts=False)` and `_invoice_description()` build the breakdown shared by the closing report and the NFS-e, parts left out of the note. |
| `workshop.order.photo` | A photo | `kind` entry/work/exit; kept as an attachment or on Cloudinary (URL); `show_to_customer`. |
| `workshop.order.checklist` | A checklist answer | Copied from a template (`load_checklist`). |
| `workshop.order.stage.log` | Time spent in each stage | Written on every stage change; `is_waiting` stages do not count as work. |
| `workshop.stage`, `.location`, `.sector`, `.service` | The shop's lists | Starting data in `data/`, English with pt_BR translations. |
| `workshop.checklist.template(.item)` | Checklist templates | Items have xml ids, so each one is translatable. |
| `workshop.billing` | Monthly closing per customer | draft → confirmed → invoiced → paid; locks its orders. |
| `workshop.order.print` | Transient | Print dialog; passes `workshop_without_photos` in the report context. |
| `res.company` | Brand and texts | Accent and background colours, logos, favicon, link-preview image, warranty and terms; `_workshop_theme_scss()` generates the backend theme. |
| `res.users.settings` | Per-user UI state | `workshop_theme`, `workshop_tour_office_done`, `workshop_tour_app_done`. |
| `res.partner` | Customer | `workshop_customer`, `workshop_auto_approve` (fleets on contract). |
| `l10n_br_nfse_nacional.document` | A service invoice | draft → done / error → cancel; DPS and NFS-e XML attached; `workshop_order_id` / `workshop_billing_id` from the glue module, with one live note per source (constraint). |

Photos, PDFs and every other attachment are stored **in PostgreSQL** in the deployed images
(`ir_attachment.location = db`), so one database dump is a complete backup.

## 4. Security

- **Groups:** `workshop_os.workshop_os_group_user` (Mechanic) and `workshop_os.workshop_os_group_manager`
  (Office, implies Mechanic and `base.group_partner_manager`). NFS-e has its own group, given to Office by the
  glue module.
- **Record rules:** every model is restricted to the user's companies (`<model>_rule_company`).
- **Office-only steps are enforced in the model**, not only hidden in views: approving, rejecting, cancelling,
  reopening, the approval fields and removing approved lines all go through `workshop.order._check_office()` in
  `create`/`write`/`unlink`. Any public method is callable over RPC, so this matters. Two narrow exceptions
  run as superuser after their own checks: `action_undo_done()` (a mechanic takes a ready order back to the status
  it had, until it is delivered, billed or invoiced: `_check_can_undo_done()`) and `_app_create_partner()` (a
  customer registered at the gate, with name, phone and kind only, since mechanics cannot create contacts).
- **The customer's answer** comes through `/os/<token>/decision`, compared in constant time, and runs the private
  `_customer_decide()`, which cannot be called over RPC.
- **Photos** only accept URLs from Odoo (`/web/image/`) or `https://res.cloudinary.com/`, and an attachment must
  belong to the same order. Cloudinary uploads are signed on the server; the browser only gets a one-time
  signature (`upload_ticket`).
- **Self sign-up is closed** and OdooBot's onboarding is disabled.
- Secrets (database password, administrator password, Cloudinary secret, A1 certificate) live in the environment
  or in the database, never in the repository.

## 5. Front end

### Mechanic app

A full-screen client action (`workshop_os.mechanic_app`, path `/odoo/mechanic-app`) written in OWL. Screens
(`HomeScreen`, `NewOrderScreen`, `OrderScreen`) live in a small stack so the back button behaves like a phone app.
Each screen loads its data in one call to a model method: `app_home`, `app_read`, `app_new_form`, `app_create`,
`app_add_services`, `app_action`, `app_save_checklist`, `upload_ticket` + `add_photo`, `find_by_plate`. Services
and customers are never sent whole: the `SearchSelect` component asks `app_services` and `app_partners` as the
mechanic types.

It is installable as a PWA: `controllers/web.py` names the manifest after the shop and starts it on `/odoo`, which
routes each role to its screen (`_workshop_home_action`). The phone keeps half-typed orders in `localStorage`.

OWL note: an arrow handler in a template (`t-on-click="() => open(x)"`) calls the method without `this`; components
that use them run `bindMethods(this)` in `setup()` (a test checks it).

### Office

- **Dashboard:** client action `workshop_os.dashboard`, data from `workshop.order.dashboard_data()`.
- **View patches** (`static/src/backend/`):
  - `notebook.xml`: on phones a notebook with more than two pages shows a `<select>` instead of tabs;
  - `status_bar_buttons.xml`: on phones the first two header buttons stay in view;
  - `form_status_indicator.xml`: labelled Save/Discard buttons (a bottom bar on phones);
  - `customer_link.js`: header widget that copies the approval link within the tap;
  - `backend.scss`: title bar alignment, phone cards, the section picker's look.
  - Inline `<kanban>` views inside one2many fields give phones cards instead of cut-off tables.
- **Template extensions are tested:** `test_template_extensions_find_their_place` checks every xpath of our
  extensions against Odoo's own templates, so an Odoo update that moves an anchor fails CI instead of breaking
  every form.

### Theming

The accent and background colours of `res.company` are turned into SCSS variables (`_workshop_theme_scss`),
written to an attachment served at `/_custom/workshop_os/brand_variables.scss` and prepended to
`web._assets_primary_variables` by an `ir.asset`. Saving the brand settings rewrites it and clears the asset cache,
so Odoo's own buttons, links and navbar take the shop's colours. Text on white uses a darkened accent that passes
WCAG AA (`$primary`); filled surfaces use the accent as it is (`$o-brand-primary`).

### Guided tour

`static/src/tour/workshop_tour.js` registers a `workshop_tour` service, an overlay in `main_components` and a
user-menu item. Two tracks, `office` and `app`, are lists of steps:

```js
{
    page: "workshop.order#form",          // client action tag, model, or "model#form"
    target: ".o_form_view .o_form_statusbar",  // what to point at; none centres the card
    open: () => action.doAction(...),     // brings the page when another one is showing
    when: async () => true,               // leave the step out (no order yet, no rights...)
    optional: true,                       // skip it if the target never shows up
    title: _t("..."), body: _t("..."),
}
```

Each track opens by itself on a user's first visit (dashboard or app home) and marks itself seen in
`res.users.settings`. To add a step, add an entry to `officeSteps()` or `appSteps()`, translate its strings, and
walk the tour at 390 px and 1280 px.

## 6. Public pages and routes

| Route | Auth | What |
|---|---|---|
| `/os/<token>` | public | Customer approval page (status, timeline, photos by moment, services with checkboxes, signature). |
| `/os/<token>/decision` | public, JSON | The customer's approval or rejection. |
| `/workshop_os/app-icon/<size>` | public | App icon generated from the company's symbol. |
| `/workshop_os/favicon.ico`, `/workshop_os/icon/<size>` | public | The company's browser icon, each size as drawn. |
| `/workshop_os/og-image/<company_id>` | public | Link-preview image. |
| `/workshop_os/logo/<company_id>/<variant>` | public | Logos (dark, light, mark, mark_light). |
| `/web/manifest.webmanifest` | public | PWA manifest in the shop's name and colours. |

## 7. Reports

- **Work order** (`workshop_os.report_workshop_order`): `web.basic_layout` with the shop's brand, services,
  totals, photos grouped by moment (up to eight, embedded when stored in the database), warranty and signatures.
  `action_print()` asks about photos when there are some and prints with `config=False`, because the report does not
  use Odoo's external layout.
- **Monthly closing** (`workshop_os.report_workshop_billing`): the breakdown of `_service_rows()`, the parts
  (`_service_rows(parts=True)`) and the orders.
- **DANFSe** (`l10n_br_nfse_nacional`): drawn from the authorised XML per NT 008, with the public-consultation QR
  code.

## 8. NFS-e

- **Assisted mode:** computed `assist_*` fields lay out every value for the Emissor Nacional website; the user
  pastes back the access key and `action_register_issued()` records the note.
- **Direct mode:** the DPS is built by the national layout's rules, validated against the XSDs in `data/`, signed
  (enveloped XMLDSig, RSA-SHA1, inclusive C14N) with the A1 certificate kept by Odoo's `certificate` module, sent
  over mutual TLS, and the answer is parsed case-insensitively. A lost answer that comes back as E0014 recovers the
  note that already exists.
- **Text:** `tools/nfse_xml.clean_text()` keeps the Latin-1 range the schema accepts; descriptions are capped at
  `MAX_DESCRIPTION` (1000).
- **Glue:** `workshop.nfse.source` gives orders and closings `action_create_nfse()` (reuses the live note) and
  `_nfse_values()`. The note's amount is `_nfse_amount()`, the services only (parts are billed as goods), and a
  source with no services refuses to create a note. A hand-made note can pick an order or a closing and is filled by
  onchange; a constraint keeps one live note per source.

## 9. Translations

1. Write every string in English, in code with `_()` / `self.env._()` (Python) or `_t()` (JS), in XML as plain text.
2. Upgrade the module in a database with pt_BR loaded, then export:
   `odoo i18n export -c <conf> -d <db> -l pt_BR -o /tmp/workshop_os.po workshop_os`
3. Merge the export into `i18n/pt_BR.po`, keeping existing translations and adding the new ones. Keep a sentence on
   one line in XML: a line break inside a sentence ends up inside the msgid.
4. Python code translations are read from the `.po` at runtime (restart Odoo); view and field translations are
   loaded into the database on upgrade. An existing translation is not overwritten on upgrade: when the source of a
   term changes, check the database value (or upgrade with `--i18n-overwrite` on a test database).
5. `i18n_extra/pt_BR.po` holds about 140 terms Odoo core ships untranslated in pt_BR ("My Preferences" and
   others); web client lookups fall back to any module's translation.

## 10. Local development and tests

```bash
docker compose up -d db
docker compose run --rm odoo odoo -d oficina -i workshop_os,workshop_os_nfse --with-demo --load-language=pt_BR --stop-after-init
docker compose up -d odoo          # http://localhost:8070
```

The addons are mounted from the working tree. Python changes need `docker compose restart odoo`; XML and data
changes need an upgrade (`-u workshop_os`); SCSS/JS changes are picked up after a restart.

Tests (88 in total):

```bash
docker compose run --rm odoo odoo -d test -i workshop_os,workshop_os_nfse \
  --test-tags /workshop_os,/l10n_br_nfse_nacional,/workshop_os_nfse --stop-after-init
```

They cover plates, the order flow and its office-only steps over RPC, photos, the customer page, the monthly
closing, reports, the NFS-e DPS against the XSDs, signatures, the mocked API, cancellation, the DANFSe, one live note
per source, invoice descriptions, the theme and style compilation, template extensions, translations of core terms,
the manifest, and the guided-tour settings.

**CI** (`.github/workflows/ci.yml`, every push and pull request): install and tests, install with demo data in
Portuguese, the production image build, and the self-hosted stack with its own PostgreSQL (logs in as the demo
office user).

## 11. Environments and deployment

```
 developer ── git push ──▶ GitHub (main) ──▶ CI
                              │
                              ├──▶ Render (autoDeploy) ──▶ public demo, sample data
                              │
                              └──▶ production server: deployed on purpose (git pull + docker compose)
```

- **GitHub** holds the code. Nothing secret is committed; `deploy/.env` is ignored.
- **The demo** is a Render web service built from the `Dockerfile` (`render.yaml`), with `autoDeploy: true`: every
  push to `main` rebuilds it. It runs on a managed PostgreSQL with `LOAD_DEMO=true`.
- **A production server** runs `deploy/docker-compose.yml` from a clone of the repository. It is **not** updated by
  a push: someone deploys it on purpose, so a shop's system changes only when intended.

### The image and the entrypoint

The `Dockerfile` copies the three modules into the official Odoo 19 image. `deploy/entrypoint.sh` configures Odoo
from environment variables and, on start:

- **empty database:** creates it, stores attachments in the database, installs the modules in pt_BR (with sample
  data when `LOAD_DEMO=true`) and sets the administrator;
- **existing database:** compares a fingerprint of the addons with the one saved in
  `ir_config_parameter` (`deploy.addons_fingerprint`) and runs `-u` on the modules only when the code changed.

While installing or upgrading, `deploy/placeholder.py` answers on the port with a "preparing the system" page.

### Deploying to a production server

```bash
ssh <server>
cd /opt/oficina-os
sudo docker exec oficina-os-backup-1 sh -c 'pg_dump -Fc "$DB_NAME" > /backups/pre-deploy-$(date +%Y%m%d-%H%M).dump'
git pull --ff-only
sudo docker compose -f deploy/docker-compose.yml --env-file deploy/.env up -d --build odoo
sudo docker logs -f oficina-os-odoo-1      # "[deploy] new release: upgrading ..." then "Modules loaded"
```

### Migrations

- Module upgrades run pre-, post- and end-migrate scripts from `migrations/<version>/` only when the manifest version
  increases. Bump `version` whenever a migration is added, and keep scripts idempotent.
- Existing migrations rename xml ids (following the Odoo guidelines), rename the NFS-e model with its table and
  every reference, and turn untouched Portuguese starting data into English sources with Portuguese translations.
- A removed model leaves its table behind (Odoo removes the `ir.model` row only after every migration stage); drop it
  in a later version, checking the registry.

## 12. Operations

- **Backups:** the `backup` service of `deploy/docker-compose.yml` writes a compressed `pg_dump` to
  `deploy/backups/<db>-<date>.dump` every day and keeps `BACKUP_DAYS` (14) days. Take a manual dump before every
  deploy. Attachments are in the database, so the dump is complete. Copy dumps off the server as well.
- **Restore** (stops the shop for a minute):

  ```bash
  sudo docker compose -f deploy/docker-compose.yml --env-file deploy/.env stop odoo
  sudo docker exec -i oficina-os-db-1 pg_restore -U odoo -d odoo --clean --if-exists < deploy/backups/<file>.dump
  sudo docker compose -f deploy/docker-compose.yml --env-file deploy/.env start odoo
  ```

- **Rollback:** check out the previous commit and redeploy. When the release migrated data, restore the dump taken
  before it instead.
- **Odoo shell:** `sudo docker exec -it oficina-os-odoo-1 odoo shell -c /tmp/odoo.conf -d odoo --no-http`.
- **Sample data** (`deploy/sample_data.py`), run in an Odoo shell:
  - `SAMPLE=create PHOTOS=<folder>` adds customers, trucks and orders in every stage (tagged `oficina_exemplo`) and
    a starting service catalogue;
  - `SAMPLE=check` lists what removal would delete;
  - `SAMPLE=remove` deletes the samples and what was made on them, restarts the order numbering, and stops on an
    issued service invoice.
- **The demo** sleeps on Render's free plan; `.github/workflows/keepalive.yml` pings it during shop hours when the
  repository variable `KEEPALIVE_URL` is set. [demo-database.md](demo-database.md) covers moving it to a new
  database.

## 13. Conventions

- **Odoo coding guidelines:** xml ids `<model>_view_<type>`, `<model>_action`, `<model>_menu`, `<model>_rule_company`;
  view names `<model>.view.<type>`; one file per model; controllers in `<module>.py`; methods ordered computes →
  constraints → CRUD → actions → business → app API; `@api.ondelete` guards named `_unlink_except_*`.
- **CSS:** classes prefixed `o_workshop_*` (`o_workshop_app_*`, `o_workshop_dash_*`, `o_workshop_page_*`), state
  classes `o_workshop_is_*`, variables `--Workshop-*`; no id selectors. The libsass compiler evaluates CSS `min()`
  and `max()` itself: avoid them with mixed units.
- **Commits:** a summary line of what changed for the user, then why. Tests and translations go with the change.

## 14. Customising for a client

- **White-label is configuration:** the shop's name, logos, colours, icon, link preview, texts, services, stages,
  checklists and users are data set in the Settings or in the database. A new shop needs no code.
- **Client-specific code** (an integration, a custom report, a data import) belongs in a separate addon, for
  example `<client>_custom`, kept in its own private repository and mounted as an extra addons path on that
  client's server. The public modules stay generic, and the client's code and data stay private.
- **Licence:** the modules are under the Odoo Proprietary License (OPL-1). The code is public to read and to
  evaluate; using it for real, adapting it for a client or selling it needs a written licence from the author (see
  `COPYRIGHT`). A client's private addon may use any licence compatible with the OPL-1.

## 15. Troubleshooting

| Symptom | Likely cause |
|---|---|
| "Style error" banner and an old-looking backend | SCSS failed to compile (often `min()`/`max()` with mixed units); run `test_styles_compile`. |
| Every form with tabs fails to open (OwlError "cannot be located in element tree") | A template extension's xpath no longer matches Odoo's template; run `test_template_extensions_find_their_place`. |
| A new term shows in English | Not in `i18n/pt_BR.po`, or the database kept an older translation; export, merge, upgrade. |
| The service after a deploy shows "preparing the system" for minutes | The upgrade is running; follow `docker logs`. An error there leaves the previous version's data untouched. |
| A connection test to Cloudinary says the key is unknown | The API key field holds the key's name instead of its number. |
