"""
Recompute content_items.url_hash with the current URL normalisation.

Usage (manual, never at container start, no Alembic step):

    docker compose exec api python -m app.tools.rehash               # dry-run (default)
    docker compose exec api python -m app.tools.rehash --dry-run --report /tmp/rehash.csv
    docker compose exec api python -m app.tools.rehash --apply --report /tmp/rehash.csv

Older rows were hashed with the legacy normalisation (scheme://host+path, no
query/port/fragment). The new `hash_url` keeps the query string, so hashes
change and different legacy rows can collapse onto the same new hash.

Collision handling: per group of items sharing a new hash, the oldest item
(smallest created_at, then id) becomes canonical and gets the new hash. Younger
items are NEVER deleted; they get a marker hash instead:

    <first 23 hex chars of new hash>:dup:<uuid>

Length limit: `url_hash` is VARCHAR(64). The full form `<64-hex>:dup:<uuid>`
would need 105 chars, so the hash prefix is truncated to 23 chars
(23 + 5 + 36 = 64). The UUID keeps the marker unique; the prefix links it to
the canonical item; the full new hash is in the CSV report.

Items without URL (notes) are left untouched. `--apply` runs in one
transaction and is idempotent: the assignment is deterministic, so a second
run finds every item already at its target hash and changes nothing.
"""

import argparse
import asyncio
import csv
import sys
import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import async_session_maker, engine
from app.models.content import ContentItem
from app.services.urlnorm import hash_url

URL_HASH_MAX_LEN = 64
DUP_PREFIX_LEN = 23

ACTION_UNCHANGED = "unchanged"
ACTION_REHASH = "rehash"
ACTION_DUP = "dup"
ACTION_DUP_UNCHANGED = "dup-unchanged"


def dup_hash(new_hash: str, item_id: uuid.UUID) -> str:
    value = f"{new_hash[:DUP_PREFIX_LEN]}:dup:{item_id}"
    assert len(value) <= URL_HASH_MAX_LEN
    return value


@dataclass
class Row:
    id: uuid.UUID
    url: str
    old_hash: str | None
    new_hash: str
    created_at: datetime | None
    target_hash: str = ""
    action: str = ""


@dataclass
class Plan:
    rows: list[Row] = field(default_factory=list)
    collisions: list[list[Row]] = field(default_factory=list)

    @property
    def changes(self) -> list[Row]:
        return [r for r in self.rows if r.old_hash != r.target_hash]

    @property
    def unchanged(self) -> list[Row]:
        return [r for r in self.rows if r.old_hash == r.target_hash]


def build_plan(items: list[tuple[uuid.UUID, str, str | None, datetime | None]]) -> Plan:
    """Pure planning step: decide the target hash for every item with a URL."""
    groups: dict[str, list[Row]] = defaultdict(list)
    for item_id, url, old_hash, created_at in items:
        row = Row(item_id, url, old_hash, hash_url(url), created_at)
        groups[row.new_hash].append(row)

    plan = Plan()
    for new_hash, rows in groups.items():
        rows.sort(key=lambda r: (r.created_at or datetime.min, str(r.id)))
        for i, row in enumerate(rows):
            row.target_hash = new_hash if i == 0 else dup_hash(new_hash, row.id)
            if row.old_hash == row.target_hash:
                row.action = ACTION_UNCHANGED if i == 0 else ACTION_DUP_UNCHANGED
            else:
                row.action = ACTION_REHASH if i == 0 else ACTION_DUP
        plan.rows.extend(rows)
        if len(rows) > 1:
            plan.collisions.append(rows)
    return plan


async def _load(db: AsyncSession, *, lock: bool) -> tuple[Plan, set[str]]:
    stmt = select(
        ContentItem.id, ContentItem.url, ContentItem.url_hash, ContentItem.created_at
    ).where(ContentItem.url.is_not(None))
    if lock:
        stmt = stmt.with_for_update()
    plan = build_plan([tuple(r) for r in (await db.execute(stmt)).all()])

    # Hashes held by rows outside the plan (url IS NULL but url_hash set):
    # a target colliding with one of them would violate the unique index.
    foreign = await db.execute(
        select(ContentItem.url_hash).where(
            ContentItem.url.is_(None), ContentItem.url_hash.is_not(None)
        )
    )
    return plan, {h for (h,) in foreign.all()}


async def run_rehash(*, apply: bool, report_path: str | None = None, out=None) -> Plan:
    out = out or sys.stdout
    async with async_session_maker() as db:
        async with db.begin():
            plan, foreign_hashes = await _load(db, lock=apply)
            blocked = [r for r in plan.changes if r.target_hash in foreign_hashes]
            if blocked:
                ids = ", ".join(str(r.id) for r in blocked)
                raise RuntimeError(f"Target hash already held by an item without URL: {ids}")

            if apply and plan.changes:
                # Phase 1: move every changing row to a unique temporary hash so
                # phase 2 never hits the unique index (e.g. swaps between rows).
                for row in plan.changes:
                    await db.execute(
                        update(ContentItem)
                        .where(ContentItem.id == row.id)
                        .values(url_hash=f"tmp:{row.id}")
                    )
                for row in plan.changes:
                    await db.execute(
                        update(ContentItem)
                        .where(ContentItem.id == row.id)
                        .values(url_hash=row.target_hash)
                    )
            # Leaving the block commits (apply) or commits a no-op read (dry-run).

    _print_summary(plan, apply=apply, out=out)
    if report_path:
        _write_report(plan, report_path)
        print(f"Report written: {report_path}", file=out)
    return plan


def _print_summary(plan: Plan, *, apply: bool, out) -> None:
    mode = "APPLY" if apply else "DRY-RUN (nothing written)"
    print(f"Rehash {mode}", file=out)
    print(f"  items with URL : {len(plan.rows)}", file=out)
    print(f"  unchanged      : {len(plan.unchanged)}", file=out)
    print(f"  {'changed' if apply else 'to change'}      : {len(plan.changes)}", file=out)
    print(f"  collision groups: {len(plan.collisions)}", file=out)
    for group in plan.collisions:
        print(f"  - new hash {group[0].new_hash}:", file=out)
        for row in group:
            role = "canonical" if row is group[0] else "duplicate"
            print(f"      {role:9} {row.id} {row.created_at} {row.url}", file=out)


def _write_report(plan: Plan, path: str) -> None:
    with open(path, "w", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(["id", "url", "old_hash", "new_hash", "target_hash", "action"])
        for row in plan.rows:
            writer.writerow(
                [row.id, row.url, row.old_hash, row.new_hash, row.target_hash, row.action]
            )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m app.tools.rehash", description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true", help="report only (default)")
    mode.add_argument("--apply", action="store_true", help="write new hashes")
    parser.add_argument("--report", metavar="PATH", help="write a CSV report")
    args = parser.parse_args(argv)

    async def _run() -> None:
        try:
            await run_rehash(apply=args.apply, report_path=args.report)
        finally:
            await engine.dispose()

    asyncio.run(_run())
    return 0


if __name__ == "__main__":
    sys.exit(main())
