from __future__ import annotations

MONTH_NAMES = [
	"enero",
	"febrero",
	"marzo",
	"abril",
	"mayo",
	"junio",
	"julio",
	"agosto",
	"septiembre",
	"octubre",
	"noviembre",
	"diciembre",
]

DISPLAY_MONTH_NAMES = list(reversed(MONTH_NAMES))


def month_name(month: int) -> str:
	if 1 <= month <= 12:
		return MONTH_NAMES[month - 1]
	return str(month)


def format_month_year(year: int, month: int) -> str:
	return f"{month_name(month)} de {year}"


def format_full_date(day: int, month: int, year: int) -> str:
	return f"{day} de {month_name(month)} de {year}"
