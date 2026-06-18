from addon.globalPlugins.cashflow.version import (
	ADDON_AUTHOR,
	ADDON_DESCRIPTION,
	ADDON_EMAIL,
	ADDON_NAME,
	ADDON_SUMMARY,
	ADDON_URL,
	ADDON_VERSION,
)


addon_info = {
	"addon_name": ADDON_NAME,
	"addon_summary": ADDON_SUMMARY,
	"addon_description": ADDON_DESCRIPTION,
	"addon_version": ADDON_VERSION,
	"addon_author": f"{ADDON_AUTHOR} <{ADDON_EMAIL}>",
	"addon_url": ADDON_URL,
	"addon_docFileName": "readme.html",
	"addon_minimumNVDAVersion": "2026.1",
	"addon_lastTestedNVDAVersion": "2026.1",
}
