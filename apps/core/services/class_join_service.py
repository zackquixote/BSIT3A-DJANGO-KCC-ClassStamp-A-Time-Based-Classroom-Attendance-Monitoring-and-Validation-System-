"""Helpers for generating and validating student class join codes."""

import hashlib
import secrets


_JOIN_CODE_ALPHABET = 'ABCDEFGHJKLMNPQRSTUVWXYZ23456789'
_JOIN_CODE_LENGTH = 12


def normalize_join_code(code):
    """Normalize a user-entered join code before hashing."""
    return ''.join(
        character
        for character in (code or '').upper()
        if character not in {'-', ' ', '\t', '\r', '\n'}
    )


def hash_join_code(code):
    """Return a one-way digest suitable for storing in the database."""
    return hashlib.sha256(normalize_join_code(code).encode('ascii')).hexdigest()


def generate_join_code():
    """Return a random display code and its stored digest."""
    raw_code = ''.join(secrets.choice(_JOIN_CODE_ALPHABET) for _ in range(_JOIN_CODE_LENGTH))
    display_code = '-'.join((raw_code[:4], raw_code[4:8], raw_code[8:]))
    return display_code, hash_join_code(raw_code)
