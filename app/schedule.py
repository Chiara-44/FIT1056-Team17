# filename: schedule.py
# group: Team 17
# names: Chiara, Harry
# created: 18/09/26
# last modified: 25/10/26


import json
import os
import shutil
from datetime import date, datetime, timedelta

from app.users import User, hash_password, PERMISSIONS
from app.clients import Client
from app.storeroom import (FoodbankItem, clean_quantity, clean_allergens, parse_expiry,
                           diet_conflicts, CONDITIONS, FLAGS)
from app.hampers import Hamper, COMPLETED
from app.pickups import Pickup, parse_pickup_time
from app.tasks import Task, StockReport


# list of valid roles
ROLES = ("volunteer", "staff", "admin")

# Why stock can be changed by hand (FR-10). Only "count correction" can add stock;
# every other reason takes stock away.
ADJUSTMENT_REASONS = ("damaged", "expired", "missing", "discarded", "count correction")

# Users are logged out after this many minutes without activity (NFR-02, NFR-15)
SESSION_TIMEOUT_MINUTES = 10

# How many daily backups of the data file to keep (NFR-11)
BACKUPS_TO_KEEP = 14

# Filters search_inventory understands (FR-11)
SEARCH_FILTERS = ("text", "exclude_allergens", "suitable_for", "in_stock", "flag")

# Default data file, found relative to the project rather than wherever the app is launched from
DEFAULT_DATA_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                                 "data", "FST.json")


class ScheduleManager:
    """The main controller for all business logic and data handling."""

    def __init__(self, data_path=DEFAULT_DATA_PATH):
        self.data_path = data_path

        # Defaults so the app still works if the file is missing or broken
        self.volunteers = []
        self.staff = []
        self.admins = []
        self.clients = []
        self.storeroom = []
        self.hampers = []
        self.pickups = []
        self.donations = []
        self.tasks = []
        self.stock_reports = []
        self.stock_adjustments = []
        self.audit_log = []
        self.last_activity = None
        self._now = datetime.now  # replaced in tests to simulate time passing

        self.next_report_id = 1
        self.next_volunteer_id = 1
        self.next_staff_id = 1
        self.next_admin_id = 1
        self.next_client_id = 1
        self.next_item_id = 1
        self.next_hamper_id = 1
        self.next_pickup_id = 1
        self.next_task_id = 1

        self.current_user = None
        self._needs_resave = False

        self._load_data()

    # ---------- Loading helpers ----------

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
                role,  # the list a user is stored in decides their role
            )
            users.append(user)
        return users

    def _build_clients(self, records):
        return [
            Client(
                r.get("id"),
                r.get("name", ""),
                r.get("phone", ""),
                r.get("allergies", {}),
                r.get("preferences", []),
                r.get("household_size", 1),
                household=r.get("household"),
                email=r.get("email", ""),
                contact_method=r.get("contact_method"),
                accessibility_needs=r.get("accessibility_needs", []),
                food_notes=r.get("food_notes", ""),
                language=r.get("language", ""),
                private_notes=r.get("private_notes", []),
            )
            for r in records
        ]

    def _build_items(self, records):
        return [
            FoodbankItem(
                r.get("id"),
                r.get("name", ""),
                r.get("allergens", []),
                r.get("may_contain", []),
                r.get("preferences", []),
                r.get("quantity", 0),
                r.get("expiry"),
                r.get("condition", "good"),
            )
            for r in records
        ]

    def _build_hampers(self, records):
        return [
            Hamper(
                r.get("id"),
                r.get("client_id"),
                r.get("packer_username", ""),
                r.get("packer_role", ""),
                r.get("items", {}),
                r.get("status", "draft"),
                r.get("allergy_acknowledged", False),
                r.get("substitution_notes", []),
                r.get("substitutions", {}),
            )
            for r in records
        ]

    def _build_pickups(self, records):
        return [
            Pickup(
                r.get("id"),
                r.get("hamper_id"),
                r.get("client_id"),
                r.get("scheduled_at"),
                r.get("status", "scheduled"),
                r.get("collected_at"),
                r.get("collected_by", ""),
            )
            for r in records
        ]

    # ---------- Load / save ----------

    # TODO: Validate record types, required fields and ID counters before accepting data.
    def _load_data(self):
        """Loads data from the JSON file and populates the object lists.

        Raises ValueError with a readable message if a record in the file is invalid,
        so main.py can show it instead of crashing with a traceback.
        """
        try:
            with open(self.data_path, "r") as f:
                data = json.load(f)
        except FileNotFoundError:
            print(f"Data file not found at '{os.path.abspath(self.data_path)}'. "
                  "Starting with a clean state.")
            return
        except json.JSONDecodeError as e:
            raise ValueError(f"Data file '{self.data_path}' is not valid JSON ({e}). "
                             "Fix or restore the file before starting.")

        try:
            self.volunteers = self._build_users(data.get("volunteers", []), "volunteer")
            self.staff = self._build_users(data.get("staff", []), "staff")
            self.admins = self._build_users(data.get("admins", []), "admin")
            self.clients = self._build_clients(data.get("clients", []))
            self.storeroom = self._build_items(data.get("storeroom", []))
            self.hampers = self._build_hampers(data.get("hampers", []))
            self.pickups = self._build_pickups(data.get("pickups", []))
            self.tasks = [Task(**r) for r in data.get("tasks", [])]
            self.stock_reports = [StockReport(**r) for r in data.get("stock_reports", [])]
        except ValueError as e:
            raise ValueError(f"Data file '{self.data_path}' has an invalid record: {e}")
        self.donations = list(data.get("donations", []))
        self.stock_adjustments = list(data.get("stock_adjustments", []))
        self.audit_log = list(data.get("audit_log", []))

        self.next_volunteer_id = data.get("next_volunteer_id", 1)
        self.next_staff_id = data.get("next_staff_id", 1)
        self.next_admin_id = data.get("next_admin_id", 1)
        self.next_client_id = data.get("next_client_id", 1)
        self.next_item_id = data.get("next_item_id", 1)
        self.next_hamper_id = data.get("next_hamper_id", 1)
        self.next_pickup_id = data.get("next_pickup_id", 1)
        self.next_task_id = data.get("next_task_id", 1)
        self.next_report_id = data.get("next_report_id", 1)

        # Replace any plain-text passwords in the file with hashes straight away
        if self._needs_resave:
            self._save_data()
            self._needs_resave = False

    def _save_data(self):
        """Converts object lists back to dictionaries and saves to JSON.

        Writes to a temporary file first and then swaps it in, so a crash part-way
        through saving can't leave a half-written data file (NFR-11).
        """
        data_to_save = {
            "volunteers": [u.to_dict() for u in self.volunteers],
            "staff": [u.to_dict() for u in self.staff],
            "admins": [u.to_dict() for u in self.admins],
            "clients": [c.to_dict() for c in self.clients],
            "storeroom": [i.to_dict() for i in self.storeroom],
            "hampers": [h.to_dict() for h in self.hampers],
            "pickups": [p.to_dict() for p in self.pickups],
            "tasks": [t.to_dict() for t in self.tasks],
            "stock_reports": [r.to_dict() for r in self.stock_reports],
        
            "donations": self.donations,
            "stock_adjustments": self.stock_adjustments,
            "audit_log": self.audit_log,
            "next_volunteer_id": self.next_volunteer_id,
            "next_staff_id": self.next_staff_id,
            "next_admin_id": self.next_admin_id,
            "next_client_id": self.next_client_id,
            "next_item_id": self.next_item_id,
            "next_hamper_id": self.next_hamper_id,
            "next_pickup_id": self.next_pickup_id,
            "next_task_id": self.next_task_id,
            "next_report_id": self.next_report_id,
        }
        folder = os.path.dirname(self.data_path)
        if folder:
            os.makedirs(folder, exist_ok=True)
        temp_path = self.data_path + ".tmp"
        with open(temp_path, "w") as f:
            json.dump(data_to_save, f, indent=4)
        self._backup_today()
        os.replace(temp_path, self.data_path)

    def _backup_today(self):
        """Copies the current data file into a dated backup once per day (NFR-11).

        Only the newest BACKUPS_TO_KEEP backups are kept. A failed backup never
        stops the save itself.
        """
        if not os.path.exists(self.data_path):
            return
        folder = os.path.join(os.path.dirname(os.path.abspath(self.data_path)), "backups")
        name = os.path.splitext(os.path.basename(self.data_path))[0]
        target = os.path.join(folder, f"{name}-{self._now().date().isoformat()}.json")
        try:
            if not os.path.exists(target):
                os.makedirs(folder, exist_ok=True)
                shutil.copy2(self.data_path, target)
            backups = sorted(f for f in os.listdir(folder)
                             if f.startswith(name + "-") and f.endswith(".json"))
            for old in backups[:-BACKUPS_TO_KEEP]:
                os.remove(os.path.join(folder, old))
        except OSError:
            pass

    def _audit(self, action, details=""):
        """Records who did what and when, for accountability (Section 8.4)."""
        user = self.current_user
        self.audit_log.append({
            "when": self._now().isoformat(timespec="seconds"),
            "user": user.username if user else "",
            "role": user.role if user else "",
            "action": action,
            "details": details,
        })

    def audit_entries(self, limit=None):
        """The audit log, newest first. Administrators only."""
        self.require_permission("manage_users")
        entries = list(reversed(self.audit_log))
        return entries[:limit] if limit else entries

    # ---------- Login and permissions ----------

    def _users_for_role(self, role):
        return {
            "volunteer": self.volunteers,
            "staff": self.staff,
            "admin": self.admins,
        }.get(role)

    def login(self, username, password, role):
        """Returns the matching User and sets current_user, or None if login fails.

        A failed attempt always logs out whoever was logged in before.
        """
        self.current_user = None
        users = self._users_for_role(role)
        if users is None:
            return None
        for user in users:
            if user.username == username and user.check_password(password):
                self.current_user = user
                self.last_activity = self._now()
                return user
        return None

    def logout(self):
        self.current_user = None
        self.last_activity = None

    def session_expired(self):
        """True if the logged-in user has been inactive for too long (shared computers)."""
        if self.current_user is None or self.last_activity is None:
            return False
        return self._now() - self.last_activity > timedelta(minutes=SESSION_TIMEOUT_MINUTES)

    def can(self, permission):
        """True if the logged-in user's role includes this permission."""
        if self.current_user is None:
            return False
        return permission in PERMISSIONS.get(self.current_user.role, set())

    def require_permission(self, *permissions):
        """Raises PermissionError unless the current user has at least one of the permissions (FR-03).

        Called at the start of every protected operation, so access is enforced in the
        service layer and not only by hiding menu options.
        """
        if self.current_user is None:
            raise PermissionError("Please log in first.")
        if self.session_expired():
            self.logout()
            raise PermissionError(f"You were logged out after {SESSION_TIMEOUT_MINUTES} minutes "
                                  "without activity. Please log in again.")
        self.last_activity = self._now()
        if not any(self.can(p) for p in permissions):
            raise PermissionError(f"Your role ({self.current_user.role}) can't do this.")

    def add_user(self, name, username, password, role):
        """Creates a user with a hashed password. Returns the new User.

        Only admins may create accounts, except when there are no admins yet
        (first-time setup and tests).
        """
        if not self.needs_setup():
            self.require_permission("manage_users")
        elif role != "admin":
            raise ValueError("The first account must be an admin")
        if role not in ROLES:
            raise ValueError(f"Role must be one of {ROLES}")
        if not name.strip() or not username.strip():
            raise ValueError("Name and username cannot be empty")
        if len(password) < 6:
            raise ValueError("Password must be at least 6 characters")
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

        user = User(new_id, name.strip(), username.strip(), hash_password(password), role)
        self._users_for_role(role).append(user)
        self._audit("add user", f"{role} account '{user.username}'")
        self._save_data()
        return user

    def needs_setup(self):
        """True only on a brand-new install with no accounts at all."""
        return not (self.volunteers or self.staff or self.admins)

    # ---------- Clients ----------

    def add_client(self, name, phone, allergies, preferences, household_size=1, **details):
        """Registers a client (FR-04, FR-06 to FR-08).

        details can include household (adults/children/infants), email, contact_method,
        accessibility_needs, food_notes and language. Only staff and admins can do this.
        """
        self.require_permission("manage_clients")
        details.pop("private_notes", None)  # notes are added with add_client_note instead
        client = Client(self.next_client_id, name, phone, allergies, preferences,
                        household_size, **details)
        self.clients.append(client)
        self.next_client_id += 1
        self._audit("register client", f"client #{client.id}")
        self._save_data()
        return client

    def find_client(self, client_id):
        for client in self.clients:
            if client.id == client_id:
                return client
        return None

    def _get_client(self, client_id):
        client = self.find_client(client_id)
        if client is None:
            raise ValueError(f"No client with number {client_id}")
        return client

    # ---------- Storeroom ----------

    def add_item(self, name, allergens, may_contain, preferences, quantity=0, expiry=None):
        self.require_permission("manage_inventory")
        item = FoodbankItem(self.next_item_id, name, allergens, may_contain, preferences,
                            quantity, expiry)
        self.storeroom.append(item)
        self.next_item_id += 1
        self._save_data()
        return item

    def find_item(self, item_id):
        for item in self.storeroom:
            if item.id == item_id:
                return item
        return None

    def _get_item(self, item_id):
        item = self.find_item(item_id)
        if item is None:
            raise ValueError(f"No stock item with number {item_id}")
        return item
    

    def record_donation(self, name, allergens, may_contain, preferences, quantity,
                        expiry=None, donor=""):
        """ If a matching batch already exists (same name, allergens, 
        may-contain, dietary tags and expiry) its quantity goes up; 
        otherwise a new stock item is created.
        """

        self.require_permission("manage_inventory")
        quantity = clean_quantity(quantity)
        if quantity == 0:
            raise ValueError("A donation must have a quantity of at least 1")
        expiry = parse_expiry(expiry)
        if expiry is not None and expiry < date.today():
            raise ValueError("This item has already expired and can't be added to stock")
        allergens = clean_allergens(allergens)
        may_contain = clean_allergens(may_contain)
        preferences = {p.strip().lower() for p in preferences if p.strip()}
        conflicts = diet_conflicts(allergens, preferences)
        if conflicts:
            raise ValueError(f"{name.strip()} {'; '.join(conflicts)}")

        match = None
        for item in self.storeroom:
            if (item.name.lower() == name.strip().lower()
                    and item.allergens == allergens
                    and item.may_contain == may_contain
                    and item.preferences == preferences
                    and item.expiry == expiry
                    and item.condition == "good"):
                match = item
                break

        if match:
            match.quantity += quantity
            item = match
        else:
            item = self.add_item(name, sorted(allergens), sorted(may_contain), sorted(preferences),
                                 quantity, expiry)

        self.donations.append({
            "item_id": item.id,
            "name": item.name,
            "quantity": quantity,
            "donor": donor.strip(),
            "date": date.today().isoformat(),
            "recorded_by": self.current_user.username,
        })
        self._audit("record donation", f"{quantity} x {item.name} (item #{item.id})")
        self._save_data()
        return item

    def safe_items_for(self, client):
        """In-stock, unexpired items that are safe for this client."""
        return [item for item in self.storeroom
                if item.quantity > 0 and item.is_usable() and client.can_have(item)]

    # ---------- Hampers (UC-01) ----------

    def find_hamper(self, hamper_id):
        for hamper in self.hampers:
            if hamper.id == hamper_id:
                return hamper
        return None

    def _get_draft_hamper(self, hamper_id):
        """Returns a draft hamper the current user is allowed to change."""
        self.require_permission("pack_hamper", "create_hamper")
        hamper = self.find_hamper(hamper_id)
        if hamper is None:
            raise ValueError(f"No hamper with number {hamper_id}")
        if not hamper.is_draft():
            raise ValueError("This hamper has already been completed")
        return hamper

    def create_hamper(self, client_id):
        """Starts a draft hamper for a client, packed by the current user (FR-14)."""
        self.require_permission("pack_hamper", "create_hamper")
        self._get_client(client_id)
        hamper = Hamper(self.next_hamper_id, client_id,
                        self.current_user.username, self.current_user.role)
        self.hampers.append(hamper)
        self.next_hamper_id += 1
        self._save_data()
        return hamper

    def acknowledge_allergy_warning(self, hamper_id):
        """Records that the packer has read the client's severe allergy warning (FR-17)."""
        hamper = self._get_draft_hamper(hamper_id)
        hamper.allergy_acknowledged = True
        self._save_data()

    def _needs_acknowledgement(self, hamper):
        client = self._get_client(hamper.client_id)
        return bool(client.severe_allergies()) and not hamper.allergy_acknowledged

    def _check_item_allowed(self, hamper, item, quantity):
        """Raises ValueError explaining why an item can't go in this hamper (FR-13, FR-16)."""
        client = self._get_client(hamper.client_id)
        conflicts = item.allergy_conflicts(client.allergies)
        if conflicts:
            raise ValueError(f"{item.name} is not safe for this client: {', '.join(conflicts)}")
        missing = client.preferences - item.suitable_diets()
        if missing:
            raise ValueError(f"{item.name} doesn't meet this client's needs: "
                             f"not {', '.join(sorted(missing))}")
        if item.is_expired():
            raise ValueError(f"{item.name} is past its expiry date")
        if item.condition != "good":
            raise ValueError(f"{item.name} is marked as {item.condition} and can't be packed")
        available = item.quantity - hamper.quantity_of(item.id)
        if quantity > available:
            raise ValueError(f"Only {max(available, 0)} x {item.name} available")

    def add_hamper_item(self, hamper_id, item_id, quantity=1):
        """Adds stock to a draft hamper after all safety checks pass."""
        hamper = self._get_draft_hamper(hamper_id)
        if self._needs_acknowledgement(hamper):
            raise PermissionError("Please acknowledge the severe allergy warning first")
        quantity = clean_quantity(quantity)
        if quantity == 0:
            raise ValueError("Quantity must be at least 1")
        item = self._get_item(item_id)
        self._check_item_allowed(hamper, item, quantity)
        hamper.add(item.id, quantity)
        self._save_data()
        return hamper

    def remove_hamper_item(self, hamper_id, item_id, quantity=None):
        hamper = self._get_draft_hamper(hamper_id)
        if hamper.remove(item_id, quantity) == 0:
            raise ValueError("That item isn't in the hamper")
        self._save_data()
        return hamper

    def substitute_item(self, hamper_id, old_item_id, new_item_id, quantity=None):
        """Swaps an item for a safe replacement and writes a respectful note (FR-18, FR-19).

        The note is about the food only and never mentions medical details. If the
        replacement isn't allowed, the hamper is left exactly as it was.
        """
        hamper = self._get_draft_hamper(hamper_id)
        old_item = self._get_item(old_item_id)
        new_item = self._get_item(new_item_id)
        current = hamper.quantity_of(old_item.id)
        if current == 0:
            raise ValueError(f"{old_item.name} isn't in the hamper")
        quantity = current if quantity is None else clean_quantity(quantity)
        if quantity == 0 or quantity > current:
            raise ValueError(f"Quantity must be between 1 and {current}")

        hamper.remove(old_item.id, quantity)
        try:
            self.add_hamper_item(hamper.id, new_item.id, quantity)
        except (ValueError, PermissionError):
            hamper.add(old_item.id, quantity)  # put the original back (roll back)
            raise
        hamper.line_for(new_item.id).substituted_for = old_item.id

        note = (f"We've included {new_item.name} instead of {old_item.name} today, as "
                f"{old_item.name} wasn't available. If this doesn't suit you, please let "
                f"us know and we'll do our best to help.")
        hamper.substitution_notes.append(note)
        self._save_data()
        return note

    def complete_hamper(self, hamper_id):
        """Finalises a hamper and takes its items out of stock (FR-14, FR-17).

        Every item is checked again before any stock changes, so a failed completion
        leaves both the hamper and the storeroom untouched.
        """
        hamper = self._get_draft_hamper(hamper_id)
        if self._needs_acknowledgement(hamper):
            raise PermissionError("Please acknowledge the severe allergy warning first")
        if hamper.total_items() == 0:
            raise ValueError("The hamper is empty")

        for item_id, quantity in hamper.items.items():
            item = self._get_item(item_id)
            # Check this item on its own, so its own quantity in the hamper isn't counted twice
            hamper_without = Hamper(None, hamper.client_id, "", "")
            self._check_item_allowed(hamper_without, item, quantity)

        for item_id, quantity in hamper.items.items():
            self._get_item(item_id).quantity -= quantity
        hamper.status = COMPLETED
        self._audit("complete hamper", f"hamper #{hamper.id} for client #{hamper.client_id}")
        self._save_data()
        return hamper

    def cancel_hamper(self, hamper_id):
        """Discards a draft hamper. Stock is untouched because drafts don't deduct it."""
        hamper = self._get_draft_hamper(hamper_id)
        self.hampers.remove(hamper)
        self._save_data()

    # ---------- Pickups (F-06) ----------

    def find_pickup(self, pickup_id):
        for pickup in self.pickups:
            if pickup.id == pickup_id:
                return pickup
        return None

    def _get_pickup(self, pickup_id):
        pickup = self.find_pickup(pickup_id)
        if pickup is None:
            raise ValueError(f"No pickup with number {pickup_id}")
        return pickup

    def _check_pickup_time(self, when, now=None):
        """Parses a pickup time and makes sure it isn't in the past."""
        when = parse_pickup_time(when)
        now = (now or datetime.now()).replace(second=0, microsecond=0)
        if when < now:
            raise ValueError("Pickup time can't be in the past")
        return when

    def schedule_pickup(self, hamper_id, when, now=None):
        """Books a time for the client to collect a completed hamper (FR-26).

        Only completed hampers can be booked, so a client is never told to come in for
        a hamper that hasn't been packed yet. Each hamper can only have one active pickup.
        """
        self.require_permission("manage_pickups")
        hamper = self.find_hamper(hamper_id)
        if hamper is None:
            raise ValueError(f"No hamper with number {hamper_id}")
        if hamper.status != COMPLETED:
            raise ValueError("The hamper needs to be completed before a pickup can be booked")
        for existing in self.pickups:
            if existing.hamper_id == hamper.id and existing.status != "cancelled":
                raise ValueError(f"Hamper #{hamper.id} already has pickup #{existing.id}")
        when = self._check_pickup_time(when, now)
        pickup = Pickup(self.next_pickup_id, hamper.id, hamper.client_id, when)
        self.pickups.append(pickup)
        self.next_pickup_id += 1
        self._save_data()
        return pickup

    def reschedule_pickup(self, pickup_id, when, now=None):
        """Moves a scheduled pickup to a new time."""
        self.require_permission("manage_pickups")
        pickup = self._get_pickup(pickup_id)
        if not pickup.is_active():
            raise ValueError(f"Only scheduled pickups can be moved (this one is {pickup.status})")
        pickup.scheduled_at = self._check_pickup_time(when, now)
        self._save_data()
        return pickup

    def cancel_pickup(self, pickup_id):
        self.require_permission("manage_pickups")
        pickup = self._get_pickup(pickup_id)
        pickup.cancel()
        self._audit("cancel pickup", f"pickup #{pickup.id}")
        self._save_data()
        return pickup

    def record_collection(self, pickup_id, when=None):
        """Records that the client has collected their hamper (FR-27).

        Volunteers at the pickup counter can do this as well as staff.
        """
        self.require_permission("record_pickup")
        pickup = self._get_pickup(pickup_id)
        pickup.mark_collected(self.current_user.username, when)
        self._audit("record collection", f"pickup #{pickup.id}")
        self._save_data()
        return pickup

    def pickups_on(self, day=None):
        """Scheduled and collected pickups for one day (default today), earliest first."""
        self.require_permission("record_pickup", "manage_pickups")
        day = day or date.today()
        found = [p for p in self.pickups
                 if p.scheduled_at.date() == day and p.status != "cancelled"]
        return sorted(found, key=lambda p: p.scheduled_at)

    def pickup_label(self, pickup, now=None):
        """One line for the pickup list, safe to show at a public counter (NFR-15).

        Shows the pickup number, time, client number and first name only. No allergies,
        dietary needs, phone numbers or other private details.
        """
        client = self.find_client(pickup.client_id)
        first_name = client.name.split()[0] if client else "Unknown"
        status = pickup.status
        if pickup.is_overdue(now):
            status = "not collected yet (time passed)"
        return (f"Pickup #{pickup.id}  {pickup.scheduled_at.strftime('%H:%M')}  "
                f"Client #{pickup.client_id} ({first_name})  Hamper #{pickup.hamper_id}  {status}")

    # ---------- User roles (FR-02) ----------

    def all_users(self):
        """Every account, for the admin's user list. Each User knows its own role."""
        self.require_permission("manage_users")
        return self.admins + self.staff + self.volunteers

    def assign_role(self, user_id, current_role, new_role):
        """Moves a user to a different role (FR-02). Returns the updated User.

        IDs are only unique within a role, so the user is found by id and current role.
        They get a new id in their new role, keep their name, username and password,
        and unfinished volunteer tasks are unassigned so staff can give them to someone else.
        """
        self.require_permission("manage_users")
        if current_role not in ROLES or new_role not in ROLES:
            raise ValueError(f"Role must be one of {ROLES}")
        if new_role == current_role:
            raise ValueError(f"This user is already {current_role}")
        old_list = self._users_for_role(current_role)
        user = next((u for u in old_list if u.id == user_id), None)
        if user is None:
            raise ValueError(f"No {current_role} with number {user_id}")
        if user is self.current_user:
            raise ValueError("You can't change your own role")
        if current_role == "admin" and len(self.admins) == 1:
            raise ValueError("There must always be at least one admin")
        new_list = self._users_for_role(new_role)
        if any(u.username == user.username for u in new_list):
            raise ValueError(f"A {new_role} with username '{user.username}' already exists")

        if new_role == "volunteer":
            new_id = self.next_volunteer_id
            self.next_volunteer_id += 1
        elif new_role == "staff":
            new_id = self.next_staff_id
            self.next_staff_id += 1
        else:
            new_id = self.next_admin_id
            self.next_admin_id += 1

        if current_role == "volunteer":
            for task in self.tasks:
                if task.assigned_to == user.username and not task.is_done():
                    task.assigned_to = ""
        old_list.remove(user)
        user.id = new_id
        user.role = new_role
        new_list.append(user)
        self._audit("change role", f"'{user.username}' from {current_role} to {new_role}")
        self._save_data()
        return user

    # Fields staff are allowed to change with update_client
    EDITABLE_CLIENT_FIELDS = ("name", "phone", "email", "contact_method", "allergies",
                              "preferences", "household", "accessibility_needs",
                              "food_notes", "language")

    def update_client(self, client_id, **changes):
        """Updates a client's details (FR-05).

        The changed client is fully checked before anything is saved, so if any value is
        invalid the original record stays exactly as it was.
        """
        self.require_permission("manage_clients")
        client = self._get_client(client_id)
        unknown = set(changes) - set(self.EDITABLE_CLIENT_FIELDS)
        if unknown:
            raise ValueError(f"These details can't be changed here: {', '.join(sorted(unknown))}")

        data = client.to_dict()
        data.update(changes)
        updated = Client(client.id, data["name"], data["phone"], data["allergies"],
                         data["preferences"], household=data["household"],
                         email=data["email"], contact_method=data["contact_method"],
                         accessibility_needs=data["accessibility_needs"],
                         food_notes=data["food_notes"], language=data["language"],
                         private_notes=client.private_notes)
        self.clients[self.clients.index(client)] = updated
        self._audit("update client", f"client #{client.id}: {', '.join(sorted(changes))}")
        self._save_data()
        return updated

    def add_client_note(self, client_id, text):
        """Adds a private note that only staff and admins can see."""
        self.require_permission("manage_clients")
        client = self._get_client(client_id)
        client.add_private_note(text, self.current_user.username)
        self._audit("add private note", f"client #{client.id}")
        self._save_data()
        return client

    # ---------- Inventory search, flags and adjustments (FR-10 to FR-12) ----------

    def search_inventory(self, filters=None):
        """Returns stock items matching every filter given, in item number order (FR-11).

        filters is a dict that can include:
          text              part of the item name (any case)
          exclude_allergens items that contain or may contain any of these are left out
          suitable_for      items must have all these dietary tags, e.g. ["vegan"]
          in_stock          True to show only items with a quantity above 0
          flag              only items with this flag, e.g. "near expiry" (see FLAGS)
        """
        self.require_permission("manage_inventory", "pack_hamper", "report_stock")
        filters = dict(filters or {})
        unknown = set(filters) - set(SEARCH_FILTERS)
        if unknown:
            raise ValueError(f"Unknown search filter(s): {', '.join(sorted(unknown))}")

        text = str(filters.get("text") or "").strip().lower()
        exclude = clean_allergens(filters.get("exclude_allergens") or [])
        suitable_for = {p.strip().lower() for p in filters.get("suitable_for") or [] if p.strip()}
        in_stock = bool(filters.get("in_stock"))
        flag = filters.get("flag")
        if flag is not None and flag not in FLAGS:
            raise ValueError(f"Flag must be one of: {', '.join(FLAGS)}")

        results = []
        for item in self.storeroom:
            if text and text not in item.name.lower():
                continue
            if exclude & (item.allergens | item.may_contain):
                continue
            if not suitable_for.issubset(item.suitable_diets()):
                continue
            if in_stock and item.quantity == 0:
                continue
            if flag is not None and flag not in item.flags():
                continue
            results.append(item)
        return sorted(results, key=lambda i: i.id)

    def flagged_items(self):
        """Every item with at least one warning flag, for the stock screen (FR-12)."""
        self.require_permission("manage_inventory", "pack_hamper", "report_stock")
        return [item for item in self.storeroom if item.flags()]

    def set_item_condition(self, item_id, condition):
        """Marks a whole batch as good, damaged or contaminated (FR-12, FR-13).

        Damaged and contaminated stock stays on record but can't be packed.
        """
        self.require_permission("manage_inventory")
        item = self._get_item(item_id)
        condition = str(condition).strip().lower()
        if condition not in CONDITIONS:
            raise ValueError(f"Condition must be one of: {', '.join(CONDITIONS)}")
        item.condition = condition
        self._audit("mark condition", f"item #{item.id} {condition}")
        self._save_data()
        return item

    def adjust_stock(self, item_id, quantity_change, reason, note="", report_id=None):
        """Changes a stock quantity by hand and records why (FR-10, NFR-12).

        quantity_change is negative to remove stock (damaged, expired, missing, discarded)
        and can only be positive for a "count correction". Stock can never go below zero.
        If report_id is given, that volunteer stock report is marked as dealt with.
        """
        self.require_permission("manage_inventory")
        item = self._get_item(item_id)
        if reason not in ADJUSTMENT_REASONS:
            raise ValueError(f"Reason must be one of: {', '.join(ADJUSTMENT_REASONS)}")
        if isinstance(quantity_change, bool) or not isinstance(quantity_change, int):
            raise ValueError("The change must be a whole number")
        if quantity_change == 0:
            raise ValueError("The change can't be 0")
        if quantity_change > 0 and reason != "count correction":
            raise ValueError(f"Stock can only be added back with a count correction, not '{reason}'")
        if item.quantity + quantity_change < 0:
            raise ValueError(f"There are only {item.quantity} x {item.name} in stock")
        note = str(note or "").strip()
        if len(note) > 300:
            raise ValueError("Note must be 300 characters or fewer")

        report = None
        if report_id is not None:
            report = next((r for r in self.stock_reports if r.id == report_id), None)
            if report is None:
                raise ValueError(f"No stock report with number {report_id}")
            if report.resolved:
                raise ValueError(f"Stock report #{report_id} has already been dealt with")
            if report.item_id != item.id:
                raise ValueError(f"Stock report #{report_id} is about a different item")

        item.quantity += quantity_change
        if report:
            report.resolved = True
        self.stock_adjustments.append({
            "item_id": item.id,
            "name": item.name,
            "change": quantity_change,
            "reason": reason,
            "note": note,
            "report_id": report_id,
            "date": date.today().isoformat(),
            "recorded_by": self.current_user.username,
        })
        self._audit("adjust stock", f"item #{item.id} {quantity_change:+d} ({reason})")
        self._save_data()
        return item


    # ---Volunteer tasks (F-05)---

    def _get_volunteer(self, username):
        for volunteer in self.volunteers:
            if volunteer.username == username:
                return volunteer
        raise ValueError(f"No volunteer with username '{username}'")

    def find_task(self, task_id):
        for task in self.tasks:
            if task.id == task_id:
                return task
        return None

    def _get_task(self, task_id):
        task = self.find_task(task_id)
        if task is None:
            raise ValueError(f"No task with number {task_id}")
        return task

    def create_task(self, title, description="", assign_to=""):
        """Creates a volunteer task, optionally assigning it straight away (FR-20, FR-21)."""
        self.require_permission("manage_tasks")
        if assign_to:
            self._get_volunteer(assign_to)
        task = Task(self.next_task_id, title, description, assigned_to=assign_to,
                    created_by=self.current_user.username)
        self.tasks.append(task)
        self.next_task_id += 1
        self._save_data()
        return task

    def assign_task(self, task_id, username):
        """Assigns a task to a volunteer, or reassigns it to another one (FR-21, FR-22)."""
        self.require_permission("manage_tasks")
        task = self._get_task(task_id)
        self._get_volunteer(username)
        task.assign(username)
        self._save_data()
        return task

    def all_tasks(self):
        """Every task, unfinished ones first, for staff and admins."""
        self.require_permission("manage_tasks")
        return sorted(self.tasks, key=lambda t: (t.is_done(), t.id))

    def tasks_for_current_user(self):
        """The logged-in volunteer's own tasks, unfinished ones first (FR-23).

        Checks the role as well as the username, because a staff member could
        share a username with a volunteer.
        """
        self.require_permission("view_own_tasks")
        user = self.current_user
        if user.role != "volunteer":
            return []
        mine = [t for t in self.tasks if t.assigned_to == user.username]
        return sorted(mine, key=lambda t: (t.is_done(), t.id))

    def update_task_progress(self, task_id, status, note=""):
        """Lets a volunteer update one of their own tasks (FR-24)."""
        self.require_permission("update_task")
        task = self._get_task(task_id)
        user = self.current_user
        if not (user.role == "volunteer" and task.assigned_to == user.username):
            raise PermissionError("You can only update tasks assigned to you")
        task.update_progress(status, note)
        self._save_data()
        return task

    def report_stock_problem(self, item_id, problem, quantity, note=""):
        """Records that stock is damaged, expired or missing (FR-25).

        Stock isn't changed here. Staff review open reports and adjust stock.
        """
        self.require_permission("report_stock")
        item = self._get_item(item_id)
        quantity = clean_quantity(quantity)
        if quantity == 0:
            raise ValueError("Quantity must be at least 1")
        if quantity > item.quantity:
            raise ValueError(f"There are only {item.quantity} x {item.name} in stock")
        report = StockReport(self.next_report_id, item.id, problem, quantity, note,
                             reported_by=self.current_user.username)
        self.stock_reports.append(report)
        self.next_report_id += 1
        self._save_data()
        return report

    def open_stock_reports(self):
        """Stock problems that staff haven't dealt with yet."""
        self.require_permission("manage_inventory")
        return [r for r in self.stock_reports if not r.resolved]

    def generate_report(self, report_type):
        """Generates operational reports (FR-28 to FR-32)."""
        self.require_permission("run_reports") # Blocks unauthorized users
        
        if report_type == "stock":
            # FR-28: Current stock levels
            return [{"id": item.id, "name": item.name, "quantity": item.quantity} 
                    for item in self.storeroom]
                    
        elif report_type == "expiry":
            # FR-29: Items that are expired or expiring today
            today = date.today()
            return [{"id": item.id, "name": item.name, "quantity": item.quantity, "expiry": item.expiry.isoformat()} 
                    for item in self.storeroom if item.expiry and item.expiry <= today]
                    
        elif report_type == "shortages":
            # FR-30: Items with a dangerously low stock (under 10 items)
            return [{"id": item.id, "name": item.name, "quantity": item.quantity} 
                    for item in self.storeroom if item.quantity < 10]
                    
        elif report_type == "donations":
            # FR-31: History of all logged donations
            return self.donations
            
        elif report_type == "hampers":
            # FR-32: Overview of hamper distribution
            completed = [h for h in self.hampers if h.status == COMPLETED]
            return {
                "total_completed": len(completed),
                "total_drafts": len(self.hampers) - len(completed)
            }
        else:
            raise ValueError(f"Unknown report type: {report_type}")
