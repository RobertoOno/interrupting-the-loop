"""Local daily reservations for Claude/AWS runs; not an account-wide billing cap.

Append-only journal, exclusive admission lock, no automatic release after crashes.
Unsettled reservations carry forward until their actual charges are reconciled.
"""

import fcntl
import json
import os
from contextlib import contextmanager
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from zoneinfo import ZoneInfo

DAILY_LIMIT = Decimal("150")
ZONE = ZoneInfo("America/Sao_Paulo")


def money(value):
    amount = Decimal(str(value))
    if not amount.is_finite() or amount < 0:
        raise ValueError("cost must be finite and nonnegative")
    return amount


def now():
    return datetime.now(ZONE)


def balance(events, day):
    reservations, settlements = {}, {}
    for row in events:
        identity = row["run_id"]
        if row["event"] == "reserve":
            if identity in reservations or money(row["usd"]) <= 0:
                raise ValueError("invalid or duplicated reservation")
            reservations[identity] = row
        elif row["event"] == "settle":
            if identity not in reservations or identity in settlements:
                raise ValueError("invalid or duplicated settlement")
            if money(row["usd"]) > money(reservations[identity]["usd"]):
                raise ValueError("charge exceeded reservation; manual reconciliation required")
            settlements[identity] = row
        else:
            raise ValueError("unknown budget journal event")
    total = Decimal("0")
    for identity, reservation in reservations.items():
        start = reservation["at"][:10]
        settlement = settlements.get(identity)
        # Allocate full cost to every touched local day, conservatively. Outstanding
        # reservations never expire simply because midnight or a process exit occurs.
        if start <= day and (settlement is None or day <= settlement["at"][:10]):
            total += money((settlement or reservation)["usd"])
    return total


class DailyBudget:
    def __init__(self, path: Path):
        self.path = path

    @contextmanager
    def journal(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a+", encoding="utf-8") as handle:
            fcntl.flock(handle, fcntl.LOCK_EX)
            handle.seek(0)
            events = [json.loads(line) for line in handle if line.strip()]
            yield handle, events

    @staticmethod
    def append(handle, event):
        handle.write(json.dumps(event, sort_keys=True) + "\n")
        handle.flush()
        os.fsync(handle.fileno())

    def reserve(self, run_id, ceiling, *, at=None):
        instant = at or now()
        if instant.tzinfo is None:
            raise ValueError("timezone-aware timestamp required")
        instant = instant.astimezone(ZONE)
        amount = money(ceiling)
        if amount <= 0:
            raise ValueError("positive reservation required")
        with self.journal() as (handle, events):
            used = balance(events, instant.date().isoformat())
            if any(row["run_id"] == run_id for row in events):
                raise ValueError("run already reserved; no automatic reruns")
            if used + amount > DAILY_LIMIT:
                raise RuntimeError("daily Claude/AWS limit would be exceeded; stop and consult Roberto")
            event = {"event": "reserve", "run_id": run_id, "usd": str(amount),
                     "at": instant.isoformat(), "daily_limit_usd": str(DAILY_LIMIT),
                     "timezone": str(ZONE), "committed_today_usd": str(used + amount)}
            self.append(handle, event)
            return event

    def settle(self, run_id, actual, *, at=None):
        instant = at or now()
        if instant.tzinfo is None:
            raise ValueError("timezone-aware timestamp required")
        event = {"event": "settle", "run_id": run_id, "usd": str(money(actual)),
                 "at": instant.astimezone(ZONE).isoformat(), "basis": "reported tokens at frozen list rates; not invoice"}
        with self.journal() as (handle, events):
            reservation = next((r for r in events if r["event"] == "reserve" and r["run_id"] == run_id), None)
            if reservation is None or event["at"] < reservation["at"]:
                raise ValueError("missing reservation or reversed timestamps")
            balance([*events, event], event["at"][:10])
            self.append(handle, event)
        return event
