# SavvyEats — Codebase Audit & Issue Triage Report

**Project:** SavvyEats — Subscription Meal Delivery Application
**Platform:** Frappe / ERPNext (Python backend) + Vue.js 3 mobile frontend
**Audit Date:** 24 June 2026
**Prepared by:** Engineering Team
**Document Status:** For Client Review & Approval

---

## 1. Purpose of This Document

The client reported **10 issues**. This document is the result of a full code audit. For each issue it records:

- **Status** — whether the feature already exists and works, exists but is broken, or is not implemented.
- **Where it lives** in the code.
- **Root cause** (for broken items).
- **Proposed fix / implementation plan.**
- **Severity, effort estimate, and dependencies.**

No code has been changed yet. **Work begins only after the client approves this plan.**

---

## 2. How the System Is Built (Context)

A few facts that shape every issue below:

- There is **no separate "Subscription" record**. A subscription is a **submitted Sales Order** with extra fields (`subscription_status`, `pause_start_date`, `pause_end_date`, `start_date`, `end_date`, etc.).
- **Delivery automation** runs as a daily scheduled job that builds delivery records and Delivery Notes from active Sales Orders.
- **Payments** go through the **SkipCash** gateway.
- **Push notifications** use **Firebase (FCM)**; the token storage and sender are already in place.
- The **mobile app (Vue.js) is a separate codebase** and is **not part of this backend repository**. Issues that are purely in the mobile UI (notably Issue 8, and the on-screen part of Issues 2 and 7) require access to that frontend repo.

---

## 3. Issue-by-Issue Findings

### Issue 1A — Subscription Renewal Reminder (3 days before end)
- **Status:** ✅ Exists & Working (minor configuration note)
- **Findings:** A daily job already finds subscriptions ending soon, then sends a push notification + email to the customer and an email to managers. It de-duplicates so the same person isn't notified twice.
- **Note:** The "days before end" value currently defaults to **2 days**, not 3. This is a single setting change to make it 3 days as requested. We also recommend a small reliability improvement so that if the server misses a day, that day's customers are not skipped.
- **Severity:** Low · **Effort:** ~0.5 hour

### Issue 1B — Meal Selection Reminder Notification
- **Status:** ⚠️ Exists but Behaves Differently Than Requested
- **Findings:** A reminder job exists, but instead of checking *"has the customer selected meals for the next delivery day by the cutoff time?"*, it checks *"does the customer have at least N future days planned in total?"* As a result, a customer who has left **tomorrow** empty but planned later days will **not** be reminded.
- **Proposed fix:** Change the logic to specifically check the upcoming delivery day(s) and remind when those are unselected by the cutoff. (An unused "days before" setting already exists for this.)
- **Severity:** Medium · **Effort:** ~3 hours

### Issue 2 — Voucher / Coupon Code Not Applied Correctly
- **Status:** ❌ Exists but Broken (Critical)
- **Findings — three separate problems:**
  1. **The discount is never applied.** When a code is entered, it is stored on the order but **the total never changes**, so the customer is charged full price.
  2. **Validation is faulty.** Due to a logic error, expired or fully-used coupons can still be accepted in some cases.
  3. **Usage is never counted**, so a "use once" coupon can be reused indefinitely.
- **Proposed fix:** Properly calculate and apply the discount to the order total, fix the validation checks, and increment the coupon usage **at the moment of successful payment**. The discount must be recalculated on the server at payment time so the amount sent to SkipCash is correct and cannot be tampered with.
- **Severity:** Critical (affects revenue & customer trust) · **Effort:** ~6 hours

### Issue 3 — Daily Delivery Automation Review
- **Status:** ✅ Exists & Working (needs hardening)
- **Findings:** The daily job correctly builds the delivery list and Delivery Notes from active subscriptions for the target date, and avoids duplicates.
- **Weaknesses to address:**
  - **No error handling** — if one bad order fails, the whole day's batch can stop with no alert.
  - It depends entirely on the subscription status being correct, which **Issue 4 shows is currently wrong**.
- **Proposed fix:** Add per-order error handling + alerting, and align with the Issue 4 fix.
- **Severity:** Medium · **Effort:** ~3 hours · **Depends on:** Issue 4

### Issue 4 — Pause Feature: Clients Disappear from Delivery List Immediately ⚠️ MOST CRITICAL
- **Status:** ❌ Exists but Broken (Critical)
- **Root cause (confirmed):** When a customer requests a pause for a **future** date range, the system **immediately** marks the entire subscription as "Paused" right now — even if the pause is meant to start in two weeks. The delivery list only includes "Active" subscriptions, so the customer **vanishes from all deliveries immediately**, including the deliveries they should still receive **before** the pause begins.
- **Proposed fix:** Make the delivery list respect the **actual pause dates** rather than the all-or-nothing status. Deliveries before the pause window keep running; only the dates inside the pause window are skipped. (The per-date pause information is already being stored correctly — it simply isn't being honored by the delivery list.)
- **Severity:** Critical · **Effort:** ~5 hours · **Priority:** Fix first

### Issue 5 — Pause Notification Email Not Sent to Managers
- **Status:** ✅ Exists & Working (most likely a settings issue)
- **Findings:** The code **does** email managers when a subscription is paused. The most likely reason it isn't being received is that the **"Enable Pause Notifications" toggle is switched off**, or the intended recipients are a different group than "System Managers."
- **Proposed fix:** Verify the toggle is on and confirm the correct recipient group. Add visible error logging so silent failures can be diagnosed. Optionally make the recipient list a configurable setting.
- **Severity:** Low · **Effort:** ~1 hour

### Issue 6 — Subscription Created on Behalf of Client: Price Change + Wrong Payment Name
- **Status:** ❌ Exists but Broken (both parts)

**6A — Price changes during payment link generation**
- **Findings:** The payment amount is read **live at the moment the customer opens the payment link**, not locked when the order was created. If anything recalculates pricing in between (e.g. price-list/date changes), the amount can shift. A recent change added partial protection, but the price is still not firmly locked.
- **Proposed fix:** **Lock the price** when the order is created, store it, and have the payment gateway always use that locked amount. Re-verify it at payment confirmation.

**6B — Payment appears under staff name instead of the customer**
- **Root cause (confirmed):** The payment's payer name/email/phone are taken from the **staff member who created the order**, not from the **customer**. So payments made on behalf of clients show the staff's identity.
- **Proposed fix:** Source the payer details from the **customer** on the order (with a sensible fallback), so the payment correctly reflects the client.

- **Severity:** High · **Effort:** ~6 hours (both parts) · **Note:** Must be coordinated with the Issue 2 discount work.

### Issue 7 — Maximum Meal Selection with Extra-Charge Option
- **Status:** ❌ Not Implemented
- **Current state:** Each meal type has a configured limit (e.g. 1 breakfast, 2 meals, 2 snacks). There is **no mechanism** to allow extra items beyond the limit, and **no extra-charge concept** anywhere in the system.
- **Proposed implementation:**
  1. Add an "extra item price" setting per meal type.
  2. Allow selecting beyond the limit, charging the extra price for the additional items and tagging them so they don't affect the calorie count.
  3. The added charge flows into the order total automatically (and into the payment, subject to the Issue 6A price-lock).
  4. Return the surcharge to the app so it can show the message: *"Extra items will not affect your calorie count."*
  5. The on-screen selection limit + message changes live in the **mobile (Vue) repo**.
- **Severity:** Medium · **Effort:** ~8 hours backend + frontend work · **Depends on:** pricing design + Issue 6A

### Issue 8 — Remove "Main Health Goal" Question at Savvy Choice Step
- **Status:** ⚠️ Frontend Change — Not in This Repository
- **Findings:** The "health goal" question is rendered by the **mobile app (Vue)**, which is not in this backend codebase. The backend simply provides the list of health goals; it does not force the question.
- **Proposed fix:** In the mobile app's onboarding flow, hide the health-goal step when the selected plan is **Savvy Choice**. No backend change is required.
- **Severity:** Low · **Effort:** ~1–2 hours (frontend) · **Depends on:** access to the mobile app repo

### Issue 9 — Pre-Renewal Before Current Subscription Ends
- **Status:** ❌ Not Implemented
- **Findings:** Today there is **no supported way** to schedule a renewal that starts after the current subscription ends. A newly created subscription is forced "Active" immediately, there is **no rule preventing two active subscriptions** from overlapping, and there is **no job to auto-start a future-dated subscription** on its start date. This risks double deliveries.
- **Proposed design:**
  - Let a pre-renewal be created as **"Pending"** with a future start date (the status already exists but is unused).
  - Collect payment up front at renewal time.
  - Add a daily job that **activates** the pending subscription on its start date.
  - The delivery list ignores Pending subscriptions, so nothing delivers early.
- **Severity:** High · **Effort:** ~10 hours · **Note:** Best designed together with Issue 4 (both touch subscription status + delivery logic).

### Issue 10 — "My Way" Plan
- **Status:** ⏸️ Deferred — Blocked (awaiting UI/UX design from XY)
- **Findings:** No placeholder or partial work exists for this plan. Nothing to do until the design is provided.
- **Action:** Hold until design is ready.

---

## 4. Summary Table

| # | Issue | Status | Severity | Est. Effort | Suggested Priority |
|---|-------|--------|----------|-------------|--------------------|
| 4 | Pause bug — clients drop from delivery list | Broken | 🔴 Critical | 5h | **1** |
| 2 | Voucher / coupon not applied | Broken | 🔴 Critical | 6h | **2** |
| 6 | Behalf subscription — wrong payer name + price drift | Broken | 🟠 High | 6h | **3** |
| 9 | Pre-renewal support | Not implemented | 🟠 High | 10h | **4** |
| 1b | Meal selection reminder (wrong logic) | Partially working | 🟡 Medium | 3h | 5 |
| 7 | Extra meal charge beyond limit | Not implemented | 🟡 Medium | 8h + FE | 6 |
| 3 | Delivery automation hardening | Working | 🟡 Medium | 3h | 7 |
| 5 | Pause email to managers | Working (config) | 🟢 Low | 1h | 8 |
| 1a | Renewal reminder (default 2d, set to 3d) | Working | 🟢 Low | 0.5h | 9 |
| 8 | Remove health goal at Savvy Choice | Frontend repo | 🟢 Low | 1–2h | 10 |
| 10 | "My Way" plan | Deferred | — | — | — |

**Total estimated effort (Issues 1–9, excluding deferred #10 and frontend-only #8):** approximately **32–35 hours** of backend work, plus separate mobile-app work for Issues 7 and 8.

> Effort figures are engineering estimates for development only and exclude testing on the live environment, review cycles, and client UAT.

---

## 5. Recommended Delivery Plan (Phased)

**Phase 1 — Critical fixes (stop active customer harm):**
1. Issue 4 — Pause / delivery-list bug (fix first; no dependencies)
2. Issue 2 — Voucher discount + validation + usage count

**Phase 2 — Payment integrity & renewals:**
3. Issue 6 — Correct payer identity + lock the price
4. Issue 9 — Pre-renewal support (designed alongside Issue 4)

**Phase 3 — Enhancements & polish:**
5. Issue 1b — Correct meal-reminder logic
6. Issue 7 — Extra meal items with charge (backend + mobile)
7. Issue 3 — Delivery automation hardening

**Phase 4 — Quick wins / config:**
8. Issue 5 — Confirm pause-email setting
9. Issue 1a — Set reminder to 3 days

**Blocked / external:**
- Issue 8 — Mobile app change (needs frontend repo access)
- Issue 10 — "My Way" plan (needs design from XY)

---

## 6. What We Need From the Client to Start

1. **Approval** of this plan and the suggested priority order (or your preferred order).
2. **Decisions on a few details:**
   - Issue 2: where the discount value comes from (existing pricing rules vs. simple amount/percentage on the coupon).
   - Issue 5: confirm who should receive pause emails (System Managers vs. a specific Operations group).
   - Issue 7: the extra-item pricing model (per meal type vs. a flat charge).
3. **Access to the mobile app (Vue) repository** for Issues 7 and 8.
4. **The "My Way" design from XY** when ready (Issue 10).

---

## 7. Notable Technical Risks Flagged During Audit

These were found while auditing and are recommended for attention (some overlap with the issues above):

- **Payment amount is recalculated when the link is opened**, not locked at creation — addressed by Issue 6A.
- **Payment payer is the staff member, not the customer** — addressed by Issue 6B.
- **Subscription status handling is inconsistent** — the pause, renewal, and a never-used "Pending" status all need to be brought under one clear set of rules (Issues 4 & 9).
- **Several scheduled jobs lack error handling/alerting** — a single bad record can silently stop a batch (Issue 3).
- **An owner-reassignment action lacks a permission check** — should be restricted to authorized staff.
- **The voucher discount and the price-protection logic will conflict** if built separately — they must be designed together.
- **Push-notification tokens are never cleaned up** when they become invalid, which will waste sends over time.

---

*End of document — awaiting client approval to proceed.*
