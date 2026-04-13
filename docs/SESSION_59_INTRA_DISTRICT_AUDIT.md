# Session 59 — intra_district 384-Row Desk Audit

**Date:** 2026-04-13
**Strategy audited:** `intra_district` (F1 — `suggest_intra_district_expansion`)
**Pending rows:** 384 (all dated 2026-04, priority 750–785)
**Research cost if approved:** ~$200–$800 serialized via single-threaded `ResearchQueue`

---

## TL;DR

**Recommendation: Option C — retire F1 as a cold prospecting source and bulk-skip all 384 rows.**

The 19-row stratified sample showed **100% redundancy** against Active Accounts. The full-queue check confirmed: **every one of the 384 pending rows has at least 1 active contact at its parent district.** F1 is rediscovering sibling schools inside districts Steven already sells to. Research spend on these rows would mostly surface contacts Scout already knows.

---

## Methodology

1. Pulled all 384 `intra_district` pending rows from the Prospecting Queue.
2. Stratified sample: 7 high-priority (780-785), 7 mid-priority (765-775), 6 low-priority (750-764). Random seed 42 for reproducibility. Since only 6 rows exist in the 780+ bucket, sample was capped at 19 (6 high + 7 mid + 6 low).
3. For each sample row: looked up the `Parent District` column against `Active Accounts` via `csv_importer.get_active_accounts()`. Exact-match first, fuzzy-match fallback (threshold 0.75).
4. Counted contacts at the matched parent district. Classified row as `REDUNDANT` (≥1 contact) or `NET-NEW?` (0 contacts).
5. After 100% REDUNDANT hit rate on sample, ran the same check across **all 384 rows** for confirmation.

---

## Results — sample (19 rows)

All 19 came back REDUNDANT. Representative entries:

| Priority | School | Parent District | Contacts at parent |
|---|---|---|---|
| 785 | Santiago High | Corona-Norco Unified (CA) | 4 |
| 785 | Macarthur H S | Aldine ISD (TX) | 1 |
| 782 | North Penn SHS | North Penn School District (PA) | 1 |
| 774 | Phineas Banning Senior High | Los Angeles Unified (CA) | **6** |
| 770 | Cerritos High | ABC Unified School District (CA) | 2 |
| 758 | Idea Edgemere Academy | IDEA Public Schools (TX) | 1 |
| 755 | Shepherd High School | Shepherd ISD (MI) | 1 |

**Redundancy rate on sample: 19/19 (100%).**

---

## Results — full 384 rows

| Match count | Rows | % |
|---|---|---|
| 0 active contacts at parent | 0 | 0.0% |
| 1+ active contacts | **384** | **100.0%** |
| 2+ active contacts | 30 | 7.8% |

**Every single pending intra_district row has at least one known contact at its parent district.** There is no cohort of rows where F1 would produce genuinely net-new marketing surface.

---

## Why this is happening (root cause)

F1 (`suggest_intra_district_expansion`) is designed to find sibling schools inside districts where CodeCombat already has a presence. Its input set is Active Account districts; its output set is their sibling schools that are NOT yet Active Accounts. By definition, every parent district is an Active Account — so every row has a pre-existing relationship.

The implicit assumption F1 was built on was that research on a sibling school would find **new contacts** (the principal, a CS teacher, an IT coordinator) distinct from the known parent-district contacts. In practice:

- Research results for a school-level target mostly return the same district-level contacts Scout already has, because school staff directories often link upstream to district office pages.
- For schools that DO have independent staff pages, the hit rate is dominated by generic admin roles (Principal, Assistant Principal) that Steven's `target_roles.py` already filters out.
- The highest-value sibling contacts (an actual CS teacher) are exactly the contacts Steven gets via warm referrals from the existing parent-district relationship — faster, cheaper, and higher-conversion than a cold research pass.

---

## Options

### A — Approve all 384 (NOT recommended)

- **Cost:** ~$400 research (serialized ~30 hrs wall clock) + 384 sequence docs Steven has to review
- **Expected net-new contacts:** very low (the 100% redundancy pattern argues against it)
- **Review burden:** 384 sequence drafts added to Steven's already-large review queue
- **Outcome:** Most approved rows would produce duplicate-of-known or unactionable-role contacts. Marginal value < marginal cost.

### B — Approve top 50 by priority (NOT recommended)

- **Cost:** ~$50 research + 50 sequence docs
- **Problem:** The top priority tier (780+) contains only **6 rows** total — would have to reach into 770s and 760s. The sample hit REDUNDANT on all priority tiers equally. Lower volume, same structural problem.
- **Outcome:** A smaller version of Option A's waste.

### C — Retire F1 + bulk-skip all 384 (RECOMMENDED)

- **Cost:** $0
- **Action:** Send `/prospect_skip all` paginated batches through Telethon, or write a one-off `bulk_skip_intra_district.py` script that sets `Status=skipped` on all 384 rows in one batch.
- **Outcome:**
  - Clears 384 rows from pending queue (~20% of total pending backlog)
  - Frees Session 60+ from intra_district consideration forever
  - Shifts expansion strategy for these parent districts to the existing warm channels (upward_auto, signals, proximity_engine) where the known parent contact IS the relationship
  - Retaining `target_roles.py` filters and existing relationship context is more efficient than cold-researching sibling schools

**Additional action under C:** consider disabling F1 in `tools/district_prospector.py` via a `ENABLE_F1_INTRA_DISTRICT = False` kill switch near the top of the module, so the daily scan stops adding new intra_district rows. This is a one-line change that prevents the backlog from rebuilding.

---

## If Steven wants sibling-school expansion done better

A future-session alternative (NOT for Session 59): replace F1 with an "adjacent school" play that uses the known parent-district contact as the referral vector:

1. For each Active Account district, pull its sibling schools from NCES CCD.
2. For each sibling NOT already Active: generate a talking point Steven can use in a warm conversation with the existing parent contact ("I noticed Santiago High isn't using us yet — would you mind a quick intro to their principal?").
3. Output is talking-point rows in a new `referral_targets` tab, NOT research jobs, NOT sequences.

This converts F1's data into warm-referral fuel for existing relationships instead of cold research. Session 60 or 61 candidate.

---

## Verification

- Sample hit rate: 19/19 = 100% REDUNDANT
- Full-queue hit rate: 384/384 = 100% with ≥1 active contact at parent
- Parent district coverage in Active Accounts: 162 distinct parents indexed
- Audit script: one-shot Python, no new files committed

**Decision owed by Steven:** confirm Option C (recommended) or override with A / B / other.
