from __future__ import annotations

from decimal import Decimal

from . import settings


def format_amount(amount: Decimal) -> str:
	text = f"{amount:.2f}".replace(".", ",")
	return _("{amount} {currency}").format(amount=text, currency=settings.currency_label())


def item_kind_label(kind: str) -> str:
	if kind == "cobro":
		return _("cobro")
	if kind == "ingreso":
		return _("ingreso")
	return _("pago")


def item_kind_plural(kind: str) -> str:
	if kind == "cobro":
		return _("cobros")
	if kind == "ingreso":
		return _("ingresos")
	return _("pagos")
