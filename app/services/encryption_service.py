"""AES-256-GCM file encryption for backups and Fernet encryption for stored secrets.

Encrypted file layout::

    MAGIC (8) | scrypt salt (16) | nonce prefix (4) | chunk* 
    chunk = ciphertext length (4, big endian) | AES-GCM ciphertext+tag

Files are processed in 1 MiB chunks so large backups need little memory. Each
chunk uses its own nonce (prefix + counter) and authenticates whether it is the
final chunk, so truncation and re-ordering are detected.
"""
import base64
import hashlib
import os

from cryptography.exceptions import InvalidTag
from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.scrypt import Scrypt
from flask import current_app

from ..exceptions import EncryptionError

MAGIC = b"DBSAFE01"
SALT_SIZE = 16
PREFIX_SIZE = 4
CHUNK_SIZE = 1024 * 1024
TAG_SIZE = 16
MIN_KEY_LENGTH = 12


def validate_key(passphrase):
    if not passphrase or len(passphrase) < MIN_KEY_LENGTH:
        raise EncryptionError(
            f"The encryption key is missing or shorter than {MIN_KEY_LENGTH} characters. "
            "Set DBSAFE_ENCRYPTION_KEY in your .env file.")
    return True


def get_backup_key():
    return current_app.config.get("ENCRYPTION_KEY")


def _derive_key(passphrase, salt):
    kdf = Scrypt(salt=salt, length=32, n=2 ** 15, r=8, p=1)
    return kdf.derive(passphrase.encode("utf-8"))


def _nonce(prefix, counter):
    return prefix + counter.to_bytes(8, "big")


def encrypt_file(source, destination, passphrase):
    validate_key(passphrase)
    salt = os.urandom(SALT_SIZE)
    prefix = os.urandom(PREFIX_SIZE)
    cipher = AESGCM(_derive_key(passphrase, salt))
    with open(source, "rb") as fin, open(destination, "wb") as fout:
        fout.write(MAGIC + salt + prefix)
        counter = 0
        chunk = fin.read(CHUNK_SIZE)
        while True:
            following = fin.read(CHUNK_SIZE)
            final = not following
            ciphertext = cipher.encrypt(_nonce(prefix, counter), chunk, b"\x01" if final else b"\x00")
            fout.write(len(ciphertext).to_bytes(4, "big") + ciphertext)
            if final:
                break
            counter += 1
            chunk = following


def decrypt_file(source, destination, passphrase):
    validate_key(passphrase)
    try:
        with open(source, "rb") as fin:
            header = fin.read(len(MAGIC) + SALT_SIZE + PREFIX_SIZE)
            if len(header) != len(MAGIC) + SALT_SIZE + PREFIX_SIZE or not header.startswith(MAGIC):
                raise EncryptionError("This file is not a DBSafe encrypted backup")
            salt = header[len(MAGIC):len(MAGIC) + SALT_SIZE]
            prefix = header[len(MAGIC) + SALT_SIZE:]
            cipher = AESGCM(_derive_key(passphrase, salt))
            with open(destination, "wb") as fout:
                counter = 0
                length_bytes = fin.read(4)
                if len(length_bytes) != 4:
                    raise EncryptionError("The encrypted backup is truncated")
                while True:
                    length = int.from_bytes(length_bytes, "big")
                    if length < TAG_SIZE or length > CHUNK_SIZE + TAG_SIZE:
                        raise EncryptionError("The encrypted backup is corrupted")
                    ciphertext = fin.read(length)
                    if len(ciphertext) != length:
                        raise EncryptionError("The encrypted backup is truncated")
                    following = fin.read(4)
                    final = len(following) == 0
                    if not final and len(following) != 4:
                        raise EncryptionError("The encrypted backup is truncated")
                    try:
                        plaintext = cipher.decrypt(_nonce(prefix, counter), ciphertext,
                                                   b"\x01" if final else b"\x00")
                    except InvalidTag:
                        raise EncryptionError(
                            "Decryption failed: wrong encryption key or the backup was modified"
                        ) from None
                    fout.write(plaintext)
                    if final:
                        break
                    counter += 1
                    length_bytes = following
    except OSError as exc:
        raise EncryptionError(f"Could not read or write the file: {exc}") from exc


# -- stored secrets (database passwords) -------------------------------------
def _fernet():
    secret = current_app.config["SECRET_KEY"]
    key = base64.urlsafe_b64encode(hashlib.sha256(secret.encode("utf-8")).digest())
    return Fernet(key)


def encrypt_secret(text):
    return _fernet().encrypt(text.encode("utf-8")).decode("ascii")


def decrypt_secret(token):
    try:
        return _fernet().decrypt(token.encode("ascii")).decode("utf-8")
    except (InvalidToken, ValueError):
        raise EncryptionError(
            "Stored database password cannot be decrypted (was DBSAFE_SECRET_KEY changed?). "
            "Edit the connection and enter the password again.") from None
