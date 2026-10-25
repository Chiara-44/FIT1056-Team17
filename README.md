# FoodShare Tracker (FIT1056 Team 17)

A Python system with a command-line interface and a Streamlit web interface that helps a
community food bank record donations, track stock and prepare food hampers that are safe for
each client's allergies and dietary needs, while keeping client information private.

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

The sample data file stores salted PBKDF2 hashes of these passwords, not the passwords
themselves. If a file with plain-text passwords is loaded, they are hashed straight away.

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
| Consent | Before registering a client, staff are told why each detail is needed and must confirm the client agrees to their details being stored. Without it nothing is saved. The consent date is shown on the client's profile. | NFR-03 |
| Readable colours | The Streamlit theme in `.streamlit/config.toml` sets text, caption and button colours with a contrast ratio of at least 4.5:1 (WCAG 2.1 AA). The default red buttons only reached 3.3:1. Run Streamlit from the project folder so the theme is picked up. | NFR-09 |
| Fair hamper allowance | Every household gets the same allowance of 5 items per person (`ITEMS_PER_PERSON` in `app/clients.py`). The packing screen shows how much of the allowance is used, and adding past it is refused. | NFR-13 |

## App

All business rules live in `app/`. Both interfaces only call `ScheduleManager`, so permissions,
allergy checks and stock limits are enforced in one place.

### clients.py
- `Client`: a client's household (adults, children, infants), allergies with severity, dietary
  needs, food notes, language, accessibility needs, contact details, consent date and staff-only
  private notes. Every value is validated in the constructor.
- `packing_summary()`: client number, first name, household and food needs only (NFR-02).
- `staff_details()`: the full profile, including private notes, for staff and admins.
- `hamper_allowance`: `ITEMS_PER_PERSON` (5) multiplied by household size (NFR-13).
- `ClientPackingView`: what volunteers receive instead of a `Client`. Asking it for contact
  details, accessibility needs or notes raises `PermissionError` (NFR-02, NFR-15).

### schedule.py
- `ScheduleManager`: loads and saves `data/FST.json`, checks permissions with
  `require_permission()` at the start of every protected action, and holds the rules for clients,
  stock, donations, hampers, pickups, tasks, users and reports.
- `add_client(name, phone, allergies, preferences, household_size=1, consent=True, **details)`:
  refuses to save a client unless consent is given (NFR-03).
- `find_client(id)` / `list_clients()`: full records for staff and admins, `ClientPackingView`
  objects for volunteers.
- `create_hamper()`, `add_hamper_item()`, `substitute_item()`, `complete_hamper()`: hamper
  packing. Every item goes through `_check_item_allowed()` (allergies, diet, expiry, condition,
  stock and allowance), and completion is all-or-nothing.
- `_save_data()`: writes to a temporary file and swaps it in (NFR-11), keeps daily backups, and
  refuses to save if another session saved first; `reload_if_changed()` loads the newer data (NFR-12).
- `generate_report(type)`: stock, expiry (expired and within 7 days), shortages, donations and
  hampers (FR-28 to FR-32, admins only).

### storeroom.py
- `FoodbankItem`: a batch of stock with allergens, "may contain" traces, dietary tags, quantity,
  expiry date and condition.
- `allergy_conflicts(client_allergies)`: an item that contains a client's allergen is blocked at
  any severity; an item that "may contain" it is blocked when the allergy is severe.

### hampers.py, pickups.py, tasks.py
- `Hamper` and `HamperItem`: hamper lines, quantities, recorded substitutions and status.
- `Pickup`: a booked collection time and whether it has been collected.
- `Task` and `StockReport`: volunteer tasks and reports of damaged, expired or missing stock.

### users.py
- `PERMISSIONS`: the actions each role may perform (volunteer, staff, admin).
- `User`: one class with a role. `set_password()` stores a salted PBKDF2-SHA256 hash and
  `check_password()` compares hashes in constant time.

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
│   ├── usability_fix_test.py      Fixes from the usability walkthrough (allergy confirmation, diet tags, phone, dates)
│   ├── human_centred_test.py      Consent before registering a client and the same hamper allowance per person
│   ├── performance_test.py        Response times with 10,000 stock records and 10 threads (NFR-04, NFR-05)
│   ├── review_fix_test.py         Two sessions saving at once, client privacy in the service layer, expiry report
│   ├── client_test.py             Household, contact method, editing, private notes, privacy
│   ├── password_test.py           Password hashing and login
│   ├── pickup_test.py             Booking, collection, privacy and boundary tests for pickups
│   ├── report_test.py             Operational reports, permissions and boundaries
│   ├── task_test.py               Volunteer tasks, permissions, stock reports
│   └── test_schedule.py           First-admin setup and donation merging rules
├── .streamlit
│   └── config.toml    Colour theme with readable contrast (NFR-09)
├── conftest.py        Lets pytest find the app package
├── main.py            Command-line menus
├── README.md
└── requirements.txt
```

## Known issues and limitations
- The graphical interface uses Streamlit instead of the Tkinter GUI planned in Deliverable 1,
  and data is stored in JSON rather than SQLite. The command-line interface is still included.
- Several copies of the app, or several browser sessions, can use the same data file. Each one
  reloads newer data before acting, and a save is refused (with a message to try again) if
  another session saved first. The file is still meant for one site; a database would be needed
  for several sites.
- If the app is closed while a hamper is being packed, that draft hamper stays in the data
  file. It doesn't affect stock.
- In some IDE consoles (for example IDLE), the password may still be visible while typing.
  It is hidden in a normal terminal.
