from datetime import date
from pathlib import Path
from schedule_parser.parse_cg import parse_schedule_from_cg
import re
from pathlib import Path

def load_html_fixture(path: Path) -> str:
    data = path.read_bytes()

    # 1) Ищем charset в meta (работает для большинства html)
    head = data[:5000].decode("ascii", errors="ignore")
    m = re.search(r'charset=["\']?([a-zA-Z0-9_-]+)', head, re.IGNORECASE)
    if m:
        enc = m.group(1).lower()
        try:
            return data.decode(enc, errors="replace")
        except LookupError:
            pass

    # 2) Пробуем UTF-8 (часто браузер сохраняет так)
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError:
        pass

    # 3) Фоллбек на cp1251
    return data.decode("cp1251", errors="replace")

HTML_PATH = Path("tests/fixtures/cg352.htm")
html = load_html_fixture(HTML_PATH)


events = parse_schedule_from_cg(
    html=html,
    cg_url="cg352.htm",
    group_code="АТ141",
    date_from=date(2026, 1, 12),
    date_to=date(2026, 1, 16),
)

print("[local-test] events:", len(events))

cur = None
for e in events:
    if cur != e.date:
        cur = e.date
        print("\n==", cur.strftime("%d.%m.%Y"), "==")
    sg = "вся группа" if e.subgroup == 0 else f"подгруппа {e.subgroup}"
    print(f"{e.slot_number:>2} | {sg:<10} | {e.subject_text} | {e.room_text} | {e.teacher_text}")
