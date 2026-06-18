from __future__ import annotations

from datetime import date, timedelta

import wx

import gui
import ui as nvda_ui

from .. import sounds
from ..categories import get_categories
from ..models import (
	CashflowItem,
	ITEM_KIND_COLLECTION,
	ITEM_KIND_INCOME,
	ITEM_KIND_PAYMENT,
	RECURRENCE_MONTHLY,
	RECURRENCE_ONCE,
	parse_amount,
)
from ..months import DISPLAY_MONTH_NAMES, format_full_date
from .category_dialog import CategoryManagerDialog


class PaymentDialog(wx.Dialog):
	def __init__(self, parent, kind=ITEM_KIND_PAYMENT, item: CashflowItem | None = None, store=None):
		self._kind = kind
		self._item = item
		self._store = store
		title = self._title()
		super().__init__(parent, title=title, style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER)
		self.payment: CashflowItem | None = None
		self._build()
		wx.CallAfter(sounds.play, "open")
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
		self.dayCtrl = helper.addLabeledControl(_("&Dia:"), wx.SpinCtrl, min=1, max=31, initial=today.day)
		self.monthCtrl = helper.addLabeledControl(_("&Mes:"), wx.Choice, choices=DISPLAY_MONTH_NAMES)
		self.monthCtrl.SetSelection(len(DISPLAY_MONTH_NAMES) - today.month)
		self.yearCtrl = helper.addLabeledControl(_("&Anio:"), wx.SpinCtrl, min=1900, max=2100, initial=today.year)
		self.categoryCtrl = helper.addLabeledControl(
			_("&Categoria:"),
			wx.ComboBox,
			choices=get_categories(),
			style=wx.CB_DROPDOWN,
		)
		self.categoryCtrl.SetValue("Otros")
		self.categoryCtrl.Bind(wx.EVT_KEY_DOWN, self._on_category_key_down)
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
		self.Bind(wx.EVT_CHAR_HOOK, self._on_char_hook)

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
		self.monthCtrl.SetSelection(len(DISPLAY_MONTH_NAMES) - self._item.start_date.month)
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
			(self.dayCtrl, _("Dia")),
			(self.monthCtrl, _("Mes")),
			(self.yearCtrl, _("Anio")),
			(self.categoryCtrl, _("Categoria")),
			(self.recurrenceChoice, _("Recurrencia")),
			(self.durationCtrl, _("Duracion en meses para pagos mensuales")),
		):
			control.SetName(name)

	def _on_recurrence_changed(self, event):
		self._update_duration_state()
		event.Skip()

	def _on_char_hook(self, event):
		key_code = event.GetKeyCode()
		if key_code == wx.WXK_ESCAPE:
			sounds.play("close")
			self.EndModal(wx.ID_CANCEL)
			return
		if key_code in (wx.WXK_RETURN, wx.WXK_NUMPAD_ENTER):
			self._on_ok(event)
			return
		event.Skip()

	def _update_duration_state(self):
		is_monthly = self.recurrenceChoice.GetSelection() == 1
		self.durationCtrl.Enable(is_monthly)
		if not is_monthly:
			self.durationCtrl.SetValue("")

	def _refresh_categories(self):
		current = self.categoryCtrl.GetValue().strip()
		categories = get_categories()
		self.categoryCtrl.Clear()
		for category in categories:
			self.categoryCtrl.Append(category)
		if current and current in categories:
			self.categoryCtrl.SetValue(current)
		elif categories:
			self.categoryCtrl.SetValue(categories[0])
		else:
			self.categoryCtrl.SetValue("Otros")

	def _open_category_manager(self):
		if self._store is None:
			return
		dialog = CategoryManagerDialog(self, self._store)
		try:
			dialog.ShowModal()
		finally:
			dialog.Destroy()
		self._refresh_categories()
		self.categoryCtrl.SetFocus()

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
			selection = self.monthCtrl.GetSelection()
			month = len(DISPLAY_MONTH_NAMES) - selection if selection != wx.NOT_FOUND else date.today().month
			start_date = date(self.yearCtrl.GetValue(), month, self.dayCtrl.GetValue())
		except ValueError:
			sounds.play("error")
			wx.MessageBox(_("La fecha no es valida."), _("Cashflow"), wx.OK | wx.ICON_ERROR, self)
			return
		if self._needs_confirmation_for_date(start_date):
			sounds.play("open")
			if gui.messageBox(
				self._date_confirmation_message(start_date),
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
		kind_label = {
			ITEM_KIND_COLLECTION: _("cobro"),
			ITEM_KIND_INCOME: _("ingreso"),
			ITEM_KIND_PAYMENT: _("pago"),
		}.get(self._kind, _("elemento"))
		nvda_ui.message(_("{kind} {name} ha sido agregado.").format(kind=kind_label, name=name))
		self.EndModal(wx.ID_OK)

	def _needs_confirmation_for_date(self, start_date):
		today = date.today()
		if start_date < today:
			return True
		if start_date > today + timedelta(days=365):
			return True
		return False

	def _date_confirmation_message(self, start_date):
		today = date.today()
		if start_date < today:
			return _("Esta fecha es pasada. Deseas guardarla igual?")
		if start_date > today + timedelta(days=365):
			return _("Detecté que esta fecha esta bastante lejana: {date}. La quieres guardar igual?").format(
				date=format_full_date(start_date.day, start_date.month, start_date.year)
			)
		return _("Deseas guardar esta fecha?")

	def _on_category_key_down(self, event):
		key_code = event.GetKeyCode()
		if key_code in (wx.WXK_RETURN, wx.WXK_NUMPAD_ENTER):
			self._open_category_manager()
			return
		event.Skip()
