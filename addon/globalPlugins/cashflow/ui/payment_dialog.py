from __future__ import annotations

from datetime import date, timedelta

import wx

import gui

from .. import sounds
from ..models import (
	CashflowItem,
	ITEM_KIND_COLLECTION,
	ITEM_KIND_INCOME,
	ITEM_KIND_PAYMENT,
	RECURRENCE_MONTHLY,
	RECURRENCE_ONCE,
	SUGGESTED_CATEGORIES,
	parse_amount,
)


class PaymentDialog(wx.Dialog):
	def __init__(self, parent, kind=ITEM_KIND_PAYMENT, item: CashflowItem | None = None):
		self._kind = kind
		self._item = item
		title = self._title()
		super().__init__(parent, title=title, style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER)
		self.payment: CashflowItem | None = None
		self._build()
		self.SetEscapeId(wx.ID_CANCEL)
		self.nameCtrl.SetFocus()
		self.Fit()

	def _title(self):
		if self._kind == ITEM_KIND_COLLECTION:
			return _("Editar cobro") if self._item else _("Agregar cobro")
		if self._kind == ITEM_KIND_INCOME:
			return _("Editar ingreso") if self._item else _("Agregar ingreso")
		return _("Editar pago") if self._item else _("Agregar pago")

	def _build(self):
		panel = wx.Panel(self)
		sizer = wx.BoxSizer(wx.VERTICAL)
		helper = gui.guiHelper.BoxSizerHelper(panel, sizer=sizer)

		if self._kind == ITEM_KIND_COLLECTION:
			name_label = _("&Nombre del cobro:")
		elif self._kind == ITEM_KIND_INCOME:
			name_label = _("&Nombre del ingreso:")
		else:
			name_label = _("&Nombre del pago:")
		today = date.today()
		self.nameCtrl = helper.addLabeledControl(name_label, wx.TextCtrl)
		self.amountCtrl = helper.addLabeledControl(_("&Importe:"), wx.TextCtrl)
		self.yearCtrl = helper.addLabeledControl(_("&Anio:"), wx.SpinCtrl, min=1900, max=2100, initial=today.year)
		self.monthCtrl = helper.addLabeledControl(_("&Mes:"), wx.SpinCtrl, min=1, max=12, initial=today.month)
		self.dayCtrl = helper.addLabeledControl(_("&Dia:"), wx.SpinCtrl, min=1, max=31, initial=today.day)
		self.categoryCtrl = helper.addLabeledControl(
			_("&Categoria:"),
			wx.ComboBox,
			choices=SUGGESTED_CATEGORIES,
			style=wx.CB_DROPDOWN,
		)
		self.categoryCtrl.SetValue("Otros")
		self.recurrenceChoice = helper.addLabeledControl(
			_("&Recurrencia:"),
			wx.Choice,
			choices=[_("Unico"), _("Mensual")],
		)
		self.recurrenceChoice.SetSelection(0)
		self.durationCtrl = helper.addLabeledControl(
			_("Duracion en &meses para pagos mensuales, vacio para indefinida:"),
			wx.TextCtrl,
		)
		self._load_item()
		self._set_accessible_names()
		self._update_duration_state()
		self.recurrenceChoice.Bind(wx.EVT_CHOICE, self._on_recurrence_changed)

		buttons = wx.StdDialogButtonSizer()
		okButton = wx.Button(panel, wx.ID_OK)
		cancelButton = wx.Button(panel, wx.ID_CANCEL)
		buttons.AddButton(okButton)
		buttons.AddButton(cancelButton)
		buttons.Realize()
		sizer.Add(buttons, 0, wx.ALL | wx.EXPAND, 12)
		panel.SetSizer(sizer)
		outer = wx.BoxSizer(wx.VERTICAL)
		outer.Add(panel, 1, wx.EXPAND)
		self.SetSizer(outer)
		self.Bind(wx.EVT_BUTTON, self._on_ok, id=wx.ID_OK)

	def _load_item(self):
		if not self._item:
			return
		self.nameCtrl.SetValue(self._item.name)
		self.amountCtrl.SetValue(str(self._item.amount).replace(".", ","))
		self.yearCtrl.SetValue(self._item.start_date.year)
		self.monthCtrl.SetValue(self._item.start_date.month)
		self.dayCtrl.SetValue(self._item.start_date.day)
		self.categoryCtrl.SetValue(self._item.category)
		self.recurrenceChoice.SetSelection(1 if self._item.recurrence == RECURRENCE_MONTHLY else 0)
		if self._item.duration_months is not None:
			self.durationCtrl.SetValue(str(self._item.duration_months))

	def _set_accessible_names(self):
		if self._kind == ITEM_KIND_COLLECTION:
			name = _("Nombre del cobro")
		elif self._kind == ITEM_KIND_INCOME:
			name = _("Nombre del ingreso")
		else:
			name = _("Nombre del pago")
		for control, name in (
			(self.nameCtrl, name),
			(self.amountCtrl, _("Importe")),
			(self.yearCtrl, _("Anio")),
			(self.monthCtrl, _("Mes")),
			(self.dayCtrl, _("Dia")),
			(self.categoryCtrl, _("Categoria")),
			(self.recurrenceChoice, _("Recurrencia")),
			(self.durationCtrl, _("Duracion en meses para pagos mensuales")),
		):
			control.SetName(name)

	def _on_recurrence_changed(self, event):
		self._update_duration_state()
		event.Skip()

	def _update_duration_state(self):
		is_monthly = self.recurrenceChoice.GetSelection() == 1
		self.durationCtrl.Enable(is_monthly)
		if not is_monthly:
			self.durationCtrl.SetValue("")

	def _on_ok(self, event):
		name = self.nameCtrl.GetValue().strip()
		if not name:
			sounds.play("error")
			wx.MessageBox(_("El nombre es obligatorio."), _("Cashflow"), wx.OK | wx.ICON_ERROR, self)
			self.nameCtrl.SetFocus()
			return
		try:
			amount = parse_amount(self.amountCtrl.GetValue())
		except ValueError as exc:
			sounds.play("error")
			wx.MessageBox(str(exc), _("Cashflow"), wx.OK | wx.ICON_ERROR, self)
			return
		try:
			start_date = date(self.yearCtrl.GetValue(), self.monthCtrl.GetValue(), self.dayCtrl.GetValue())
		except ValueError:
			sounds.play("error")
			wx.MessageBox(_("La fecha no es valida."), _("Cashflow"), wx.OK | wx.ICON_ERROR, self)
			return
		if self._needs_confirmation_for_date(start_date):
			sounds.play("open")
			if gui.messageBox(
				_("La fecha elegida es pasada o muy futura. Desea continuar?"),
				_("Confirmar fecha"),
				wx.YES_NO | wx.YES_DEFAULT | wx.ICON_QUESTION,
				self,
			) != wx.YES:
				return
		recurrence = RECURRENCE_MONTHLY if self.recurrenceChoice.GetSelection() == 1 else RECURRENCE_ONCE
		duration_months = None
		if recurrence == RECURRENCE_MONTHLY and self.durationCtrl.GetValue().strip():
			try:
				duration_months = int(self.durationCtrl.GetValue().strip())
			except ValueError:
				sounds.play("error")
				wx.MessageBox(_("La duracion debe ser un numero entero."), _("Cashflow"), wx.OK | wx.ICON_ERROR, self)
				self.durationCtrl.SetFocus()
				return
			if duration_months <= 0:
				sounds.play("error")
				wx.MessageBox(_("La duracion debe ser mayor que cero."), _("Cashflow"), wx.OK | wx.ICON_ERROR, self)
				self.durationCtrl.SetFocus()
				return
		category = self.categoryCtrl.GetValue().strip() or "Otros"
		values = dict(
			name=name,
			amount=amount,
			start_date=start_date,
			category=category,
			recurrence=recurrence,
			duration_months=duration_months,
			kind=self._kind,
			order=self._item.order if self._item else 0,
			records=list(self._item.records) if self._item else [],
		)
		if self._item:
			values["id"] = self._item.id
		self.payment = CashflowItem(**values)
		self.EndModal(wx.ID_OK)

	def _needs_confirmation_for_date(self, start_date):
		today = date.today()
		if start_date < today:
			return True
		if start_date > today + timedelta(days=365):
			return True
		return False
