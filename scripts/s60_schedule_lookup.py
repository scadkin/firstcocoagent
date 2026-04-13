"""Session 60 schedule ID lookup — fetch seq 1999's live schedule and enumerate all distinct schedule IDs across the sequence library."""
import os
import sys
from collections import Counter, defaultdict

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

import tools.outreach_client as oc
oc._load_persisted_tokens()
if not oc._access_token and not oc._refresh_token:
    print("ERROR: no Outreach tokens loaded from /tmp or GitHub.", file=sys.stderr)
    sys.exit(1)

# 1. Direct fetch of seq 1999 with schedule sideload
print("=" * 70)
print("FETCH 1: /sequences/1999?include=schedule")
print("=" * 70)
raw = oc._api_get("/sequences/1999")
data = raw.get("data", {})
attrs = data.get("attributes", {})
rels = data.get("relationships", {})
sched_rel = rels.get("schedule", {}).get("data")
included = raw.get("included", [])

print(f"Sequence name: {attrs.get('name', '?')}")
print(f"Sequence enabled: {attrs.get('enabled')}")
print(f"Schedule relationship: {sched_rel}")
print(f"Included count: {len(included)}")
for inc in included:
    if inc.get("type") == "schedule":
        print(f"  Schedule id={inc.get('id')} name={inc.get('attributes', {}).get('name', '?')}")
        print(f"  Full schedule attrs: {inc.get('attributes', {})}")

# 2. Enumerate schedule IDs across the whole library
print()
print("=" * 70)
print("FETCH 2: all sequences (owner=Steven) with schedule relationship")
print("=" * 70)

params = {"filter[owner][id]": oc._user_id or "11", "page[size]": "100"}
all_seqs = []
schedule_id_counts = Counter()
schedule_id_to_names = defaultdict(set)
schedule_id_to_seq_names = defaultdict(list)
included_schedule_names = {}

page = 1
while True:
    if page == 1:
        result = oc._api_get("/sequences", params)
    else:
        next_url = result.get("links", {}).get("next")
        if not next_url:
            break
        from urllib.parse import urlparse, parse_qs
        qs = parse_qs(urlparse(next_url).query)
        p = {k: v[0] for k, v in qs.items()}
        result = oc._api_get("/sequences", p)

    for inc in result.get("included", []):
        if inc.get("type") == "schedule":
            included_schedule_names[str(inc.get("id"))] = inc.get("attributes", {}).get("name", "?")

    for item in result.get("data", []):
        seq_id = item.get("id")
        seq_name = item.get("attributes", {}).get("name", "")
        sched = item.get("relationships", {}).get("schedule", {}).get("data")
        sched_id = sched.get("id") if sched else None
        all_seqs.append((seq_id, seq_name, sched_id))
        if sched_id is not None:
            schedule_id_counts[str(sched_id)] += 1
            schedule_id_to_seq_names[str(sched_id)].append((seq_id, seq_name))

    if not result.get("links", {}).get("next"):
        break
    page += 1
    if page > 20:
        break

print(f"Total sequences owned: {len(all_seqs)}")
print(f"Distinct schedule IDs in use: {sorted(schedule_id_counts.keys(), key=lambda x: int(x))}")
print()
print("Schedule ID → name (from sideload) → count → sample sequence names:")
for sid in sorted(schedule_id_counts.keys(), key=lambda x: int(x)):
    name = included_schedule_names.get(sid, "(name not sideloaded)")
    count = schedule_id_counts[sid]
    print(f"  id={sid:>4} name={name!r:<40} used_by={count} sequences")
    for seq_id, seq_name in schedule_id_to_seq_names[sid][:3]:
        print(f"     - {seq_id}: {seq_name[:70]}")
    if count > 3:
        print(f"     ... and {count - 3} more")

print()
print("=" * 70)
print(f"SPECIFIC ANSWER — sequence id 1999:")
print("=" * 70)
for seq_id, seq_name, sched_id in all_seqs:
    if seq_id == "1999":
        print(f"  Name: {seq_name}")
        print(f"  Schedule ID: {sched_id}")
        print(f"  Schedule Name: {included_schedule_names.get(str(sched_id), '(unknown)')}")
        break
