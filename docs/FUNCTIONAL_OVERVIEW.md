# SavvyEats — Functional Overview

> A plain-language guide to what the SavvyEats app does, who uses it, and how the
> pieces fit together. No prior knowledge of the codebase is assumed.

---

## 1. What is SavvyEats?

SavvyEats is a **meal-subscription and delivery platform** built on top of
Frappe / ERPNext (a Frappe "app" named `savvyeats`). Customers subscribe to a
**meal plan** for a period of time (weeks or months), choose which dishes they
want delivered on which days, pay online, and then receive recurring deliveries.
Drivers fulfil those deliveries, and the customer can track them in real time.

The platform has three audiences:

| Audience | How they use it | Interface |
|----------|-----------------|-----------|
| **Customers** | Sign up, build a subscription, pick meals, pay, track & rate deliveries | Mobile app (talks to the JSON APIs in `savvyeats/api/`) |
| **Drivers** | See today's delivery trips, start trips, mark stops delivered/failed, upload proof, share GPS location | Mobile app (`savvyeats/api/driver/`) |
| **Staff / Admins** | Manage dish plans, pricing, schedules, zones, orders, deliveries, and settings | Frappe Desk (ERPNext back office) |

Everything is built on standard ERPNext documents — a subscription is a
**Sales Order**, a delivery is a **Delivery Note**, payment creates a **Payment
Entry**, and route fulfilment uses **Delivery Trips**. SavvyEats adds custom
DocTypes, custom fields, business rules, and a mobile-friendly API layer on top.

---

## 2. Core concepts (the vocabulary)

Understanding these terms makes the rest of the document straightforward.

- **Dish Plan** — A named meal program (e.g. a calorie-targeted plan). Defines
  which **Meals** it includes, calorie range, allowed week plans, and a default
  pricing option. Plans can be grouped under a **Dish Plan Type**.
- **Meal** — A meal slot such as *Breakfast*, *Lunch*, *Dinner*, *Snack*. Each
  dish plan declares the meals it offers plus min/max quantity per day.
- **Dish Plan Pricing** — A price configuration for a dish plan. Lists a
  per-day price for each meal. A plan has a default pricing option, and the
  price the customer pays depends on which meals they select.
- **Week Plan** — Which days of the week deliveries happen on (e.g. Sun–Thu).
  Drives how the calendar of delivery dates is generated.
- **Dish Schedule** — The published menu for a specific calendar date: which
  actual food **Items** are available for each meal of each dish plan that day.
  Customers pick their dishes from the published schedule.
- **Item** — An ERPNext stock item representing a real dish or an **Add-on**.
- **Allergen / Health Goal** — Tags a customer selects during onboarding,
  stored on the order so meals can be tailored/filtered.
- **Subscription** — In SavvyEats this *is* a submitted **Sales Order** with a
  `subscription_status` (Active / Paused / Completed).
- **Delivery** — A **Delivery Note** for one customer on one delivery date.
- **Subscription Delivery** — A daily batch document that gathers every
  delivery due on a given date and turns them into Delivery Notes in one go.
- **Zone / Delivery Area / Driver Zone** — Geographic structures used for
  addresses and assigning drivers to areas.

---

## 3. The customer journey (end to end)

### 3.1 Sign-up & authentication
File: `savvyeats/api/user.py`

1. **Send OTP** (`send_otp`) — User submits email + mobile number. The system
   checks the email/mobile aren't already taken, rate-limits sign-ups
   (max 300 OTPs/hour globally), generates a 6-digit OTP, stores it in
   **OTP Verification** (5-minute expiry), and sends it by SMS (Qatar `+974`
   prefix).
2. **Verify OTP** (`verify_otp`) — Confirms the OTP, then creates a **User**
   (Website User type) with the chosen password and issues an **API key/secret**
   pair for token auth. May place the user **on a waiting list** (see §6).
3. **Login** (`login`) — Standard Frappe authentication; returns the API
   key/secret and whether the user is "new" (no Customer record yet).
4. **Forgot password** — `forget_send_otp` → `forget_verify_otp` →
   `update_password` mirror the OTP flow for password resets.
5. **Profile & notification preferences** (`update_details`, `update_fcm_token`)
   — Update profile fields and store the device's **FCM Token** for push
   notifications. Many notification toggles exist (special offers, weekly
   progress, do-not-disturb, etc.).

### 3.2 Onboarding setup data
File: `savvyeats/api/settings.py`

The app fetches everything needed to render the plan builder via
`get_setup_data_v2` (and legacy `get_setup_data`): enabled **dish plans**
(with their pricings, week plans, and meals), **dish plan types**, **allergens**,
**health goals**, **delivery time slots**, and **improved suggestions**. The
`ui_type` App Setting switches between a flat list ("Standard") and a grouped-by-
type presentation ("Dish Plan Type").

Other content endpoints serve the **About**, **Terms & Conditions**, **Privacy
Policy** web pages, **Customer Support** details, and global **App Settings**.

### 3.3 Building the order (the draft cart)
File: `savvyeats/api/order.py`

The cart is a **draft Sales Order** (`docstatus = 0`, `is_online = 1`).

1. **Get / create draft** (`get_draft_order`) — Finds the user's open draft or
   creates one. Passing `new=true` wipes the existing draft back to a clean
   slate (`_reset_sales_order_in_place`).
2. **Update draft** (`update_draft_order`, `validate_draft_order`) — Saves
   chosen dish plan, week plan, period (weeks/months), allergens, health goals,
   delivery time slot, etc. Protected fields (name, owner, customer, items)
   can't be overwritten by the client. Each save recomputes the delivery
   calendar via `sales_order_delivery` (see §4.1).
3. **Add meal items** (`add_items`) — The heart of meal selection:
   - Determines the correct **Dish Plan Pricing** by matching the set of meals
     the customer selected against each pricing's required meals; falls back to
     the plan's default pricing.
   - Rebuilds the order's item lines: for each chosen dish on each delivery date
     it adds an item at the per-meal price; for any meal/day not yet chosen it
     fills placeholder lines (`"Item Not Selected"`) up to the meal's max
     quantity so the schedule and price are complete.
4. **Browse the menu** (`api/items.py` → `get_plan_items`) — Returns, per
   delivery date, the published **Dish Schedule** items available for the order's
   dish plan, plus purchasable **Add-ons** with their prices.
5. **Addresses** (`get_addresses`, `add_address`, `update_address`,
   `remove_address`, `verify_addresses`) — Addresses are tied to the User via
   dynamic links and carry **delivery days** (which weekday is delivered to
   which address). `verify_addresses` enforces that every delivery day in the
   plan maps to exactly one address (no gaps, no duplicate days).
6. **Contact info** (`update_contact_information`) — Saves name/phone onto both
   the User and the order.
7. **Voucher** (`apply_voucher_code`) — Validates and attaches a **Coupon Code**
   (checks validity window and usage limits).

### 3.4 Payment & submission
Files: `savvyeats/api/payment.py`, `savvyeats/www/*`

1. **Get payment link** (`get_payment_link`) — Returns a hosted payment URL
   (`/skip-cash/<order_id>`). If the total is 0, it's flagged as already paid.
2. **Payment pages** — `www/skip-cash`, `www/pay`, and the
   `www/redirect/cybersource` & `www/redirect/qpay` gateways render the hosted
   checkout. Gateways post back to the `/payment-response/...` routes
   (success / failure / error) declared in `hooks.py`.
3. **Verify payment** (`verify_payment`) — Confirms a **Payment Log** with an
   `ACCEPT` decision exists, then:
   - Converts the placeholder **"Online Customer"** into a real **Customer**
     record (creating one if needed).
   - **Submits** the Sales Order (sets `subscription_status = "Active"`).
   - Creates and submits a matching **Payment Entry**.
   - Increments the waiting-list subscriber counter for genuinely new customers.
   - Zero-total orders skip the gateway and submit directly.
4. A scheduled job (`update_payment_logs`, every 5 min) sweeps recently accepted
   payment logs and calls `verify_payment` automatically, so an order finalises
   even if the app didn't poll.

### 3.5 Living with an active subscription

- **Dashboard** (`api/dashboard.py` → `get_dashboard`) — Shows the active order,
  per-day and per-meal **nutrient breakdowns** (from SQL views
  `delivery_daily_nutrients_view` / `delivery_meal_nutrients_view`), today's
  delivery, and item images.
- **Current subscription** (`api/subscription.py` → `get_current_subscription`).
- **Deliveries list & detail** (`get_deliveries`, `get_delivery_details`) —
  Reads from a `deliveries` SQL view; paginated, highlights today's delivery,
  includes shipping address.
- **Live tracking** (`get_delivery_location`) — Returns the driver's latest GPS
  point for an in-progress delivery (see also the `track_delivery` desk page).
- **Rating** (`rate_delivery`, `rate_delivery_item`) — Customers rate a whole
  delivery (with comments + improvement suggestions) or individual items.

### 3.6 Pause & resume
File: `savvyeats/api/subscription.py`

If enabled in **App Settings**, a customer can **pause** an active subscription
for a date range (`pause_subscription`):
- Limited by `max_pause_count`.
- Pending delivery days in the window are marked **Paused**.
- A background job (`clear_paused_delivery_items`, daily) walks each paused day
  one at a time, appends a replacement delivery date after the pause window (on
  a valid week-plan weekday), moves that day's items to the new date as
  "Item Not Selected", and extends the subscription end date accordingly.
- **Resume** (`resume_subscription`) reactivates early and recalculates the end
  date. A daily job (`auto_resume_paused_subscriptions`) auto-resumes once the
  pause end date passes.
- System Managers get an email when a subscription is paused.

---

## 4. How the schedule & delivery engine works

### 4.1 Generating the delivery calendar
File: `savvyeats/custom/sales_order_savvyeats.py`

On every Sales Order save, `sales_order_delivery()`:
1. Computes `end_date` from `start_date` + `period_type`/`period_count`
   (weeks or months), minus one day.
2. Uses `delivery_schedule(start, end, week_plan_days)` to enumerate every
   calendar date that falls on an allowed weekday.
3. Rebuilds the **Sales Order Delivery Days** child table (one row per delivery
   date, with weekday + status), and records `actual_start_date` /
   `actual_end_date`.

`validate_addresses()` then ensures every delivery weekday has exactly one
address mapped, and stamps the right address onto each delivery-day row.

`preserve_custom_rates()` protects API-set meal prices from being overwritten by
ERPNext's pricing rules.

### 4.2 Turning subscriptions into deliveries
Files: `subscription_delivery.py`, `custom/delivery_note_savvyeats.py`,
`background_jobs.py`

- A cron job (`create_subscription_delivery`, daily at 15:00) creates a
  **Subscription Delivery** for a date a few days ahead
  (`delivery_creation_days`, default 2 — supports back-to-back subscriptions).
- `fetch_deliveries()` scans all active subscriptions, and for each one due on
  that date, generates a **Delivery Note** (via ERPNext's `make_delivery_note`)
  scoped to that delivery date, then lists every line item.
- Submitting the Subscription Delivery submits all the underlying Delivery Notes
  in one action; cancelling cancels them.
- **Delivery Note** validation (`custom/delivery_note_savvyeats.py`) enforces
  one Sales Order per note, items matching the posting date, and copies meal /
  note / address details from the order. Submitting/cancelling a note flips the
  matching delivery-day status between **Scheduled** and **Pending**.

### 4.3 Driver fulfilment
Files: `savvyeats/api/driver/deliveries.py`,
`savvyeats/overrides/delivery_trip_savvyeats.py`

- Delivery Notes are grouped into **Delivery Trips** (ERPNext routing,
  customised via `DeliveryTripOverride`).
- **Get today's trips** (`get_delivery_trips`) — Returns the driver's scheduled
  trips for today with each stop's address.
- **Start delivery** (`start_delivery`) — Marks a stop *In Transit*, locks it,
  and records the first GPS point.
- **Update status** (`update_delivery_status`) — Sets *Delivered* / *Failed
  Attempt* (with failure reason + driver notes), stamps end time, and accepts an
  uploaded **delivery-proof photo** (auto-optimised) attached to the trip.
- **GPS tracking** (`update_driver_location`) — Streams **Driver Location**
  points; old points are purged hourly (`remove_old_location`), and the
  customer app reads the latest one for live tracking.

---

## 5. Scheduled background jobs
File: `savvyeats/background_jobs.py` (wired in `hooks.py`)

| Job | Cadence | Purpose |
|-----|---------|---------|
| `remove_expired_otp` | hourly | Delete expired OTP records |
| `remove_old_location` | hourly | Purge yesterday's GPS points |
| `update_expired_orders` | daily | Mark unpaid drafts past their first delivery (minus buffer days) as expired |
| `auto_complete_active_orders` | daily | Mark subscriptions past their end date as Completed |
| `auto_resume_paused_subscriptions` | daily | Auto-resume pauses whose end date has passed |
| `create_subscription_delivery` | 15:00 daily | Build the next day(s) Subscription Delivery & Delivery Notes |
| `update_payment_logs` | every 5 min | Finalise orders for accepted-but-unprocessed payments |
| `notify_incomplete_meal_plans` | hourly (at configured hour) | Push/notify customers who haven't planned enough upcoming meals |
| `notify_subscription_ending` | 08:00 daily | Remind customers (and email staff) when a subscription is ending soon |
| `clear_paused_delivery_items` | 00:00 daily | Reschedule paused deliveries to after the pause window |

Notifications are sent via Frappe **Notification Log**, email (`frappe.sendmail`),
and Firebase Cloud Messaging (`savvyeats/fcm.py`).

---

## 6. Waiting-list / capacity control
Files: `api/user.py` (`apply_waiting_list_logic`), `api/payment.py`
(`increment_users_subscribed_if_new_customer`)

When **App Settings** has `waiting_list` enabled within a `from_date`–`to_date`
window with a `max_subscriptions_count`:
- New sign-ups are flagged `on_waiting_list` once `users_subscribed` reaches the
  cap.
- The counter only increments when a **genuinely new** customer completes a paid
  subscription (verified against Payment Entries), preventing double-counting.

---

## 7. Key configuration (admin-facing)

- **App Settings** (single DocType) — The main control panel: `ui_type`,
  buffer/creation-day windows, waiting-list controls, and feature toggles for
  pausing, meal reminders, subscription-end reminders, and notifications.
- **SavvyEats Settings** (single DocType) — Operational config such as the
  invoice print format and payment gateway list.
- **FCM Notification Settings** / **FCM Token** — Push notification setup.
- **On Boarding App Settings** — Onboarding content.
- Catalog DocTypes managed by staff: Dish Plan, Dish Plan Type, Dish Plan
  Pricing, Meal, Week Plan, Dish Schedule, Allergen, Health Goal, Nutrient,
  Item Nutrients, Delivery Time Slot, Zone, Delivery Area, Driver Zone,
  Improved Suggestions, Custom Support FAQ.

---

## 8. Reporting

- **Subscription Funnel Analysis** (`savvyeats/report/subscription_funnel_analysis`)
  — Analyses how prospects move from sign-up → draft order → paid subscription.

---

## 9. Integration points & customisations summary
File: `savvyeats/hooks.py`

- **Doc events** customise **Address**, **Sales Order**, and **Delivery Note**
  validation/lifecycle.
- **Delivery Trip** class is overridden for SavvyEats routing logic.
- Desk **client scripts** enhance Address, Sales Order, Driver, Item forms and
  the Sales Order / Delivery Note list views.
- **Website route rules** map customer-facing payment URLs to the hosted
  checkout/response pages.
- All customer & driver mobile traffic goes through the whitelisted methods in
  `savvyeats/api/` and returns a **consistent bilingual envelope**
  (`status`, `message_en`, `message_ar`, plus `data` or `errors`) via
  `send_success_response` / `send_error_response`.

---

## 10. Data model at a glance

```
User ──< Address (delivery_days) 
  │
  └──> Customer ──< Sales Order (= Subscription)
                       │  ├─ dish_plan, dish_plan_pricing, week_plan, period
                       │  ├─ meals[]  allergens[]  health_goals[]
                       │  ├─ items[]            (one row per dish per date)
                       │  ├─ delivery_dates[]   (one row per delivery day)
                       │  └─ addresses[]        (day → address mapping)
                       │
                       └──> Delivery Note (per date)  ──< Delivery Note Item
                                  │                            (rating, meal, note)
                                  └──> grouped into Delivery Trip ──< Delivery Stop
                                                                          │
                                                                          └─ Driver Location (GPS)

Subscription Delivery (per date)  ── batches/creates ──> Delivery Notes
Dish Plan ──< Dish Plan Pricing ──< per-meal prices
Dish Schedule (per date) ── publishes available Items per meal per plan
```

---

*Generated as a functional overview of the `savvyeats` Frappe app. For field-level
detail, see the DocType JSONs under `savvyeats/savvyeats/doctype/` and the
whitelisted methods under `savvyeats/api/`.*
