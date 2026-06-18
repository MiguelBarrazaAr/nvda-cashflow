from __future__ import annotations

from .storage import CashflowStore


def get_categories(store: CashflowStore | None = None) -> list[str]:
	categories = set()
	if store is not None:
		for item in store.all_items():
			category = (item.category or "").strip()
			if category:
				categories.add(category)
	if not categories:
		return ["Otros"]
	return sorted(categories, key=str.casefold)
