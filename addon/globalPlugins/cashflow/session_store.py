from __future__ import annotations

from datetime import date

from .models import CashflowItem
from .recurrence import Occurrence, occurrences_for_month


class SessionStore:
	def __init__(self):
		self._items: list[CashflowItem] = []

	def add_payment(self, item: CashflowItem) -> None:
		self._items.append(item)

	def all_items(self) -> list[CashflowItem]:
		return list(self._items)

	def occurrences_for(self, target: date | None = None) -> list[Occurrence]:
		target = target or date.today()
		return occurrences_for_month(self._items, target.year, target.month)

	def pending_for(self, target: date | None = None) -> list[Occurrence]:
		return [occurrence for occurrence in self.occurrences_for(target) if not occurrence.paid]

	def paid_for(self, target: date | None = None) -> list[Occurrence]:
		return [occurrence for occurrence in self.occurrences_for(target) if occurrence.paid]

	def mark_paid(self, item_id: str, period: str) -> bool:
		for item in self._items:
			if item.id == item_id:
				return item.mark_paid(period)
		return False
