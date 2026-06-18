from __future__ import annotations

from array import array
import os
import tempfile
import threading
import wave
import winsound

from logHandler import log

from . import settings


_BASE_DIR = os.path.join(os.path.dirname(__file__), "sounds")
_FILES = {
	"show": "show.wav",
	"hide": "hide.wav",
	"open": "open.wav",
	"close": "close.wav",
	"confirm": "Confirm.wav",
	"mark": "mark.wav",
	"pending": "pendind.wav",
	"delete": "delete.wav",
	"error": "Error.wav",
}
_LOW_VOLUME = {"mark", "pending", "delete"}
_VOLUME_CACHE = {}
_VOLUME_LOCK = threading.Lock()


def _scaled_copy(path: str, volume: float) -> str:
	cache_key = (path, volume)
	with _VOLUME_LOCK:
		cached = _VOLUME_CACHE.get(cache_key)
		if cached and os.path.exists(cached):
			return cached
	try:
		with wave.open(path, "rb") as source:
			params = source.getparams()
			frames = source.readframes(source.getnframes())
		if params.sampwidth == 1:
			samples = bytearray(frames)
			for index, sample in enumerate(samples):
				scaled = int((sample - 128) * volume)
				samples[index] = max(0, min(255, scaled + 128))
			scaled = bytes(samples)
		elif params.sampwidth == 2:
			samples = array("h")
			samples.frombytes(frames)
			for index, sample in enumerate(samples):
				scaled = int(sample * volume)
				samples[index] = max(-32768, min(32767, scaled))
			scaled = samples.tobytes()
		elif params.sampwidth == 4:
			samples = array("i")
			samples.frombytes(frames)
			for index, sample in enumerate(samples):
				scaled = int(sample * volume)
				samples[index] = max(-(2**31), min(2**31 - 1, scaled))
			scaled = samples.tobytes()
		else:
			return path
		fd, temp_path = tempfile.mkstemp(prefix="cashflow_", suffix=".wav")
		os.close(fd)
		with wave.open(temp_path, "wb") as target:
			target.setparams(params)
			target.writeframes(scaled)
	except Exception:
		log.debugWarning("No se pudo reducir el volumen de un sonido de Cashflow", exc_info=True)
		return path
	with _VOLUME_LOCK:
		_VOLUME_CACHE[cache_key] = temp_path
	return temp_path


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
		if name in _LOW_VOLUME:
			path = _scaled_copy(path, 0.3)
		winsound.PlaySound(path, winsound.SND_FILENAME | winsound.SND_ASYNC)
	except Exception:
		log.exception("No se pudo reproducir el sonido de Cashflow")
