from __future__ import annotations

import wx

from ..formatting import format_amount, item_kind_plural


class KindSummaryDialog(wx.Dialog):
	def __init__(self, parent, kind, title, data, filter_label, on_action=None):
		super().__init__(parent, title=title, style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER)
		self.selectedAction = None
		self._kind = kind
		self._data = data
		self._filter_label = filter_label
		self._on_action = on_action
		self._lists = {}
		self._build()
		self.Bind(wx.EVT_CHAR_HOOK, self._on_char_hook)
		self.Fit()

	def _build(self):
		panel = wx.Panel(self)
		sizer = wx.BoxSizer(wx.VERTICAL)
		self.filterText = wx.StaticText(panel, label=self._filter_label)
		sizer.Add(self.filterText, 0, wx.ALL | wx.EXPAND, 12)
		self._add_list(panel, sizer, "pending", _("Pendientes:"), self._data["pending"])
		self._add_list(panel, sizer, "paid", _("Realizados:"), self._data["paid"])
		row = wx.BoxSizer(wx.HORIZONTAL)
		for label, action in (
			(_("&Gestionar"), "manage"),
			(_("&Cambiar filtro"), "filter"),
			(_("Ver &informe"), "report"),
		):
			button = wx.Button(panel, label=label)
			button.Bind(wx.EVT_BUTTON, lambda event, current=action: self._finish((current,)))
			row.Add(button, 0, wx.RIGHT, 8)
		sizer.Add(row, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM | wx.ALIGN_RIGHT, 12)
		panel.SetSizer(sizer)
		outer = wx.BoxSizer(wx.VERTICAL)
		outer.Add(panel, 1, wx.EXPAND)
		self.SetSizer(outer)
		self._lists["pending"][0].SetFocus()

	def _add_list(self, parent, sizer, key, label, occurrences):
		sizer.Add(wx.StaticText(parent, label=label), 0, wx.LEFT | wx.RIGHT | wx.TOP, 12)
		list_box = wx.ListBox(parent, choices=self._choices(occurrences))
		list_box.SetName(label.replace(":", ""))
		list_box.Bind(wx.EVT_CONTEXT_MENU, lambda event, current=key: self._open_context(current))
		list_box.Bind(wx.EVT_LISTBOX_DCLICK, lambda event, current=key: self._open_context(current))
		sizer.Add(list_box, 1, wx.LEFT | wx.RIGHT | wx.BOTTOM | wx.EXPAND, 12)
		if occurrences:
			list_box.SetSelection(0)
		self._lists[key] = (list_box, occurrences)

	def _choices(self, occurrences):
		if not occurrences:
			return [_("No hay elementos para mostrar.")]
		return [
			_("{name}, {date}, {amount}, categoria {category}").format(
				name=occurrence.item.name,
				date=occurrence.due_date.isoformat(),
				amount=format_amount(occurrence.item.amount),
				category=occurrence.item.category,
			)
			for occurrence in occurrences
		]

	def set_data(self, data):
		self._data = data
		for key in ("pending", "paid"):
			list_box, occurrences = self._lists[key]
			new_occurrences = data.get(key, [])
			list_box.Set(self._choices(new_occurrences))
			if new_occurrences:
				list_box.SetSelection(0)
			self._lists[key] = (list_box, new_occurrences)

	def _open_context(self, key):
		list_box, occurrences = self._lists[key]
		if not occurrences:
			return
		index = list_box.GetSelection()
		if index == wx.NOT_FOUND or index >= len(occurrences):
			return
		menu = wx.Menu()
		actions = [("mark_pending", _("Marcar como pendiente"))] if key == "paid" else [("mark_paid", _("Marcar como realizado"))]
		actions.extend([("edit", _("Editar")), ("delete", _("Eliminar"))])
		for action, label in actions:
			item = menu.Append(wx.ID_ANY, label)
			self.Bind(wx.EVT_MENU, lambda event, current=action: self._finish((current, key, index)), item)
		self.PopupMenu(menu)
		menu.Destroy()

	def _focused_list_key(self):
		focused = wx.Window.FindFocus()
		for key, (list_box, occurrences) in self._lists.items():
			if focused is list_box:
				return key
		for key in ("pending", "paid"):
			if self._lists[key][1]:
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

	def _on_char_hook(self, event):
		key = event.GetKeyCode()
		if key == wx.WXK_ESCAPE:
			self.EndModal(wx.ID_CLOSE)
			return
		if key in (ord("T"), ord("t")) or (key == ord("T") and event.GetModifiers() == wx.MOD_CONTROL):
			self._finish(("announce_filter",))
			return
		current = self._focused_list_key()
		if current and key in (wx.WXK_RETURN, wx.WXK_NUMPAD_ENTER):
			self._open_context(current)
			return
		if current and key in (wx.WXK_DELETE, wx.WXK_NUMPAD_DELETE):
			self._finish_selected("delete", current)
			return
		if current and key == wx.WXK_SPACE:
			self._finish_selected("mark_pending" if current == "paid" else "mark_paid", current)
			return
		if current and key in (ord("E"), ord("e")):
			self._finish_selected("edit", current)
			return
		event.Skip()

	def _finish(self, action):
		if self._on_action and action and len(action) > 1:
			if self._on_action(action, self):
				return
		self.selectedAction = action
		self.EndModal(wx.ID_OK)
