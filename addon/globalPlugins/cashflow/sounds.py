from __future__ import annotations

import os
import winsound

from logHandler import log

from . import settings


_BASE_DIR = os.path.join(os.path.dirname(__file__), "sounds")
_FILES = {
	"show": "Show.wav",
	"close": "close.wav",
	"confirm": "Confirm.wav",
	"error": "Error.wav",
	"open": "open.wav",
}


def play(name: str) -> None:
	if not settings.sounds_enabled():
		return
	file_name = _FILES.get(name)
	if not file_name:
		return
	path = os.path.join(_BASE_DIR, file_name)
	if not os.path.exists(path):
		return
	try:
		winsound.PlaySound(path, winsound.SND_FILENAME | winsound.SND_ASYNC)
	except Exception:
		log.exception("No se pudo reproducir el sonido de Cashflow")
