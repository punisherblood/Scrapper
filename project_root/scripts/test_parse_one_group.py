from datetime import date
from schedule_parser.parse_cg import fetch_group_schedule

events = fetch_group_schedule(
    cg_url="cg352.htm",
    group_code="АТ141",
    date_from=date(2026, 1, 12),
    date_to=date(2026, 1, 16),
)

print("events:", len(events))
for e in events[:10]:
    print(e.date, e.slot_number, e.subgroup, e.subject_text, e.teacher_text, e.room_text)
from collections import Counter

keys = []
for e in events:
    keys.append((e.date, e.slot_number, e.subgroup, e.source_journal_url))
c = Counter(keys)
dups = [k for k,v in c.items() if v>1]
print("duplicates:", len(dups))
for k in dups[:10]:
    print(k, "count=", c[k])