# filename: users.py
# group: Team 17
# names: Chiara
# created: 18/09/26
# last modified: 16/10/26

import hashlib
import hmac
import os

# PBKDF2 settings. Stored with each hash so they can be raised later without breaking old passwords.
HASH_PREFIX = "pbkdf2_sha256"
ITERATIONS = 200_000


# Each role maps to the actions it may perform. Menus only show the options a role has, and one User class
# covers volunteers, staff and admins. Admins do not pack hampers and only admins run reports.
# Enforced by ScheduleManager.require_permission() at the start of every protected action (FR-03).
PERMISSIONS = {
    "volunteer": {"view_own_tasks", "update_task", "report_stock", "pack_hamper", "record_pickup"},
    "staff": {"view_own_tasks", "update_task", "report_stock", "pack_hamper", "record_pickup",
              "manage_clients", "manage_inventory", "create_hamper", "manage_tasks", "manage_pickups"},
    "admin": {"manage_users", "run_reports", "manage_clients", "manage_inventory",
              "create_hamper", "manage_tasks", "manage_pickups", "record_pickup"},
}


def hash_password(password, iterations=ITERATIONS):
    """Returns a salted PBKDF2-SHA256 hash of the password as a string (safe to store in JSON).

    Format: pbkdf2_sha256$<iterations>$<salt hex>$<hash hex>
    A new random salt is used every time, so the same password gives different hashes.
    Uses only Python's standard library, so nothing extra needs installing.
    """
    if not isinstance(password, str):
        raise TypeError("Password must be text")
    salt = os.urandom(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
    return f"{HASH_PREFIX}${iterations}${salt.hex()}${digest.hex()}"


def verify_password(password, stored_hash):
    """True if the password matches the stored hash. False for a missing or corrupted hash."""
    try:
        prefix, iterations, salt_hex, digest_hex = stored_hash.split("$")
        if prefix != HASH_PREFIX:
            return False
        salt = bytes.fromhex(salt_hex)
        expected = bytes.fromhex(digest_hex)
        digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, int(iterations))
    except (ValueError, AttributeError):
        return False
    # compare_digest takes the same time whether or not the hashes match (avoids timing attacks)
    return hmac.compare_digest(digest, expected)


class User:
    def __init__(self, id, name, username, password_hash, role):
        self.id = id
        self.name = name
        self.username = username
        self.password_hash = password_hash  # never the plain password
        self.role = role

    def set_password(self, password):
        self.password_hash = hash_password(password)

    def check_password(self, password):
        """True if the password matches the stored hash."""
        if not self.password_hash:
            return False
        return verify_password(password, self.password_hash)

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "username": self.username,
            "password_hash": self.password_hash,
            "role": self.role,
        }