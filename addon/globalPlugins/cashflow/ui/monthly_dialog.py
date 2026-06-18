from __future__ import annotations

import wx

from logHandler import log

from .. import sounds
from ..formatting import format_amount


class MonthlyPaymentsDialog(wx.Dialog):
	def __init__(self, parent, title, occurrences, kind, paid):
		super().__init__(parent, title=title, style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER)
		self.selectedAction = None
		self._occurrences = occurrences
		self._kind = kind
		self._paid = paid
		self._busy = False
		self._build()
		self.Bind(wx.EVT_CHAR_HOOK, self._on_char_hook)
		wx.CallAfter(sounds.play, "open")
		self.Fit()

	def _build(self):
		sizer = wx.BoxSizer(wx.VERTICAL)
		self.listBox = wx.ListBox(self, choices=self._choices())
		self.listBox.Bind(wx.EVT_CONTEXT_MENU, lambda event: self._open_context())
		self.listBox.Bind(wx.EVT_LISTBOX_DCLICK, lambda event: self._open_context())
		sizer.Add(self.listBox, 1, wx.ALL | wx.EXPAND, 12)
		button_sizer = wx.StdDialogButtonSizer()
		mark_label = _("Marcar como &pendiente") if self._paid else _("Marcar como &realizado")
		self.markButton = wx.Button(self, label=mark_label)
		self.markButton.Enable(bool(self._occurrences))
		self.markButton.Bind(wx.EVT_BUTTON, lambda event: self._finish_selected("mark_pending" if self._paid else "mark_paid"))
		self.newButton = wx.Button(self, label=_("&Nuevo"))
		self.newButton.Bind(wx.EVT_BUTTON, lambda event: self._finish(("add",)))
		closeButton = wx.Button(self, wx.ID_CANCEL, _("&Cerrar"))
		button_sizer.AddButton(self.markButton)
		button_sizer.AddButton(self.newButton)
		button_sizer.AddButton(closeButton)
		button_sizer.Realize()
		sizer.Add(button_sizer, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM | wx.EXPAND, 12)
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
		if index == wx.NOT_FOUND and self._occurrences:
			self.listBox.SetSelection(0)
			index = 0
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
		self._busy = True
		try:
			self.PopupMenu(menu)
		finally:
			menu.Destroy()
			self._busy = False

	def _finish(self, action):
		self.selectedAction = action
		self.EndModal(wx.ID_OK)

	def _finish_selected(self, action):
		index = self.listBox.GetSelection()
		if index == wx.NOT_FOUND and self._occurrences:
			self.listBox.SetSelection(0)
			index = 0
		if index == wx.NOT_FOUND or index >= len(self._occurrences):
			return
		self._finish((action, index))

	def _on_char_hook(self, event):
		key_code = event.GetKeyCode()
		log.info("cashflow monthly key=%s focus=%s count=%d", key_code, type(wx.Window.FindFocus()).__name__ if wx.Window.FindFocus() else None, len(self._occurrences))
		if self._busy and key_code != wx.WXK_ESCAPE:
			return
		if key_code == wx.WXK_ESCAPE:
			sounds.play("close")
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
