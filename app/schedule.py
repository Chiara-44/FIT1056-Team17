import json
import os
from app.user import User
from app.client import Client
from app.foodbank_item import FoodbankItem

ROLES = ("volunteer", "staff", "admin")


class ScheduleManager:
    """The main controller for all business logic and data handling."""

    def __init__(self, data_path="data/FST.json"):
        self.data_path = data_path

        # Defaults so the app still works if the file is missing or broken
        self.volunteers = []
        self.staff = []
        self.admins = []
        self.clients = []
        self.storeroom = []
        self.next_volunteer_id = 1
        self.next_staff_id = 1
        self.next_admin_id = 1
        self.next_client_id = 1
        self.next_item_id = 1
        self.current_user = None

        self._load_data()

    # ---------- Loading helpers ----------

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

    def _build_clients(self, records):
        clients = []
        for r in records:
            client = Client(
                r.get("id"),
                r.get("name", ""),
                r.get("phone", ""),
                r.get("allergies", []),
                r.get("preferences", []),
                r.get("household_size", 1),
            )
            clients.append(client)
        return clients

    def _build_items(self, records):
        items = []
        for r in records:
            item = FoodbankItem(
                r.get("id"),
                r.get("name", ""),
                r.get("allergens", []),
                r.get("may_contain", []),
                r.get("preferences", []),
                r.get("quantity", 0),
            )
            items.append(item)
        return items

    # ---------- Load / save ----------

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
        self.clients = self._build_clients(data.get("clients", []))
        self.storeroom = self._build_items(data.get("storeroom", []))

        self.next_volunteer_id = data.get("next_volunteer_id", 1)
        self.next_staff_id = data.get("next_staff_id", 1)
        self.next_admin_id = data.get("next_admin_id", 1)
        self.next_client_id = data.get("next_client_id", 1)
        self.next_item_id = data.get("next_item_id", 1)

    def _save_data(self):
        """Converts object lists back to dictionaries and saves to JSON."""
        data_to_save = {
            "volunteers": [u.to_dict() for u in self.volunteers],
            "staff": [u.to_dict() for u in self.staff],
            "admins": [u.to_dict() for u in self.admins],
            "clients": [c.to_dict() for c in self.clients],
            "storeroom": [i.to_dict() for i in self.storeroom],
            "next_volunteer_id": self.next_volunteer_id,
            "next_staff_id": self.next_staff_id,
            "next_admin_id": self.next_admin_id,
            "next_client_id": self.next_client_id,
            "next_item_id": self.next_item_id,
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

    # ---------- Clients ----------

    def add_client(self, name, phone, allergies, preferences, household_size=1):
        client = Client(self.next_client_id, name, phone, allergies, preferences, household_size)
        self.clients.append(client)
        self.next_client_id += 1
        self._save_data()
        return client

    def find_client(self, client_id):
        for client in self.clients:
            if client.id == client_id:
                return client
        return None

    # ---------- Storeroom ----------

    def add_item(self, name, allergens, may_contain, preferences, quantity=0):
        item = FoodbankItem(self.next_item_id, name, allergens, may_contain, preferences, quantity)
        self.storeroom.append(item)
        self.next_item_id += 1
        self._save_data()
        return item

    def find_item(self, item_id):
        for item in self.storeroom:
            if item.id == item_id:
                return item
        return None

    def safe_items_for(self, client):
        """In-stock items that are safe for this client."""
        return [item for item in self.storeroom if item.quantity > 0 and client.can_have(item)]