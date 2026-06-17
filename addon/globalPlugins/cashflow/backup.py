from __future__ import annotations

import hashlib
import hmac
import json
import os
from dataclasses import asdict


MAGIC = b"CFBKP1"
SALT_SIZE = 16
NONCE_SIZE = 16
ITERATIONS = 200_000


def encrypt_payload(payload: dict, password: str) -> bytes:
	data = json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
	salt = os.urandom(SALT_SIZE)
	nonce = os.urandom(NONCE_SIZE)
	key = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, ITERATIONS, dklen=32)
	enc_key = hashlib.sha256(key + b"enc").digest()
	mac_key = hashlib.sha256(key + b"mac").digest()
	ciphertext = _xor_stream(data, enc_key, nonce)
	header = MAGIC + bytes([1]) + salt + nonce + ciphertext
	mac = hmac.new(mac_key, header, hashlib.sha256).digest()
	return header + mac


def decrypt_payload(blob: bytes, password: str) -> dict:
	if not blob.startswith(MAGIC):
		raise ValueError("El archivo no es una copia de seguridad valida.")
	version = blob[len(MAGIC)]
	if version != 1:
		raise ValueError("La copia de seguridad usa una version no soportada.")
	offset = len(MAGIC) + 1
	salt = blob[offset:offset + SALT_SIZE]
	nonce = blob[offset + SALT_SIZE:offset + SALT_SIZE + NONCE_SIZE]
	mac = blob[-32:]
	ciphertext = blob[offset + SALT_SIZE + NONCE_SIZE:-32]
	key = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, ITERATIONS, dklen=32)
	enc_key = hashlib.sha256(key + b"enc").digest()
	mac_key = hashlib.sha256(key + b"mac").digest()
	expected_mac = hmac.new(mac_key, blob[:-32], hashlib.sha256).digest()
	if not hmac.compare_digest(mac, expected_mac):
		raise ValueError("La contraseña es incorrecta o el archivo esta corrupto.")
	data = _xor_stream(ciphertext, enc_key, nonce)
	return json.loads(data.decode("utf-8"))


def _xor_stream(data: bytes, key: bytes, nonce: bytes) -> bytes:
	output = bytearray()
	counter = 0
	index = 0
	while index < len(data):
		block = hmac.new(key, nonce + counter.to_bytes(8, "big"), hashlib.sha256).digest()
		counter += 1
		for byte in block:
			if index >= len(data):
				break
			output.append(data[index] ^ byte)
			index += 1
	return bytes(output)
