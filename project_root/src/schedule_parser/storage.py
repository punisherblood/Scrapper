# src/schedule_parser/storage.py
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Iterable, Optional, Sequence

import psycopg
from psycopg.rows import dict_row
from psycopg import sql

from .config import DB_DSN
from .parse_hg import GroupRef
from .parse_cg import LessonEvent

import logging

logger = logging.getLogger("storage")

@dataclass(frozen=True)
class DbIds:
    subject_id: Optional[int]
    teacher_id: Optional[int]
    room_id: Optional[int]


class Storage:
    """
    Postgres storage layer.
    Responsibilities:
      - connect
      - upsert reference tables (groups/subjects/teachers/rooms)
      - replace lesson_events for a group in a date range
      - parser_runs bookkeeping
    """

    def __init__(self, dsn: str = DB_DSN) -> None:
        self._dsn = dsn

    def connect(self) -> psycopg.Connection:
        # autocommit=False by default; we control transactions
        return psycopg.connect(self._dsn, row_factory=dict_row)

    # ----------------------------
    # Parser runs
    # ----------------------------
    
    def create_run(self, conn: psycopg.Connection) -> int:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO parser_runs(status)
                VALUES ('started')
                RETURNING id
                """
            )
            run_id = cur.fetchone()["id"]
        conn.commit()
        return int(run_id)

    def finish_run(
        self,
        conn: psycopg.Connection,
        run_id: int,
        status: str,
        message: Optional[str] = None,
        groups_total: Optional[int] = None,
        groups_ok: Optional[int] = None,
        groups_failed: Optional[int] = None,
        events_saved: Optional[int] = None,
    ) -> None:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE parser_runs
                SET finished_at = now(),
                    status = %s,
                    message = %s,
                    groups_total = %s,
                    groups_ok = %s,
                    groups_failed = %s,
                    events_saved = %s
                WHERE id = %s
                """,
                (status, message, groups_total, groups_ok, groups_failed, events_saved, run_id),
            )
        conn.commit()
    
    # ----------------------------
    # Groups
    # ----------------------------

    def upsert_groups(self, conn: psycopg.Connection, groups: Sequence[GroupRef]) -> None:
        """
        Upsert groups by code. Updates cg_url + updated_at.
        """
        if not groups:
            return

        rows = [(g.code, g.cg_url) for g in groups]

        with conn.cursor() as cur:
            cur.executemany(
                """
                INSERT INTO groups(code, cg_url, active)
                VALUES (%s, %s, TRUE)
                ON CONFLICT (code)
                DO UPDATE SET
                  cg_url = EXCLUDED.cg_url,
                  active = TRUE,
                  updated_at = now()
                """,
                rows,
            )
        conn.commit()

    def get_group_id(self, conn: psycopg.Connection, group_code: str) -> int:
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM groups WHERE code = %s", (group_code,))
            row = cur.fetchone()
            if not row:
                raise ValueError(f"Group not found in DB: {group_code}")
            return int(row["id"])

    # ----------------------------
    # Reference tables: subjects/teachers/rooms
    # ----------------------------

    def _upsert_subject(self, cur, name: str) -> int:
        cur.execute(
            """
            INSERT INTO subjects(name)
            VALUES (%s)
            ON CONFLICT (name) DO UPDATE SET updated_at = now()
            RETURNING id
            """,
            (name,),
        )
        return int(cur.fetchone()["id"])

    def _upsert_teacher(self, cur, name: str, source_url: Optional[str]) -> int:
        # Keep the first known source_url; update if empty and new value exists
        cur.execute(
            """
            INSERT INTO teachers(name, source_url)
            VALUES (%s, %s)
            ON CONFLICT (name)
            DO UPDATE SET
              source_url = COALESCE(teachers.source_url, EXCLUDED.source_url),
              updated_at = now()
            RETURNING id
            """,
            (name, source_url),
        )
        return int(cur.fetchone()["id"])

    def _upsert_room(self, cur, name: str, source_url: Optional[str]) -> int:
        cur.execute(
            """
            INSERT INTO rooms(name, source_url)
            VALUES (%s, %s)
            ON CONFLICT (name)
            DO UPDATE SET
              source_url = COALESCE(rooms.source_url, EXCLUDED.source_url),
              updated_at = now()
            RETURNING id
            """,
            (name, source_url),
        )
        return int(cur.fetchone()["id"])

    def resolve_ids(self, conn: psycopg.Connection, ev: LessonEvent) -> DbIds:
        """
        Ensure subject/teacher/room exist and return their ids.
        This does small upserts per event (simple but OK for MVP).
        You can batch-optimize later.
        """
        subject_id = teacher_id = room_id = None

        with conn.cursor() as cur:
            if ev.subject_text:
                subject_id = self._upsert_subject(cur, ev.subject_text)

            if ev.teacher_text:
                teacher_id = self._upsert_teacher(cur, ev.teacher_text, ev.source_teacher_url)

            if ev.room_text:
                room_id = self._upsert_room(cur, ev.room_text, ev.source_room_url)

        conn.commit()
        return DbIds(subject_id=subject_id, teacher_id=teacher_id, room_id=room_id)

    # ----------------------------
    # Lesson events
    # ----------------------------
    
    def replace_events_for_group(
        self,
        conn: psycopg.Connection,
        group_id: int,
        date_from: date,
        date_to: date,
        events: Sequence[LessonEvent],
    ) -> int:
        """
        Replace schedule events for group in [date_from, date_to].
        Strategy:
          1) DELETE old events in range
          2) INSERT all new events (bulk)
        Returns number of inserted events.
        """
        with conn.cursor() as cur:
            # 1) Delete old
            cur.execute(
                """
                DELETE FROM lesson_events
                WHERE group_id = %s
                  AND event_date BETWEEN %s AND %s
                """,
                (group_id, date_from, date_to),
            )
    
        conn.commit()

        if not events:
            return 0
        
         # ---------- DEDUPLICATION ----------
        def _event_key(ev: LessonEvent):
            if ev.source_journal_url:
                return (ev.date, ev.slot_number, ev.subgroup, ev.source_journal_url)
            return (
                ev.date,
                ev.slot_number,
                ev.subgroup,
                ev.subject_text,
                ev.teacher_text,
                ev.room_text,
            )

        original_len = len(events)
        unique = {}
        for ev in events:
            unique[_event_key(ev)] = ev

        events = list(unique.values())
        events.sort(key=lambda e: (e.date, e.slot_number, e.subgroup))

        dropped = original_len - len(events)
        if dropped > 0:
            logger.info(
                "DEDUP: dropped %d duplicate events for group_id=%s",
                dropped,
                group_id,
            )
        # ---------- END DEDUP ----------

        # 2) Insert new
        inserted = 0
        with conn.cursor() as cur:
            rows = []
            for ev in events:
                ids = self.resolve_ids(conn, ev)

                rows.append(
                    (
                        ev.date,
                        group_id,
                        ev.slot_number,
                        ev.subgroup,
                        ids.subject_id,
                        ids.teacher_id,
                        ids.room_id,
                        ev.lesson_type,
                        ev.source_group_url,
                        ev.source_journal_url,
                        ev.source_teacher_url,
                        ev.source_room_url,
                        # raw fields
                        ev.subject_text,
                        ev.teacher_text,
                        ev.room_text,
                    )
                )

            cur.executemany(
                """
                INSERT INTO lesson_events(
                  event_date, group_id, slot_number, subgroup,
                  subject_id, teacher_id, room_id,
                  lesson_type,
                  source_group_url, source_journal_url, source_teacher_url, source_room_url,
                  subject_text_raw, teacher_text_raw, room_text_raw,
                  updated_at
                )
                VALUES (
                  %s, %s, %s, %s,
                  %s, %s, %s,
                  %s,
                  %s, %s, %s, %s,
                  %s, %s, %s,
                  now()
                )
                """,
                rows,
            )
            inserted = len(rows)

        conn.commit()
        return inserted
