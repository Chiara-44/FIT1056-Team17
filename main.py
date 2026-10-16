# filename: main.py
# group: Team 17
# names: Chiara
# created: 18/09/26
# last modified: 16/10/26
#
# Command-line interface for FoodShare Tracker.
# Every screen only offers what the logged-in role is allowed to do, and the
# ScheduleManager checks permissions again in case a menu is ever wrong.

from datetime import date
from getpass import getpass

from app.schedule import ScheduleManager, ROLES, DEFAULT_DATA_PATH
from app.storeroom import ALLERGENS, PREFERENCES, parse_expiry
from app.clients import CONTACT_METHODS, ACCESSIBILITY_NEEDS, SEVERITIES


# ---------- Small input helpers ----------

def ask(prompt):
    return input(prompt).strip()


def ask_int(prompt, allow_blank=False):
    """Keeps asking until a whole number is entered. Returns None for blank if allowed."""
    while True:
        text = ask(prompt)
        if allow_blank and text == "":
            return None
        try:
            return int(text)
        except ValueError:
            print("  Please enter a number.")


def ask_list(prompt):
    """Reads a comma-separated list, e.g. 'peanuts, dairy'. Blank gives an empty list."""
    text = ask(prompt)
    return [part.strip() for part in text.split(",") if part.strip()]


def pause():
    input("\nPress Enter to continue...")


# ---------- Login ----------

def login_prompt(manager):
    """Keeps asking until the user logs in successfully or quits."""
    while True:
        print("\n=== FoodShare Tracker: Log in ===")
        role = ask(f"Role ({'/'.join(ROLES)}, or q to quit): ").lower()
        if role == "q":
            return None
        if role not in ROLES:
            print("Please type volunteer, staff or admin.")
            continue

        username = ask("Username: ")
        password = getpass("Password (hidden): ")

        user = manager.login(username, password, role)
        if user:
            print(f"\nWelcome, {user.name}! You're logged in as {user.role}.")
            return user
        print("That username and password don't match. Please try again.")


# ---------- Screens ----------

def show_stock(manager):
    print("\n--- Current stock ---")
    if not manager.storeroom:
        print("No stock recorded yet.")
        return
    print(f"{'No.':<4} {'Item':<22} {'Qty':>4}  {'Expiry':<11} Contains / may contain")
    for item in manager.storeroom:
        expiry = item.expiry.isoformat() if item.expiry else "-"
        if item.is_expired():
            expiry += " EXPIRED"
        contains = ", ".join(sorted(item.allergens)) or "-"
        may = ", ".join(sorted(item.may_contain))
        if may:
            contains += f" / may contain {may}"
        print(f"{item.id:<4} {item.name:<22} {item.quantity:>4}  {expiry:<11} {contains}")


def record_donation_screen(manager):
    print("\n--- Record a donation ---")
    print(f"Allergens: {', '.join(sorted(ALLERGENS))}")
    print(f"Dietary tags: {', '.join(sorted(PREFERENCES))}")
    name = ask("Item name: ")
    quantity = ask_int("Quantity: ")
    allergens = ask_list("Contains (comma separated, blank for none): ")
    may_contain = ask_list("May contain (comma separated, blank for none): ")
    prefs = ask_list("Suitable for (comma separated, blank for none): ")
    expiry = ask("Expiry date YYYY-MM-DD (blank if none): ")
    donor = ask("Donor name (optional): ")
    item = manager.record_donation(name, allergens, may_contain, prefs, quantity,
                                   expiry or None, donor)
    print(f"Thanks! Recorded. {item.name} now has {item.quantity} in stock (item #{item.id}).")


def list_clients(manager):
    """Staff and admins see contact details; packers only see what they need to pack."""
    print("\n--- Clients ---")
    if not manager.clients:
        print("No clients yet.")
        return
    full_view = manager.can("manage_clients")
    for client in manager.clients:
        if full_view:
            print(f"#{client.id} {client.name}  phone: {client.phone or '-'}")
            print("   " + client.packing_summary().split("\n", 1)[1].replace("\n", "\n   "))
        else:
            print(client.packing_summary())


def ask_choices(options, prompt, many=False):
    """Shows numbered options and returns the chosen one (or list, if many=True).

    Picking by number avoids typos like 'nutz'. Blank means none (when many=True).
    """
    options = list(options)
    for i, option in enumerate(options, 1):
        print(f"  {i}. {option}")
    while True:
        text = ask(prompt)
        if many and text == "":
            return []
        try:
            picks = [int(part) for part in text.replace(",", " ").split()]
            if picks and all(1 <= n <= len(options) for n in picks):
                chosen = [options[n - 1] for n in picks]
                return chosen if many else chosen[0]
        except ValueError:
            pass
        print(f"  Please type a number from 1 to {len(options)}" +
              (", or several separated by spaces." if many else "."))


def ask_household():
    print("Who is in the household? (press Enter for 0)")
    household = {}
    for key, label in (("adults", "Adults (18 and over)"), ("children", "Children (3 to 17)"),
                       ("infants", "Infants (under 3)")):
        household[key] = ask_int(f"  {label}: ", allow_blank=True) or 0
    return household


def ask_allergies():
    chosen = ask_choices(sorted(ALLERGENS), "Allergies (numbers separated by spaces, Enter for none): ",
                         many=True)
    allergies = {}
    for allergen in chosen:
        print(f"How serious is the {allergen} allergy?")
        allergies[allergen] = ask_choices(SEVERITIES, "  Choose: ")
    return allergies


def ask_contact(phone, email):
    """Returns (phone, email, contact_method), asking only for the details that are needed."""
    print("How would they like us to contact them?")
    method = ask_choices(CONTACT_METHODS, "Choose: ")
    if method in ("sms", "phone call") and not phone:
        phone = ask("Phone number: ")
    if method == "email" and not email:
        email = ask("Email address: ")
    return phone, email, method


def add_client_screen(manager):
    print("\n--- Register a client ---")
    print("We only ask for what we need to prepare safe, suitable food and to get in touch.")
    print("Anything marked optional can be skipped.")
    name = ask("Name (or the name they prefer to use): ")
    household = ask_household()
    print("Dietary needs:")
    prefs = ask_choices(sorted(PREFERENCES), "Choose (numbers separated by spaces, Enter for none): ",
                        many=True)
    allergies = ask_allergies()
    food_notes = ask("Food preferences or cultural needs (optional, e.g. no pork, prefers rice): ")
    phone, email, method = ask_contact("", "")
    language = ask("Preferred language (optional): ")
    print("Accessibility needs (optional):")
    access = ask_choices(ACCESSIBILITY_NEEDS, "Choose (numbers separated by spaces, Enter for none): ",
                         many=True)
    client = manager.add_client(name, phone, allergies, prefs, household=household, email=email,
                                contact_method=method, accessibility_needs=access,
                                food_notes=food_notes, language=language)
    print(f"Saved. {client.name} is client #{client.id}.")


EDIT_FIELDS = [
    ("Name", "name"), ("Household", "household"), ("Dietary needs", "preferences"),
    ("Allergies", "allergies"), ("Food preferences / cultural needs", "food_notes"),
    ("Contact details and method", "contact"), ("Preferred language", "language"),
    ("Accessibility needs", "accessibility_needs"),
]


def edit_client(manager, client):
    label = ask_choices([f[0] for f in EDIT_FIELDS], "What would you like to change? ")
    field = dict(EDIT_FIELDS)[label]
    if field == "name":
        changes = {"name": ask("New name: ")}
    elif field == "household":
        changes = {"household": ask_household()}
    elif field == "preferences":
        changes = {"preferences": ask_choices(sorted(PREFERENCES),
                                              "Choose (Enter for none): ", many=True)}
    elif field == "allergies":
        changes = {"allergies": ask_allergies()}
    elif field == "food_notes":
        changes = {"food_notes": ask("Food preferences or cultural needs: ")}
    elif field == "language":
        changes = {"language": ask("Preferred language: ")}
    elif field == "accessibility_needs":
        changes = {"accessibility_needs": ask_choices(ACCESSIBILITY_NEEDS,
                                                      "Choose (Enter for none): ", many=True)}
    else:
        phone = ask(f"Phone (Enter to keep '{client.phone or 'none'}', '-' to remove): ")
        email = ask(f"Email (Enter to keep '{client.email or 'none'}', '-' to remove): ")
        phone = "" if phone == "-" else (phone or client.phone)
        email = "" if email == "-" else (email or client.email)
        phone, email, method = ask_contact(phone, email)
        changes = {"phone": phone, "email": email, "contact_method": method}
    manager.update_client(client.id, **changes)
    print("Saved.")


def client_details_screen(manager):
    """Staff/admin view of one client's full profile, with editing and private notes."""
    list_clients(manager)
    client_id = ask_int("\nClient number (blank to go back): ", allow_blank=True)
    if client_id is None:
        return
    while True:
        client = manager.find_client(client_id)
        if client is None:
            print("No client with that number.")
            return
        print("\n" + client.staff_details())
        print("\n[e] Edit details  [n] Add a private note  [b] Back")
        choice = ask("Choose: ").lower()
        try:
            if choice == "b":
                return
            elif choice == "e":
                edit_client(manager, client)
            elif choice == "n":
                manager.add_client_note(client.id, ask("Note (staff only): "))
                print("Note saved.")
            else:
                print("Please choose one of the letters shown.")
        except (ValueError, PermissionError) as e:
            print(f"Can't do that: {e}")


def show_hamper(manager, hamper):
    print(f"\nHamper #{hamper.id} contains:")
    if not hamper.items:
        print("  (empty)")
    for line in hamper.lines:
        item = manager.find_item(line.item_id)
        text = f"  {line.quantity} x {item.name if item else 'unknown item'} (item #{line.item_id})"
        if line.substituted_for is not None:
            old = manager.find_item(line.substituted_for)
            text += f", replacing {old.name if old else 'item #' + str(line.substituted_for)}"
        print(text)
    for note in hamper.substitution_notes:
        print(f"  Note for client: {note}")


def show_safe_items(manager, client, hamper):
    print("\nItems that are safe and suitable for this client:")
    safe = manager.safe_items_for(client)
    if not safe:
        print("  None in stock right now.")
    for item in safe:
        left = item.quantity - hamper.quantity_of(item.id)
        print(f"  #{item.id:<3} {item.name:<22} {left} available")


def prepare_hamper_screen(manager):
    """UC-01: prepare a hamper, enforcing the allergy acknowledgement and safety checks."""
    print("\n--- Prepare a hamper ---")
    list_clients(manager)
    client_id = ask_int("\nClient number (blank to go back): ", allow_blank=True)
    if client_id is None:
        return
    client = manager.find_client(client_id)
    if client is None:
        print("No client with that number.")
        return

    hamper = manager.create_hamper(client.id)
    print("\n" + client.packing_summary())

    severe = client.severe_allergies()
    if severe:
        print("\n!!! SEVERE ALLERGY WARNING !!!")
        print(f"This client has a severe allergy to: {', '.join(severe)}.")
        print("Items that contain these, or may contain traces, will be blocked.")
        while ask("Type YES to confirm you have read this warning: ").upper() != "YES":
            print("You need to confirm before packing.")
        manager.acknowledge_allergy_warning(hamper.id)

    while True:
        show_hamper(manager, hamper)
        show_safe_items(manager, client, hamper)
        print("\n[a] Add item  [r] Remove item  [s] Substitute item  "
              "[c] Complete hamper  [x] Cancel hamper")
        choice = ask("Choose: ").lower()
        try:
            if choice == "a":
                item_id = ask_int("Item number: ")
                quantity = ask_int("Quantity: ")
                manager.add_hamper_item(hamper.id, item_id, quantity)
                print("Added.")
            elif choice == "r":
                item_id = ask_int("Item number to remove: ")
                manager.remove_hamper_item(hamper.id, item_id)
                print("Removed.")
            elif choice == "s":
                old_id = ask_int("Item number to replace: ")
                new_id = ask_int("Replacement item number: ")
                note = manager.substitute_item(hamper.id, old_id, new_id)
                print(f"Swapped. Note saved for the client:\n  \"{note}\"")
            elif choice == "c":
                manager.complete_hamper(hamper.id)
                print(f"Hamper #{hamper.id} is complete and stock has been updated.")
                return
            elif choice == "x":
                manager.cancel_hamper(hamper.id)
                print("Hamper cancelled. No stock was used.")
                return
            else:
                print("Please choose one of the letters shown.")
        except (ValueError, PermissionError) as e:
            print(f"Can't do that: {e}")


def add_user_screen(manager):
    print("\n--- Add a user ---")
    name = ask("Full name: ")
    username = ask("Username: ")
    role = ask(f"Role ({'/'.join(ROLES)}): ").lower()
    password = getpass("Temporary password (min 6 characters, hidden): ")
    user = manager.add_user(name, username, password, role)
    print(f"Created {user.role} account '{user.username}'.")


def show_pickups(manager, day):
    pickups = manager.pickups_on(day)
    label = "today" if day == date.today() else day.strftime("%d/%m/%Y")
    print(f"\n--- Pickups for {label} ---")
    if not pickups:
        print("No pickups booked.")
    for pickup in pickups:
        print(manager.pickup_label(pickup))


def hampers_ready_for_pickup(manager):
    """Completed hampers that don't have a pickup booked yet."""
    booked = {p.hamper_id for p in manager.pickups if p.status != "cancelled"}
    return [h for h in manager.hampers if h.status == "completed" and h.id not in booked]


def pickups_screen(manager):
    """F-06: view the day's pickups, record collections and (for staff) book pickups."""
    can_manage = manager.can("manage_pickups")
    day = date.today()
    while True:
        show_pickups(manager, day)
        options = "\n[c] Record a collection  [d] Show another day"
        if can_manage:
            options += "\n[s] Book a pickup  [r] Change a pickup time  [x] Cancel a pickup"
        print(options + "\n[b] Back to main menu")
        choice = ask("Choose: ").lower()
        try:
            if choice == "b":
                return
            elif choice == "c":
                pickup_id = ask_int("Pickup number: ")
                pickup = manager.record_collection(pickup_id)
                print(f"Pickup #{pickup.id} marked as collected. Thanks!")
            elif choice == "d":
                text = ask("Date (DD/MM/YYYY or YYYY-MM-DD, blank for today): ")
                if not text:
                    day = date.today()
                elif "/" in text:
                    d, m, y = text.split("/")
                    day = date(int(y), int(m), int(d))
                else:
                    day = parse_expiry(text)
            elif choice == "s" and can_manage:
                ready = hampers_ready_for_pickup(manager)
                if not ready:
                    print("There are no completed hampers waiting for a pickup time.")
                    continue
                print("\nCompleted hampers without a pickup:")
                for h in ready:
                    client = manager.find_client(h.client_id)
                    first = client.name.split()[0] if client else "Unknown"
                    print(f"  Hamper #{h.id} for client #{h.client_id} ({first})")
                hamper_id = ask_int("Hamper number: ")
                when = ask("Pickup time (e.g. 25/10/2026 14:30): ")
                pickup = manager.schedule_pickup(hamper_id, when)
                print(f"Booked pickup #{pickup.id} for {pickup.scheduled_at.strftime('%d/%m/%Y %H:%M')}.")
            elif choice == "r" and can_manage:
                pickup_id = ask_int("Pickup number: ")
                when = ask("New time (e.g. 25/10/2026 14:30): ")
                pickup = manager.reschedule_pickup(pickup_id, when)
                print(f"Pickup #{pickup.id} moved to {pickup.scheduled_at.strftime('%d/%m/%Y %H:%M')}.")
            elif choice == "x" and can_manage:
                pickup_id = ask_int("Pickup number: ")
                manager.cancel_pickup(pickup_id)
                print(f"Pickup #{pickup_id} cancelled.")
            else:
                print("Please choose one of the letters shown.")
        except (ValueError, PermissionError) as e:
            print(f"Can't do that: {e}")


# Each menu option: (key, label, permission needed (None = any logged-in user), function)
MENU = [
    ("1", "View stock", None, show_stock),
    ("2", "Record a donation", "manage_inventory", record_donation_screen),
    ("3", "View clients", ("manage_clients", "pack_hamper"), list_clients),
    ("4", "Register a client", "manage_clients", add_client_screen),
    ("5", "Prepare a hamper", ("pack_hamper", "create_hamper"), prepare_hamper_screen),
    ("6", "Add a user", "manage_users", add_user_screen),
    ("7", "Pickups", ("record_pickup", "manage_pickups"), pickups_screen),
    ("8", "Client details (edit, private notes)", "manage_clients", client_details_screen),
]


def allowed(manager, permission):
    if permission is None:
        return True
    if isinstance(permission, tuple):
        return any(manager.can(p) for p in permission)
    return manager.can(permission)


def main_menu(manager):
    """Shows the options for the current role until the user logs out or quits.

    Returns True to go back to the login screen, False to quit.
    """
    while True:
        options = [o for o in MENU if allowed(manager, o[2])]
        user = manager.current_user
        print(f"\n=== Main menu ({user.name}, {user.role}) ===")
        for key, label, _, _ in options:
            print(f"[{key}] {label}")
        print("[l] Log out   [q] Quit")
        choice = ask("Choose: ").lower()

        if choice == "l":
            manager.logout()
            print("Logged out.")
            return True
        if choice == "q":
            manager.logout()
            return False

        match = next((o for o in options if o[0] == choice), None)
        if match is None:
            print("Please choose one of the options shown.")
            continue
        try:
            match[3](manager)
        except (ValueError, PermissionError) as e:
            print(f"Can't do that: {e}")
        pause()


def main(data_path=DEFAULT_DATA_PATH):
    try:
        manager = ScheduleManager(data_path)  # loads data automatically
    except (ValueError, OSError) as e:
        print(f"FoodShare Tracker couldn't start: {e}")
        return

    try:
        while True:
            if login_prompt(manager) is None:
                break
            if not main_menu(manager):
                break
    except (KeyboardInterrupt, EOFError):
        print()
    print("Goodbye.")


if __name__ == "__main__":
    main()
