from __future__ import annotations

import calendar
from dataclasses import dataclass
from datetime import date

from .models import CashflowItem, RECURRENCE_MONTHLY, RECURRENCE_ONCE


@dataclass(frozen=True)
class Occurrence:
	item: CashflowItem
	due_date: date
	period: str
	paid: bool


def month_period(year: int, month: int) -> str:
	return f"{year:04d}-{month:02d}"


def months_between(start: date, year: int, month: int) -> int:
	return (year - start.year) * 12 + month - start.month


def occurrence_for_month(item: CashflowItem, year: int, month: int) -> Occurrence | None:
	period = month_period(year, month)
	offset = months_between(item.start_date, year, month)
	if item.recurrence == RECURRENCE_ONCE:
		if item.start_date.year != year or item.start_date.month != month:
			return None
		return Occurrence(item=item, due_date=item.start_date, period=period, paid=item.is_paid_for(period))
	if item.recurrence != RECURRENCE_MONTHLY or offset < 0:
		return None
	if item.duration_months is not None and offset >= item.duration_months:
		return None
	last_day = calendar.monthrange(year, month)[1]
	if item.start_date.day > last_day:
		return None
	due_date = date(year, month, item.start_date.day)
	return Occurrence(item=item, due_date=due_date, period=period, paid=item.is_paid_for(period))


def occurrences_for_month(items: list[CashflowItem], year: int, month: int) -> list[Occurrence]:
	occurrences = []
	for item in items:
		occurrence = occurrence_for_month(item, year, month)
		if occurrence is not None:
			occurrences.append(occurrence)
	return sorted(occurrences, key=lambda occurrence: (occurrence.due_date, occurrence.item.name.lower()))
