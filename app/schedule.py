# filename: schedule.py
# group: Team 17
# names: Chiara
# created: 18/09/26
# last modified: 16/10/26


import json
import os
from datetime import date, datetime

from app.users import User, hash_password, PERMISSIONS
from app.clients import Client
from app.storeroom import FoodbankItem, clean_quantity, clean_allergens, parse_expiry
from app.hampers import Hamper, COMPLETED
from app.pickups import Pickup, parse_pickup_time


# list of valid roles
ROLES = ("volunteer", "staff", "admin")

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
        self.next_volunteer_id = 1
        self.next_staff_id = 1
        self.next_admin_id = 1
        self.next_client_id = 1
        self.next_item_id = 1
        self.next_hamper_id = 1
        self.next_pickup_id = 1
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
        except ValueError as e:
            raise ValueError(f"Data file '{self.data_path}' has an invalid record: {e}")
        self.donations = list(data.get("donations", []))

        self.next_volunteer_id = data.get("next_volunteer_id", 1)
        self.next_staff_id = data.get("next_staff_id", 1)
        self.next_admin_id = data.get("next_admin_id", 1)
        self.next_client_id = data.get("next_client_id", 1)
        self.next_item_id = data.get("next_item_id", 1)
        self.next_hamper_id = data.get("next_hamper_id", 1)
        self.next_pickup_id = data.get("next_pickup_id", 1)

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
            "donations": self.donations,
            "next_volunteer_id": self.next_volunteer_id,
            "next_staff_id": self.next_staff_id,
            "next_admin_id": self.next_admin_id,
            "next_client_id": self.next_client_id,
            "next_item_id": self.next_item_id,
            "next_hamper_id": self.next_hamper_id,
            "next_pickup_id": self.next_pickup_id,
        }
        folder = os.path.dirname(self.data_path)
        if folder:
            os.makedirs(folder, exist_ok=True)
        temp_path = self.data_path + ".tmp"
        with open(temp_path, "w") as f:
            json.dump(data_to_save, f, indent=4)
        os.replace(temp_path, self.data_path)

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
                return user
        return None

    def logout(self):
        self.current_user = None

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
        if not any(self.can(p) for p in permissions):
            raise PermissionError(f"Your role ({self.current_user.role}) can't do this.")

    # TODO: Define a separate first-admin setup path.
    def add_user(self, name, username, password, role):
        """Creates a user with a hashed password. Returns the new User.

        Only admins may create accounts, except when there are no admins yet
        (first-time setup and tests).
        """
        if self.admins:
            self.require_permission("manage_users")
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
        self._save_data()
        return user

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
        """Records an incoming donation and adds it to stock (FR-09, FR-10).

        If a matching batch already exists (same name, allergens and expiry) its quantity
        goes up; otherwise a new stock item is created. Every donation is also kept in
        a history list for later reporting.
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

        match = None
        for item in self.storeroom:
            if (item.name.lower() == name.strip().lower() and item.allergens == allergens
                    and item.may_contain == may_contain and item.expiry == expiry):
                match = item
                break

        if match:
            match.quantity += quantity
            item = match
            self._save_data()
        else:
            item = self.add_item(name, sorted(allergens), sorted(may_contain), preferences,
                                 quantity, expiry)

        self.donations.append({
            "item_id": item.id,
            "name": item.name,
            "quantity": quantity,
            "donor": donor.strip(),
            "date": date.today().isoformat(),
            "recorded_by": self.current_user.username,
        })
        self._save_data()
        return item

    def safe_items_for(self, client):
        """In-stock, unexpired items that are safe for this client."""
        return [item for item in self.storeroom
                if item.quantity > 0 and not item.is_expired() and client.can_have(item)]

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
        missing = client.preferences - item.preferences
        if missing:
            raise ValueError(f"{item.name} doesn't meet this client's needs: "
                             f"not {', '.join(sorted(missing))}")
        if item.is_expired():
            raise ValueError(f"{item.name} is past its expiry date")
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
        self._save_data()
        return pickup

    def record_collection(self, pickup_id, when=None):
        """Records that the client has collected their hamper (FR-27).

        Volunteers at the pickup counter can do this as well as staff.
        """
        self.require_permission("record_pickup")
        pickup = self._get_pickup(pickup_id)
        pickup.mark_collected(self.current_user.username, when)
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

    # ---------- Not yet implemented (planned for the final submission) ----------

    def assign_role(self, user_id, current_role, new_role):
        # TODO [FR-02]: Require manage_users; validate the new role and persist the move.
        # TODO: Handle IDs that currently overlap across the three role collections.
        raise NotImplementedError

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
        self._save_data()
        return updated

    def add_client_note(self, client_id, text):
        """Adds a private note that only staff and admins can see."""
        self.require_permission("manage_clients")
        client = self._get_client(client_id)
        client.add_private_note(text, self.current_user.username)
        self._save_data()
        return client

    def search_inventory(self, filters):
        # TODO [FR-11..12]: Search/filter items and flag unsafe/near-expiry batches.
        raise NotImplementedError

    def adjust_stock(self, item_id, quantity_change, reason):
        # TODO [FR-10, NFR-12]: Record damaged/discarded stock with a reason.
        raise NotImplementedError

    def manage_task(self, action, task_data):
        # TODO [FR-20..25]: Add task creation/assignment/reassignment for authorised staff.
        raise NotImplementedError

    def generate_report(self, report_type):
        # TODO [FR-28..32]: Require run_reports; report stock, expiry, shortages,
        # donations and hamper distribution from saved data.
        raise NotImplementedError
