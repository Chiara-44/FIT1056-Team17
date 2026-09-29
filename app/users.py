# filename: users.py
# group: Team 17
# names: Chiara
# created: 18/09/26
# last modified: 29/09/26

import bcrypt


# This is an example of how we could do it and just have the options render based on what the permissions are 
# available to the role. This also means we can have just one struct for volunteers, staff and admin.
PERMISSIONS = {
    "volunteer": {"view_own_tasks", "update_task", "report_stock", "pack_hamper"},
    "staff": {"view_own_tasks", "update_task", "report_stock", "pack_hamper",
              "manage_clients", "manage_inventory", "create_hamper", "manage_tasks", "manage_pickups"},
    "admin": {"manage_users", "run_reports", "manage_clients", "manage_inventory",
              "create_hamper", "manage_tasks", "manage_pickups"},
}


def hash_password(password):
    """Returns a bcrypt hash of the password as a string (safe to store in JSON)."""
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


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
        try:
            return bcrypt.checkpw(password.encode("utf-8"), self.password_hash.encode("utf-8"))
        except ValueError:
            # Stored hash is corrupted or not a bcrypt hash
            return False

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "username": self.username,
            "password_hash": self.password_hash,
            "role": self.role,
        }