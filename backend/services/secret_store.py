from __future__ import annotations

import base64
import ctypes
import hashlib
import hmac
import os
import secrets
from pathlib import Path

from ..core.config import DATA_DIR


DPAPI_PREFIX = "dpapi:v1:"
FILE_PREFIX = "file:v1:"
PLAINTEXT_PREFIX = "plain:v1:"


class _DataBlob(ctypes.Structure):
    _fields_ = [("cbData", ctypes.c_uint32), ("pbData", ctypes.POINTER(ctypes.c_ubyte))]


def _blob(value: bytes) -> tuple[_DataBlob, ctypes.Array]:
    buffer = ctypes.create_string_buffer(value)
    pointer = ctypes.cast(buffer, ctypes.POINTER(ctypes.c_ubyte))
    return _DataBlob(len(value), pointer), buffer


def _dpapi_protect(value: bytes) -> bytes:
    if os.name != "nt":
        raise OSError("Windows DPAPI is unavailable")
    crypt32 = ctypes.windll.crypt32
    kernel32 = ctypes.windll.kernel32
    source, source_buffer = _blob(value)
    result = _DataBlob()
    if not crypt32.CryptProtectData(ctypes.byref(source), None, None, None, None, 0, ctypes.byref(result)):
        raise OSError(f"CryptProtectData failed: {ctypes.GetLastError()}")
    try:
        return ctypes.string_at(result.pbData, result.cbData)
    finally:
        kernel32.LocalFree(result.pbData)


def _dpapi_unprotect(value: bytes) -> bytes:
    if os.name != "nt":
        raise OSError("Windows DPAPI is unavailable")
    crypt32 = ctypes.windll.crypt32
    kernel32 = ctypes.windll.kernel32
    source, source_buffer = _blob(value)
    result = _DataBlob()
    if not crypt32.CryptUnprotectData(ctypes.byref(source), None, None, None, None, 0, ctypes.byref(result)):
        raise OSError(f"CryptUnprotectData failed: {ctypes.GetLastError()}")
    try:
        return ctypes.string_at(result.pbData, result.cbData)
    finally:
        kernel32.LocalFree(result.pbData)


def _key_path() -> Path:
    return DATA_DIR / ".secret-key"


def _file_key() -> bytes:
    path = _key_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.is_file():
        value = path.read_bytes()
        if len(value) >= 32:
            return value
    value = secrets.token_bytes(32)
    path.write_bytes(value)
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass
    return value


def _keystream(key: bytes, nonce: bytes, length: int) -> bytes:
    output = bytearray()
    counter = 0
    while len(output) < length:
        output.extend(hmac.new(key, b"short-drama-settings" + nonce + counter.to_bytes(4, "big"), hashlib.sha256).digest())
        counter += 1
    return bytes(output[:length])


def _file_protect(value: bytes) -> bytes:
    key = _file_key()
    nonce = secrets.token_bytes(16)
    ciphertext = bytes(item ^ mask for item, mask in zip(value, _keystream(key, nonce, len(value))))
    tag = hmac.new(key, nonce + ciphertext, hashlib.sha256).digest()
    return nonce + tag + ciphertext


def _file_unprotect(value: bytes) -> bytes:
    if len(value) < 48:
        raise ValueError("密钥数据格式无效")
    key = _file_key()
    nonce, tag, ciphertext = value[:16], value[16:48], value[48:]
    expected = hmac.new(key, nonce + ciphertext, hashlib.sha256).digest()
    if not hmac.compare_digest(tag, expected):
        raise ValueError("密钥校验失败，无法解密")
    return bytes(item ^ mask for item, mask in zip(ciphertext, _keystream(key, nonce, len(ciphertext))))


def is_protected(value: str | None) -> bool:
    return str(value or "").startswith((DPAPI_PREFIX, FILE_PREFIX))


def protect_secret(value: str) -> str:
    if not value:
        return ""
    raw = value.encode("utf-8")
    if os.name == "nt":
        return DPAPI_PREFIX + base64.urlsafe_b64encode(_dpapi_protect(raw)).decode("ascii")
    return FILE_PREFIX + base64.urlsafe_b64encode(_file_protect(raw)).decode("ascii")


def unprotect_secret(value: str | None) -> str:
    stored = str(value or "")
    if not stored:
        return ""
    if stored.startswith(DPAPI_PREFIX):
        raw = _dpapi_unprotect(base64.urlsafe_b64decode(stored[len(DPAPI_PREFIX):].encode("ascii")))
        return raw.decode("utf-8")
    if stored.startswith(FILE_PREFIX):
        raw = _file_unprotect(base64.urlsafe_b64decode(stored[len(FILE_PREFIX):].encode("ascii")))
        return raw.decode("utf-8")
    # Read legacy values once so an upgrade does not lock users out. The next
    # settings read migrates them to an encrypted representation.
    if stored.startswith(PLAINTEXT_PREFIX):
        return stored[len(PLAINTEXT_PREFIX):]
    return stored


def storage_status() -> dict[str, object]:
    return {
        "mode": "windows_dpapi" if os.name == "nt" else "local_key_file",
        "encrypted": True,
        "scope": "current_user",
        "legacyPlaintextSupported": True,
    }
