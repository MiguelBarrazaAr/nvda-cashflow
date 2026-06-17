from __future__ import annotations

import wx

from ..formatting import format_amount
from ..models import ITEM_KIND_COLLECTION, ITEM_KIND_PAYMENT
from ..models import ITEM_KIND_INCOME


class MainDialog(wx.Dialog):
	def __init__(self, parent, data=None, on_action=None, selected_kind=ITEM_KIND_PAYMENT, available_kinds=None):
		super().__init__(parent, title=_("Cashflow"), style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER)
		self.selectedAction = None
		self._on_action = on_action
		self._available_kinds = available_kinds or [ITEM_KIND_PAYMENT, ITEM_KIND_COLLECTION, ITEM_KIND_INCOME]
		self._data = data or {
			ITEM_KIND_PAYMENT: {"pending": None, "paid": None},
			ITEM_KIND_COLLECTION: {"pending": None, "paid": None},
			ITEM_KIND_INCOME: {"pending": None, "paid": None},
		}
		self._selected_kind = selected_kind
		self._lists = {}
		self._build()
		self.Bind(wx.EVT_CHAR_HOOK, self._on_char_hook)
		self.Fit()

	def _build(self):
		panel = wx.Panel(self)
		sizer = wx.BoxSizer(wx.VERTICAL)
		self.kindLabel = wx.StaticText(panel, label=_("Tipo:"))
		sizer.Add(self.kindLabel, 0, wx.LEFT | wx.RIGHT | wx.TOP, 12)
		self._kind_labels = [self._kind_label(kind) for kind in self._available_kinds]
		self.kindList = wx.ListBox(
			panel,
			choices=self._kind_labels,
			style=wx.LB_SINGLE,
		)
		self.kindList.SetName(_("Tipos de movimiento"))
		self.kindList.Bind(wx.EVT_LISTBOX, self._on_kind_changed)
		self.kindList.Bind(wx.EVT_KEY_DOWN, self._on_kind_key_down)
		sizer.Add(self.kindList, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM | wx.EXPAND, 12)

		self._add_list(panel, sizer, "pending", _("Pendientes:"), self._data_for_selected()["pending"])
		self._add_list(panel, sizer, "paid", _("Realizados:"), self._data_for_selected()["paid"])
		self.manageButton = wx.Button(panel, label=_("&Gestionar"))
		self.manageButton.Bind(wx.EVT_BUTTON, lambda event: self._finish(("manage", self._selected_kind)))
		sizer.Add(self.manageButton, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM | wx.EXPAND, 12)

		panel.SetSizer(sizer)
		outer = wx.BoxSizer(wx.VERTICAL)
		outer.Add(panel, 1, wx.EXPAND)
		self.SetSizer(outer)
		self._set_kind_selection(self._selected_kind)
		self._refresh_view()
		self._lists["pending"][0].SetFocus()

	def _add_list(self, parent, sizer, key, label, occurrences):
		sizer.Add(wx.StaticText(parent, label=label), 0, wx.LEFT | wx.RIGHT | wx.TOP, 12)
		list_box = wx.ListBox(parent, choices=self._choices(occurrences))
		list_box.SetName(label.replace(":", ""))
		list_box.Bind(wx.EVT_LISTBOX_DCLICK, lambda event, current=key: self._open_context(current))
		list_box.Bind(wx.EVT_CONTEXT_MENU, lambda event, current=key: self._open_context(current))
		list_box.Bind(wx.EVT_KEY_DOWN, lambda event, current=key: self._on_list_key_down(event, current))
		sizer.Add(list_box, 1, wx.LEFT | wx.RIGHT | wx.BOTTOM | wx.EXPAND, 12)
		if occurrences:
			list_box.SetSelection(0)
		self._lists[key] = (list_box, occurrences)

	def _set_kind_selection(self, kind):
		if kind not in self._available_kinds:
			kind = self._available_kinds[0]
		index = self._available_kinds.index(kind)
		self.kindList.SetSelection(index)
		self._selected_kind = kind

	def _kind_label(self, kind):
		if kind == ITEM_KIND_COLLECTION:
			return _("Cobros")
		if kind == ITEM_KIND_INCOME:
			return _("Ingresos")
		return _("Pagos")

	def _data_for_selected(self):
		return self._data.get(self._selected_kind, {"pending": None, "paid": None})

	def _on_kind_changed(self, event):
		selection = self.kindList.GetSelection()
		self._selected_kind = self._available_kinds[selection]
		self._refresh_view()
		event.Skip()

	def _refresh_view(self):
		data = self._data_for_selected()
		self.kindLabel.SetLabel(_("Tipo: {kind}").format(kind=self._kind_label(self._selected_kind)))
		self._lists["pending"][0].Set(self._choices(data["pending"]))
		self._lists["paid"][0].Set(self._choices(data["paid"]))
		if data["pending"]:
			self._lists["pending"][0].SetSelection(0)
		elif data["paid"]:
			self._lists["paid"][0].SetSelection(0)
		self.Layout()

	def _choices(self, occurrences):
		if occurrences is None:
			return [_("Cargando datos.")]
		if not occurrences:
			return [_("No hay elementos para mostrar.")]
		return [self._format_occurrence(occurrence) for occurrence in occurrences]

	def set_data(self, data):
		self._data = data
		self._refresh_view()

	def get_data(self):
		return self._data_for_selected()

	def get_selected_kind(self):
		return self._selected_kind

	def _format_occurrence(self, occurrence):
		item = occurrence.item
		return _("{name}, {date}, {amount}, categoria {category}").format(
			name=item.name,
			date=occurrence.due_date.isoformat(),
			amount=format_amount(item.amount),
			category=item.category,
		)

	def _open_context(self, key):
		list_box, occurrences = self._lists[key]
		if not occurrences:
			return
		index = list_box.GetSelection()
		if index == wx.NOT_FOUND or index >= len(occurrences):
			return
		is_paid = key.startswith("paid")
		menu = wx.Menu()
		actions = []
		if is_paid:
			actions.append(("mark_pending", _("Marcar como pendiente")))
		else:
			actions.append(("mark_paid", _("Marcar como realizado")))
		actions.extend([
			("edit", _("Editar")),
			("delete", _("Eliminar")),
		])
		for action, label in actions:
			item = menu.Append(wx.ID_ANY, label)
			self.Bind(wx.EVT_MENU, lambda event, current=action: self._finish((current, key, index)), item)
		self.PopupMenu(menu)
		menu.Destroy()

	def _on_char_hook(self, event):
		key_code = event.GetKeyCode()
		if key_code == wx.WXK_ESCAPE:
			self.EndModal(wx.ID_CLOSE)
			return
		event.Skip()

	def _on_kind_key_down(self, event):
		key_code = event.GetKeyCode()
		if key_code in (wx.WXK_RETURN, wx.WXK_NUMPAD_ENTER):
			self._refresh_view()
			return
		event.Skip()

	def _on_list_key_down(self, event, key):
		key_code = event.GetKeyCode()
		if key_code in (wx.WXK_RETURN, wx.WXK_NUMPAD_ENTER):
			self._open_context(key)
			return
		if key_code in (wx.WXK_DELETE, wx.WXK_NUMPAD_DELETE):
			self._finish_selected("delete", key)
			return
		if key_code == wx.WXK_SPACE:
			self._finish_selected("mark_pending" if key.startswith("paid") else "mark_paid", key)
			return
		if key_code in (ord("E"), ord("e")):
			self._finish_selected("edit", key)
			return
		event.Skip()

	def _focused_list_key(self):
		focused = wx.Window.FindFocus()
		for key, (list_box, occurrences) in self._lists.items():
			if focused is list_box:
				return key
		return None

	def _finish_selected(self, action, key):
		list_box, occurrences = self._lists[key]
		if not occurrences:
			return
		index = list_box.GetSelection()
		if index == wx.NOT_FOUND or index >= len(occurrences):
			return
		self._finish((action, key, index))

	def _finish(self, action):
		if self._on_action and action and action[0] != "manage":
			if self._on_action(action, self):
				return
		self.selectedAction = action
		self.EndModal(wx.ID_OK)
