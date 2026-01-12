# src/schedule_parser/parse_cg.py
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime
from typing import List, Optional, Tuple

from bs4 import BeautifulSoup, Tag

from .http_client import get_html


# ---------- Models ----------

@dataclass(frozen=True)
class LessonEvent:
    date: date
    group_code: str
    slot_number: int
    subgroup: int  # 0 = whole group, 1..N = subgroup column index

    subject_text: str
    lesson_type: Optional[str]  # e.g. "Лек."
    teacher_text: Optional[str]
    room_text: Optional[str]

    source_group_url: str
    source_journal_url: Optional[str]
    source_teacher_url: Optional[str]
    source_room_url: Optional[str]


# ---------- Regex helpers ----------

# Matches "Физическая культура (Лек.)" -> subject="Физическая культура", type="Лек."
_SUBJECT_TYPE_RE = re.compile(r"^(?P<subj>.*?)(?:\s*\((?P<typ>[^()]*)\)\s*)?$")

# Dates on site are usually like "13.01.2026"
_DATE_RE = re.compile(r"(?P<d>\d{2})\.(?P<m>\d{2})\.(?P<y>\d{4})")


# ---------- Public API ----------

def fetch_group_schedule(
    cg_url: str,
    group_code: str,
    date_from: date,
    date_to: date,
) -> List[LessonEvent]:
    """
    Fetch cg###.htm for a group and parse events within [date_from, date_to].
    """
    html = get_html(cg_url)
    return parse_schedule_from_cg(
        html=html,
        cg_url=cg_url,
        group_code=group_code,
        date_from=date_from,
        date_to=date_to,
    )


def parse_schedule_from_cg(
    html: str,
    cg_url: str,
    group_code: str,
    date_from: date,
    date_to: date,
) -> List[LessonEvent]:
    """
    Pure parsing function (no network). Extract LessonEvents from cg page HTML.
    Implements subgroup logic using td classes and colspan (no j#### fetching).
    """
    soup = BeautifulSoup(html, "html.parser")
    events: List[LessonEvent] = []

    # NOTE:
    # Different cg pages might have slightly different structure.
    # We rely on a robust approach: scan the document, detect "current date",
    # then parse subsequent lesson rows until next date.
    #
    # A common pattern: date is shown as text node "13.01.2026" near a table.
    # We will scan tables and detect date headers preceding them.

    # Find all tables; for each, try to find a date near it.
    tables = soup.find_all("table")
    for table in tables:
        table_date = _find_date_for_table(table)
        if table_date is None:
            continue

        # Filter date range early
        if table_date < date_from or table_date > date_to:
            continue

        # Parse lesson rows (tr)
        for tr in table.find_all("tr"):
            slot_number = _extract_slot_number(tr)
            if slot_number is None:
                continue

            # All tds in the row
            tds = tr.find_all("td", recursive=False)
            if not tds:
                continue

            # First td is the slot cell (class hd). Everything after is subgroup area
            subgroup_tds = tds[1:]
            if not subgroup_tds:
                continue

            n = _sum_colspan(subgroup_tds)
            if n <= 0:
                continue

            # Case A: whole group if exists td.ur with colspan == N
            whole_td = _find_whole_group_td(subgroup_tds, n)
            if whole_td is not None:
                ev = _extract_event_from_lesson_td(
                    td=whole_td,
                    lesson_date=table_date,
                    group_code=group_code,
                    slot_number=slot_number,
                    subgroup=0,
                    source_group_url=cg_url,
                )
                if ev is not None:
                    events.append(ev)
                continue

            # Case B: subgroup split
            col_idx = 1
            for td in subgroup_tds:
                cs = _get_colspan(td)
                is_lesson = _td_has_class(td, "ur")
                if is_lesson:
                    ev = _extract_event_from_lesson_td(
                        td=td,
                        lesson_date=table_date,
                        group_code=group_code,
                        slot_number=slot_number,
                        subgroup=col_idx,
                        source_group_url=cg_url,
                    )
                    if ev is not None:
                        events.append(ev)

                col_idx += cs

    # Stable sort: by date, slot, subgroup
    events.sort(key=lambda e: (e.date, e.slot_number, e.subgroup))
    return events


# ---------- Internal helpers: date detection ----------

def _find_date_for_table(table: Tag) -> Optional[date]:
    """
    Try to find a date (dd.mm.yyyy) associated with this table.
    We look:
      - in previous siblings text
      - in parent/previous elements
    """
    # 1) Search in previous siblings up to some limit
    prev = table
    for _ in range(10):
        prev = prev.previous_sibling
        if prev is None:
            break
        txt = _text_of(prev)
        d = _parse_date_from_text(txt)
        if d:
            return d

    # 2) Search in parent previous siblings
    parent = table.parent
    for _ in range(10):
        if parent is None:
            break
        txt = _text_of(parent)
        d = _parse_date_from_text(txt)
        if d:
            return d
        parent = parent.previous_sibling  # type: ignore

    return None


def _parse_date_from_text(text: str) -> Optional[date]:
    m = _DATE_RE.search(text or "")
    if not m:
        return None
    try:
        d = int(m.group("d"))
        mo = int(m.group("m"))
        y = int(m.group("y"))
        return date(y, mo, d)
    except ValueError:
        return None


def _text_of(node) -> str:
    if node is None:
        return ""
    if isinstance(node, str):
        return node.strip()
    if hasattr(node, "get_text"):
        return node.get_text(" ", strip=True)
    return str(node).strip()


# ---------- Internal helpers: row parsing ----------

def _extract_slot_number(tr: Tag) -> Optional[int]:
    """
    Slot number is in td with class 'hd' (first cell).
    Example: <td class="hd">4</td>
    """
    first = tr.find("td", class_="hd")
    if not first:
        return None
    txt = first.get_text(" ", strip=True)
    if not txt.isdigit():
        return None
    return int(txt)


def _sum_colspan(tds: List[Tag]) -> int:
    return sum(_get_colspan(td) for td in tds)


def _get_colspan(td: Tag) -> int:
    v = td.get("colspan")
    if v is None:
        return 1
    try:
        return int(v)
    except ValueError:
        return 1


def _td_has_class(td: Tag, cls: str) -> bool:
    classes = td.get("class") or []
    return cls in classes


def _find_whole_group_td(subgroup_tds: List[Tag], n: int) -> Optional[Tag]:
    """
    Whole-group lesson is encoded as td.ur with colspan == N.
    """
    for td in subgroup_tds:
        if _td_has_class(td, "ur") and _get_colspan(td) == n:
            return td
    return None


# ---------- Internal helpers: extracting lesson from td.ur ----------

def _extract_event_from_lesson_td(
    td: Tag,
    lesson_date: date,
    group_code: str,
    slot_number: int,
    subgroup: int,
    source_group_url: str,
) -> Optional[LessonEvent]:
    """
    Extract subject/teacher/room and source URLs from a lesson cell td.ur.
    """
    # Skip if it is actually empty
    cell_text = td.get_text(" ", strip=True)
    if not cell_text:
        return None

    # subject + journal
    a_subj = td.find("a", class_="z1", href=True)
    subject_raw = a_subj.get_text(" ", strip=True) if a_subj else ""
    journal_url = a_subj["href"].strip() if a_subj else None

    subject_text, lesson_type = _parse_subject_and_type(subject_raw)

    # room
    a_room = td.find("a", class_="z2", href=True)
    room_text = a_room.get_text(" ", strip=True) if a_room else None
    room_url = a_room["href"].strip() if a_room else None

    # teacher
    a_teacher = td.find("a", class_="z3", href=True)
    teacher_text = a_teacher.get_text(" ", strip=True) if a_teacher else None
    teacher_url = a_teacher["href"].strip() if a_teacher else None

    # Sometimes subject might be empty; fallback to cell text (rare)
    if not subject_text:
        subject_text = subject_raw.strip() or cell_text

    return LessonEvent(
        date=lesson_date,
        group_code=group_code,
        slot_number=slot_number,
        subgroup=subgroup,
        subject_text=subject_text,
        lesson_type=lesson_type,
        teacher_text=teacher_text,
        room_text=room_text,
        source_group_url=source_group_url,
        source_journal_url=journal_url,
        source_teacher_url=teacher_url,
        source_room_url=room_url,
    )


def _parse_subject_and_type(subject_raw: str) -> Tuple[str, Optional[str]]:
    """
    Parse subject string like 'Физическая культура (Лек.)'
    Return (subject_text, lesson_type).
    If type is empty '()' -> lesson_type=None.
    """
    s = (subject_raw or "").strip()
    if not s:
        return "", None

    m = _SUBJECT_TYPE_RE.match(s)
    if not m:
        return s, None

    subj = (m.group("subj") or "").strip()
    typ = m.group("typ")
    if typ is not None:
        typ = typ.strip()
        if not typ:
            typ = None
    return subj, typ
