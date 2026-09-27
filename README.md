# Oficina OS

[![English](https://img.shields.io/badge/lang-English-1f6feb.svg)](README.md)
[![Português](https://img.shields.io/badge/lang-Portugu%C3%AAs-2ea043.svg)](README.pt-BR.md)

Work orders for truck electrics and air-conditioning shops, built on **Odoo 19 Community**. The mechanic
runs the job from a phone, the fleet customer approves the quote from a WhatsApp link, and the office
closes the month and issues the **NFS-e** through Brazil's national system.

White-label: each shop gets its own logos, colours and phone icon. The interface is in Brazilian
Portuguese.

<p>
  <img src="docs/screenshots/app-home.png" width="200" alt="Mechanic app: the yard">
  <img src="docs/screenshots/app-new-order.png" width="200" alt="Receiving a truck">
  <img src="docs/screenshots/app-order.png" width="200" alt="Work order on the phone">
  <img src="docs/screenshots/customer-approval.png" width="200" alt="Customer approval page">
</p>

<img src="docs/screenshots/office-dashboard.png" alt="Office dashboard">

## What is inside

| Module | What it does |
|---|---|
| [`workshop_os`](workshop_os) | Vehicles by plate (Mercosul and old format), work orders, stages with time spent in each one, locations, checklists, photos, the mechanic app (OWL, installable as a PWA), the customer approval page with signature, the office dashboard, the monthly closing per fleet, and PDFs. |
| [`l10n_br_nfse_nacional`](l10n_br_nfse_nacional) | NFS-e through the Sistema Nacional NFS-e. **Assisted** mode prepares every field for the Emissor Nacional website. **Direct** mode signs the DPS with the company's A1 certificate and sends it to SEFIN Nacional. Also: cancellation, DANFSe PDF. Works without the workshop module. |
| [`workshop_os_nfse`](workshop_os_nfse) | Glue module, installed automatically: issues the note of a monthly closing or a finished work order. |

### The mechanic's phone

- **Receive a truck from the plate.** A known vehicle brings its customer and odometer, and an open order is reopened instead of duplicated. A new vehicle is registered in the same form.
- **Work the order.** Change stage and bay with one tap. Add services from favourites and search. Take photos, which are compressed on the phone and stored in the database or on Cloudinary. Answer the arrival checklist, mark the job ready, and share the approval link on WhatsApp.
- **Keep typing safe.** Drafts are kept in the browser, so an incoming call doesn't lose a half-typed order.

### The customer

The approval link is `/os/<token>` and needs no login. The fleet manager sees:

- the status and the stage timeline;
- what was found and the photos the shop chose to show;
- the services, each with its own checkbox.

They approve part of the quote, or all of it, and sign with a finger. The approval shows up in the office right away. Fleets on contract are approved automatically.

### The office

- **Dashboard:** late orders, orders waiting for approval, trucks ready for pickup, what is done but not billed, and the month's revenue by customer.
- **Views:** kanban, calendar and pivot, plus a service analysis.
- **Monthly closing:** each fleet gets a report grouped by service with the list of orders, then the NFS-e with one click.

<p>
  <img src="docs/screenshots/work-order-pdf.png" width="420" alt="Work order PDF">
  <img src="docs/screenshots/danfse.png" width="420" alt="DANFSe drawn from the authorised NFS-e">
</p>

## NFS-e Nacional, the parts that matter

The direct mode follows the national layout 1.01 and its rejection rules (codes like E0121 are from Annex I):

- **DPS built by the rules.**
  - The provider block stays lean: no name or address, which the registry fills in (E0121, E0128).
  - The ISS rate is sent only when an ME/EPP has the ISS withheld (E0625/E0621).
  - The Law 12.741 tax estimate depends on the regime: `pTotTribSN` for ME/EPP, never `indTotTrib` (E0712).
  - Text is cleaned to the Latin-1 range the schema accepts (E1235).
- **Checked before it leaves.** Every DPS and cancellation event is validated against the official XSDs, which ship with the module. Problems show up as readable messages instead of a remote E1235.
- **Signature and transport.**
  - Enveloped XMLDSig, as the national manual specifies: inclusive C14N, RSA-SHA1, end certificate only.
  - The signature uses the certificate kept by Odoo's `certificate` module. The request goes over mutual TLS and is GZip+Base64 packed.
  - Answers are read case-insensitively, because the API has been seen answering in both camelCase and PascalCase.
- **No duplicates.** If an answer is lost and the resend comes back as E0014, the module fetches the note that already exists.
- **DANFSe per NT 008.**
  - The ADN PDF API was switched off on 03/08/2026, so the module draws the DANFSe itself.
  - It prints only what the authorised XML contains, adds the public-consultation QR code, and marks test-environment and cancelled notes.

Without a certificate, the assisted mode still takes the typing out of it: it lays out each value to copy, then records the access key of the issued note.

<img src="docs/screenshots/nfse-assisted.png" alt="Assisted emission">

## Run it locally

```bash
docker compose up -d db
docker compose run --rm odoo odoo -d oficina -i workshop_os,workshop_os_nfse --with-demo --load-language=pt_BR --stop-after-init
docker compose up -d odoo
```

Open http://localhost:8070. The demo logins are `admin` / `admin` for the office and `mecanico` / `mecanico` for the mechanic, who lands straight in the app. To see the phone app, open it with the browser in phone emulation or on a phone on the same network.

Run the tests:

```bash
docker compose run --rm odoo odoo -d test -i workshop_os,workshop_os_nfse --test-tags /workshop_os,/l10n_br_nfse_nacional,/workshop_os_nfse --stop-after-init
```

The 39 tests cover:

- **Workshop:** plate rules, approval, customer page, billing, reports, style compilation, Brazilian defaults on a new database.
- **NFS-e:** the DPS against the official XSD, each regime's rules, signature verification and tampering, mocked API success, rejection and E0014 recovery, cancellation, DANFSe, CEP lookup.

## Deploy (Render + Supabase)

The [`Dockerfile`](Dockerfile) adds the modules to the official Odoo 19 image. [`deploy/entrypoint.sh`](deploy/entrypoint.sh) configures Odoo from environment variables:

- **First boot:** creates the database, keeps every attachment in PostgreSQL (the container disk is ephemeral), installs the modules in pt-BR and sets the administrator's login and password.
- **Later deploys:** upgrades the modules only when their code changed.

| Variable | Value |
|---|---|
| `DB_HOST`, `DB_PORT`, `DB_USER` | Supabase **session pooler** (IPv4; `LISTEN` works, which Odoo's cron needs). User is `postgres.<project-ref>`. |
| `DB_PASSWORD` | database password |
| `DB_NAME` | `odoo` (created on first boot) |
| `ODOO_ADMIN_EMAIL`, `ODOO_ADMIN_PASSWORD` | administrator created on first boot |
| `LOAD_DEMO` | `false` for a real shop |

Put the database and the web service in the **same region**, e.g. Supabase East US (North Virginia) and Render Virginia. Odoo runs many queries per request, so a cross-continent link would make every page slow.

On the free plan, Odoo uses about 230 MB of the 512 MB. [`keepalive.yml`](.github/workflows/keepalive.yml) pings the service during shop hours when the repository variable `KEEPALIVE_URL` is set.

## License

Odoo Proprietary License v1.0 (OPL-1). See [LICENSE](LICENSE) and [COPYRIGHT](COPYRIGHT).

The code is public to read and to evaluate: anyone may run it on their own computer to get to know the system. Using
it for real, in production or as a service for others, needs a license agreed in writing with the author.
