from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from uuid import uuid4


RECURRENCE_ONCE = "unico"
RECURRENCE_MONTHLY = "mensual"
ITEM_KIND_PAYMENT = "egreso"
ITEM_KIND_INCOME = "ingreso"
ITEM_KIND_COLLECTION = "cobro"


SUGGESTED_CATEGORIES = [
	"Servicios",
	"Impuestos",
	"Alquiler",
	"Tarjetas",
	"Prestamos",
	"Salud",
	"Educacion",
	"Transporte",
	"Alimentacion",
	"Suscripciones",
	"Otros",
]


@dataclass
class PaymentRecord:
	period: str
	registered_on: date
	amount: Decimal

	def to_dict(self) -> dict:
		return {
			"periodo": self.period,
			"fecha_registro": self.registered_on.isoformat(),
			"importe": str(self.amount),
		}

	@classmethod
	def from_dict(cls, data: dict) -> "PaymentRecord":
		return cls(
			period=data["periodo"],
			registered_on=parse_date(data["fecha_registro"]),
			amount=Decimal(str(data["importe"])),
		)


@dataclass
class CashflowItem:
	name: str
	amount: Decimal
	start_date: date
	category: str = "Otros"
	recurrence: str = RECURRENCE_ONCE
	duration_months: int | None = None
	kind: str = ITEM_KIND_PAYMENT
	order: int = 0
	id: str = field(default_factory=lambda: str(uuid4()))
	records: list[PaymentRecord] = field(default_factory=list)

	def is_paid_for(self, period: str) -> bool:
		return any(record.period == period for record in self.records)

	def mark_paid(self, period: str, registered_on: date | None = None) -> bool:
		if self.is_paid_for(period):
			return False
		self.records.append(
			PaymentRecord(
				period=period,
				registered_on=registered_on or date.today(),
				amount=self.amount,
			)
		)
		return True

	def mark_pending(self, period: str) -> bool:
		before = len(self.records)
		self.records = [record for record in self.records if record.period != period]
		return len(self.records) != before

	def to_dict(self) -> dict:
		return {
			"id": self.id,
			"tipo": self.kind,
			"orden": self.order,
			"nombre": self.name,
			"importe": str(self.amount),
			"categoria": self.category,
			"fecha_inicio": self.start_date.isoformat(),
			"recurrencia": {
				"tipo": self.recurrence,
				"duracion_meses": self.duration_months,
			},
			"pagos_registrados": [record.to_dict() for record in self.records],
		}

	@classmethod
	def from_dict(cls, data: dict) -> "CashflowItem":
		recurrence = data.get("recurrencia", {})
		return cls(
			id=data["id"],
			name=data["nombre"],
			amount=Decimal(str(data["importe"])),
			category=data.get("categoria") or "Otros",
			start_date=parse_date(data["fecha_inicio"]),
			recurrence=recurrence.get("tipo", RECURRENCE_ONCE),
			duration_months=recurrence.get("duracion_meses"),
			kind=data.get("tipo", ITEM_KIND_PAYMENT),
			order=int(data.get("orden", 0)),
			records=[
				PaymentRecord.from_dict(record)
				for record in data.get("pagos_registrados", [])
			],
		)


def parse_amount(value: str) -> Decimal:
	normalized = value.strip().replace(".", "").replace(",", ".")
	if not normalized:
		raise ValueError("El importe es obligatorio.")
	try:
		amount = Decimal(normalized)
	except InvalidOperation as exc:
		raise ValueError("El importe no es valido.") from exc
	if amount <= 0:
		raise ValueError("El importe debe ser mayor que cero.")
	return amount


def parse_date(value: str) -> date:
	try:
		return datetime.strptime(value.strip(), "%Y-%m-%d").date()
	except ValueError as exc:
		raise ValueError("La fecha debe tener formato AAAA-MM-DD.") from exc


def current_period(today: date | None = None) -> str:
	today = today or date.today()
	return f"{today.year:04d}-{today.month:02d}"
