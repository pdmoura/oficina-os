# User manual

[![English](https://img.shields.io/badge/lang-English-1f6feb.svg)](user-manual.md)
[![Português](https://img.shields.io/badge/lang-Portugu%C3%AAs-2ea043.svg)](user-manual.pt-BR.md)

This manual is for the people who use the system every day: the office, the mechanics and whoever sets the
shop up. To install, run or change the system, see the [developer guide](developer-guide.md).

The screens are shown here with their English names, as they read when a user's language is English. Shops in
Brazil use them in Portuguese; the [Portuguese manual](user-manual.pt-BR.md) uses those names.

## Contents

1. [Who does what](#1-who-does-what)
2. [First login](#2-first-login)
3. [Dashboard](#3-dashboard)
4. [Work orders](#4-work-orders)
5. [Approval by the customer](#5-approval-by-the-customer)
6. [Mechanic app](#6-mechanic-app)
7. [Customers and vehicles](#7-customers-and-vehicles)
8. [Monthly closing](#8-monthly-closing)
9. [NFS-e (service invoices)](#9-nfs-e-service-invoices)
10. [Settings](#10-settings)
11. [Frequent questions](#11-frequent-questions)

## 1. Who does what

| Role | Works in | Can |
|---|---|---|
| **Mechanic** | The mechanic app, on a phone | Receive trucks, change stage and bay, add services, photos and the checklist, mark the job ready. Does not approve quotes or touch prices and billing. |
| **Office** | The dashboard and Odoo's screens, on a computer or a phone | Everything a mechanic does, plus: approve or reject quotes, cancel and reopen orders, register customers, close the month and issue NFS-e. |
| **Administrator** | Everything, plus the Settings | The shop's brand, texts, photos, NFS-e and users. |

Each person's role is set in **Settings → Users & Companies → Users**, in the **Workshop** field (Mechanic or
Office).

## 2. First login

1. Open the system's address in the browser and sign in with your login and password.
2. Each role lands on its screen: the office on the **Dashboard**, the mechanic in the **mechanic app**.
3. The first time, a **guided tour** walks through the main screens, highlighting each part with an explanation.
   Use **Next** and **Back**, or **Skip tour**. To open it again:
   - in the office: your user menu (top right) → **Guided tour**;
   - in the app: menu (☰) → **Guided tour**.

### Install it on a phone

The system works as an app, with no app store:

- **Android (Chrome):** sign in, tap ⋮ → **Install app**.
- **iPhone (Safari):** sign in, tap Share (□↑) → **Add to Home Screen**.

An icon with the shop's brand shows up. It opens full screen, straight on the screen of your role. You stay signed
in as long as you use the system at least once a week.

## 3. Dashboard

The office's home screen (**Workshop → Yard**):

- **The day's numbers:** trucks in the shop, late orders, orders waiting for approval, ready for pickup, what was
  done this month and what is not billed yet. Tapping a number opens those orders.
- **Stages:** one card per stage (Office, Waiting for parts, Queued, In progress, On hold, Testing / check) with
  how many trucks are in it. Tapping opens that stage's orders.
- **Lists:** late orders, trucks ready for pickup and the month's customers.
- **Top buttons:** light or dark theme, **Mechanic app** and **All orders**.

The dashboard refreshes itself every minute.

## 4. Work orders

### The board

**Workshop → Work Orders** shows the open orders in columns, one per stage. On a computer, drag a card to change
its stage. On a phone, swipe between columns. The list icon switches to a table; there are also calendar and
analysis views.

Each card shows the number, plate, vehicle, customer, bay, time in the current stage and the promised date (red
when late).

### Create an order

The quickest way is the mechanic app's **Receive vehicle** (see section 6), which starts from the plate. In the
office, use **New** on the board: pick the customer and the vehicle, the stage, the bay, the mechanic and the
promised date. The number (OS 00001, OS 00002...) is given when you save; until then the order reads "New".

### Inside an order

**Sections** (on a phone, pick the section in the yellow list above the content):

- **Services:** one per line, with description, mechanic, quantity, hours, price and approval. Pick from the
  catalogue or type a free line. Tick **Part** on parts and materials: they show a PART tag, and under the lines the
  order shows **Labour** and **Parts** apart. Parts stay out of the NFS-e (section 9).
- **Problem and diagnosis:** what the driver reported, what the mechanic found, internal notes and the warranty
  text.
- **Checklist:** the arrival checklist answered in the app (OK, Attention, Problem, N/A).
- **Photos:** the photos taken in the app, grouped as **Arrival**, **During the job** and **Delivery**.
- **Timeline:** where the order has been, when, and how long it stayed in each stage.
- **Approval:** who approved, when, and the signature.

**Top buttons** (on a phone the first two stay in view and the others go under ⋮):

| Button | Shown when | Does |
|---|---|---|
| **Approve** | awaiting approval or rejected | Approves the quote (pending services become approved). |
| **Reject** | awaiting approval | Marks the quote as rejected. |
| **Mark ready** | approved | The job is done; the order becomes "Ready". |
| **Deliver** | ready | The truck has left. |
| **WhatsApp** | open order | Opens WhatsApp with the message and approval link for the customer's phone. |
| **Customer link** | always | Copies the approval link and says "Customer link copied". |
| **Print** | always | Makes the order's PDF. When there are photos, it asks whether to include them. |
| **Reopen** | ready, delivered or cancelled | Takes the order back to approved. |
| **Cancel** | not delivered | Cancels the order (asks for confirmation). |

Approving, rejecting, cancelling and reopening belong to the office: mechanics don't see those buttons, and the
system refuses them through any other path too. An order already in a monthly closing cannot be cancelled or
reopened.

## 5. Approval by the customer

The **customer link** opens a page without login, in the shop's brand:

- the order's status and timeline;
- the reported problem and the diagnosis;
- the photos marked for the customer, grouped as Arrival, During the job and Delivery;
- the services, each with its own checkbox.

The customer can approve all of it or part of it, types their name and signs with a finger. The approval shows up
in the office right away. Someone who prefers the phone call: the office uses **Approve** on the order.

**Fleets on contract** (an option on the customer) get their orders approved automatically.

## 6. Mechanic app

### Home

- **Search:** type part of the plate, the order number or the customer.
- **Numbers:** open, late and waiting-for-approval orders.
- **Stages:** filter the trucks by stage. The button next to it switches between a row and a grid, and the app
  remembers your choice.
- **Cards:** each truck in the yard, with plate, vehicle, customer, stage, time in the stage, bay and a **Late**
  tag once past the promised date.
- **Receive vehicle** (yellow button): starts a new order.

### Receive a truck

1. Type the plate (Mercosul or the old format).
2. A known truck brings its customer and last odometer. If it already has an open order, the app opens that order
   instead of creating another.
3. A new truck: fill in the customer, brand and model; it is registered on the way.
4. Enter the odometer, who brought it, the reported problem and the services, and confirm.

### Inside an order in the app

- **Stage** and **Location:** one tap to change.
- **Services:** add from favourites or search, remove with the bin. An approved service can only be removed by
  the office. Parts from the catalogue come in with a PART tag.
- **Photos:** three blocks, **Arrival** (how the truck came in: front, sides, dashboard and any damage), **Job**
  (the fault and the repair, which the customer sees on the link) and **Delivery** (the truck ready to leave).
  Each block has its own **Photo** button, and the block for the order's current moment stands out. Photos are
  shrunk on the phone before they are sent.
- **Checklist:** answer item by item; the progress shows on the tab.
- **History:** the stages the order went through.
- **Job ready:** when the work is finished. The office sees it right away.
- **Share** (icon at the top): sends the customer link on WhatsApp or another app.

### Menu (☰)

Light or dark theme, **Office view** (office only), **Guided tour**, **Refresh** and **Sign out**. A new order
typed halfway is kept on the phone: a phone call in the middle does not lose it.

## 7. Customers and vehicles

- **Workshop → Customers → Customers:** fleets and walk-in customers. On the **Workshop** tab, tick **Pre-approved
  orders** for fleets on contract. The phone on the customer is the one the WhatsApp button uses.
- **Workshop → Customers → Vehicles:** plate, the customer's fleet number, brand, model, year, colour, fuel, VIN
  and last odometer. A vehicle shows all its orders.

## 8. Monthly closing

For fleets that pay once a month (**Workshop → Billing → Monthly Closing**):

1. **New:** pick the customer and the period (the previous month by default).
2. **Load orders of the period:** brings the customer's finished orders that are not closed yet.
3. Check and **Confirm**. The orders are now tied to this closing.
4. **Print report:** one line per service, with quantity, unit price and amount, the parts in a table of their
   own, and the list of orders.
5. **Issue NFS-e:** issues the month's note (see section 9). Once issued, the closing becomes **Invoiced**.
6. **Mark paid** when the payment comes in.

**Workshop → Billing → Services Analysis** shows the services by period, customer, sector and mechanic.

## 9. NFS-e (service invoices)

Brazil's service invoice goes through the **Sistema Nacional NFS-e**. There are two modes, chosen in
**Settings → NFS-e**:

- **Assisted:** the system lays out every value to copy into the Emissor Nacional website. No certificate needed.
- **Direct:** the system signs and sends the note by itself. It needs the company's A1 digital certificate.

### Create the note

- **From a finished order** (not in a monthly closing): **Issue NFS-e** on the order.
- **From a confirmed monthly closing:** **Issue NFS-e** on the closing.
- **From the NFS-e menu → New:** pick the **Work order** or the **Monthly closing** at the top, and the note fills
  itself in.

In all three the note brings the customer, the amount of the services, the competence and the **service
description**, one line per service:

```
Services on work order OS 00011, plate NXR4D27 (Mercedes-Benz Axor 2544):
- Air-conditioning gas charge (R-134a): 1 × R$ 320.00 = R$ 320.00
- Receiver drier replacement: 1 × R$ 240.00 = R$ 240.00
Total: R$ 560.00
```

The description can be edited before issuing and takes up to 1000 characters. For a very large closing it shortens
itself: first the list of orders goes, then the smallest services become one "Other services" line. The total
always stays.

An order or a closing can have only one live note. To issue again, cancel the previous one.

### Issue in assisted mode

1. On the note, **Emissor Nacional** tab, tap **Open Emissor Nacional**.
2. Copy each value (copy button next to it) into the website's form: customer's CNPJ/CPF and name, competence,
   service code, amount, ISS rate and description.
3. Issue the note on the website and copy its **access key** (50 digits).
4. Paste the key on the note and tap **Register issued note**.

In direct mode, the note's **Issue NFS-e** button does all of that by itself. In both modes the **DANFSe** (the
note's PDF) is available once issued, and an issued note can be cancelled with **Cancel NFS-e**.

> **Parts:** lines marked **Part** stay out of the note. Its amount and description cover labour only, because
> parts are billed as goods (ICMS), outside the service invoice. An order with parts only has no NFS-e.

## 10. Settings

Only the administrator sees **Workshop → Configuration → Settings**.

### Brand

- **Accent colour:** paints buttons and highlights across the system, the app, the customer page and the login.
- **Background colour and login card:** the sign-in screen, light or dark.
- **Logos:** the full logo for light backgrounds (PDFs, light login) and for dark ones (dashboard, dark login), the
  symbol (the app's header) and the symbol for the light theme.
- **Browser icon:** the tab's and the phone shortcuts' picture (.ico or .png).
- **Link preview image:** what shows up when a link is shared on WhatsApp (1200×630).

### Texts

The **warranty** printed on every order and the **terms** the customer accepts when approving.

### Photos

Where the photos are kept:

- **Database** (default): works on any server, nothing to set up.
- **Cloudinary:** keeps the database small and loads photos faster. In Cloudinary, open **Settings (the gear) →
  API Keys** and copy:
  - **Cloud name:** the name at the top of the page;
  - **API key:** the **number** in the "API Key" column, not the key's name (such as "Root");
  - **API secret:** the "API Secret" on the same line, shown by tapping the eye;
  - **Folder:** any name you like. Cloudinary creates it with the first photo.

  Then tap **Test connection**: the system sends a test photo to the folder and deletes it. Photos taken before
  stay where they are.

### The shop's lists (Configuration menu)

- **Services:** name, sector, hours and price. Those marked **favourite** come first in the app. Mark **Part** on
  parts and materials, and they reach the order already marked.
- **Stages:** the board's columns, in the shop's order, with a colour. Time in a **waiting stage** (parts, approval)
  does not count as work time.
- **Locations:** bays, yard, road test, at the customer's.
- **Sectors:** electrical, air conditioning, electronic fuel injection and so on.
- **Checklists:** the items of the arrival and delivery checklists, by section.

### Users

**Settings → Users & Companies → Users → New:** name, login (e-mail or a nickname) and, in the **Workshop** field,
**Mechanic** or **Office**. After saving, set the password in **⚙ Action → Change Password** and give it to the
person, who can change it in **My Preferences**.

## 11. Frequent questions

**The system asked for my password again.** Sign-ins expire after a week without use. Sign in again.

**There is no internet in the yard.** The app needs a connection (Wi-Fi or mobile data). What was typed in a new
order stays on the phone until the connection is back.

**A photo did not upload.** A "Photo not sent" message says why. Check the connection and try again. If photos go
to Cloudinary, ask the administrator to use **Test connection** in the Settings.

**The customer link was not copied.** Some browsers block copying. The link then stays on screen to copy by hand.

**An order has no number ("New").** It is not saved yet: tap **Save**.

**The mechanic doesn't see Approve.** Approving belongs to the office. If they need to approve, change their role
to Office.

**I want the tour again.** User menu → **Guided tour** (in the app: ☰ → **Guided tour**).
