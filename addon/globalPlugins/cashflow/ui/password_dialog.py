from __future__ import annotations

import wx

from .. import sounds


class PasswordDialog(wx.Dialog):
	def __init__(self, parent, title, prompt):
		super().__init__(parent, title=title, style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER)
		self.password = ""
		panel = wx.Panel(self)
		sizer = wx.BoxSizer(wx.VERTICAL)
		sizer.Add(wx.StaticText(panel, label=prompt), 0, wx.ALL | wx.EXPAND, 12)
		self.passwordCtrl = wx.TextCtrl(panel, style=wx.TE_PASSWORD)
		sizer.Add(self.passwordCtrl, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM | wx.EXPAND, 12)
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
		self.Bind(wx.EVT_CHAR_HOOK, self._on_char_hook)
		self.SetEscapeId(wx.ID_CANCEL)
		wx.CallAfter(sounds.play, "open")

	def _on_ok(self, event):
		self.password = self.passwordCtrl.GetValue()
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
