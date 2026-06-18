from __future__ import annotations


ADDON_NAME = "cashflow"
ADDON_SUMMARY = "Cashflow"
ADDON_DESCRIPTION = "Gestor accesible de pagos para NVDA."
ADDON_VERSION = "0.6.4"
ADDON_AUTHOR = "Miguel Barraza"
ADDON_EMAIL = "miguelbarraza2015@gmail.com"
ADDON_URL = "https://www.miguelbarraza.com.ar"


def display_name() -> str:
	return f"{ADDON_SUMMARY} {ADDON_VERSION}"
