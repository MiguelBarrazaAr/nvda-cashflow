from __future__ import annotations

import csv
import json
import os
import threading
from datetime import datetime

import globalVars
from logHandler import log

from . import sqlite313 as sqlite3
from .models import CashflowItem, ITEM_KIND_COLLECTION, ITEM_KIND_INCOME, ITEM_KIND_PAYMENT
from .serialization import (
	export_rows_to_csv,
	export_rows_to_json,
	export_rows_to_xlsx,
	import_rows_from_csv,
	import_rows_from_json,
)


SCHEMA_VERSION = "1"


class CashflowStore:
	def __init__(self, base_path: str | None = None):
		root = base_path or os.path.join(globalVars.appArgs.configPath, "cashflow")
		self._root = root
		self._db_path = os.path.join(root, "cashflow.db")
		self._items: list[CashflowItem] = []
		self._initialized = False
		self._loaded = False
		self._loading = False
		self._init_lock = threading.Lock()
		self._revision = 0
		self._kind_cache: dict[tuple[int, str], list[CashflowItem]] = {}
		self._occurrence_cache: dict[tuple[int, str, int | None, int | None], list] = {}

	def _connect(self):
		os.makedirs(self._root, exist_ok=True)
		if not self._initialized:
			with self._init_lock:
				if not self._initialized:
					self._initialize()
					self._initialized = True
		return self._raw_connect()

	def _raw_connect(self):
		os.makedirs(self._root, exist_ok=True)
		return sqlite3.connect(self._db_path)

	def _initialize(self) -> None:
		with self._raw_connect() as connection:
			connection.execute(
				"""
				CREATE TABLE IF NOT EXISTS metadata (
					key TEXT PRIMARY KEY,
					value TEXT NOT NULL
				)
				"""
			)
			connection.execute(
				"""
				CREATE TABLE IF NOT EXISTS cashflow_items (
					id TEXT PRIMARY KEY,
					payload TEXT NOT NULL,
					created_at TEXT NOT NULL,
					updated_at TEXT NOT NULL
				)
				"""
			)
			connection.execute(
				"INSERT OR REPLACE INTO metadata (key, value) VALUES (?, ?)",
				("schema_version", SCHEMA_VERSION),
			)

	def reload(self) -> None:
		self._loading = True
		try:
			items = []
			with self._connect() as connection:
				rows = connection.execute("SELECT payload FROM cashflow_items ORDER BY created_at").fetchall()
			for index, row in enumerate(rows):
				try:
					item = CashflowItem.from_dict(json.loads(row[0]))
					if not item.order:
						item.order = index + 1
					items.append(item)
				except Exception:
					log.exception("No se pudo cargar un pago de Cashflow")
			self._items = sorted(items, key=lambda item: (item.kind, item.order, item.name.lower()))
			self._loaded = True
			self._touch()
		finally:
			self._loading = False

	@property
	def is_loaded(self) -> bool:
		return self._loaded

	@property
	def is_loading(self) -> bool:
		return self._loading

	@property
	def revision(self) -> int:
		return self._revision

	def _touch(self) -> None:
		self._revision += 1
		self._kind_cache.clear()
		self._occurrence_cache.clear()

	def add_payment(self, item: CashflowItem) -> None:
		if not item.order:
			item.order = self._next_order(item.kind)
		self._items.append(item)
		self._upsert(item)
		self._touch()

	def update_item(self, item: CashflowItem) -> None:
		for index, current in enumerate(self._items):
			if current.id == item.id:
				self._items[index] = item
				self._upsert(item)
				self._touch()
				return
		self.add_payment(item)

	def delete_item(self, item_id: str) -> bool:
		before = len(self._items)
		self._items = [item for item in self._items if item.id != item_id]
		if len(self._items) == before:
			return False
		with self._connect() as connection:
			connection.execute("DELETE FROM cashflow_items WHERE id = ?", (item_id,))
		self._touch()
		return True

	def delete_items_for_category(self, category: str) -> int:
		matching = [item for item in self._items if item.category == category]
		if not matching:
			return 0
		ids = {item.id for item in matching}
		self._items = [item for item in self._items if item.id not in ids]
		with self._connect() as connection:
			for item_id in ids:
				connection.execute("DELETE FROM cashflow_items WHERE id = ?", (item_id,))
		self._touch()
		return len(matching)

	def rename_category(self, old_category: str, new_category: str) -> int:
		if old_category == new_category:
			return 0
		changed = 0
		for item in self._items:
			if item.category == old_category:
				item.category = new_category
				self._upsert(item)
				changed += 1
		if changed:
			self._touch()
		return changed

	def items_for_category(self, category: str) -> list[CashflowItem]:
		return [item for item in self._items if item.category == category]

	def clear_all(self) -> None:
		self._items = []
		with self._connect() as connection:
			connection.execute("DELETE FROM cashflow_items")
		self._touch()

	def replace_all(self, items: list[CashflowItem]) -> None:
		self.clear_all()
		for item in items:
			self._items.append(item)
			self._upsert(item)
		self._touch()

	def all_items(self) -> list[CashflowItem]:
		return list(self._items)

	def payments(self) -> list[CashflowItem]:
		return self._items_for_kind(ITEM_KIND_PAYMENT)

	def collections(self) -> list[CashflowItem]:
		return self._items_for_kind(ITEM_KIND_COLLECTION)

	def incomes(self) -> list[CashflowItem]:
		return self._items_for_kind(ITEM_KIND_INCOME)

	def items_for_kind(self, kind: str) -> list[CashflowItem]:
		return self._items_for_kind(kind)

	def _items_for_kind(self, kind: str) -> list[CashflowItem]:
		cache_key = (self._revision, kind)
		cached = self._kind_cache.get(cache_key)
		if cached is not None:
			return list(cached)
		items = sorted([item for item in self._items if item.kind == kind], key=lambda item: (item.order, item.name.lower()))
		self._kind_cache[cache_key] = list(items)
		return list(items)

	def _next_order(self, kind: str) -> int:
		items = self._items_for_kind(kind)
		if not items:
			return 1
		return max(item.order for item in items) + 1

	def move_item(self, item_id: str, direction: int) -> bool:
		item = self._find(item_id)
		if item is None:
			return False
		items = self._items_for_kind(item.kind)
		index = next((i for i, current in enumerate(items) if current.id == item_id), -1)
		new_index = index + direction
		if index < 0 or new_index < 0 or new_index >= len(items):
			return False
		other = items[new_index]
		item.order, other.order = other.order, item.order
		self._upsert(item)
		self._upsert(other)
		self._touch()
		return True

	def export_items(self, kind: str, path: str) -> None:
		rows = [item.to_dict() for item in self._items_for_kind(kind)]
		format_name = self._format_from_path(path)
		if format_name == "json":
			export_rows_to_json(rows, path)
		elif format_name == "xlsx":
			export_rows_to_xlsx(rows, path)
		else:
			export_rows_to_csv(rows, path)

	def import_items(self, kind: str, path: str) -> int:
		format_name = self._format_from_path(path)
		if format_name == "json":
			rows = import_rows_from_json(path)
		else:
			rows = import_rows_from_csv(path)
		imported = 0
		next_order = self._next_order(kind)
		for row in rows:
			item = CashflowItem(
				name=(row.get("nombre") or "").strip(),
				amount=self._parse_csv_amount(row.get("importe")),
				category=(row.get("categoria") or "Otros").strip() or "Otros",
				start_date=self._parse_csv_date(row),
				recurrence=self._parse_row_recurrence(row),
				duration_months=self._parse_row_duration(row),
				kind=kind,
				order=next_order,
			)
			next_order += 1
			self._items.append(item)
			self._upsert(item)
			imported += 1
		return imported

	def _parse_csv_amount(self, value):
		from .models import parse_amount

		return parse_amount(value or "")

	def _parse_csv_date(self, row):
		from datetime import date

		if row.get("fecha_inicio"):
			from .models import parse_date
			return parse_date(row.get("fecha_inicio"))
		return date(int(row.get("anio") or 0), int(row.get("mes") or 0), int(row.get("dia") or 0))

	def _parse_csv_duration(self, value):
		value = (value or "").strip()
		if not value:
			return None
		return int(value)

	def _parse_row_recurrence(self, row):
		recurrence = row.get("recurrencia")
		if isinstance(recurrence, dict):
			return (recurrence.get("tipo") or "unico").strip() or "unico"
		return (recurrence or "unico").strip() or "unico"

	def _parse_row_duration(self, row):
		recurrence = row.get("recurrencia")
		if isinstance(recurrence, dict):
			return self._parse_csv_duration(recurrence.get("duracion_meses"))
		return self._parse_csv_duration(row.get("duracion_meses"))

	def _format_from_path(self, path: str) -> str:
		suffix = os.path.splitext(path)[1].lower()
		if suffix == ".json":
			return "json"
		if suffix in (".xlsx", ".xlsm"):
			return "xlsx"
		return "csv"

	def _find(self, item_id: str) -> CashflowItem | None:
		for item in self._items:
			if item.id == item_id:
				return item
		return None

	def _upsert(self, item: CashflowItem) -> None:
		now = datetime.now().isoformat(timespec="seconds")
		payload = json.dumps(item.to_dict(), ensure_ascii=False, sort_keys=True)
		with self._connect() as connection:
			connection.execute(
				"""
				INSERT INTO cashflow_items (id, payload, created_at, updated_at)
				VALUES (?, ?, ?, ?)
				ON CONFLICT(id) DO UPDATE SET
					payload = excluded.payload,
					updated_at = excluded.updated_at
				""",
				(item.id, payload, now, now),
			)

	def occurrences_for(self, target=None):
		from .recurrence import occurrences_for_month
		from datetime import date

		target = target or date.today()
		cache_key = (self._revision, "all", target.year, target.month)
		cached = self._occurrence_cache.get(cache_key)
		if cached is not None:
			return list(cached)
		occurrences = sorted(occurrences_for_month(self._items, target.year, target.month), key=lambda occurrence: occurrence.due_date)
		self._occurrence_cache[cache_key] = list(occurrences)
		return list(occurrences)

	def occurrences_for_kind(self, kind: str, target=None):
		from .recurrence import occurrences_for_month
		from datetime import date

		target = target or date.today()
		items = self._items_for_kind(kind)
		cache_key = (self._revision, kind, target.year, target.month)
		cached = self._occurrence_cache.get(cache_key)
		if cached is not None:
			return list(cached)
		occurrences = sorted(occurrences_for_month(items, target.year, target.month), key=lambda occurrence: occurrence.due_date)
		self._occurrence_cache[cache_key] = list(occurrences)
		return list(occurrences)

	def pending_for(self, target=None):
		cache_key = (self._revision, "pending-all", getattr(target, "year", None), getattr(target, "month", None))
		cached = self._occurrence_cache.get(cache_key)
		if cached is not None:
			return list(cached)
		occurrences = [occurrence for occurrence in self.occurrences_for(target) if not occurrence.paid]
		self._occurrence_cache[cache_key] = list(occurrences)
		return list(occurrences)

	def paid_for(self, target=None):
		cache_key = (self._revision, "paid-all", getattr(target, "year", None), getattr(target, "month", None))
		cached = self._occurrence_cache.get(cache_key)
		if cached is not None:
			return list(cached)
		occurrences = sorted([occurrence for occurrence in self.occurrences_for(target) if occurrence.paid], key=lambda occurrence: occurrence.due_date, reverse=True)
		self._occurrence_cache[cache_key] = list(occurrences)
		return list(occurrences)

	def pending_payments_for(self, target=None):
		cache_key = (self._revision, ITEM_KIND_PAYMENT, "pending", getattr(target, "year", None), getattr(target, "month", None))
		cached = self._occurrence_cache.get(cache_key)
		if cached is not None:
			return list(cached)
		occurrences = [occurrence for occurrence in self.occurrences_for_kind(ITEM_KIND_PAYMENT, target) if not occurrence.paid]
		self._occurrence_cache[cache_key] = list(occurrences)
		return list(occurrences)

	def paid_payments_for(self, target=None):
		cache_key = (self._revision, ITEM_KIND_PAYMENT, "paid", getattr(target, "year", None), getattr(target, "month", None))
		cached = self._occurrence_cache.get(cache_key)
		if cached is not None:
			return list(cached)
		occurrences = sorted([occurrence for occurrence in self.occurrences_for_kind(ITEM_KIND_PAYMENT, target) if occurrence.paid], key=lambda occurrence: occurrence.due_date, reverse=True)
		self._occurrence_cache[cache_key] = list(occurrences)
		return list(occurrences)

	def pending_incomes_for(self, target=None):
		cache_key = (self._revision, ITEM_KIND_INCOME, "pending", getattr(target, "year", None), getattr(target, "month", None))
		cached = self._occurrence_cache.get(cache_key)
		if cached is not None:
			return list(cached)
		occurrences = [occurrence for occurrence in self.occurrences_for_kind(ITEM_KIND_INCOME, target) if not occurrence.paid]
		self._occurrence_cache[cache_key] = list(occurrences)
		return list(occurrences)

	def paid_incomes_for(self, target=None):
		cache_key = (self._revision, ITEM_KIND_INCOME, "paid", getattr(target, "year", None), getattr(target, "month", None))
		cached = self._occurrence_cache.get(cache_key)
		if cached is not None:
			return list(cached)
		occurrences = sorted([occurrence for occurrence in self.occurrences_for_kind(ITEM_KIND_INCOME, target) if occurrence.paid], key=lambda occurrence: occurrence.due_date, reverse=True)
		self._occurrence_cache[cache_key] = list(occurrences)
		return list(occurrences)

	def pending_collections_for(self, target=None):
		cache_key = (self._revision, ITEM_KIND_COLLECTION, "pending", getattr(target, "year", None), getattr(target, "month", None))
		cached = self._occurrence_cache.get(cache_key)
		if cached is not None:
			return list(cached)
		occurrences = [occurrence for occurrence in self.occurrences_for_kind(ITEM_KIND_COLLECTION, target) if not occurrence.paid]
		self._occurrence_cache[cache_key] = list(occurrences)
		return list(occurrences)

	def paid_collections_for(self, target=None):
		cache_key = (self._revision, ITEM_KIND_COLLECTION, "paid", getattr(target, "year", None), getattr(target, "month", None))
		cached = self._occurrence_cache.get(cache_key)
		if cached is not None:
			return list(cached)
		occurrences = sorted([occurrence for occurrence in self.occurrences_for_kind(ITEM_KIND_COLLECTION, target) if occurrence.paid], key=lambda occurrence: occurrence.due_date, reverse=True)
		self._occurrence_cache[cache_key] = list(occurrences)
		return list(occurrences)

	def mark_paid(self, item_id: str, period: str) -> bool:
		for item in self._items:
			if item.id == item_id:
				changed = item.mark_paid(period)
				if changed:
					self._upsert(item)
					self._touch()
				return changed
		return False

	def mark_pending(self, item_id: str, period: str) -> bool:
		for item in self._items:
			if item.id == item_id:
				changed = item.mark_pending(period)
				if changed:
					self._upsert(item)
					self._touch()
				return changed
		return False
