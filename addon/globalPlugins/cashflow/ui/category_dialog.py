from __future__ import annotations

import wx

import addonHandler

from ..categories import get_categories


addonHandler.initTranslation()


class CategoryManagerDialog(wx.Dialog):
	def __init__(self, parent, store):
		super().__init__(parent, title=_("Gestionar categorías"), style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER)
		self._store = store
		self._build()
		self.Fit()

	def _build(self):
		sizer = wx.BoxSizer(wx.VERTICAL)
		self.listBox = wx.ListBox(self, choices=get_categories(self._store))
		sizer.Add(self.listBox, 1, wx.ALL | wx.EXPAND, 12)
		buttons = wx.StdDialogButtonSizer()
		closeButton = wx.Button(self, wx.ID_CLOSE, _("&Cerrar"))
		buttons.AddButton(closeButton)
		buttons.Realize()
		sizer.Add(buttons, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM | wx.ALIGN_RIGHT, 12)
		self.SetSizer(sizer)
		self.SetEscapeId(wx.ID_CLOSE)
		self.Bind(wx.EVT_BUTTON, lambda event: self.EndModal(wx.ID_CLOSE), closeButton)
