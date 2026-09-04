# App Settings — Reference Guide

`App Settings` is a Single DocType (only one record exists) that controls the SavvyEats
mobile app and the backend automation. Open it in Desk at **App Settings**, or read it from
the app via the `savvyeats.api.settings.get_app_settings` API.

Only the **System Manager** role can read or edit it.

Every setting below is listed with what it does, its default, and where the code actually
uses it. Some fields are only passed through to the mobile app and have no backend logic —
those are marked clearly.

---

## Quick reference

| Setting | Type | Default | Enforced by |
|---|---|---|---|
| Welcome Screen Text | Data | — | Mobile app only |
| Welcome Screen Background | Image | — | Mobile app only |
| Onboarding | Table | — | Mobile app only |
| Force Update | Check | 0 | Mobile app only |
| Start Date | Date | — | Mobile app only |
| IOS Version | Data | — | Mobile app only |
| Android Version | Data | — | Mobile app only |
| UI Type | Select | Standard | Backend |
| Max Months | Int | — | Mobile app only |
| Max Weeks | Int | — | Mobile app only |
| Buffer Days | Int | — | Backend |
| Delivery Creation Days | Int | 2 | Backend |
| Enable Meal Notifications | Check | 0 | Backend |
| Meal Reminder Threshold (Days) | Int | 2 | Backend |
| Meal Reminder Days Before Delivery | Int | 1 | **Not used** |
| Meal Reminder Time | Time | 09:00 | Backend |
| Enable Subscription End Reminder | Check | 0 | Backend |
| Subscription End Reminder Days Before | Int | 3 | Backend |
| Enable Upcoming Delivery Meal Reminder | Check | 0 | Backend |
| Reminder Days Before Delivery | Int | 1 | Backend |
| Reminder Time | Time | 18:00 | Backend |
| Enable Pre-Renewal | Check | 0 | Backend |
| Renewal Window Days | Int | 7 | Backend |
| Renewal Cutoff Days | Int | 4 | Validation only |
| Enable Pause Subscription Feature | Check | 0 | Backend |
| Max Pause Count Per Subscription | Int | 1 | Backend |
| Enable Pause Notifications | Check | 0 | Backend |
| Waiting List | Check | 0 | Backend |
| Max Subscriptions Count | Int | — | Backend |
| Users Subscribed | Int | — | Backend (auto) |
| From Date / To Date | Date | — | Backend |

---

## 1. Welcome Screen

The first screen a new user sees when opening the app.

- **Welcome Screen Text** — The text shown on the welcome screen.
- **Welcome Screen Background** — The background image for that screen.

> These are only delivered to the mobile app through `get_app_settings`. No backend logic
> reads them.

---

## 2. Onboarding

- **Onboarding (child table)** — The intro slides shown to a new user. Each row has:
  - **Heading** — the slide title
  - **Text** — the slide description
  - **Background** — the slide image

Add one row per slide; the order of rows is the order of slides.

> Mobile app only — no backend logic.

---

## 3. App Version & UI

- **Force Update** — Tick this to tell the app that the user *must* update before continuing.
  The app decides how to show the block screen.
- **Start Date** — A general start date sent to the app. Backend logic does not use it.
- **IOS Version** / **Android Version** — The latest published app version numbers. The app
  compares its own version against these to decide whether an update is available/required.

  > These four are mobile-app-only.

- **UI Type** — Controls how meal plans are returned to the app by `get_setup_data_v2`
  (`savvyeats/api/settings.py:78-86`):
  - `Standard` → the app receives a flat list of Dish Plans (only plans whose own
    `ui_type` is also `Standard`).
  - `Dish Plan Type` → Dish Plans are grouped under their Dish Plan Type (categories), and
    the app receives the category list instead.

---

## 4. Plan Length Limits

- **Max Months** — The maximum number of months a customer may subscribe for.
- **Max Weeks** — The maximum number of weeks a customer may subscribe for.

> Both are sent to the app, which enforces the limit in the plan-selection screen. There is
> no backend validation for them.

---

## 5. Delivery Timing

### Buffer Days
The **kitchen-prep buffer** — how many days ahead an order must be locked in so the kitchen
has time to plan, procure and prep. There is no default; leaving it blank means **0**.

It affects four things:

**1. Expiring unpaid draft orders** (`savvyeats/background_jobs.py:13-34`)

A daily job scans every unsubmitted (unpaid) Sales Order. If its **earliest delivery date**
has fallen inside the buffer, the order is marked `expired = 1` and the customer can no
longer pay for that cart.

```
expire if:  (today + Buffer Days) > earliest delivery date
```

So a draft stays valid as long as `earliest delivery date >= today + Buffer Days`.

**2. A renewal's start date** (`savvyeats/api/subscription.py:315-323`)

```
renewal start = max(current subscription end + 1, today + 1 + Buffer Days)
```

If the buffer pushes the start past the day after the current subscription ends, the
renewal is returned to the app with `has_gap = true` and the number of `gap_days`, so the
customer can be shown how many days they will be without meals.

**3. Shifting a queued renewal after a pause** (`savvyeats/api/subscription.py:541-544`)

A pause extends the current subscription's end date, so the already-scheduled renewal's
start is recalculated with the same formula.

**4. Validating Renewal Cutoff Days** (`savvyeats/savvyeats/doctype/app_settings/app_settings.py:15-27`)

App Settings refuses to save when `Renewal Cutoff Days < Buffer Days`, because a cutoff
shorter than the prep buffer can never guarantee a zero-gap renewal.

#### Example — Buffer Days = 3, today is 1 Aug

| Scenario | Result |
|---|---|
| Draft cart, first delivery 5 Aug | Stays valid (5 ≥ 4) |
| Draft cart, first delivery 4 Aug | Stays valid — exactly on the edge |
| Draft cart, first delivery 3 Aug | **Expired** (4 > 3), can no longer be paid |
| Subscription ends 10 Aug, renewed today | Starts 11 Aug, no gap (11 > 5) |
| Subscription ends 2 Aug, renewed today | Starts 5 Aug — buffer pushed it, **2-day gap** |

#### Choosing a value

- **Higher buffer** = more planning room for the kitchen, but drafts expire sooner and
  last-minute renewals show a gap to the customer.
- **Lower buffer** = more flexibility for customers, but shorter notice for the kitchen.
- Set it to the kitchen's real lead time — 2 to 4 days is typical.
- Before raising it, check **Renewal Cutoff Days**: if the new buffer exceeds the cutoff,
  saving is blocked until the cutoff is raised first.

> **Note — the two formulas differ by one day.** Draft expiry uses `today + Buffer Days`
> while renewal start uses `today + 1 + Buffer Days`, so renewals are one day stricter than
> new orders. At Buffer Days = 3 a new customer can book 4 Aug, but a renewing customer's
> earliest start is 5 Aug. This is how the code behaves today; align the two if that is not
> the intended product rule.

### Delivery Creation Days *(default 2)*
How many days ahead the system creates **Subscription Delivery** documents.

The daily job creates a delivery for every date from **today** up to **today + N**
(`savvyeats/background_jobs.py:84-105`). Because it covers the whole range and skips dates
that already have one, a missed scheduler run is automatically backfilled on the next run
instead of losing a delivery day permanently.

---

## 6. Meal Notifications — "you're running low on planned meals"

Reminds a customer when they have not planned enough upcoming days.

- **Enable Meal Notifications** *(default off)* — Master switch. Turning it off stops all
  of these reminders immediately.
- **Meal Reminder Threshold (Days)** *(default 2)* — If a customer has meals selected for
  fewer than this many upcoming delivery days, they get a reminder. Applies to both `Active`
  and `Pending` (scheduled renewal) subscriptions. A user receives at most one of these per day.
- **Meal Reminder Time** *(default 09:00)* — The time of day the reminder is sent.

  > The job runs hourly and only compares the **hour**. Minutes are ignored — `09:30`
  > behaves exactly like `09:00`.

- **Meal Reminder Days Before Delivery** — **This field currently has no effect.** It exists
  on the form but no code reads it. Use the *Upcoming Delivery Meal Reminder* section below
  for a "X days before delivery" reminder.

Code: `savvyeats/background_jobs.py:247-...` (`notify_incomplete_meal_plans`)

---

## 7. Subscription End Notifications

Reminds a customer that their subscription is about to expire.

- **Enable Subscription End Reminder** *(default off)* — Master switch.
- **Subscription End Reminder Days Before** *(default 3)* — How many days before the end
  date to send the reminder.

The job looks at a **date range** (today → today + N) rather than an exact date, so a missed
scheduler run does not skip anyone. Each subscription receives this reminder only **once**,
no matter which day the job catches it.

Code: `savvyeats/background_jobs.py:323-...` (`notify_subscription_ending`)

---

## 8. Upcoming Delivery Meal Reminder

This is a **separate feature** from section 6. That one is a "running low on planned days"
nudge based on a total count. This one targets **one specific delivery date** and fires only
if *every* item for that date is still unselected.

- **Enable Upcoming Delivery Meal Reminder** *(default off)* — Master switch.
- **Reminder Days Before Delivery** *(default 1)* — e.g. `1` = remind the day before the
  delivery date.
- **Reminder Time** *(default 18:00)* — The time of day to send it.

  > Again, only the **hour** is used; minutes are ignored.

Each delivery date triggers at most one reminder per user, de-duplicated across all runs.

Code: `savvyeats/background_jobs.py:407-...` (`notify_unselected_next_delivery`)

---

## 9. Pre-Renewal

Lets a customer buy their next subscription **before** the current one ends, so there is no
break in service.

- **Enable Pre-Renewal** *(default off — ships OFF)* — Master switch. While it is off:
  - the `create_renewal` API returns "Pre-renewal is currently disabled",
  - renewal reminders are not sent,
  - scheduled renewals are not activated,
  - every submitted subscription simply stays `Active`.
- **Renewal Window Days** *(default 7)* — How many days before the end date the "Renew" call
  to action appears and the daily renewal reminders begin.

  > This is **not a hard deadline** — renewal is allowed right up to the last day. Reminders
  > stop automatically once a `Pending` renewal exists for that subscription or the
  > subscription ends. One reminder per subscription per day.

- **Renewal Cutoff Days** *(default 4)* — The zero-gap cutoff.

  > Currently this is **validation only**: saving App Settings fails if
  > `Renewal Cutoff Days < Buffer Days`, because a cutoff shorter than the kitchen-prep
  > buffer can never guarantee a zero-gap renewal. No other code reads the value yet.
  > (`savvyeats/savvyeats/doctype/app_settings/app_settings.py:15-27`)

### How a renewal flows
1. Customer renews → a **Draft** (unpaid) Sales Order is created, with the current plan's
   meal selections copied onto the new delivery dates.
2. On payment it is submitted with status **Pending**.
3. Only one `Pending` renewal is allowed per customer at a time.
4. A daily job flips `Pending` → `Active` on its start date
   (`activate_scheduled_subscriptions`); the old subscription is completed once its
   end date passes.
5. Renewing is blocked while a subscription is **Paused**.

---

## 10. Subscriptions — Pause

- **Enable Pause Subscription Feature** *(default off)* — Lets customers pause and resume
  their subscription from the app. While off, the pause API returns an error.
- **Max Pause Count Per Subscription** *(default 1)* — How many times a single subscription
  may be paused. Once the limit is hit, further pause requests are rejected.
- **Enable Pause Notifications** *(default off)* — Sends an email to all **System Managers**
  whenever a subscription is paused, including the customer name and pause start/end dates.

Code: `savvyeats/api/subscription.py:135-...`

---

## 11. Subscriptions — Waiting List

Caps how many customers you accept during a launch/campaign period. Anyone beyond the cap is
flagged as being on the waiting list.

**The whole feature is skipped unless all four of these are set:** Waiting List is ON,
**From Date**, **To Date**, and a non-zero **Max Subscriptions Count**. Outside the
From/To date range the waiting list is ignored completely.

- **Waiting List** — Turns the capacity limit on.
- **From Date** / **To Date** — The campaign period the cap applies to.
- **Max Subscriptions Count** — How many customers you will accept in that period.
- **Users Subscribed** — A live counter, maintained automatically. It increases by 1 the
  first time a customer creates a **paid, active** subscription inside the date window
  (`savvyeats/api/payment.py:160-210`). A repeat order from the same customer in the same
  window does **not** increase it.

When `Users Subscribed >= Max Subscriptions Count`, any new user is flagged with
`on_waiting_list = 1` and the app shows them the waiting-list screen
(`savvyeats/api/user.py:337-364`).

> **Tip:** You can edit **Users Subscribed** manually to reset or adjust remaining capacity.

---

## Fields with no effect (as of today)

Keep these in mind when configuring — changing them does nothing:

| Field | Status |
|---|---|
| Meal Reminder Days Before Delivery | No code reads it. |
| Renewal Cutoff Days | Only validated against Buffer Days; never used in renewal logic. |

---

## Notes for developers

- App Settings is a **Single** DocType, so read values with
  `frappe.db.get_single_value("App Settings", "<fieldname>")` or
  `frappe.get_cached_doc("App Settings", "App Settings")`.
- The doc is cached; `validate()` calls `clear_cache()` and `on_update()` re-warms the cache,
  so saved changes take effect immediately.
- `get_app_settings` is `allow_guest=True` — the whole document, including the waiting-list
  counters, is readable by unauthenticated clients. Do not put anything secret in here.
- All notification jobs are scheduled **hourly** and self-gate on the configured hour, which
  is why the `Time` fields only respect the hour part.
