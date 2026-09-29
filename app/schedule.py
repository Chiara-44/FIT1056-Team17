import json
import os
from app.user import User

ROLES = ("volunteer", "staff", "admin")


class ScheduleManager:
    """The main controller for all business logic and data handling."""

    def __init__(self, data_path="data/FST.json"):
        self.data_path = data_path

        # Defaults so the app still works if the file is missing or broken
        self.volunteers = []
        self.staff = []
        self.admins = []
        self.next_volunteer_id = 1
        self.next_staff_id = 1
        self.next_admin_id = 1
        self.current_user = None

        self._load_data()

    # ---------- Data ----------

    def _build_users(self, records, role):
        users = []
        for r in records:
            user = User(
                r.get("id"),
                r.get("name", ""),
                r.get("username", ""),
                r.get("password", ""),
                r.get("role", role),
            )
            users.append(user)
        return users

    def _load_data(self):
        """Loads data from the JSON file and populates the object lists."""
        try:
            with open(self.data_path, "r") as f:
                data = json.load(f)
        except FileNotFoundError:
            print(f"Data file not found at '{os.path.abspath(self.data_path)}'. "
                  "Starting with a clean state.")
            return
        except json.JSONDecodeError as e:
            print(f"Data file is not valid JSON ({e}). Starting with a clean state.")
            return

        self.volunteers = self._build_users(data.get("volunteers", []), "volunteer")
        self.staff = self._build_users(data.get("staff", []), "staff")
        self.admins = self._build_users(data.get("admins", []), "admin")
        self.attendance_log = data.get("attendance", [])

        self.next_volunteer_id = data.get("next_volunteer_id", 1)
        self.next_staff_id = data.get("next_staff_id", 1)
        self.next_admin_id = data.get("next_admin_id", 1)

    def _save_data(self):
        """Converts object lists back to dictionaries and saves to JSON."""
        data_to_save = {
            "volunteers": [u.to_dict() for u in self.volunteers],
            "staff": [u.to_dict() for u in self.staff],
            "admins": [u.to_dict() for u in self.admins],
            
            "next_volunteer_id": self.next_volunteer_id,
            "next_staff_id": self.next_staff_id,
            "next_admin_id": self.next_admin_id,
        }
        folder = os.path.dirname(self.data_path)
        if folder:
            os.makedirs(folder, exist_ok=True)
        with open(self.data_path, "w") as f:
            json.dump(data_to_save, f, indent=4)

    # ---------- Login ----------

    def _users_for_role(self, role):
        return {
            "volunteer": self.volunteers,
            "staff": self.staff,
            "admin": self.admins,
        }.get(role)

    def login(self, username, password, role):
        """Returns the matching User and sets current_user, or None if login fails."""
        users = self._users_for_role(role)
        if users is None:
            return None
        for user in users:
            if user.username == username and user.password == password:
                self.current_user = user
                return user
        return None

    def logout(self):
        self.current_user = None