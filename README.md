

## File structure

```
├── app
│   ├── clients.py
│   ├── schedule.py
│   ├── storeroom.py
│   ├── users.py
├── data
│   ├── FST.json
├── test
│   ├── password_test.py
│   ├── food_requirement_test.py
├── main.py
├── README.md
├── requirements.txt
```



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


## Data