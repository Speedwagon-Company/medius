from __future__ import annotations

import base64


def mask_wallet(wallet: str, visible_head: int = 6, visible_tail: int = 4) -> str:
    if not wallet:
        return ""
    if len(wallet) <= visible_head + visible_tail:
        return "*" * len(wallet)
    return f"{wallet[:visible_head]}...{wallet[-visible_tail:]}"


def _get_fernet(key: str):
    try:
        from cryptography.fernet import Fernet
    except ImportError as exc:
        raise RuntimeError(
            "cryptography package is required for payout data encryption"
        ) from exc

    normalized_key = key.strip().encode("utf-8")
    if len(normalized_key) == 32:
        normalized_key = base64.urlsafe_b64encode(normalized_key)
    return Fernet(normalized_key)


def encrypt_text(plaintext: str, key: str) -> str:
    if not plaintext:
        return ""
    fernet = _get_fernet(key)
    return fernet.encrypt(plaintext.encode("utf-8")).decode("utf-8")


def decrypt_text(ciphertext: str, key: str) -> str:
    if not ciphertext:
        return ""
    fernet = _get_fernet(key)
    return fernet.decrypt(ciphertext.encode("utf-8")).decode("utf-8")

