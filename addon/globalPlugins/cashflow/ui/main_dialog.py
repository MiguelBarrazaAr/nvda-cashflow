from __future__ import annotations

import time

import wx

from logHandler import log

from .. import sounds
from ..formatting import format_amount
from ..models import ITEM_KIND_COLLECTION, ITEM_KIND_INCOME, ITEM_KIND_PAYMENT


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
		self._load_kind_data = None
		self._requested_load_kinds = set()
		self._show_sound_played = False
		self._open_started_at = None
		self._active_list_key = None
		self._busy = False
		self._last_key_code = None
		self._last_key_at = 0.0
		self._last_action_key = None
		self._last_action_at = 0.0
		self._lists = {}
		self._build()
		self.Bind(wx.EVT_SHOW, self._on_show)
		self.Bind(wx.EVT_CHAR_HOOK, self._on_char_hook)
		self.Fit()

	def _build(self):
		panel = wx.Panel(self)
		sizer = wx.BoxSizer(wx.VERTICAL)

		self.kindLabel = wx.StaticText(panel, label=_("Tipo:"))
		sizer.Add(self.kindLabel, 0, wx.LEFT | wx.RIGHT | wx.TOP, 12)

		self.kindCtrl = wx.Choice(panel, choices=[self._kind_label(kind) for kind in self._available_kinds])
		self.kindCtrl.SetName(_("Tipos de movimiento"))
		self.kindCtrl.Bind(wx.EVT_CHOICE, self._on_kind_changed)
		sizer.Add(self.kindCtrl, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM | wx.EXPAND, 12)

		self.loadingText = wx.StaticText(panel, label=_("Cargando datos..."))
		sizer.Add(self.loadingText, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 12)

		self._add_list(panel, sizer, "pending", _("Pendientes:"))
		self._add_list(panel, sizer, "paid", _("Realizados:"))

		self.manageButton = wx.Button(panel, label=_("&Gestionar"))
		self.manageButton.Bind(wx.EVT_BUTTON, lambda event: self._finish(("manage", self._selected_kind)))
		sizer.Add(self.manageButton, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM | wx.EXPAND, 12)

		panel.SetSizer(sizer)
		outer = wx.BoxSizer(wx.VERTICAL)
		outer.Add(panel, 1, wx.EXPAND)
		self.SetSizer(outer)
		self._set_kind_selection(self._selected_kind)
		self._refresh_view()

	def _add_list(self, parent, sizer, key, label):
		sizer.Add(wx.StaticText(parent, label=label), 0, wx.LEFT | wx.RIGHT | wx.TOP, 12)
		list_box = wx.ListBox(parent, choices=[_("Cargando datos.")])
		list_box.SetName(label.replace(":", ""))
		list_box.Bind(wx.EVT_SET_FOCUS, lambda event, current=key: self._set_active_list(current, event))
		list_box.Bind(wx.EVT_LISTBOX, lambda event, current=key: self._set_active_list(current))
		list_box.Bind(wx.EVT_LISTBOX_DCLICK, lambda event, current=key: self._open_context(current))
		list_box.Bind(wx.EVT_CONTEXT_MENU, lambda event, current=key: self._open_context(current))
		sizer.Add(list_box, 1, wx.LEFT | wx.RIGHT | wx.BOTTOM | wx.EXPAND, 12)
		self._lists[key] = {"ctrl": list_box, "occurrences": []}

	def _set_kind_selection(self, kind):
		if kind not in self._available_kinds:
			kind = self._available_kinds[0]
		self._selected_kind = kind
		self.kindCtrl.SetSelection(self._available_kinds.index(kind))

	def _kind_label(self, kind):
		if kind == ITEM_KIND_COLLECTION:
			return _("Cobros")
		if kind == ITEM_KIND_INCOME:
			return _("Ingresos")
		return _("Pagos")

	def _data_for_selected(self):
		return self._data.get(self._selected_kind, {"pending": None, "paid": None})

	def _on_kind_changed(self, event):
		selection = self.kindCtrl.GetSelection()
		log.info("cashflow kind changed selection=%s", selection)
		if 0 <= selection < len(self._available_kinds):
			self._selected_kind = self._available_kinds[selection]
			self._set_active_list(None)
			self._refresh_view()
			self._request_load(self._selected_kind)
		event.Skip()

	def _refresh_view(self):
		data = self._data_for_selected()
		loading = data["pending"] is None or data["paid"] is None
		log.info(
			"cashflow refresh kind=%s pending=%s paid=%s loading=%s active=%s",
			self._selected_kind,
			data["pending"] is None,
			data["paid"] is None,
			loading,
			self._active_list_key,
		)
		self.loadingText.Show(loading)
		self.kindLabel.SetLabel(_("Tipo: {kind}").format(kind=self._kind_label(self._selected_kind)))
		self._populate_list("pending", data["pending"])
		self._populate_list("paid", data["paid"])
		if self._active_list_key not in self._lists or not self._lists[self._active_list_key]["occurrences"]:
			self._active_list_key = self._first_available_list_key()
		self.Layout()

	def _populate_list(self, key, occurrences):
		list_box = self._lists[key]["ctrl"]
		self._lists[key]["occurrences"] = list(occurrences or [])
		list_box.Set(self._choices_for_occurrences(occurrences))
		if list_box.GetCount():
			list_box.SetSelection(0)

	def _choices_for_occurrences(self, occurrences):
		if occurrences is None:
			return [_("Cargando datos.")]
		if not occurrences:
			return [_("No hay elementos para mostrar.")]
		return [self._format_occurrence(occurrence) for occurrence in occurrences]

	def _format_occurrence(self, occurrence):
		item = occurrence.item
		return _("{name}, {date}, {amount}, categoria {category}").format(
			name=item.name,
			date=occurrence.due_date.isoformat(),
			amount=format_amount(item.amount),
			category=item.category,
		)

	def set_data(self, data):
		self._data = data
		self._refresh_view()

	def set_kind_data(self, kind, data):
		if self._data.get(kind) == data:
			log.info("cashflow set kind data skipped kind=%s reason=unchanged", kind)
			return
		self._data[kind] = data
		self._requested_load_kinds.discard(kind)
		if kind == self._selected_kind:
			self._refresh_view()
			if self._open_started_at is not None:
				log.info("Cashflow main dialog data ready in %.3fs", time.monotonic() - self._open_started_at)

	def set_kind_loader(self, loader):
		self._load_kind_data = loader

	def get_data(self):
		return self._data_for_selected()

	def get_selected_kind(self):
		return self._selected_kind

	def _open_context(self, key):
		log.info("cashflow open context list=%s", key)
		occurrences = self._lists[key]["occurrences"]
		if not occurrences:
			log.info("cashflow open context ignored list=%s reason=empty", key)
			return
		index = self._selected_index(key)
		if index == wx.NOT_FOUND or index >= len(occurrences):
			log.info("cashflow open context ignored list=%s reason=no-selection", key)
			return
		is_paid = key == "paid"
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
		self.set_busy(True)
		try:
			self.PopupMenu(menu)
		finally:
			menu.Destroy()
			self._lists[key]["ctrl"].SetFocus()
			self.set_busy(False)
		log.info("cashflow open context closed list=%s index=%s", key, index)

	def _set_active_list(self, key, event=None):
		self._active_list_key = key
		log.info("cashflow active list=%s", key)
		if event is not None:
			event.Skip()

	def _focused_list_key(self):
		focused = wx.Window.FindFocus()
		for key, value in self._lists.items():
			if focused is value["ctrl"]:
				return key
		return None

	def _event_list_key(self, event):
		source = event.GetEventObject()
		for key, value in self._lists.items():
			if source is value["ctrl"]:
				return key
		return self._focused_list_key()

	def _current_list_key(self):
		focused = self._focused_list_key()
		if focused:
			return focused
		if self._active_list_key in self._lists and self._lists[self._active_list_key]["occurrences"]:
			return self._active_list_key
		return self._first_available_list_key()

	def _first_available_list_key(self):
		for key in ("pending", "paid"):
			if self._lists[key]["occurrences"]:
				return key
		return None

	def _selected_index(self, key):
		list_box = self._lists[key]["ctrl"]
		index = list_box.GetSelection()
		if index == wx.NOT_FOUND and self._lists[key]["occurrences"]:
			list_box.SetSelection(0)
			return 0
		return index

	def _finish_selected(self, action, key):
		log.info("cashflow finish selected action=%s list=%s", action, key)
		occurrences = self._lists[key]["occurrences"]
		if not occurrences:
			log.info("cashflow finish selected ignored action=%s list=%s reason=empty", action, key)
			return
		index = self._selected_index(key)
		if index == wx.NOT_FOUND or index >= len(occurrences):
			log.info("cashflow finish selected ignored action=%s list=%s reason=index", action, key)
			return
		self._finish((action, key, index))

	def _finish(self, action):
		log.info("cashflow finish action=%s", action)
		if self._on_action and action:
			if self._on_action(action, self):
				log.info("cashflow finish handled action=%s", action)
				return
		self.selectedAction = action
		self.EndModal(wx.ID_OK)
		log.info("cashflow finish closed modal action=%s", action)

	def set_busy(self, busy):
		self._busy = busy

	def _request_load(self, kind):
		if kind in self._requested_load_kinds:
			log.info("cashflow request load skipped kind=%s reason=already-requested", kind)
			return
		if self._load_kind_data is None:
			log.info("cashflow request load skipped kind=%s reason=no-loader", kind)
			return
		if not self._needs_load(kind):
			log.info("cashflow request load skipped kind=%s reason=loaded", kind)
			return
		self._requested_load_kinds.add(kind)
		self.loadingText.SetLabel(_("Cargando datos..."))
		log.info("cashflow request load kind=%s", kind)
		self._load_kind_data(kind)

	def _needs_load(self, kind):
		data = self._data.get(kind, {"pending": None, "paid": None})
		return data["pending"] is None or data["paid"] is None

	def set_open_started_at(self, started_at):
		self._open_started_at = started_at

	def set_kind_load_failed(self, kind):
		self._requested_load_kinds.discard(kind)
		if kind == self._selected_kind:
			self._data[kind] = {"pending": [], "paid": []}
			self._refresh_view()

	def _on_show(self, event):
		if event.IsShown():
			if not self._show_sound_played:
				self._show_sound_played = True
				if self._open_started_at is not None:
					log.info("Cashflow main dialog shown in %.3fs", time.monotonic() - self._open_started_at)
				wx.CallAfter(sounds.play, "show")
			self._request_load(self._selected_kind)
			wx.CallAfter(self._focus_default)
		event.Skip()

	def _focus_default(self):
		key = self._current_list_key()
		if key in self._lists and self._lists[key]["ctrl"].GetCount():
			self._lists[key]["ctrl"].SetFocus()
			return
		self.kindCtrl.SetFocus()

	def _on_char_hook(self, event):
		key_code = event.GetKeyCode()
		focused = wx.Window.FindFocus()
		current_key = self._event_list_key(event)
		now = time.monotonic()
		action_keys = {
			wx.WXK_RETURN,
			wx.WXK_NUMPAD_ENTER,
			wx.WXK_SPACE,
			wx.WXK_DELETE,
			wx.WXK_NUMPAD_DELETE,
			ord("E"),
			ord("e"),
			ord("I"),
			ord("i"),
		}
		if self._busy and key_code != wx.WXK_ESCAPE:
			log.info("cashflow dialog key ignored reason=busy key=%s", key_code)
			return True
		if self._last_key_code == key_code and (now - self._last_key_at) < 0.05:
			log.info(
				"cashflow dialog key ignored duplicate key=%s focus=%s current=%s active=%s delta=%.3f",
				key_code,
				type(focused).__name__ if focused else None,
				current_key,
				self._active_list_key,
				now - self._last_key_at,
			)
			return True
		self._last_key_code = key_code
		self._last_key_at = now
		if key_code in action_keys and event.IsAutoRepeat():
			log.info(
				"cashflow dialog action ignored auto-repeat key=%s focus=%s current=%s active=%s",
				key_code,
				type(focused).__name__ if focused else None,
				current_key,
				self._active_list_key,
			)
			return True
		if key_code in action_keys and self._last_action_key == key_code and (now - self._last_action_at) < 0.25:
			log.info(
				"cashflow dialog action ignored duplicate key=%s focus=%s current=%s active=%s delta=%.3f",
				key_code,
				type(focused).__name__ if focused else None,
				current_key,
				self._active_list_key,
				now - self._last_action_at,
			)
			return True
		log.info(
			"cashflow dialog key=%s focus=%s current=%s active=%s",
			key_code,
			type(focused).__name__ if focused else None,
			current_key,
			self._active_list_key,
		)
		if key_code == wx.WXK_ESCAPE:
			sounds.play("hide")
			self.EndModal(wx.ID_CLOSE)
			return True
		if focused is self.kindCtrl and key_code in (wx.WXK_RETURN, wx.WXK_NUMPAD_ENTER):
			self._request_load(self._selected_kind)
			return True
		if current_key is None:
			if key_code in (ord("I"), ord("i")):
				self._last_action_key = key_code
				self._last_action_at = now
				self._finish(("add", self._selected_kind))
				return True
			event.Skip()
			return False
		if key_code in (wx.WXK_RETURN, wx.WXK_NUMPAD_ENTER):
			self._last_action_key = key_code
			self._last_action_at = now
			self._set_active_list(current_key)
			self._open_context(current_key)
			return True
		if key_code in (wx.WXK_DELETE, wx.WXK_NUMPAD_DELETE):
			self._last_action_key = key_code
			self._last_action_at = now
			self._set_active_list(current_key)
			self._finish_selected("delete", current_key)
			return True
		if key_code == wx.WXK_SPACE:
			self._last_action_key = key_code
			self._last_action_at = now
			self._set_active_list(current_key)
			self._finish_selected("mark_pending" if current_key == "paid" else "mark_paid", current_key)
			return True
		if key_code in (ord("E"), ord("e")):
			self._last_action_key = key_code
			self._last_action_at = now
			self._set_active_list(current_key)
			self._finish_selected("edit", current_key)
			return True
		if key_code in (ord("I"), ord("i")):
			self._last_action_key = key_code
			self._last_action_at = now
			self._finish(("add", self._selected_kind))
			return True
		event.Skip()
		return False
