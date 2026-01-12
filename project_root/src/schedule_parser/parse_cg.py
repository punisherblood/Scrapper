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

    table = soup.find("table")
    maxColspan = _colspanCounter(table)
    slotNumber = 0
    for tr in table.find_all("tr"):
        if len(tr.find_all("td")) == 3:
            table_date = _parse_date_from_text(tr.find("td").text)    
        if table_date != None:
            slotNumber += 1
            subgroup = 0
            for td in tr.find_all("td"):
                if not td.has_attr("rowspan") and td.get("class")!=['hd']:
                    if int(td.get("colspan")) == maxColspan:
                        subgroup = 0
                    else:
                        subgroup += 1
                    ev = _extract_event_from_lesson_td(td,table_date,group_code,slotNumber,subgroup,cg_url)
                    if ev is not None:
                        events.append(ev)
        if slotNumber == 8:
            table_date = None
            slotNumber = 0
    events.sort(key=lambda e: (e.date, e.slot_number, e.subgroup))
    return events



# ---------- Internal helpers: date detection ----------
def _colspanCounter(table: Tag) -> Optional[int]:
    for td in table.find("thead").find_all("td")[-1]:
        return int(td.text)
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
