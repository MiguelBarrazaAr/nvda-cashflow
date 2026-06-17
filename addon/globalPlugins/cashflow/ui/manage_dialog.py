from __future__ import annotations

import wx

from ..formatting import format_amount, item_kind_plural


class ManageItemsDialog(wx.Dialog):
	def __init__(self, parent, kind, items, on_action=None):
		super().__init__(parent, title=_("Gestionar {items}").format(items=item_kind_plural(kind)), style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER)
		self.selectedAction = None
		self._kind = kind
		self._items = items
		self._on_action = on_action
		self._build()
		self.Bind(wx.EVT_CHAR_HOOK, self._on_char_hook)
		self.Fit()

	def _build(self):
		sizer = wx.BoxSizer(wx.VERTICAL)
		self.listBox = wx.ListBox(self, choices=self._choices())
		self.listBox.SetName(_("Lista de {items}").format(items=item_kind_plural(self._kind)))
		self.listBox.Bind(wx.EVT_CONTEXT_MENU, lambda event: self._open_context())
		self.listBox.Bind(wx.EVT_LISTBOX_DCLICK, lambda event: self._open_context())
		self.listBox.Bind(wx.EVT_KEY_DOWN, self._on_key_down)
		sizer.Add(self.listBox, 1, wx.ALL | wx.EXPAND, 12)
		row = wx.BoxSizer(wx.HORIZONTAL)
		for label, action in (
			(_("&Agregar"), "add"),
			(_("&Modificar"), "edit"),
			(_("&Eliminar"), "delete"),
			(_("&Importar"), "import"),
			(_("E&xportar"), "export"),
		):
			button = wx.Button(self, label=label)
			button.Bind(wx.EVT_BUTTON, lambda event, current=action: self._finish(current))
			row.Add(button, 0, wx.RIGHT, 8)
		sizer.Add(row, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM | wx.ALIGN_RIGHT, 12)
		self.SetSizer(sizer)
		if self._items:
			self.listBox.SetSelection(0)
		self.listBox.SetFocus()

	def _choices(self):
		if not self._items:
			return [_("No hay elementos cargados.")]
		return [
			_("{name}, {amount}, categoria {category}, desde {date}").format(
				name=item.name,
				amount=format_amount(item.amount),
				category=item.category,
				date=item.start_date.isoformat(),
			)
			for item in self._items
		]

	def set_items(self, items):
		self._items = items
		self.listBox.Set(self._choices())
		if self._items:
			self.listBox.SetSelection(0)

	def _finish(self, action):
		index = self.listBox.GetSelection()
		if action not in ("add", "import", "export") and (index == wx.NOT_FOUND or index >= len(self._items)):
			return
		if self._on_action and self._on_action((action, index), self):
			return
		self.selectedAction = (action, index)
		self.EndModal(wx.ID_OK)

	def _open_context(self):
		menu = wx.Menu()
		index = self.listBox.GetSelection()
		actions = [
			("add", _("Agregar")),
			("edit", _("Modificar")),
			("delete", _("Eliminar")),
			("import", _("Importar")),
			("export", _("Exportar")),
		]
		if self._items and index != wx.NOT_FOUND:
			if index > 0:
				actions.insert(3, ("up", _("Subir")))
			if index < len(self._items) - 1:
				insert_at = 4 if index > 0 else 3
				actions.insert(insert_at, ("down", _("Bajar")))
		has_items = bool(self._items)
		for action, label in actions:
			item = menu.Append(wx.ID_ANY, label)
			if action not in ("add", "import", "export") and not has_items:
				item.Enable(False)
			self.Bind(wx.EVT_MENU, lambda event, current=action: self._finish(current), item)
		self.PopupMenu(menu)
		menu.Destroy()

	def _on_char_hook(self, event):
		key_code = event.GetKeyCode()
		if key_code == wx.WXK_ESCAPE:
			self.EndModal(wx.ID_CLOSE)
			return
		event.Skip()

	def _on_key_down(self, event):
		key_code = event.GetKeyCode()
		if key_code in (wx.WXK_RETURN, wx.WXK_NUMPAD_ENTER):
			self._open_context()
			return
		if key_code in (wx.WXK_DELETE, wx.WXK_NUMPAD_DELETE):
			self._finish("delete")
			return
		if key_code in (ord("I"), ord("i")):
			self._finish("add")
			return
		if key_code in (ord("E"), ord("e")):
			self._finish("edit")
			return
		event.Skip()
