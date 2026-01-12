# src/schedule_parser/runner.py
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Optional

from .config import DEFAULT_DAYS_AHEAD
from .parse_hg import fetch_groups, GroupRef
from .parse_cg import fetch_group_schedule
from .storage import Storage
from .http_client import HttpClientError

logger = logging.getLogger("runner")


@dataclass(frozen=True)
class RunOptions:
    group_code: Optional[str] = None      # если задано — прогон только одной группы
    date_from: Optional[date] = None
    date_to: Optional[date] = None


def _calc_range(opts: RunOptions) -> tuple[date, date]:
    df = opts.date_from or date.today()
    dt = opts.date_to or (df + timedelta(days=DEFAULT_DAYS_AHEAD))
    return df, dt


def run_parser(opts: RunOptions) -> None:
    date_from, date_to = _calc_range(opts)

    storage = Storage()
    conn = storage.connect()

    run_id = storage.create_run(conn)
    logger.info("Parser run started: id=%s, range=%s..%s", run_id, date_from, date_to)

    groups_total = 0
    groups_ok = 0
    groups_failed = 0
    events_saved_total = 0

    try:
        # 1) Получаем список групп
        all_groups = fetch_groups()

        # Фильтр по одной группе (если нужно)
        if opts.group_code:
            all_groups = [g for g in all_groups if g.code == opts.group_code]

        groups_total = len(all_groups)
        if groups_total == 0:
            storage.finish_run(
                conn, run_id,
                status="failed",
                message=f"No groups found (filter={opts.group_code})",
                groups_total=0, groups_ok=0, groups_failed=0, events_saved=0
            )
            return

        # 2) Сохраняем группы в БД
        storage.upsert_groups(conn, all_groups)

        # 3) Цикл по группам
        for g in all_groups:
            try:
                # Получаем group_id из БД
                group_id = storage.get_group_id(conn, g.code)

                # Парсим расписание группы
                events = fetch_group_schedule(
                    cg_url=g.cg_url,
                    group_code=g.code,
                    date_from=date_from,
                    date_to=date_to,
                )

                # Пишем в БД (replace)
                inserted = storage.replace_events_for_group(
                    conn=conn,
                    group_id=group_id,
                    date_from=date_from,
                    date_to=date_to,
                    events=events,
                )

                events_saved_total += inserted
                groups_ok += 1
                logger.info("OK: %s (%s) events=%d", g.code, g.cg_url, inserted)

            except (HttpClientError, Exception) as e:
                groups_failed += 1
                logger.exception("FAIL: %s (%s) error=%s", g.code, g.cg_url, e)

        # 4) Итог
        status = "success" if groups_failed == 0 else "partial"
        storage.finish_run(
            conn,
            run_id,
            status=status,
            message=None if status == "success" else "Some groups failed; see logs",
            groups_total=groups_total,
            groups_ok=groups_ok,
            groups_failed=groups_failed,
            events_saved=events_saved_total,
        )
        logger.info(
            "Parser run finished: status=%s total=%d ok=%d failed=%d events=%d",
            status, groups_total, groups_ok, groups_failed, events_saved_total
        )

    except Exception as e:
        storage.finish_run(
            conn,
            run_id,
            status="failed",
            message=str(e),
            groups_total=groups_total,
            groups_ok=groups_ok,
            groups_failed=groups_failed,
            events_saved=events_saved_total,
        )
        logger.exception("Parser run failed fatally: %s", e)

    finally:
        conn.close()


if __name__ == "__main__":
    # Простейший локальный запуск:
    # 1) прогнать все группы:
    #run_parser(RunOptions())

    # 2) или одну группу:
    run_parser(RunOptions(group_code="АТ141"))