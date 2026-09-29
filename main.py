# filename: main.py
# group: Team 17
# names: Chiara
# created: 18/09/26
# last modified: 29/09/26

from app.schedule import ScheduleManager, ROLES


def login_prompt(manager):
    """Keeps asking until the user logs in successfully or quits."""
    while True:
        role = input(f"Role ({'/'.join(ROLES)}, or q to quit): ").strip().lower()
        if role == "q":
            return None
        if role not in ROLES:
            print("Invalid choice.")
            continue

        username = input("Username: ").strip()
        # TODO: Hide password entry; use getpass for CLI or a masked Tkinter field.
        password = input("Password: ")

        user = manager.login(username, password, role)
        if user:
            print(f"Welcome, {user.name}! Logged in as {user.role}.")
            return user
        print("Incorrect username or password.")


def main():
    # TODO: Present storage/validation failures clearly instead of crashing.
    manager = ScheduleManager()  # loads data automatically

    user = login_prompt(manager)
    if user is None:
        print("Goodbye.")
        return

    print(f"Current User: {manager.current_user.role}")
    # TODO [NEXT]: Add a menu loop for clients, inventory, hampers, tasks and pickups.
    # TODO: Offer only permitted actions, and also enforce permissions in services.
    # TODO: Add logout; build the planned Tkinter UI or document the CLI scope change.
    # TODO: show the menu for manager.current_user.role here


if __name__ == "__main__":
    main()