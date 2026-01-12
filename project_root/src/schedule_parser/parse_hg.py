# src/schedule_parser/parse_hg.py
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import List

from bs4 import BeautifulSoup

from .http_client import get_html

# Ссылка на страницу группы: cg###.htm
_CG_RE = re.compile(r"^cg\d+\.htm$", re.IGNORECASE)


@dataclass(frozen=True)
class GroupRef:
    code: str     # например "АТ141"
    cg_url: str   # например "cg352.htm"


def fetch_groups() -> List[GroupRef]:
    """
    Скачивает hg.htm и возвращает список групп (code + cg_url).
    """
    html = get_html("hg.htm")
    return parse_groups_from_hg(html)


def parse_groups_from_hg(html: str) -> List[GroupRef]:
    """
    Чистая функция: принимает HTML hg.htm, возвращает список групп.
    """
    soup = BeautifulSoup(html, "html.parser")

    groups: List[GroupRef] = []
    seen = set()

    # На hg.htm могут быть разные ссылки, берём только cg###.htm
    for a in soup.find_all("a", href=True):
        href = (a.get("href") or "").strip()
        if not href:
            continue
        if not _CG_RE.match(href):
            continue

        code = a.get_text(" ", strip=True)
        if not code:
            continue

        key = (code, href)
        if key in seen:
            continue
        seen.add(key)

        groups.append(GroupRef(code=code, cg_url=href))

    groups.sort(key=lambda g: g.code)
    return groups
