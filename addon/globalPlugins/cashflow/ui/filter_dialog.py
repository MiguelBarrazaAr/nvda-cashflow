from __future__ import annotations

from datetime import date

import wx
import gui

from .. import sounds
from ..months import MONTH_NAMES


class MonthFilterDialog(wx.Dialog):
	def __init__(self, parent, year=None, month=None):
		super().__init__(parent, title=_("Filtrar mes"), style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER)
		today = date.today()
		self.year = year or today.year
		self.month = month or today.month
		self._build()
		wx.CallAfter(sounds.play, "open")
		self.Fit()

	def _build(self):
		panel = wx.Panel(self)
		sizer = wx.BoxSizer(wx.VERTICAL)
		helper = gui.guiHelper.BoxSizerHelper(panel, sizer=sizer)
		self.yearCtrl = helper.addLabeledControl(_("&Anio:"), wx.SpinCtrl, min=1900, max=2100, initial=self.year)
		self.monthCtrl = helper.addLabeledControl(_("&Mes:"), wx.Choice, choices=MONTH_NAMES)
		self.monthCtrl.SetSelection(self.month - 1)
		row = wx.StdDialogButtonSizer()
		ok = wx.Button(panel, wx.ID_OK, _("&Filtrar"))
		cancel = wx.Button(panel, wx.ID_CANCEL)
		row.AddButton(ok)
		row.AddButton(cancel)
		row.Realize()
		sizer.Add(row, 0, wx.ALL | wx.EXPAND, 12)
		panel.SetSizer(sizer)
		outer = wx.BoxSizer(wx.VERTICAL)
		outer.Add(panel, 1, wx.EXPAND)
		self.SetSizer(outer)
		self.Bind(wx.EVT_BUTTON, self._on_ok, id=wx.ID_OK)
		self.Bind(wx.EVT_CHAR_HOOK, self._on_char_hook)
		self.SetEscapeId(wx.ID_CANCEL)

	def _on_ok(self, event):
		self.year = self.yearCtrl.GetValue()
		self.month = self.monthCtrl.GetSelection() + 1
		self.EndModal(wx.ID_OK)

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
