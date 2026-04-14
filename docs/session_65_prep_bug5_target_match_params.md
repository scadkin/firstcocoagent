# Session 65 prep — BUG 5 permanent fix in `_target_match_params`

**Status: scratch prep note, not a plan.** Written at end of Session 64 as a reading-only dump so Session 65's plan-mode session starts with code paths already mapped and open questions pre-identified. Format matches the S64 `docs/session_64_prep_prospect_loader_wiring.md` convention.

Read this, then read the cited files, then enter plan mode. Do NOT skip straight to code from this note alone.

## The gap being closed

**Today's band-aid:** `memory/public_district_email_blocklist.json` is a runtime guard with 10 exact domains (Detroit Public Schools, Pittsburgh Public Schools, OKC Public Schools, etc.) plus additional patterns. When a diocesan research job writes to Leads from Research, every extracted email domain is post-hoc checked against this list and matches are deleted. It works, but it's ugly and every new diocese with a shared-city public district requires a blocklist edit. Session 63 added Detroit to this list after a confirmed contamination incident on the Archdiocese of Detroit research job.

**The code-level hole:** `tools/research_engine.py::_target_match_params` returns a `(target_host, target_hint)` tuple used by **four** filter call sites (stage-1 page filter, stage-2 contact filter, and two L10 dedup checks). For non-playbook callers, the hint is `_district_name_hint(district_name)` — a substring token like `"chicago"` for "Archdiocese of Chicago Schools". When `_host_matches_target` runs, it returns True if the hint is a substring of the host. That means `chicago` matches **both** `archchicago.org` (target, correct) **and** `cps.edu` (Chicago Public Schools, WRONG).

The shared-city contamination is the common failure case: diocese and public district in the same city share enough of the name that the hint substring matches both.

**The existing partial fix:** `_target_match_params` already has a `_diocesan_playbook` branch (line 314) that forces strict base-domain-only matching (empty hint) **if** the caller set `diocesan_playbook=True` and `diocesan_domain=<known>` at `ResearchJob.__init__`. Diocesan jobs run through this path and DO get clean filtering.

**So why does contamination still happen?** Either (a) not all diocesan research jobs are being started with `diocesan_playbook=True` (a call-site issue in `agent/main.py`, not a research engine issue), or (b) there are non-diocesan cases where the same shared-city pattern burns us (e.g. an "Austin ISD" research job where the hint `austin` matches both `austinisd.org` and `austin.org`), or (c) both. The audit needs to establish which.

## Critical files and entry points

- `tools/research_engine.py:304-317` — `_target_match_params()`. The single source of truth. Diocesan playbook branch lives here.
- `tools/research_engine.py:217-244` — `_district_name_hint()`. Derives the short distinctive token. Strips known suffixes (`isd`, `public schools`, etc.) and `archdiocese of ` / `diocese of ` prefixes, then returns the remainder if ≥5 chars.
- `tools/research_engine.py:258-273` — `_host_matches_target()`. The substring-match rule that lets the hint contaminate.
- `tools/research_engine.py:275-281` — `_email_domain_matches_target()`. Delegates to `_host_matches_target` for email domains.
- `tools/research_engine.py:284-302` — `_base_domain()`. Returns the 2-part base domain (`archchicago.org` → `archchicago.org`). Assumes simple TLDs only.
- `tools/research_engine.py:199-206` — `ResearchJob.__init__` where `_diocesan_playbook` and `_diocesan_filter_base` are set from constructor args.
- Four call sites of `_target_match_params()`:
  - `tools/research_engine.py:658` — stage-1 page filter
  - `tools/research_engine.py:819` — stage-2 contact filter
  - `tools/research_engine.py:925` — L10 dedup check #1
  - `tools/research_engine.py:944` — L10 dedup check #2
- `agent/main.py` — grep for `diocesan_playbook=` to find all call sites that start a diocesan research job. Verify every diocesan code path passes the flag and a real `diocesan_domain`.
- `memory/public_district_email_blocklist.json` — current runtime band-aid, 10 exact domains + additional patterns in an 82-line file. Whatever the permanent fix is, this file's 10 entries are the minimum ground truth for a regression test.

## What makes the substring-match rule subtly wrong

1. **Hint length is 5+ chars but NOT exact-match.** `"chicago"` (7 chars) is in both `archchicago.org` and `cps.edu` — wait, no, it's not in `cps.edu`. Bad example. Real example: `"detroit"` is in both `archdiocesedetroit.org` and `detroitk12.org`. The substring test does not distinguish which side of the hyphen, prefix, or TLD the match lands on.
2. **Hint stripping loses discriminating tokens.** `"Archdiocese of Detroit"` → strip prefix → `"detroit"`. All distinguishing information is gone. The discriminator (`archdiocese` vs `k12`) is exactly what was stripped.
3. **Benefit-of-the-doubt rule compounds the problem.** `_is_school_host` + the non-matching-host default is "keep, don't drop" — so contaminated contacts slip through the stage-2 filter if they're on school-like domains, which public school districts obviously are.
4. **L10's cross-district check helps but isn't complete.** L10 does a separate cross-district email/host check, but it runs AFTER extraction, and the stage-1/stage-2 filters have already decided which pages/contacts to extract from. If the wrong domain's pages made it past stage 1, L10 might not catch every contact.

## Candidate fix approaches (do NOT commit to one before plan mode)

1. **Expand the playbook branch to cover all public districts with shared-city siblings.** Require every `ResearchJob` to specify a canonical `target_base_domain` up front (resolved by L4 or passed in by the caller), and drop the hint fallback entirely. Pros: exact matching, no substring. Cons: requires L4 domain discovery to succeed before any filter can run — breaks the current Phase A/B/C layering where filters run before L4 in some paths.
2. **Add a domain-disambiguation post-filter.** Keep the current filter rules but add a new pass that detects "multiple plausible base domains" and requires the target one to be explicitly chosen. Pros: minimal refactor. Cons: where does the disambiguation signal come from — a static list, a new Claude prompt, a heuristic?
3. **Require exact base-domain OR exact full-name match, no substring.** `_host_matches_target` becomes strict. The hint stops being a loose matcher and becomes a disambiguator that only resolves ties when base-domain match is ambiguous. Pros: simplest mental model. Cons: risks false negatives on legitimate subdomains or typo variants that the current substring-loose rule catches.
4. **Keep the substring rule but add a known-contaminant blocklist inside `_host_matches_target`.** Promote the JSON blocklist from runtime guard to code-level guard. Pros: minimal change to existing filter semantics. Cons: still requires blocklist maintenance for every new shared-city pair; moves the ugly into code instead of eliminating it.
5. **Hybrid: approach 1 for diocesan + approach 3 for non-diocesan.** The diocesan playbook already does approach 1 well. Apply approach 3 (exact-base-domain-only) to non-playbook code paths. Blocklist becomes a safety net, not the primary defense.

## Open questions for Session 65 plan mode

1. **How many non-diocesan research jobs actually hit the shared-city gap?** Run an audit — grep `Leads from Research` for any contact whose domain is in the blocklist. Count the false positive rate by strategy. If the answer is "only diocesan", approach 1 (expand playbook) is the clean fix. If non-diocesan is also affected, approach 3 or 5 is needed.
2. **Are all diocesan research calls currently passing `diocesan_playbook=True`?** Grep `agent/main.py` for `diocesan_playbook` and for every `research_queue.enqueue` call check whether the flag flows through. If ANY diocesan call is missing the flag, the first fix is making those call sites correct — a 5-minute code change, not a plan-mode scope.
3. **Does L4 always discover a usable `district_domain` before the filters run?** If yes, approach 1 is trivially generalizable. If no, approach 1 needs a bootstrap path for early-phase filtering.
4. **What's the regression test fixture?** BUG 5 needs at least one fixture that reproduces the Detroit Diocese → Detroit Public Schools contamination. Check `scripts/test_research_engine.py` (if it exists) and the `memory/bug_*` JSON files. The runtime blocklist's 10 entries define the minimum set of ground-truth contamination pairs.
5. **What breaks if the substring rule tightens?** The current rule is loose and permissive, which means some legitimate matches rely on that looseness. Tightening may introduce false negatives. Need to A/B against the existing diocesan research corpus before/after to measure regression.
6. **Is the blocklist the test oracle, or is it noise?** If approach 1 or 3 works cleanly, the blocklist becomes redundant and should be deleted. If it catches edge cases the code-level fix misses, it stays as a safety net. Decide during plan mode.
7. **Does the fix need a migration path for existing contaminated Leads from Research rows?** Probably yes — a one-time sweep script that deletes rows whose email domain is in the blocklist. Separate commit from the code fix.

## Risks that are NOT in the open-questions list

- **Rule 1**: research engine core logic change → plan-mode REQUIRED.
- **Rule 7**: the fix should ship with a kill switch — probably a `BUG5_STRICT_MATCHING` flag default ON, overridable for debug.
- **Rule 8**: likely 3 commits (code fix + regression test + migration sweep). Possibly 4 if the blocklist deletion is its own commit.
- **Production risk**: `_target_match_params` is on the hot path of every research job. A bug in the fix contaminates every subsequent run until reverted. Rollout needs a canary: run the new filter against a known-clean Archdiocese job first, confirm zero regression, THEN enable for bulk research.

## Recommended Session 65 opener

1. Enter plan mode.
2. Grep `agent/main.py` for all `diocesan_playbook=` call sites. Resolve open question #2 first — if any diocesan call is missing the flag, fix those call sites as a pre-plan quick win.
3. Run the blocklist audit — grep Leads from Research for contamination. Resolve open question #1.
4. Read `scripts/test_research_engine.py` (if it exists) or identify where a new regression fixture should live.
5. Write the plan — pressure-test hard per Rule 4. Ship.

## Files NOT read during this prep

- `agent/main.py` call sites for `research_queue.enqueue` (question 2)
- Any existing `scripts/test_research_engine.py` test file (question 4)
- Historical research job results to count contamination rate (question 1)
- The full `_host_matches_target` behavior with every fixture in `memory/public_district_email_blocklist.json` (question 5)

These are Session 65 reading targets, not blockers for this prep note.
