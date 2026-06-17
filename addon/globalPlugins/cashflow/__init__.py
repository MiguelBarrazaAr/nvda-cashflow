from __future__ import annotations

from datetime import date
from decimal import Decimal
from html import escape
import importlib
import json
import os
import threading

import addonHandler
import globalPluginHandler
import gui
import scriptHandler
import wx
from logHandler import log
from scriptHandler import script

from . import settings, sounds
from .backup import decrypt_payload, encrypt_payload
from .formatting import format_amount, item_kind_plural
from .models import CashflowItem, ITEM_KIND_COLLECTION, ITEM_KIND_INCOME, ITEM_KIND_PAYMENT
from .storage import CashflowStore
from .ui.filter_dialog import MonthFilterDialog
from .ui.kind_summary_dialog import KindSummaryDialog
from .ui.manage_dialog import ManageItemsDialog
from .ui.main_dialog import MainDialog
from .ui.monthly_dialog import MonthlyPaymentsDialog
from .ui.payment_dialog import PaymentDialog
from .ui.password_dialog import PasswordDialog


addonHandler.initTranslation()


CATEGORY = _("Cashflow")


class GlobalPlugin(globalPluginHandler.GlobalPlugin):
	def __init__(self):
		super().__init__()
		settings.initialize()
		self._store = CashflowStore()
		self._menu = None
		self._menuItems = []
		self._timers = []
		wx.CallAfter(self._add_tools_menu)

	def terminate(self):
		try:
			if self._menu is not None:
				gui.mainFrame.sysTrayIcon.toolsMenu.Remove(self._menu)
		except Exception:
			log.exception("No se pudo quitar el menu de Cashflow")
		settings.terminate()
		super().terminate()

	def _add_tools_menu(self):
		try:
			submenu = wx.Menu()
			self._append_menu_item(submenu, _("Gestor Cashflow"), self._on_open)

			pagos_menu = wx.Menu()
			self._append_menu_item(pagos_menu, _("Pendientes"), lambda event: self._open_main(ITEM_KIND_PAYMENT))
			self._append_menu_item(pagos_menu, _("Nuevo"), self._on_add_payment)
			self._append_menu_item(pagos_menu, _("Gestionar"), self._on_manage_payments)
			self._append_submenu(submenu, _("Pagos"), pagos_menu)

			cobros_menu = wx.Menu()
			self._append_menu_item(cobros_menu, _("Pendientes"), lambda event: self._open_main(ITEM_KIND_COLLECTION))
			self._append_menu_item(cobros_menu, _("Nuevo"), self._on_add_income)
			self._append_menu_item(cobros_menu, _("Gestionar"), self._on_manage_incomes)
			self._append_submenu(submenu, _("Cobros"), cobros_menu)

			ingresos_menu = wx.Menu()
			self._append_menu_item(ingresos_menu, _("Pendientes"), lambda event: self._open_main(ITEM_KIND_INCOME))
			self._append_menu_item(ingresos_menu, _("Nuevo"), lambda event: self._add_item(ITEM_KIND_INCOME))
			self._append_menu_item(ingresos_menu, _("Gestionar"), lambda event: self._manage_items(ITEM_KIND_INCOME))
			self._append_submenu(submenu, _("Ingresos"), ingresos_menu)

			backup_menu = wx.Menu()
			self._append_menu_item(backup_menu, _("Guardar copia de seguridad"), self._on_save_backup)
			self._append_menu_item(backup_menu, _("Recuperar copia de seguridad"), self._on_restore_backup)
			self._append_submenu(submenu, _("Copia de seguridad"), backup_menu)

			self._append_menu_item(submenu, _("Ver informe"), self._on_show_report)
			self._append_menu_item(submenu, _("Ayuda"), self._on_help)
			self._menu = gui.mainFrame.sysTrayIcon.toolsMenu.AppendSubMenu(submenu, _("Cashflow"))
		except Exception:
			log.exception("No se pudo agregar el menu de Cashflow")

	def _append_menu_item(self, menu, label, handler):
		item = menu.Append(wx.ID_ANY, label)
		gui.mainFrame.sysTrayIcon.Bind(wx.EVT_MENU, handler, item)
		self._menuItems.append(item)

	def _append_submenu(self, menu, label, submenu):
		item = menu.AppendSubMenu(submenu, label)
		self._menuItems.append(item)

	def _on_open(self, event):
		self._open_main(ITEM_KIND_PAYMENT)

	def _on_add_payment(self, event):
		self._add_payment()

	def _on_manage_payments(self, event):
		self._manage_items(ITEM_KIND_PAYMENT)

	def _on_add_income(self, event):
		self._add_item(ITEM_KIND_COLLECTION)

	def _on_manage_incomes(self, event):
		self._manage_items(ITEM_KIND_COLLECTION)

	def _on_help(self, event):
		self._show_help()

	def _on_show_report(self, event):
		self._show_report()

	def _on_save_backup(self, event):
		self._save_backup()

	def _on_restore_backup(self, event):
		self._restore_backup()

	def _open_main(self, selected_kind=ITEM_KIND_PAYMENT):
		available_kinds = self._available_kinds()
		if not available_kinds:
			self._show_error(_("Deberas activar en configuracion la casilla de cobros, ingresos o pagos para gestionar tus finanzas."))
			return
		if selected_kind not in available_kinds:
			selected_kind = available_kinds[0]
		sounds.play("show")
		dialog = MainDialog(gui.mainFrame, on_action=self._handle_live_main_action, selected_kind=selected_kind, available_kinds=available_kinds)
		def load_data():
			try:
				data = self._main_data()
			except Exception:
				log.exception("No se pudieron cargar los datos de Cashflow")
				wx.CallAfter(self._show_error, _("No se pudieron cargar los datos de Cashflow."))
				return
			wx.CallAfter(self._set_main_data, dialog, data)
		threading.Thread(target=load_data, daemon=True).start()
		def callback(result):
			if result != wx.ID_OK:
				sounds.play("close")
				return
			self._handle_main_action(dialog.selectedAction, dialog.get_data(), dialog.get_selected_kind())
		gui.runScriptModalDialog(dialog, callback)

	def _main_data(self):
		return {
			ITEM_KIND_PAYMENT: self._main_data_for_kind(ITEM_KIND_PAYMENT),
			ITEM_KIND_COLLECTION: self._main_data_for_kind(ITEM_KIND_COLLECTION),
			ITEM_KIND_INCOME: self._main_data_for_kind(ITEM_KIND_INCOME),
		}

	def _available_kinds(self):
		kinds = []
		if settings.payments_enabled():
			kinds.append(ITEM_KIND_PAYMENT)
		if settings.collections_enabled():
			kinds.append(ITEM_KIND_COLLECTION)
		if settings.incomes_enabled():
			kinds.append(ITEM_KIND_INCOME)
		return kinds

	def _main_data_for_kind(self, kind):
		if kind == ITEM_KIND_PAYMENT:
			return {
				"pending": self._store.pending_payments_for(),
				"paid": self._store.paid_payments_for(),
			}
		if kind == ITEM_KIND_COLLECTION:
			return {
				"pending": self._store.pending_collections_for(),
				"paid": self._store.paid_collections_for(),
			}
		return {
			"pending": self._store.pending_incomes_for(),
			"paid": self._store.paid_incomes_for(),
		}

	def _set_main_data(self, dialog, data):
		if dialog and not dialog.IsBeingDeleted():
			dialog.set_data(data)

	def _show_error(self, message):
		sounds.play("error")
		gui.messageBox(message, _("Cashflow"), wx.OK | wx.ICON_ERROR, gui.mainFrame)

	def _message(self, text):
		try:
			gui.speech.speakMessage(text)
		except Exception:
			log.debugWarning("No se pudo anunciar mensaje de Cashflow", exc_info=True)

	def _schedule_reopen(self, reopen):
		if reopen:
			self._schedule_call(reopen)

	def _schedule_call(self, func, *args):
		timer = None
		def run():
			try:
				func(*args)
			finally:
				if timer in self._timers:
					self._timers.remove(timer)
		timer = wx.CallLater(350, run)
		self._timers.append(timer)

	def _add_payment(self):
		self._add_item(ITEM_KIND_PAYMENT)

	def _add_item(self, kind, reopen=None):
		if kind not in self._available_kinds():
			self._show_error(_("Deberas activar en configuracion la casilla de cobros, ingresos o pagos para gestionar tus finanzas."))
			return
		dialog = PaymentDialog(gui.mainFrame, kind=kind)
		def callback(result):
			if result == wx.ID_OK and dialog.payment is not None:
				self._store.add_payment(dialog.payment)
				self._message(_("Elemento agregado."))
				sounds.play("confirm")
			self._schedule_reopen(reopen)
		gui.runScriptModalDialog(dialog, callback)

	def _edit_item(self, item, reopen=None):
		dialog = PaymentDialog(gui.mainFrame, kind=item.kind, item=item)
		def callback(result):
			if result == wx.ID_OK and dialog.payment is not None:
				self._store.update_item(dialog.payment)
				self._message(_("Elemento actualizado."))
				sounds.play("confirm")
			self._schedule_reopen(reopen)
		gui.runScriptModalDialog(dialog, callback)

	def _show_pending(self):
		self._show_occurrences(_("Pagos pendientes del mes"), self._store.pending_payments_for(), ITEM_KIND_PAYMENT, paid=False)

	def _show_paid(self):
		self._show_occurrences(_("Pagos realizados del mes"), self._store.paid_payments_for(), ITEM_KIND_PAYMENT, paid=True)

	def _show_pending_incomes(self):
		self._show_occurrences(_("Cobros pendientes del mes"), self._store.pending_collections_for(), ITEM_KIND_COLLECTION, paid=False)

	def _show_paid_incomes(self):
		self._show_occurrences(_("Cobros realizados del mes"), self._store.paid_collections_for(), ITEM_KIND_COLLECTION, paid=True)

	def _show_occurrences(self, title, occurrences, kind, paid):
		dialog = MonthlyPaymentsDialog(gui.mainFrame, title, occurrences, kind, paid)
		def callback(result):
			if result != wx.ID_OK:
				return
			action = dialog.selectedAction
			if not action:
				return
			self._handle_occurrence_action(
				action[0],
				occurrences[action[1]],
				reopen=lambda: self._show_occurrences(title, self._occurrences_for(kind, paid), kind, paid),
			)
		gui.runScriptModalDialog(dialog, callback)

	def _occurrences_for(self, kind, paid):
		if kind == ITEM_KIND_PAYMENT:
			return self._store.paid_payments_for() if paid else self._store.pending_payments_for()
		if kind == ITEM_KIND_COLLECTION:
			return self._store.paid_collections_for() if paid else self._store.pending_collections_for()
		return self._store.paid_incomes_for() if paid else self._store.pending_incomes_for()

	def _manage_items(self, kind):
		if kind not in self._available_kinds():
			self._show_error(_("Deberas activar en configuracion la casilla de cobros, ingresos o pagos para gestionar tus finanzas."))
			return
		items = self._store.items_for_kind(kind)
		dialog = ManageItemsDialog(gui.mainFrame, kind, items, on_action=lambda action, dlg: self._handle_live_manage_action(action, dlg, kind))
		def callback(result):
			if result != wx.ID_OK:
				sounds.play("close")
				return
		gui.runScriptModalDialog(dialog, callback)

	def _handle_live_manage_action(self, action, dialog, kind):
		name, index = action
		items = dialog._items
		if name == "add":
			self._schedule_call(self._add_item, kind, lambda: dialog.set_items(self._store.items_for_kind(kind)))
			return True
		if name == "edit":
			self._schedule_call(self._edit_item, items[index], lambda: dialog.set_items(self._store.items_for_kind(kind)))
			return True
		if name == "delete":
			if self._delete_item_now(items[index]):
				dialog.set_items(self._store.items_for_kind(kind))
			return True
		if name == "up":
			if self._store.move_item(items[index].id, -1):
				self._message(_("Elemento movido."))
				sounds.play("confirm")
				dialog.set_items(self._store.items_for_kind(kind))
			return True
		if name == "down":
			if self._store.move_item(items[index].id, 1):
				self._message(_("Elemento movido."))
				sounds.play("confirm")
				dialog.set_items(self._store.items_for_kind(kind))
			return True
		if name == "import":
			self._schedule_call(self._import_items, kind, lambda: dialog.set_items(self._store.items_for_kind(kind)))
			return True
		if name == "export":
			self._schedule_call(self._export_items, kind, lambda: dialog.set_items(self._store.items_for_kind(kind)))
			return True
		return False

	def _export_items(self, kind, reopen=None):
		dialog = wx.FileDialog(
			gui.mainFrame,
			message=_("Exportar datos de Cashflow"),
			defaultFile=self._default_export_name(kind),
			wildcard=_("Archivos CSV (*.csv)|*.csv|Archivos JSON (*.json)|*.json|Archivos Excel (*.xlsx)|*.xlsx"),
			style=wx.FD_SAVE | wx.FD_OVERWRITE_PROMPT,
		)
		def callback(result):
			if result == wx.ID_OK:
				try:
					path = self._normalize_export_path(dialog)
					self._store.export_items(kind, path)
					self._message(_("Datos exportados."))
					sounds.play("confirm")
				except Exception:
					log.exception("No se pudieron exportar datos de Cashflow")
					self._show_error(_("No se pudieron exportar los datos."))
			self._schedule_reopen(reopen)
		gui.runScriptModalDialog(dialog, callback)

	def _import_items(self, kind, reopen=None):
		dialog = wx.FileDialog(
			gui.mainFrame,
			message=_("Importar datos de Cashflow"),
			wildcard=_("Archivos CSV (*.csv)|*.csv|Archivos JSON (*.json)|*.json"),
			style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST,
		)
		def callback(result):
			if result == wx.ID_OK:
				try:
					count = self._store.import_items(kind, dialog.GetPath())
					self._message(_("Elementos importados: {count}.").format(count=count))
					sounds.play("confirm")
				except Exception:
					log.exception("No se pudieron importar datos de Cashflow")
					self._show_error(_("No se pudieron importar los datos."))
			self._schedule_reopen(reopen)
		gui.runScriptModalDialog(dialog, callback)

	def _default_export_name(self, kind):
		if kind == ITEM_KIND_PAYMENT:
			return "cashflow_pagos.csv"
		if kind == ITEM_KIND_COLLECTION:
			return "cashflow_cobros.csv"
		return "cashflow_ingresos.csv"

	def _normalize_export_path(self, dialog):
		path = dialog.GetPath()
		ext = os.path.splitext(path)[1].lower()
		if ext:
			return path
		filter_index = dialog.GetFilterIndex()
		extensions = [".csv", ".json", ".xlsx"]
		return path + extensions[min(filter_index, len(extensions) - 1)]

	def _save_backup(self):
		dialog = wx.FileDialog(
			gui.mainFrame,
			message=_("Guardar copia de seguridad"),
			defaultFile="cashflow.data",
			wildcard=_("Archivo de copia de seguridad (*.data)|*.data"),
			style=wx.FD_SAVE | wx.FD_OVERWRITE_PROMPT,
		)
		def callback(result):
			if result != wx.ID_OK:
				return
			password_dialog = PasswordDialog(gui.mainFrame, _("Guardar copia de seguridad"), _("Escribe una contraseña para esta copia de seguridad:"))
			def password_callback(password_result):
				if password_result != wx.ID_OK or not password_dialog.password:
					return
				try:
					payload = {"items": [item.to_dict() for item in self._store.all_items()]}
					blob = encrypt_payload(payload, password_dialog.password)
					with open(dialog.GetPath(), "wb") as file:
						file.write(blob)
					self._message(_("Copia de seguridad guardada. Conserva la contraseña para recuperarla."))
					sounds.play("confirm")
				except Exception:
					log.exception("No se pudo guardar la copia de seguridad")
					self._show_error(_("No se pudo guardar la copia de seguridad."))
			gui.runScriptModalDialog(password_dialog, password_callback)
		gui.runScriptModalDialog(dialog, callback)

	def _restore_backup(self):
		dialog = wx.FileDialog(
			gui.mainFrame,
			message=_("Recuperar copia de seguridad"),
			wildcard=_("Archivo de copia de seguridad (*.data)|*.data"),
			style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST,
		)
		def callback(result):
			if result != wx.ID_OK:
				return
			password_dialog = PasswordDialog(gui.mainFrame, _("Recuperar copia de seguridad"), _("Escribe la contraseña de la copia de seguridad:"))
			def password_callback(password_result):
				if password_result != wx.ID_OK or not password_dialog.password:
					return
				try:
					with open(dialog.GetPath(), "rb") as file:
						payload = decrypt_payload(file.read(), password_dialog.password)
				except Exception as exc:
					log.exception("No se pudo abrir la copia de seguridad")
					self._show_error(str(exc))
					return
				items = [CashflowItem.from_dict(raw) for raw in payload.get("items", [])]
				if gui.messageBox(
					_("Se sobreescribiran todos los datos actuales. Desea continuar?"),
					_("Recuperar copia de seguridad"),
					wx.YES_NO | wx.YES_DEFAULT | wx.ICON_WARNING,
					gui.mainFrame,
				) != wx.YES:
					return
				try:
					self._store.replace_all(items)
					self._message(_("Copia de seguridad recuperada."))
					sounds.play("confirm")
				except Exception:
					log.exception("No se pudo recuperar la copia de seguridad")
					self._show_error(_("No se pudo recuperar la copia de seguridad."))
			gui.runScriptModalDialog(password_dialog, password_callback)
		gui.runScriptModalDialog(dialog, callback)

	def _today_year_month(self):
		today = date.today()
		return today.year, today.month

	def _filter_label(self, year, month):
		return _("Filtro: {month:02d}/{year:04d}").format(month=month, year=year)

	def _kind_summary_data(self, kind, year, month):
		target = date(year, month, 1)
		occurrences = self._store.occurrences_for_kind(kind, target)
		return {
			"pending": [occurrence for occurrence in occurrences if not occurrence.paid],
			"paid": [occurrence for occurrence in occurrences if occurrence.paid],
		}

	def _open_kind_summary(self, kind, year=None, month=None):
		year, month = (year, month) if year and month else self._today_year_month()
		title = _("Cashflow {items}").format(items=item_kind_plural(kind))
		data = self._kind_summary_data(kind, year, month)
		dialog = KindSummaryDialog(
			gui.mainFrame,
			kind,
			title,
			data,
			self._filter_label(year, month),
			on_action=lambda action, dlg: self._handle_live_kind_action(action, dlg, kind, year, month),
		)
		def callback(result):
			if result != wx.ID_OK:
				return
			action = dialog.selectedAction
			if not action:
				return
			if action[0] == "manage":
				self._schedule_call(self._manage_items, kind)
			elif action[0] == "filter":
				self._schedule_call(self._choose_filter, kind)
			elif action[0] == "report":
				self._show_report(year, month)
			elif action[0] == "announce_filter":
				self._message(self._filter_label(year, month))
				self._schedule_call(self._open_kind_summary, kind, year, month)
		gui.runScriptModalDialog(dialog, callback)

	def _handle_live_kind_action(self, action, dialog, kind, year, month):
		data = dialog._data
		name, list_key, index = action
		occurrences = data.get(list_key)
		if not occurrences or index >= len(occurrences):
			return True
		occurrence = occurrences[index]
		if name == "mark_paid":
			if self._mark_occurrence_paid(occurrence):
				dialog.set_data(self._kind_summary_data(kind, year, month))
			return True
		if name == "mark_pending":
			if self._mark_occurrence_pending(occurrence):
				dialog.set_data(self._kind_summary_data(kind, year, month))
			return True
		if name == "delete":
			if self._delete_item_now(occurrence.item):
				dialog.set_data(self._kind_summary_data(kind, year, month))
			return True
		if name == "edit":
			self._schedule_call(self._edit_item, occurrence.item, lambda: dialog.set_data(self._kind_summary_data(kind, year, month)))
			return True
		return False

	def _choose_filter(self, kind):
		year, month = self._today_year_month()
		dialog = MonthFilterDialog(gui.mainFrame, year, month)
		def callback(result):
			if result == wx.ID_OK:
				self._schedule_call(self._open_kind_summary, kind, dialog.year, dialog.month)
		gui.runScriptModalDialog(dialog, callback)

	def _announce_pending(self, kind):
		year, month = self._today_year_month()
		pending = self._kind_summary_data(kind, year, month)["pending"]
		if pending:
			total = self._sum_occurrences(pending)
			self._message(_("{count} pendientes por {amount}.").format(count=len(pending), amount=format_amount(total)))
		else:
			self._message(_("No hay pendientes este mes."))

	def _announce_income_total(self):
		year, month = self._today_year_month()
		paid = self._kind_summary_data(ITEM_KIND_INCOME, year, month)["paid"]
		total = self._sum_occurrences(paid)
		self._message(_("Ingresos del mes: {amount}.").format(amount=format_amount(total)))

	def _sum_occurrences(self, occurrences):
		total = Decimal("0")
		for occurrence in occurrences:
			total += occurrence.item.amount
		return total

	def _show_browseable_html(self, title, html):
		try:
			nvda_ui = importlib.import_module("ui")
			nvda_ui.browseableMessage(html, title=title, isHtml=True)
		except Exception:
			log.exception("No se pudo mostrar HTML de Cashflow")
			self._show_error(_("No se pudo mostrar el informe."))

	def _show_report(self, year=None, month=None):
		year, month = (year, month) if year and month else self._today_year_month()
		html = self._build_report_html(year, month)
		self._show_browseable_html(_("Informe de Cashflow"), html)

	def _build_report_html(self, year, month):
		payment_data = self._kind_summary_data(ITEM_KIND_PAYMENT, year, month)
		collection_data = self._kind_summary_data(ITEM_KIND_COLLECTION, year, month)
		income_data = self._kind_summary_data(ITEM_KIND_INCOME, year, month)
		income_total = self._sum_occurrences(income_data["paid"]) + self._sum_occurrences(income_data["pending"])
		expense_total = self._sum_occurrences(payment_data["paid"])
		final_total = income_total + self._sum_occurrences(collection_data["paid"]) - expense_total
		return (
			f"<h1>Cashflow {month:02d}/{year:04d}</h1>"
			+ "<h2>Montos:</h2>"
			+ f"<p><strong>{escape(_('ingresos'))}:</strong> {escape(format_amount(income_total))}</p>"
			+ f"<p><strong>{escape(_('egresos'))}:</strong> {escape(format_amount(expense_total))}</p>"
			+ f"<p><strong>{escape(_('total'))}:</strong> {escape(format_amount(final_total))}</p>"
			+ self._report_section(_("Pagos"), payment_data)
			+ self._report_section(_("Cobros"), collection_data)
			+ self._report_section(_("Ingresos"), income_data)
		)

	def _report_section(self, title, data):
		pending_total = self._sum_occurrences(data["pending"])
		paid_total = self._sum_occurrences(data["paid"])
		return (
			f"<h2>{escape(title)}</h2>"
			+ f"<p>{escape(_('Pendientes'))}: {len(data['pending'])}, {escape(format_amount(pending_total))}</p>"
			+ f"<p>{escape(_('Realizados'))}: {len(data['paid'])}, {escape(format_amount(paid_total))}</p>"
			+ self._ordered_list(_("Pendientes"), data["pending"])
			+ self._ordered_list(_("Realizados"), data["paid"])
		)

	def _ordered_list(self, title, occurrences):
		if not occurrences:
			return f"<h3>{escape(title)}</h3><p>No hay elementos.</p>"
		items = "".join(
			f"<li>{escape(occurrence.item.name)}: {escape(format_amount(occurrence.item.amount))}, {escape(occurrence.due_date.isoformat())}</li>"
			for occurrence in occurrences
		)
		return f"<h3>{escape(title)}</h3><ol>{items}</ol>"

	def _show_help(self):
		html = """
<h1>Cashflow</h1>
<p>Cashflow ayuda a organizar pagos, cobros e ingresos desde NVDA.</p>
<p>La ventana principal usa un selector de tipo para ver solo pagos, cobros o ingresos, con listas de pendientes y realizados para el elemento elegido.</p>
<p>El menu de herramientas agrupa Gestor Cashflow, Pagos, Cobros, Ingresos, Copia de seguridad, Ver informe y Ayuda.</p>
<h2>Pagos y cobros</h2>
<p>Una pulsacion abre la ventana principal en el tipo elegido. Dos pulsaciones agrega un elemento. Tres pulsaciones anuncia pendientes.</p>
<h2>Ingresos</h2>
<p>Una pulsacion abre la ventana principal en ingresos. Dos pulsaciones agrega un ingreso. Tres pulsaciones anuncia el ingreso del mes.</p>
<h2>Gestores</h2>
<p>Permiten agregar, modificar, eliminar, subir, bajar, importar y exportar en CSV, JSON o Excel.</p>
<h2>Copias de seguridad</h2>
<p>Se pueden guardar copias cifradas en .data con contraseña y recuperarlas sobreescribiendo los datos actuales.</p>
<h2>Configuracion</h2>
<p>Se pueden activar o desactivar pagos, cobros e ingresos desde la categoria de Cashflow en la configuracion de NVDA.</p>
<h2>Teclas</h2>
<p>Enter abre el menu contextual. Suprimir elimina. Espacio marca como realizado o pendiente. E edita. T anuncia el filtro aplicado.</p>
<h2>Fechas</h2>
<p>Si la fecha elegida es pasada o muy futura, Cashflow pide confirmacion antes de guardar.</p>
<h2>Informes</h2>
<p>El informe muestra cantidades y montos de pagos, cobros e ingresos para el mes filtrado.</p>
"""
		self._show_browseable_html(_("Ayuda de Cashflow"), html)

	def _handle_main_action(self, action, data, selected_kind):
		if not action:
			return
		if action[0] == "manage":
			self._schedule_call(self._manage_items, action[1])
			return
		name, key, index = action
		occurrences = data.get(key)
		if not occurrences:
			return
		if index >= len(occurrences):
			return
		self._handle_occurrence_action(name, occurrences[index], reopen=lambda: self._open_main(selected_kind))

	def _handle_live_main_action(self, action, dialog):
		data = dialog.get_data()
		if not action or action[0] == "manage":
			return False
		name, key, index = action
		occurrences = data.get(key)
		if not occurrences or index >= len(occurrences):
			return True
		occurrence = occurrences[index]
		if name == "mark_paid":
			if self._mark_occurrence_paid(occurrence):
				dialog.set_data(self._main_data())
			return True
		if name == "mark_pending":
			if self._mark_occurrence_pending(occurrence):
				dialog.set_data(self._main_data())
			return True
		if name == "delete":
			if self._delete_item_now(occurrence.item):
				dialog.set_data(self._main_data())
			return True
		if name == "edit":
			self._schedule_call(self._edit_item, occurrence.item, lambda: dialog.set_data(self._main_data()))
			return True
		return False

	def _mark_occurrence_paid(self, occurrence):
		if not self._confirm_mark(occurrence.item, _("Marcar como realizado")):
			return False
		if self._store.mark_paid(occurrence.item.id, occurrence.period):
			self._message(_("Marcado como realizado."))
			sounds.play("confirm")
			return True
		return False

	def _mark_occurrence_pending(self, occurrence):
		if not self._confirm_mark(occurrence.item, _("Marcar como pendiente")):
			return False
		if self._store.mark_pending(occurrence.item.id, occurrence.period):
			self._message(_("Marcado como pendiente."))
			sounds.play("confirm")
			return True
		return False

	def _handle_occurrence_action(self, action, occurrence, reopen=None):
		if action == "mark_paid":
			self._mark_occurrence_paid(occurrence)
			self._schedule_reopen(reopen)
		elif action == "mark_pending":
			self._mark_occurrence_pending(occurrence)
			self._schedule_reopen(reopen)
		elif action == "edit":
			self._schedule_call(self._edit_item, occurrence.item, reopen)
		elif action == "delete":
			self._schedule_call(self._delete_item, occurrence.item, reopen)

	def _confirm_mark(self, item, action_label):
		sounds.play("open")
		return gui.messageBox(
			_("{action} {name}?").format(action=action_label, name=item.name),
			_("Confirmar accion"),
			wx.YES_NO | wx.YES_DEFAULT | wx.ICON_QUESTION,
			gui.mainFrame,
		) == wx.YES

	def _delete_item(self, item, reopen=None):
		self._delete_item_now(item)
		self._schedule_reopen(reopen)

	def _delete_item_now(self, item):
		sounds.play("open")
		result = gui.messageBox(
			_("Eliminar {name}?").format(name=item.name),
			_("Confirmar eliminacion"),
			wx.YES_NO | wx.YES_DEFAULT | wx.ICON_WARNING,
			gui.mainFrame,
		)
		if result != wx.YES:
			return False
		if self._store.delete_item(item.id):
			self._message(_("Elemento eliminado."))
			sounds.play("confirm")
			return True
		return False

	@script(
		description=_("1 interface: mostrar gestor de cashflow"),
		category=CATEGORY,
		gesture="kb:NVDA+control+f",
	)
	def script_openCashflow(self, gesture):
		self._open_main(ITEM_KIND_PAYMENT)

	@script(
		description=_("2 informe"),
		category=CATEGORY,
	)
	def script_cashflowReport(self, gesture):
		self._show_report()

	@script(
		description=_("3 cobros, doble pulsacion agrega un nuevo cobro, triple pulsacion anuncia los pendientes"),
		category=CATEGORY,
	)
	def script_cashflowCollections(self, gesture):
		repeat = scriptHandler.getLastScriptRepeatCount()
		if repeat == 0:
			self._open_main(ITEM_KIND_COLLECTION)
		elif repeat == 1:
			self._add_item(ITEM_KIND_COLLECTION)
		else:
			self._announce_pending(ITEM_KIND_COLLECTION)

	@script(
		description=_("4 ingresos, doble pulsacion agrega un nuevo ingreso, triple pulsacion anuncia el total del mes"),
		category=CATEGORY,
	)
	def script_cashflowIncome(self, gesture):
		repeat = scriptHandler.getLastScriptRepeatCount()
		if repeat == 0:
			self._open_main(ITEM_KIND_INCOME)
		elif repeat == 1:
			self._add_item(ITEM_KIND_INCOME)
		else:
			self._announce_income_total()

	@script(
		description=_("5 pagos, doble pulsacion agrega un nuevo pago, triple pulsacion anuncia los pendientes"),
		category=CATEGORY,
	)
	def script_cashflowPayments(self, gesture):
		repeat = scriptHandler.getLastScriptRepeatCount()
		if repeat == 0:
			self._open_main(ITEM_KIND_PAYMENT)
		elif repeat == 1:
			self._add_item(ITEM_KIND_PAYMENT)
		else:
			self._announce_pending(ITEM_KIND_PAYMENT)
