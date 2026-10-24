# FoodShare Tracker (FIT1056 Team 17)

A command-line system that helps a community food bank record donations, track stock and
prepare food hampers that are safe for each client's allergies and dietary needs, while
keeping client information private.

## How to run

Requires Python 3.10 or newer.

```bash
pip install -r requirements.txt
```

Then start either interface from the project folder (the folder containing `main.py`):

| Interface | Command |
|---|---|
| Web interface (Streamlit) | `python -m streamlit run gui/main_dashboard.py` |
| Command-line interface | `python main.py` |

The web interface opens in your browser (usually at http://localhost:8501). Both
interfaces use the same rules and the same data file, so you can switch between them.

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

## Features implemented

| Feature | What works | Requirements |
|---|---|---|
| Login and roles | Log in as volunteer, staff or admin. Passwords are stored as salted PBKDF2-SHA256 hashes (Python standard library) and hidden while typing. Log out returns to the login screen. | F-01, FR-01 |
| Role-based access | Menus only show the actions a role may use, and every protected action is checked again in `ScheduleManager.require_permission()`. | FR-03, NFR-02 |
| Client registration | Staff record name, household (adults, children, infants), dietary needs, allergies with severity, food/cultural preferences, preferred language, accessibility needs and how the client wants to be contacted. Options are picked from numbered lists. | F-02, FR-04, FR-06 to FR-08 |
| Client details | Staff and admins can view a client's full profile, edit any detail (checked before saving, so a mistake changes nothing) and add private notes that volunteers never see. | FR-05, NFR-02 |
| Privacy-aware client view | Volunteers see only client number, first name and food requirements, never contact details. | NFR-02, NFR-15 |
| Donations and stock | Staff record donations with allergens, "may contain" traces, dietary tags and expiry dates, all picked from numbered lists. A bad expiry date is asked again without losing what was typed. A donation only merges into an existing batch if the name, allergens, may-contain, dietary tags and expiry all match, so untagged stock can't be offered as vegan. Expired donations are refused. | F-03, FR-09, FR-10 |
| Hamper preparation (UC-01) | Shows the client's needs, requires the packer to confirm a severe allergy warning, lists only safe in-stock items, and blocks unsafe, unsuitable, expired or out-of-stock items. | F-04, FR-14 to FR-17 |
| Substitution | Swaps an item for a safe replacement and saves a respectful note for the client with no medical details. An unsafe swap is rolled back. | FR-18, FR-19 |
| Completing a hamper | Re-checks every item, then deducts stock and saves. If any check fails, nothing changes. Draft hampers can be cancelled without using stock. | FR-14 |
| Pickups | Staff book a pickup time for a completed hamper (DD/MM/YYYY or YYYY-MM-DD), change or cancel it. Staff and volunteers see the day's pickups and record collections. The pickup list shows only the client number and first name. | F-06, FR-26, FR-27, NFR-15 |
| Safe saving | Data is written to a temporary file then swapped in, so a crash during saving can't corrupt the data file. Bad data shows a clear message instead of crashing. | NFR-11 |
| First-time setup | On a brand-new install with no accounts, the app asks for the first admin account before showing the login screen. The first account must be an admin, and after that only admins can add users. | FR-01, FR-02 |
| Volunteer tasks | Staff create tasks, assign them to a volunteer and reassign them. Volunteers see their own tasks (unfinished first) and update the status and a progress note. | F-05, FR-20 to FR-24 |
| Stock problem reports | Volunteers report damaged, expired or missing stock. Reports don't change the stock count; staff see them under "Reported stock problems". | FR-25 |
| Operational reports | Admins generate current-stock, expiry, shortage (under 10 left), donation and hamper-distribution reports. Other roles are refused. | F-07, FR-28 to FR-32 |
| Stock search and flags | Search stock by name, allergens to leave out, dietary tags and "in stock only". Items are flagged as expired, near expiry (within 7 days), damaged, contaminated or out of stock. | FR-11, FR-12 |
| Stock adjustments | Staff remove damaged, expired, missing or discarded stock (or correct a count) with a reason, which is logged. Stock can never go below zero. Adjusting stock can close a volunteer's stock report. Damaged or contaminated batches can't be packed. | FR-10, FR-13, NFR-12 |
| Changing roles | Admins move a user to a different role. The user keeps their username and password; an admin can't change their own role and the last admin can't be removed. | FR-02 |
| Inactivity logout | Users are logged out after 10 minutes without activity, in both interfaces, so a shared computer isn't left logged in. | NFR-02, NFR-15 |
| Daily backups | The first save each day copies the data file to `data/backups/` (the newest 14 are kept). | NFR-11 |
| Audit log | Donations, stock adjustments, completed hampers, client changes, private notes, pickups and role changes are recorded with who did them and when. Admins can view the log. | Accountability |

## App
### clients.py
***SEVERITIES:***
This is a list used to ensure that allergies are one of the three; "mild", "moderate" or "severe" 


***Client [CLASS]:*** This is a struct that holds a foodbank client and their dietary needs. 

***def _clean_allergies(self, allergies):*** This funciton takes in a list of dicts of allergies and their severities, ensures they are consistent with what is tracked in the program and "cleans" them for consistent storage bewteen items.

***def severe_allergies(self):*** Returns any severe allergies that the client may have.

***def can_have(self, item):*** Returns true if the passed item is safe for the client to consume.

***def to_dict(self):*** Converts the struct into a dicts to be stored in the FST.json file.


### schedule.py
***ROLES*** List of valid roles.


***ScheduleManager [CLASS]*** The main controller for all business logic and data handling. 

**def _build_users(self, records, role):*** Converts users stored in FST.json to struct for use in program.

***def _build_clients(self, records):*** Converts clients stored in FST.json to struct for use in program.

***def _build_items(self, records):*** Converts items stored in FST.json to struct for use in program.

***def _load_data(self):*** Loads all data from FST.json into various datatypes to be directly accessed from the program.

***def _save_data(self):*** Saves all structs and releveant datatypes to the FST.json file for persistent storage

***def _users_for_role(self, role):*** Helper function that returns the relevenat users within a role.

***def login(self, username, password, role):*** Returns the matching User and sets current_user, or None if login fails. any information about the user can now be accessed by manager.current_user.[whatever you want here].

***def logout(self):*** Sets current_user to None. (logs user out)


***def add_user(self, name, username, password, role):*** adds a user to the memory. Hashes the password for safety and security.


***def add_client(self, name, phone, allergies, preferences, household_size=1):*** This function adds a client and increments the client_id.

***def find_client(self, client_id):*** finds a client by their ID. Returns None if cannot find 

***def add_item(self, name, allergens, may_contain, preferences, quantity=0):*** Adds an item and increments the item_id counter.

***def find_item(self, item_id):*** Finds an item by it's ID and returns None if it cannot be found

***def safe_items_for(self, client):*** Returns a list of In-stock items that are safe for this client.


### storeroom.py
***ALLERGENS*** A list of all recorded allergens tracked in the system

***PREFERENCES*** A list of all recorded food preferences tracked in the system

***def clean_allergens(names):*** Lowercases allergen names and checks they're in ALLERGENS. Raises ValueError on a typo.

***FoodbankItem [CLASS]*** Holds an item stored in the foodbank storeroom

***def allergy_conflicts(self, client_allergies):*** Returns a list of reasons this item is unsafe for the client's allergies.
        An empty list means no allergy conflict.
client_allergies is a dict like {"peanuts": "severe", "dairy": "mild"}.

        - Contains an allergen the client has (any severity)  -> blocked
        - May contain an allergen the client has as severe    -> blocked

***def is_safe_for(self, client_allergies, client_preferences):*** True if there are no allergy conflicts and the item meets all the client's preferences.

***def to_dict(self):*** Converts the struct into dicts to be stored in the FST.json file.

### users.py
***PERMISSIONS*** A dict that store all permission that each role has access to.

***User [CLASS]***

***def set_password(self, password):***

***def check_password(self, password):***

***def to_dict(self):***

## Project structure

```
├── app
│   ├── clients.py     Client class: dietary needs, allergies, packing summary
│   ├── hampers.py     Hamper and HamperItem classes: item lines, substitutions, status, notes
│   ├── pickups.py     Pickup class: booked time, status, who recorded the collection
│   ├── schedule.py    ScheduleManager: business rules, permissions, loading/saving
│   ├── storeroom.py   FoodbankItem class: allergens, dietary tags, expiry, quantity
│   └── users.py       User class, password hashing (hashlib), role permission matrix
├── data
│   └── FST.json       Sample data (users, clients, stock, hampers, donations)
├── gui
│   ├── main_dashboard.py   Streamlit entry point: login, first-admin setup, navigation
│   ├── common.py           Shared helpers for the pages
│   ├── client_pages.py     Register clients, view details, private notes
│   ├── inventory_pages.py  Donations, stock and stock problem reports
│   ├── hamper_pages.py     Prepare hampers with allergy checks and substitutions
│   ├── pickup_pages.py     Book pickups and record collections
│   ├── task_pages.py       Volunteer tasks
│   └── admin_pages.py      User accounts and operational reports
├── tests
│   ├── food_requirement_test.py   Allergy and diet safety rules
│   ├── functional_test.py         End-to-end, boundary and MC/DC tests through the menus
│   ├── hamper_item_test.py        HamperItem lines, quantities and recorded substitutions
│   ├── hamper_test.py             Permissions, hampers, donations, privacy, boundaries
│   ├── inventory_test.py          Stock search, flags, condition and stock adjustments
│   ├── menu_test.py               End-to-end tests for search, adjustments, roles and reports
│   ├── role_test.py               Changing a user's role
│   ├── security_test.py           Inactivity logout, daily backups and the audit log
│   ├── client_test.py             Household, contact method, editing, private notes, privacy
│   ├── password_test.py           Password hashing and login
│   ├── pickup_test.py             Booking, collection, privacy and boundary tests for pickups
│   ├── report_test.py             Operational reports, permissions and boundaries
│   ├── task_test.py               Volunteer tasks, permissions, stock reports, 
│   └── test_schedule.py           First-admin setup and donation merging rules
├── conftest.py        Lets pytest find the app package
├── main.py            Command-line menus
├── README.md
└── requirements.txt
```

## Known issues and limitations
- The graphical interface uses Streamlit instead of the Tkinter GUI planned in Deliverable 1,
  and data is stored in JSON rather than SQLite. The command-line interface is still included.
- Only one copy of the app should run at a time. Two copies would overwrite each other's saves.
- If the app is closed while a hamper is being packed, that draft hamper stays in the data
  file. It doesn't affect stock.
- In some IDE consoles (for example IDLE), the password may still be visible while typing.
  It is hidden in a normal terminal.
