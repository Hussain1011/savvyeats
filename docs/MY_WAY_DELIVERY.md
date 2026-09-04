# MY WAY — Backend Delivery Plan & Status

**App:** savvyeats (Frappe v15 / ERPNext)  ·  **Branch:** `usman_younas`  ·  **Owner:** Backend
**Status as of 4 Sep 2026:** Code complete on `usman_younas` · migrated and tested on the `savy` dev site · **2 items outstanding**
**Source spec:** `my-way-backend-tasks.md` (§ references below point at it)

---

## 1. Status at a glance

| | |
|---|---|
| Phases complete | **4 of 6** built — 1, 3, 4 and the code half of 5 |
| Codebase state | `ui_type` is `Standard\nRamadan\nMy Way`; `Component Category` exists; `grams` is on Sales Order Item, Delivery Note Item and Subscription Delivery Items |
| Verification | `bench --site savy run-tests --module savvyeats.tests.test_my_way` — **10 tests, all passing**, dish-path regressions included |
| Outstanding | **Print formats** (kitchen ticket / delivery label — they live in the site DB, not this repo) and the **component data import** (waiting on the client file) |
| Assumption taken | **§8 q1 answered as flat-per-meal**, built as Option A (a meal header row). If the client comes back "component-driven", §4.2 changes and Option C replaces it |
| Not built, by request | **Allergen filtering (BR-8).** Explicitly deferred — and note it was never "mirroring the dish path": no allergen filtering exists anywhere in the backend today |

### Phase board

| # | Phase | State | Where |
|---|---|---|---|
| 1 | Schema — `Component Category`, `Item.component_category`, `grams` ×3, `ui_type` option | **Done** | `savvyeats/custom/*.json`, `doctype/component_category/` |
| 2 | Data import — component catalogue | **Blocked on the client file** | helpers ready: `patches.setup_my_way`, `patches.backfill_component_per_gram` |
| 3 | Read endpoint — `get_plan_components` | **Done** | `api/items.py` |
| 4 | Write path — gated `add_items` + pricing | **Done (Option A)** | `api/order.py` — `_add_my_way_items` |
| 5 | Downstream — grams plumbing / print formats | **Plumbing done · print formats outstanding** | `subscription_delivery.py`, `api/subscription.py` |
| 6 | Enable the MY WAY Dish Plan | **Not started — config, needs sign-off** | `setup_my_way` then `enabled = 1` |

### What landed beyond the original spec

Four gaps the spec did not cover, each a silent failure in production:

| Gap | Why it mattered | Fix |
|---|---|---|
| `get_setup_data_v2` was **not** "no change" | `api/settings.py:78` only appends plans whose `ui_type == "Standard"` when App Settings is in Standard mode — a My Way plan would never reach the app | the branch now accepts `My Way` too |
| Renewals dropped the portions | `_copy_renewal_items` copies items field by field and had no `grams` — a renewed plate would arrive portionless | `grams` added to the copy |
| `step_grams` / `max_portion_grams` had no source | §4.1 returns them; §3 never created them | added as Item custom fields |
| The kitchen row is built by hand | `subscription_delivery.py` composes its row dict explicitly, so `grams` had to be listed — only `meal` came free | `grams` added to the dict |

---

## 2. Architecture

### 2.1 The one-line summary

MY WAY reuses the entire existing dish pipeline. It adds **one axis to the item model** (a component category), **one unit to the order line** (grams), and **one read endpoint**. Everything downstream — meal grouping, per-gram nutrition, allergens, delivery lines, kitchen tickets — already exists and carries through untouched.

### 2.2 Reuse map — verified against the repo

| Need | Already exists | Verified at |
|---|---|---|
| Components as a kind of item | `Item.item_category` = `Ingredient` | `savvyeats/savvyeats/custom/item.json` |
| Base portion in grams | `Item.serving_size` (Float) | same file ✔ |
| Per-gram nutrition | `Item Nutrients.per_gram` (Float) | `doctype/item_nutrients/item_nutrients.json:44` ✔ |
| Import tooling for the above | `data_import/items.py` already sets `per_gram` | `data_import/items.py:228,299` ✔ |
| Allergens / plan scoping on items | `Item.allergens`, `Item.dish_plans` | `custom/item.json` ✔ |
| Meal as a grouping key, order → kitchen | `Sales Order Item.meal` → `Delivery Note Item.meal` → `Subscription Delivery Items.meal` | copied by `subscription_delivery.py:139` ✔ |
| Per-meal pricing | `Dish Plan Meals.per_day_price` | `doctype/dish_plan_meals` ✔ |
| Per-plan UI branching | `Dish Plan.ui_type` Select | `doctype/dish_plan/dish_plan.json:195` ✔ |

**Consequence:** BR-4 ("a built meal stays one meal") needs **no schema work**. The grouping key already reaches the kitchen. What's missing is the *rendering*, not the plumbing (§5).

### 2.3 What is genuinely new

```
  NEW DOCTYPE                    NEW FIELDS
  ┌─────────────────────┐        Item.component_category   → Link, nullable
  │ Component Category  │◄───────Sales Order Item.grams    → Float, nullable
  │  category_name      │        Subscription Delivery Items.grams
  │  sorting_order      │        Delivery Note Item.grams
  │  required  (def 1)  │
  │  enabled   (def 1)  │        NEW SELECT OPTION
  └─────────────────────┘        Dish Plan.ui_type += "My Way"
```

Four items at launch (Protein / Carbs / Fats / Fibers) but **nothing may hardcode four** — the client may ask for three or six.

### 2.4 Read path — why a new endpoint, not an extension

`get_plan_items` (`api/items.py:10`) is built entirely around **Dish Schedule**: it walks `order.delivery_dates`, finds a Published schedule per date, and reads `schedule_json[dish_plan][meal]`.

MY WAY has no per-date schedule (BR-6) — its catalogue is flat and identical every day. Forcing it through the dated path means fabricating a schedule row per delivery date for a list that never changes.

```
  DISH PLAN (today)                    MY WAY (new)
  order.delivery_dates                 order
        │                                    │
        ▼                                    ▼
  Dish Schedule (per date)             Item where
        │ schedule_json                   item_category = Ingredient
        ▼                                  AND component_category set
  {plan: {meal: [items]}}                  AND MY WAY in dish_plans
        │                                    │
        ▼                                    ▼
  get_plan_items  ── UNTOUCHED         get_plan_components  ── NEW
```

Separate endpoint = the dish path is not modified at all. That is the backward-compatibility win.

### 2.5 Write path — the row shape (this is the core design decision)

A dish meal is **one row**. A MY WAY meal is **N rows sharing one `meal`**. Everything in §4 of the spec follows from that single difference.

```
  DISH PLAN, 1 meal                     MY WAY, 1 meal (Option A)
  ────────────────────                  ─────────────────────────
  SO Item                               SO Item  MY WAY Meal   qty 1  rate 45  meal=Meal 1  ← header, priced
    item = Grilled Chicken Bowl           SO Item  Chicken     qty 1  rate 0   grams 120
    qty 1  rate 45  meal = Meal 1         SO Item  Rice        qty 1  rate 0   grams 150
                                          SO Item  Olive Oil   qty 1  rate 0   grams 10
                                          SO Item  Broccoli    qty 1  rate 0   grams 80
  grand_total = 45                      grand_total = 45   (not 4 × 45)
```

`api/order.py:437` assigns the rate to **every** row carrying a meal. Correct for dishes, catastrophic here — see Trap 0. The MY WAY build sidesteps it entirely: `_add_my_way_items` never runs that assignment, and `test_plate_is_priced_once_not_once_per_component` asserts the total directly.

---

## 3. The pricing decision — assumed, built, still worth confirming

### §8 q1 — Is MY WAY priced flat per meal, or driven by component prices?

**Built as flat-per-meal (Option A)** so the rest of the work could land. It still cannot be *inferred* from the design — the meals counter screen says *"Your plan is priced per meal"* (flat), while the macro bar carries a live `Plan total` line that only makes sense if the total moves as components are chosen — so the client should still confirm it. A "component-driven" answer means replacing Option A with Option C, which is a smaller change than it sounds: it deletes the header row and the pricing-plan lookup rather than adding anything.

| If the answer is | Then | Effect on the build |
|---|---|---|
| **Flat per meal** | **Option A** — one `MY WAY Meal` header row per (date, meal) at `per_day_price`; component rows at rate 0 | Adds one item + one row per meal; pricing correct **by structure** |
| **Component-driven** | **Option C** — `row.rate = item_price × (grams / serving_size)`, no `Dish Plan Pricing` at all | **Deletes work.** Trap 0 disappears; the combinatorial pricing-plan problem disappears |
| *(rejected)* | Option B — split `per_day_price` across components | Rates read as arbitrary (45 ÷ 4 = 11.25); rounding must be reconciled every edit |

**Recommendation:** if the answer is flat → **A**; if component-driven → **C**. **Never B** — under B every component's rate is a function of how many components that meal happens to have, and that count varies at runtime.

**Two consequences to put in front of the client with the question:**

1. **Unbounded pricing plans.** `add_items` matches a `Dish Plan Pricing` by the *exact set* of selected meals (`api/order.py:337-365`). With "no maximum meals per day" (BR-3) that is an unbounded number of pricing documents, and a missing one silently falls through to `default_pricing_plan` at a wrong price. Under A we skip that lookup entirely and use `default_pricing_plan`; under C there is no lookup at all.
2. **A 2-component snack costs the same as a 4-component main meal**, because price attaches to the meal *slot* (`Dish Plan Meals.per_day_price` per `Meal N`), not to its contents. Under Option A the only fix is configuring `Meal 3` cheaper at setup. If the client expects "fewer components = cheaper", flat pricing is the wrong model and Option C is the answer.

**Owner:** product / client · **Status:** assumed flat, built, tested · **Cost of the answer flipping:** rework of `_add_my_way_items` and the pricing setup — contained to `api/order.py` and `patches.py`, with the test module to catch the regressions.

---

## 4. Trap register — all four closed

All four are **correct behaviour for dish plans** and wrong for MY WAY. Rather than thread gates through the shared loop, the dish build was lifted verbatim into `_add_dish_plan_items` and MY WAY got its own `_add_my_way_items` beside it, dispatched on `is_my_way_plan(order.dish_plan)`. The dish code is unchanged text, which is the easiest form of "nothing broke" to review.

*Line numbers below are the pre-refactor ones, kept so the trap can be traced back to the code that motivated it.*

### 🔴 Trap 0 — the per-row rate overcharges by the component count
`api/order.py:437`
```python
if row.meal:
    row.rate = pricing_plan_meals.get(row.meal)
    row.price_list_rate = row.rate
```
`per_day_price` prices **one meal**. A MY WAY meal is 4 rows in that meal → a QR 45 plate bills **QR 180**. Across 3 meals × 20 days the order is **4× its intended value**.
**Fixed:** Option A. One `MY WAY Meal` header row per `(delivery_date, meal)` at `per_day_price`; every component rides at rate 0. Asserted by `test_plate_is_priced_once_not_once_per_component`.
**Severity:** highest — 4× overcharge is the *default* failure if nobody looks.

### 🟠 Trap 1 — every component after the first is flagged `is_extra`
`api/order.py:444-448` — a dish meal has `max_qty = 1`; components 2–4 in the same meal trip the counter, get billed separately, **and are excluded from the calorie count** — the exact number the feature exists to show.
**Fixed:** both belts. `setup_my_way` sets `max_qty` to the enabled category count, **and** `_add_my_way_items` never runs the `is_extra` branch, so a future 5th category cannot silently reintroduce it.

### 🟠 Trap 2 — filler rows pad every snack
`api/order.py:452-476` appends `"Item Not Selected"` rows up to `min_qty`/`max_qty`. A snack legitimately has fewer components (BR-5), so every snack gets phantom lines.
**Fixed:** `_add_my_way_items` has no filler pass. The app blocks checkout until every day is complete.

### 🟡 Trap 3 — grams are dropped
The loop never reads a `grams` key, and `qty` cannot carry it: `api/order.py:421` int-coerces and floors `qty` at 1, then drives `extra_portion` off `row.qty > 1`. A 50 g portion arrives as fifty portions.
**Fixed:** `row.grams = flt(v.get("grams"))` with `row.qty = 1` regardless of portion. Note `grams` lands as `0`, not `NULL` — Frappe Float columns are `not null default 0`, so print formats must test `if grams`, not `if grams is not None`.

### ⚫ Silent-drop hazard (not a code bug — a config one)
`api/order.py:415`: `if meal and meal not in meals_list: continue`. If the `Meal 1…N` records aren't present as `Dish Plan Meals` rows, **every MY WAY item is silently dropped** and the customer gets an empty order. `setup_my_way` creates the `Meal N` records *and* their `Dish Plan Meals` rows together, so the two cannot drift apart. Seeding 12 is a starting point; running out is a config task, not a code change.

---

## 5. Downstream — data-ready, rendering not

`meal` already flowed order → delivery note → subscription delivery. `grams` did **not** — `subscription_delivery.py` composes its row dict by hand and `_copy_renewal_items` copies field by field, so both had to be taught the new field. **That plumbing is now done.** What's outstanding is presentation:

**⚠️ These print formats are not in this repo.** They are `Print Format` records in the site database (see `savvyeats_settings.invoice_print_format`), so this is site data work, not a deploy — confirm which of the three even exist before estimating it.

- [ ] Group rows by `meal`, in `Meal 1 … Meal N` order, components listed underneath — kitchen ticket, delivery label, order history. Ungrouped, a 3-meal day prints as **12 loose lines** (BR-4 forbids exactly this).
- [ ] **Do not enable `group_same_items`** — it merges by `item_code`, so the same component taken in two meals collapses and the meal distinction is lost.
- [ ] Print `grams`, not `qty` — `qty` is always 1 and tells the kitchen nothing.
- [ ] Under Option A: show the `MY WAY Meal` header row on the **kitchen ticket** as the meal heading, suppress it on the **customer-facing** label and menu.

**⚠️ Volume, needs measuring before go-live.** A 3-meal × 20-day dish plan is ~60 Sales Order Items today; the same plan in MY WAY is **~240** (6 meals → ~480). `add_items` clears and rebuilds the whole child table before a single `save()`. **Action: time a 7-day × 6-meal order.**

---

## 6. Data import — Phase 2

Client file supplies: name, weight, cost, selling price, calories, macros, pictures.

| Client column | Lands on |
|---|---|
| name | `Item.item_name` / `item_code` |
| weight | `Item.serving_size` (grams) |
| selling price | Item Price, Selling Price List |
| cost | `Item.valuation_rate` (kitchen-side, not exposed) |
| calories, macros | `Item Nutrients` — `nutrient`, `uom`, `value` **and `per_gram`** |
| pictures | `Item.image` |
| *(assigned)* | `item_category = "Ingredient"`, `component_category`, `dish_plans` includes MY WAY |

**Two hard requirements:**
1. **`per_gram` is not optional.** The app scales every live macro by grams. Backfill `per_gram = value / serving_size` at import where blank — otherwise the customer sees **0 kcal**.
2. **Confirm the canonical `Nutrient` names** for calories / protein / carbs / fat and send them to the app team. The app matches by name and unit (calories = `uom == "Kilocalorie"` today). A mismatch shows **0 kcal with no error** — the single most likely silent failure in this feature.

**Also to confirm before Phase 3:** `get_plan_items` strips a suffix from item names (`item_name.rsplit("-", 1)[0]`, `api/items.py:35`). Do **not** copy that into `get_plan_components` unless component names carry the same convention.

---

## 7. Backward-compatibility contract (the acceptance bar)

Everything is additive or gated. After this work:

- [ ] No existing field changes type, name or meaning. Every new field is new and nullable.
- [ ] No existing endpoint changes shape — `get_plan_items`, `get_setup_data_v2`, `update_draft_order`, `get_draft_order` untouched.
- [ ] `add_items` behaves **identically** for any order whose plan is not `ui_type == "My Way"`. Gate on the plan's ui_type — **never** on the presence of a `grams` key.
- [ ] A Select option is *added*, never renamed or reordered.
- [ ] Older app builds keep working: they never call `get_plan_components`, never send `grams`, never see the plan unless it's enabled.
- [ ] `grams` renders **blank** on existing dish lines, not `0 g`.

**Kill switch:** setting the MY WAY Dish Plan `enabled = 0` removes the feature from every app build immediately, with no deploy. **Verify this works before go-live** — it is the rollback plan.

---

## 8. Acceptance checklist

Automated as `savvyeats/tests/test_my_way.py` — `bench --site <site> run-tests --module savvyeats.tests.test_my_way`.
Ten tests, all passing on `savy` as of 4 Sep. Boxes left unticked are the ones a test cannot reach.

**MY WAY works**
- [x] `get_plan_components` returns categories in sort order with `serving_size`, `price` and nutrients incl. `per_gram` (derived when the import left it blank)
- [ ] ~~Allergen-excluded components do not appear~~ — **deferred by request**
- [x] A 3-category **and** a 4-category config both come back correctly (nothing assumes four)
- [x] Components carry `meal`, `grams`, `qty = 1`, `is_extra = 0`
- [x] No `"Item Not Selected"` rows on a MY WAY order
- [x] A 2-of-4-category snack saves 2 rows, unpadded
- [x] **`grand_total` = plates × per-day price — not multiplied by component count.** Trap 0 makes 4× the default failure, so this is asserted directly
- [x] One component per category per meal, last write wins (BR-1)
- [ ] Grams reach Subscription Delivery Item, Delivery Note line and kitchen ticket — *plumbing is in; needs a real delivery run to confirm end to end*
- [ ] Kitchen ticket groups by `meal` — 3 meals, not 12 loose lines — *print formats are site data, see §5*

**Nothing else broke**
- [x] A Standard-plan order still prices every meal row at `per_day_price`
- [x] Dish-plan `is_extra` still fires past `max_qty`
- [x] Filler rows still appear for unselected dish-plan dates
- [x] `grams` is `0` on every dish line
- [ ] Diff a **real** Standard and Ramadan order before/after — the test covers the shape, not one of your production orders
- [ ] `get_plan_items` response unchanged — untouched by this work, but worth one diff
- [ ] Disabling the plan removes it from the app with no deploy

---

## 9. Error contract

- [ ] `get_plan_components` reuses `validate_sales_order` (`api/order.py:8`) — same not-found / access-denied responses as every other order-scoped endpoint
- [ ] Plan not MY WAY → return an **empty `categories` list**, not an error; the app shows its empty state
- [ ] Distinct, stable `_server_messages` for: **plan-not-my-way**, **no-components-configured**, **allergens-exclude-everything-in-a-required-category**. The last is a real dead end (a customer allergic to every protein cannot complete a meal) and the app must distinguish it from an empty response

---

## 10. Response contract — the Flutter parser is name-sensitive

```jsonc
{
  "categories": [{
    "code": "Protein",        // Component Category docname
    "label": "Protein",       // falls back to code if absent
    "sort_order": 1,
    "required": 1,            // ABSENT MEANS REQUIRED
    "items": [{
      "item_code": "CHICKEN-BREAST",
      "item_name": "Chicken Breast",
      "serving_size": 50,     // grams, must be > 0
      "step_grams": 25,       // optional, falls back to serving_size
      "max_portion_grams": 300, // optional, null = no cap
      "price": 6.50,
      "doc": { /* Item doc incl. image, description, nutrients[] with per_gram */ }
    }]
  }]
}
```

| Key | Type | Note |
|---|---|---|
| `My Way` | Select option | **Exactly two words, one space.** Flutter reads `PlanUiTypeValues.myWay` |
| `categories` | List | May also be a bare top-level array; the app accepts either |
| `per_gram` | Float | **Required.** Drives every live macro number |
| `grams` | Float | On Sales Order Item + `add_items` request. Nullable. **Never `qty`** |
| `category` | String | Sent by the app on each item; safe to ignore if derived from the Item |

---

## 11. Next actions

| Action | Owner | Blocks |
|---|---|---|
| **Confirm §8 q1 was right to assume flat-per-meal.** Built as Option A; a "component-driven" answer means swapping to Option C | Product / client | Nothing today — but it is rework if the answer flips |
| Confirm canonical `Nutrient` names + units, send to app team | Backend + data | Phase 2, and silent 0-kcal failures |
| Build the kitchen ticket / delivery label print formats — group by `meal`, print `grams` not `qty`, keep `group_same_items` off, hide the `MY WAY Meal` row on customer-facing output | Backend | Go-live |
| Import the component catalogue, then run `patches.backfill_component_per_gram` | Backend + data | Phase 6 |
| Confirm the item-name suffix convention in the component file | Backend + data | Phase 3 sign-off |
| Time a 7-day × 6-meal `add_items` call (≈480 component rows + 42 header rows in one `save()`) | Backend | Go-live |
| Confirm with client that "fewer components" ≠ "cheaper" | Product | Pricing model sanity |
| Decide whether allergen filtering ships — it does **not** exist for dishes either, so it is new work either way | Product | Deferred by request |
| Run `patches.setup_my_way(<plan>, <price>)`, verify, then `enabled = 1` | Backend | Phase 6 |
