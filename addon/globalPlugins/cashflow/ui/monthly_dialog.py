from __future__ import annotations

import wx

from ..formatting import format_amount


class MonthlyPaymentsDialog(wx.Dialog):
	def __init__(self, parent, title, occurrences, kind, paid):
		super().__init__(parent, title=title, style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER)
		self.selectedAction = None
		self._occurrences = occurrences
		self._kind = kind
		self._paid = paid
		self._build()
		self.Bind(wx.EVT_CHAR_HOOK, self._on_char_hook)
		self.Fit()

	def _build(self):
		sizer = wx.BoxSizer(wx.VERTICAL)
		self.listBox = wx.ListBox(self, choices=self._choices())
		self.listBox.Bind(wx.EVT_CONTEXT_MENU, lambda event: self._open_context())
		self.listBox.Bind(wx.EVT_LISTBOX_DCLICK, lambda event: self._open_context())
		sizer.Add(self.listBox, 1, wx.ALL | wx.EXPAND, 12)
		row = wx.BoxSizer(wx.HORIZONTAL)
		mark_label = _("Marcar como &pendiente") if self._paid else _("Marcar como &realizado")
		for label, action in (
			(mark_label, "mark_pending" if self._paid else "mark_paid"),
			(_("&Editar"), "edit"),
			(_("&Eliminar"), "delete"),
		):
			button = wx.Button(self, label=label)
			button.Enable(bool(self._occurrences))
			button.Bind(wx.EVT_BUTTON, lambda event, current=action: self._finish_selected(current))
			row.Add(button, 0, wx.RIGHT, 8)
		sizer.Add(row, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM | wx.ALIGN_RIGHT, 12)
		self.SetSizer(sizer)
		if self._occurrences:
			self.listBox.SetSelection(0)
		self.listBox.SetFocus()

	def _choices(self):
		if not self._occurrences:
			return [_("No hay elementos para mostrar.")]
		return [self._format(occurrence) for occurrence in self._occurrences]

	def _format(self, occurrence):
		item = occurrence.item
		status = _("realizado") if occurrence.paid else _("pendiente")
		return _("{name}, {date}, {amount}, categoria {category}, {status}").format(
			name=item.name,
			date=occurrence.due_date.isoformat(),
			amount=format_amount(item.amount),
			category=item.category,
			status=status,
		)

	def _open_context(self):
		index = self.listBox.GetSelection()
		if index == wx.NOT_FOUND or index >= len(self._occurrences):
			return
		menu = wx.Menu()
		actions = []
		if self._paid:
			actions.append(("mark_pending", _("Marcar como pendiente")))
		else:
			actions.append(("mark_paid", _("Marcar como realizado")))
		actions.extend([
			("edit", _("Editar")),
			("delete", _("Eliminar")),
		])
		for action, label in actions:
			item = menu.Append(wx.ID_ANY, label)
			self.Bind(wx.EVT_MENU, lambda event, current=action: self._finish((current, index)), item)
		self.PopupMenu(menu)
		menu.Destroy()

	def _finish(self, action):
		self.selectedAction = action
		self.EndModal(wx.ID_OK)

	def _finish_selected(self, action):
		index = self.listBox.GetSelection()
		if index == wx.NOT_FOUND or index >= len(self._occurrences):
			return
		self._finish((action, index))

	def _on_char_hook(self, event):
		key_code = event.GetKeyCode()
		if key_code == wx.WXK_ESCAPE:
			self.EndModal(wx.ID_CLOSE)
			return
		if key_code in (wx.WXK_RETURN, wx.WXK_NUMPAD_ENTER):
			self._open_context()
			return
		if key_code in (wx.WXK_DELETE, wx.WXK_NUMPAD_DELETE):
			self._finish_selected("delete")
			return
		if key_code == wx.WXK_SPACE:
			self._finish_selected("mark_pending" if self._paid else "mark_paid")
			return
		if key_code in (ord("E"), ord("e")):
			self._finish_selected("edit")
			return
		event.Skip()

	def _focused_list_key(self):
		focused = wx.Window.FindFocus()
		if focused is self.listBox:
			return "list"
		return "list"
