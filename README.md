# FoodShare Tracker (FIT1056 Team 17)

A command-line system that helps a community food bank record donations, track stock and
prepare food hampers that are safe for each client's allergies and dietary needs, while
keeping client information private.

## How to run

Requires Python 3.10 or newer.

```bash
pip install -r requirements.txt
python main.py
```

Run the commands from the project folder (the folder containing `main.py`).

### Demo logins

| Role      | Username | Password  |
|-----------|----------|-----------|
| Volunteer | `sam`    | `vol123`  |
| Staff     | `priya`  | `staff123`|
| Admin     | `admin`  | `admin123`|

The sample data file stores these as plain-text passwords. They are replaced with salted
hashes automatically the first time the app loads the file.

### Run the tests

```bash
python -m pytest
```

## Features implemented (draft MVP)

| Feature | What works | Requirements |
|---|---|---|
| Login and roles | Log in as volunteer, staff or admin. Passwords are stored as salted PBKDF2-SHA256 hashes (Python standard library) and hidden while typing. Log out returns to the login screen. | F-01, FR-01 |
| Role-based access | Menus only show the actions a role may use, and every protected action is checked again in `ScheduleManager.require_permission()`. | FR-03, NFR-02 |
| Client registration | Staff record name, optional phone, household size, dietary needs and allergies with severity. Inputs are validated. | F-02, FR-04 to FR-07 |
| Privacy-aware client view | Volunteers see only client number, first name and food requirements, never contact details. | NFR-02, NFR-15 |
| Donations and stock | Staff record donations with allergens, "may contain" traces, dietary tags and expiry dates. Matching batches are merged and each donation is logged. Expired donations are refused. | F-03, FR-09, FR-10 |
| Hamper preparation (UC-01) | Shows the client's needs, requires the packer to confirm a severe allergy warning, lists only safe in-stock items, and blocks unsafe, unsuitable, expired or out-of-stock items. | F-04, FR-14 to FR-17 |
| Substitution | Swaps an item for a safe replacement and saves a respectful note for the client with no medical details. An unsafe swap is rolled back. | FR-18, FR-19 |
| Completing a hamper | Re-checks every item, then deducts stock and saves. If any check fails, nothing changes. Draft hampers can be cancelled without using stock. | FR-14 |
| Pickups | Staff book a pickup time for a completed hamper (DD/MM/YYYY or YYYY-MM-DD), change or cancel it. Staff and volunteers see the day's pickups and record collections. The pickup list shows only the client number and first name. | F-06, FR-26, FR-27, NFR-15 |
| Safe saving | Data is written to a temporary file then swapped in, so a crash during saving can't corrupt the data file. Bad data shows a clear message instead of crashing. | NFR-11 |

## Project structure

```
├── app
│   ├── clients.py     Client class: dietary needs, allergies, packing summary
│   ├── hampers.py     Hamper class: items, status, allergy acknowledgement, notes
│   ├── pickups.py     Pickup class: booked time, status, who recorded the collection
│   ├── schedule.py    ScheduleManager: business rules, permissions, loading/saving
│   ├── storeroom.py   FoodbankItem class: allergens, dietary tags, expiry, quantity
│   └── users.py       User class, password hashing (hashlib), role permission matrix
├── data
│   └── FST.json       Sample data (users, clients, stock, hampers, donations)
├── test
│   ├── food_requirement_test.py   Allergy and diet safety rules
│   ├── functional_test.py         End-to-end, boundary and MC/DC tests through the menus
│   ├── hamper_test.py             Permissions, hampers, donations, privacy, boundaries
│   ├── password_test.py           Password hashing and login
│   └── pickup_test.py             Booking, collection, privacy and boundary tests for pickups
├── conftest.py        Lets pytest find the app package
├── main.py            Command-line menus
├── README.md
└── requirements.txt
```

## Known issues and not yet implemented

- The interface is a command-line app rather than the Tkinter GUI planned in Deliverable 1,
  and data is stored in JSON rather than SQLite.
- Volunteer tasks (F-05) and reports (F-07) are not built yet. Their methods in `schedule.py`
  raise `NotImplementedError`.
- Editing client details, changing user roles, searching stock and recording damaged stock
  are not built yet.
- If the app is closed while a hamper is being packed, that draft hamper stays in the data
  file. It doesn't affect stock.
- In some IDE consoles (for example IDLE), the password may still be visible while typing.
  It is hidden in a normal terminal.
