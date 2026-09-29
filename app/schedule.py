# filename: schedule.py
# group: Team 17
# names: Chiara
# created: 18/09/26
# last modified: 29/09/26


import json
import os
from app.users import User, hash_password
from app.clients import Client
from app.storeroom import FoodbankItem

ROLES = ("volunteer", "staff", "admin")


class ScheduleManager:
    """The main controller for all business logic and data handling."""

    # TODO: Resolve the default data path relative to the project, not the launch directory.
    # TODO: Keep JSON persistence and update the SRS storage plan to match this decision.
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
        self._needs_resave = False

        self._load_data()

    # ---------- Loading helpers ----------

    # TODO: Validate record roles against ROLES and the containing role collection.
    def _build_users(self, records, role):
        users = []
        for r in records:
            password_hash = r.get("password_hash", "")
            # Old data had plain-text passwords: hash them and flag the file for re-saving
            if not password_hash and r.get("password"):
                password_hash = hash_password(r["password"])
                self._needs_resave = True
            user = User(
                r.get("id"),
                r.get("name", ""),
                r.get("username", ""),
                password_hash,
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

    # TODO: Validate record types, required fields and ID counters before accepting data.
    # TODO: Preserve corrupt files and prevent an accidental empty-state overwrite.
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

        # Replace any plain-text passwords in the file with hashes straight away
        if self._needs_resave:
            self._save_data()
            self._needs_resave = False

    # TODO: Write JSON to a temporary file, then atomically replace the data file.
    # TODO: Lock the full read-check-update-save operation to prevent lost stock updates.
    # TODO [TEST]: Verify restart recovery, write failures and competing stock updates.
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

    # TODO: Define failed-login session behaviour; a failed attempt currently retains current_user.
    def login(self, username, password, role):
        """Returns the matching User and sets current_user, or None if login fails."""
        users = self._users_for_role(role)
        if users is None:
            return None
        for user in users:
            if user.username == username and user.check_password(password):
                self.current_user = user
                return user
        return None

    def logout(self):
        self.current_user = None

    # TODO [FR-02..03]: Require manage_users permission before creating accounts.
    # TODO: Define a separate first-admin setup path; validate names and usernames.
    def add_user(self, name, username, password, role):
        """Creates a user with a hashed password. Returns the new User."""
        if role not in ROLES:
            raise ValueError(f"Role must be one of {ROLES}")
        for existing in self._users_for_role(role):
            if existing.username == username:
                raise ValueError(f"Username '{username}' is already taken")

        if role == "volunteer":
            new_id = self.next_volunteer_id
            self.next_volunteer_id += 1
        elif role == "staff":
            new_id = self.next_staff_id
            self.next_staff_id += 1
        else:
            new_id = self.next_admin_id
            self.next_admin_id += 1

        user = User(new_id, name, username, hash_password(password), role)
        self._users_for_role(role).append(user)
        self._save_data()
        return user

    # ---------- Clients ----------

    # TODO [FR-03..08]: Require manage_clients permission and validate all client fields.
    def add_client(self, name, phone, allergies, preferences, household_size=1):
        client = Client(self.next_client_id, name, phone, allergies, preferences, household_size)
        self.clients.append(client)
        self.next_client_id += 1
        self._save_data()
        return client

    # TODO [NFR-02]: Restrict which client fields each caller may view for their task.
    def find_client(self, client_id):
        for client in self.clients:
            if client.id == client_id:
                return client
        return None

    # ---------- Storeroom ----------

    # TODO [FR-03, FR-09]: Require manage_inventory; distinguish donations from stock records.
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

    # TODO [FR-13]: Also exclude expired, damaged and contaminated batches.
    # TODO: Enforce these checks again when adding stock to a hamper, not just when listing.
    def safe_items_for(self, client):
        """In-stock items that are safe for this client."""
        return [item for item in self.storeroom if item.quantity > 0 and client.can_have(item)]

    def require_permission(self, permission):
        # TODO [FIRST, FR-03]: Check current_user and PERMISSIONS; otherwise raise PermissionError.
        # TODO: Call this at the start of every protected service operation.
        raise NotImplementedError

    def assign_role(self, user_id, current_role, new_role):
        # TODO [FR-02]: Require manage_users; validate the new role and persist the move.
        # TODO: Handle IDs that currently overlap across the three role collections.
        raise NotImplementedError

    def update_client(self, client_id, **changes):
        # TODO [FR-05]: Require manage_clients, validate allowed changes and save.
        raise NotImplementedError

    def record_donation(self, donation_data):
        # TODO [FR-09..10]: Validate required donation details and add stock atomically.
        # TODO: Preserve donation history for reporting rather than only adding an item.
        raise NotImplementedError

    def search_inventory(self, filters):
        # TODO [FR-11..12]: Search/filter items and flag unsafe/near-expiry batches.
        # TODO: Define near-expiry thresholds and test the two-second search target.
        raise NotImplementedError

    def adjust_stock(self, item_id, quantity_change, reason):
        # TODO [FR-10, NFR-12]: Validate permission/reason and reject negative final stock.
        # TODO: Track received, reserved/packed, distributed, damaged and discarded stock.
        # TODO: Make competing updates safe and avoid deducting stock twice at collection.
        raise NotImplementedError

    def create_hamper(self, client_id, packer_id):
        # TODO [FR-14..15]: Require create_hamper; save a draft linked to client and packer.
        # TODO: Display client food requirements and Client.severe_allergies().
        raise NotImplementedError

    def add_hamper_item(self, hamper_id, item_id, quantity):
        # TODO [FR-13, FR-16]: Check packer permission, batch safety and available stock.
        # TODO: Reuse Client.can_have() for allergies/diets, including severe may-contain.
        # TODO: Reserve quantity atomically; test two packers requesting the last item.
        raise NotImplementedError

    def acknowledge_allergy_warning(self, hamper_id):
        # TODO [FR-17]: Record explicit acknowledgement by this hamper's assigned packer.
        raise NotImplementedError

    def substitute_item(self, hamper_id, old_item_id, new_item_id, quantity):
        # TODO [FR-18]: Validate replacement safety/diets and update reservations atomically.
        # TODO [FR-19]: Save a respectful substitution notice without medical details.
        # TODO: External SMS/email is optional; generating the notice is required.
        raise NotImplementedError

    def complete_hamper(self, hamper_id):
        # TODO [FR-17]: Require acknowledgement when severe allergies exist.
        # TODO: Recheck safety and stock; persist completion without duplicate deductions.
        # TODO [TEST]: Verify failed completion rolls back and repeated completion is safe.
        raise NotImplementedError

    def manage_task(self, action, task_data):
        # TODO [FR-20..25]: Add task creation/assignment/reassignment for authorised staff.
        # TODO: Allow volunteers to view/update only their assigned tasks and report stock issues.
        raise NotImplementedError

    def manage_pickup(self, action, pickup_data):
        # TODO [FR-26..27]: Require manage_pickups; schedule pickups and record collection.
        # TODO [NFR-15]: Keep medical/private client details off public pickup views.
        raise NotImplementedError

    def generate_report(self, report_type):
        # TODO [FR-28..32]: Require run_reports; report stock, expiry, shortages,
        # donations and hamper distribution from saved data; define shortage thresholds.
        raise NotImplementedError