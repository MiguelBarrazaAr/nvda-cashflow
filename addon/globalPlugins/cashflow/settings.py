from __future__ import annotations

import config
import gui
import wx
from gui import settingsDialogs


SECTION = "cashflow"

CURRENCIES = [
	("pab", "balboas"),
	("ves", "bolivares"),
	("bob", "bolivianos"),
	("crc", "colones costarricenses"),
	("nio", "cordobas"),
	("bzd", "dolares belicenos"),
	("usd", "dolares estadounidenses"),
	("gyd", "dolares guyaneses"),
	("srd", "dolares surinameses"),
	("htg", "gourdes haitianos"),
	("pyg", "guaranies"),
	("hnl", "lempiras"),
	("ars", "pesos argentinos"),
	("clp", "pesos chilenos"),
	("cop", "pesos colombianos"),
	("cup", "pesos cubanos"),
	("dop", "pesos dominicanos"),
	("mxn", "pesos mexicanos"),
	("uyu", "pesos uruguayos"),
	("gtq", "quetzales"),
	("brl", "reales brasilenos"),
	("pen", "soles"),
]


def initialize() -> None:
	config.conf.spec[SECTION] = {
		"enableSounds": "boolean(default=True)",
		"currency": "string(default='ars')",
		"enablePayments": "boolean(default=True)",
		"enableCollections": "boolean(default=True)",
		"enableIncomes": "boolean(default=True)",
	}
	if CashflowSettingsPanel not in settingsDialogs.NVDASettingsDialog.categoryClasses:
		settingsDialogs.NVDASettingsDialog.categoryClasses.append(CashflowSettingsPanel)


def terminate() -> None:
	try:
		settingsDialogs.NVDASettingsDialog.categoryClasses.remove(CashflowSettingsPanel)
	except ValueError:
		pass


def sounds_enabled() -> bool:
	return bool(config.conf[SECTION]["enableSounds"])


def currency_code() -> str:
	return str(config.conf[SECTION]["currency"])


def currency_label() -> str:
	selected = currency_code()
	for code, label in CURRENCIES:
		if code == selected:
			return _(label)
	return _(CURRENCIES[0][1])


def payments_enabled() -> bool:
	return bool(config.conf[SECTION]["enablePayments"])


def collections_enabled() -> bool:
	return bool(config.conf[SECTION]["enableCollections"])


def incomes_enabled() -> bool:
	return bool(config.conf[SECTION]["enableIncomes"])


def any_kind_enabled() -> bool:
	return payments_enabled() or collections_enabled() or incomes_enabled()


class CashflowSettingsPanel(settingsDialogs.SettingsPanel):
	title = _("Cashflow")

	def makeSettings(self, sizer):
		helper = gui.guiHelper.BoxSizerHelper(self, sizer=sizer)
		self.enableSounds = helper.addItem(wx.CheckBox(self, label=_("&Reproducir sonidos de Cashflow")))
		self.enableSounds.SetValue(sounds_enabled())
		self.enablePayments = helper.addItem(wx.CheckBox(self, label=_("&Pagos")))
		self.enablePayments.SetValue(payments_enabled())
		self.enableCollections = helper.addItem(wx.CheckBox(self, label=_("C&obros")))
		self.enableCollections.SetValue(collections_enabled())
		self.enableIncomes = helper.addItem(wx.CheckBox(self, label=_("&Ingresos")))
		self.enableIncomes.SetValue(incomes_enabled())
		self.currencyChoice = helper.addLabeledControl(
			_("&Moneda para anunciar importes:"),
			wx.Choice,
			choices=[_(label) for code, label in CURRENCIES],
		)
		current = currency_code()
		index = next((i for i, (code, label) in enumerate(CURRENCIES) if code == current), 0)
		self.currencyChoice.SetSelection(index)

	def onSave(self):
		config.conf[SECTION]["enableSounds"] = self.enableSounds.GetValue()
		config.conf[SECTION]["enablePayments"] = self.enablePayments.GetValue()
		config.conf[SECTION]["enableCollections"] = self.enableCollections.GetValue()
		config.conf[SECTION]["enableIncomes"] = self.enableIncomes.GetValue()
		config.conf[SECTION]["currency"] = CURRENCIES[self.currencyChoice.GetSelection()][0]
