# Session 59 — Diocesan Sequence Doc Review

**Date:** 2026-04-13
**Scope:** The 7 diocesan sequence docs at `Status=draft` in the Prospecting Queue — all were drafted through the generic cold fallback in `_on_prospect_research_complete` because the handler had no `private_school_network` branch. Every one violated the approved tone rules (`memory/feedback_bond_trigger_outreach_tone.md`, `feedback_sequence_copy_rules.md`, `feedback_sequence_iteration_learnings.md`).

**Fix:** Session 59 Section 4 shipped the diocesan branch in `agent/main.py:_on_prospect_research_complete` (commit `042f146`). Session 59 Section 5 regenerated 6 of the 7 docs through the new branch. LA was abandoned.

---

## Original docs — violation counts (before regen)

| Diocese | Banned phrases | Em dashes | AI in subjects | Tone match |
|---|---|---|---|---|
| Archdiocese of Chicago | 0 | 60 | 2 | 0/9 |
| Archdiocese of Boston | 1 ("I'd love to") | 52 | 1 | 0/9 |
| Archdiocese of Philadelphia | 0 | 64 | 2 | 0/9 |
| Archdiocese of Cincinnati | 1 ("quick call") | 66 | 1 | 0/9 |
| Diocese of Cleveland | 1 ("I'd love to") | 56 | 1 | 0/9 |
| Archdiocese of Detroit | 0 | 52 | 2 | 0/9 |
| Archdiocese of Los Angeles | 1 ("quick call") | 73 | 3 | 0/9 |

Every doc had 50+ em dashes, AI leading in subject lines, and zero matches on diocesan framing elements (no Bobby Duke MS case, no "throw our hat in" language, no one-pager CTA, no safe-AI framing). Confirmed none were sendable as-is.

---

## Regenerated docs (6 of 7)

All regeneration runs used the new `private_school_network` diocesan branch. Target role = "Superintendent of Catholic Schools", campaign = "Diocesan Central Office Outreach", 5 steps with graduated spacing, full inline tone rules.

| Diocese | Step 1 words | Em dashes | Banned | Verdict | New Doc |
|---|---|---|---|---|---|
| **Archdiocese of Philadelphia Schools** | 63 ✓ | 0 ✓ | 0 ✓ | **GOLD — sendable** | [Doc](https://docs.google.com/document/d/1WnJq-BZBRCCvLQt9d7hKoxfAoB7YiTvaFrBKhj8gRTs/edit) |
| **Diocese of Cleveland Schools** | 69 ✓ | 0 ✓ | 0 ✓ | **CLEAN — sendable (school-level)** | [Doc](https://docs.google.com/document/d/1_I8xjBdlGpJRapR9prhDTbuFdLvTL4lXykI2TPp1E1s/edit) |
| **Archdiocese of Boston Catholic Schools** | 56 ✓ | 0 ✓ | 0 ✓ | **CLEAN — sendable (school-level)** | [Doc](https://docs.google.com/document/d/1MfS5A24kI7KDSXXJYaNiWkXz_Vj4ZFfvYup6atP8S9M/edit) |
| **Archdiocese of Chicago Schools** | 57 ✓ | 0 ✓ | 0 ✓ | **CLEAN — sendable** | [Doc](https://docs.google.com/document/d/1RgYtjF2hchImk4rSuQAnbMFa8JTQmv1FTSHkrAryDuI/edit) |
| **Archdiocese of Cincinnati Schools** | 98 ⚠️ | 0 ✓ | 0 ✓ | **MOSTLY CLEAN — Step 1 slightly long** | [Doc](https://docs.google.com/document/d/13b4XBA1umbHDR9farby1pMxZN32nRSD8LfLwkwqL6qw/edit) |
| **Archdiocese of Detroit Schools** | 79 ✓ | 0 ✓ | 0 ✓ | **CLEAN — sendable** | [Doc](https://docs.google.com/document/d/1jppQ5tXJHMrPDLfD2i03xjKhuYLHjBddQqnzbv8jSg4/edit) |

The Prospecting Queue `Sequence Doc URL` column has been updated for all 6 regenerated rows — `/prospect` will show the new URLs automatically.

---

## LA — abandoned

**Archdiocese of Los Angeles Schools:** not regenerated.

**Why:** Of 18 total leads found by research, only 2 had verified emails, and both were from `hssala.org` (Holy Spirit Parish School — a single individual parochial high school). Zero leads hit the archdiocesan central office. Regenerating the sequence doesn't solve the underlying problem: there's nothing to send the sequence to at the diocesan level.

**Recommendation:** Leave the existing broken doc in place as a placeholder. Revisit only when research actually cracks the LA archdiocesan central office (`lacatholicschools.org` is the likely seed URL). Session 60 candidate — hand-seed research with `lacatholicschools.org` + re-run, then regenerate through the diocesan branch if yield improves.

The original broken LA doc: [https://docs.google.com/document/d/1i82XxgowNe9UUNH_ug1Tgt7iMQN5bfpKvOvfcolDQIk/edit](https://docs.google.com/document/d/1i82XxgowNe9UUNH_ug1Tgt7iMQN5bfpKvOvfcolDQIk/edit)

---

## What to watch for in review

**Minor iteration targets (not blockers):**
1. **Cincinnati Step 1 word count** — 98 words vs 80 target. Sequence builder periodically overshoots despite the explicit limit. If Steven flags it, iterate by adding stronger length enforcement or manual trim. One edit, not a regen.
2. **Step 1 subject line repetition across the 6** — regen tends to produce similar "CS across your schools" style subjects. If Steven wants more variety, the generator can be re-invoked with specific subject-line alternatives requested.

**Quality indicators to look for in each regen (per Steven's iteration learnings):**
- Does it open with a pattern ("Most diocesan offices I talk with...") rather than flattery?
- Does it lead with engagement (game-based curriculum) NOT with AI?
- Is Bobby Duke MS the ONLY case study named?
- Does it use the "throw our hat in early" framing in at least one step?
- Is the breakup step under 60 words?
- Are all 3 CTAs represented (one-pager, free trial licenses, case study data)?
- Are merge fields used: `{{first_name}}`, `{{company}}`, `{{state}}`?
- No "I'd love to", "quick call", "I hope this email finds you well", "I'm Steven", "just checking in", "circling back", "touch base"?

---

## How to send these

All 6 regenerated docs are drafts. Steven's approval workflow:
1. Open the doc, read end to end.
2. If approved: copy each step into Outreach.io (Session 59 shipped no API-side creation — diocesan sequences still need manual Outreach setup).
3. If iteration needed: reply in chat, I'll regen with specific edit notes baked into the extra_context. Each regen is ~30 sec + ~$0.05.

**Tag prospect rows in Outreach as `diocesan_central_office_2026` for filtering.** (Per `memory/feedback_sequence_copy_rules.md` tagging convention.)

---

## Pipeline impact

- **Before Session 59:** 7 sequence docs, 0 sendable. Every future diocesan approval produced another broken draft.
- **After Session 59:** 6 sequence docs sendable (5 fully clean, 1 with minor Step 1 length nit), 1 (LA) pending research restart. Future diocesan approvals ship the correct tone automatically because the branch is live in `agent/main.py`.

The unlock: Philadelphia has 20 verified central-office contacts on `@archphila.org` (Superintendent, Asst Supt Curriculum, Data Coordinator) and Cincinnati has 23 on `@catholicaoc.org`. These are the two most sendable campaigns in the entire Session 58 yield. They can go live in Outreach this week.
