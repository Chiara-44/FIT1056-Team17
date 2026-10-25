# filename: storeroom.py
# group: Team 17
# names: Chiara, Harry
# created: 29/09/26
# last modified: 25/10/26

from datetime import date, datetime, timedelta

ALLERGENS = {"peanuts", "tree nuts", "dairy", "eggs", "gluten", "soy", "fish", "shellfish", "sesame"}
PREFERENCES = {"vegan", "vegetarian", "halal", "kosher"}

# Allergens that come from animals, so an item containing them can't suit that diet (WF-02)
DIET_EXCLUDES = {"vegan": {"dairy", "eggs", "fish", "shellfish"},
                 "vegetarian": {"fish", "shellfish"}}

# Condition of a stock batch (FR-12, FR-13). Only "good" stock can go into a hamper.
CONDITIONS = ("good", "damaged", "contaminated")

# Items expiring within this many days are flagged as "near expiry" (FR-12)
NEAR_EXPIRY_DAYS = 7

# Every flag an item can have, in the order they are shown
FLAGS = ("expired", "near expiry", "damaged", "contaminated", "out of stock")


def clean_allergens(names):
    """Lowercases allergen names and checks they're in ALLERGENS. Raises ValueError on a typo."""
    cleaned = set()
    for name in names:
        name = name.strip().lower()
        if name not in ALLERGENS:
            raise ValueError(f"Unknown allergen: '{name}'")
        cleaned.add(name)
    return cleaned


def diet_conflicts(allergens, preferences):
    """Lists dietary tags that contradict the allergens, e.g. 'vegan' on an item containing dairy."""
    return [f"can't be {diet} because it contains {', '.join(sorted(DIET_EXCLUDES[diet] & set(allergens)))}"
            for diet in sorted(preferences)
            if DIET_EXCLUDES.get(diet, set()) & set(allergens)]


def parse_expiry(value):
    """Turns 'YYYY-MM-DD' or 'DD/MM/YYYY' (or a date, or None/'') into a date or None.

    Raises ValueError if invalid. DD/MM/YYYY is accepted because that's how dates are
    written on Australian packaging (WF-04).
    """
    if value is None or value == "":
        return None
    if isinstance(value, date):
        return value
    text = str(value).strip()
    for fmt in ("%Y-%m-%d", "%d/%m/%Y"):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            pass
    raise ValueError(f"Expiry date must look like DD/MM/YYYY or YYYY-MM-DD, got '{value}'")


def clean_quantity(quantity):
    """Checks a stock quantity is a whole number of zero or more. Raises ValueError otherwise."""
    if isinstance(quantity, bool):
        raise ValueError("Quantity must be a whole number")
    try:
        quantity = int(quantity)
    except (TypeError, ValueError):
        raise ValueError(f"Quantity must be a whole number, got '{quantity}'")
    if quantity < 0:
        raise ValueError("Quantity cannot be negative")
    return quantity


class FoodbankItem:
    """Holds an item stored in the foodbank storeroom."""

    def __init__(self, id, name, allergens, may_contain, preferences, quantity=0, expiry=None,
                 condition="good"):
        if not str(name).strip():
            raise ValueError("Item name cannot be empty")
        self.id = id
        self.name = str(name).strip()
        self.allergens = clean_allergens(allergens)      # definitely in the item
        self.may_contain = clean_allergens(may_contain)  # "may contain traces of"
        self.preferences = {p.strip().lower() for p in preferences}  # diets the item suits
        unknown = self.preferences - PREFERENCES
        if unknown:
            raise ValueError(f"Unknown dietary tag(s): {', '.join(sorted(unknown))}")
        self.quantity = clean_quantity(quantity)
        self.expiry = parse_expiry(expiry)
        condition = str(condition or "good").strip().lower()
        if condition not in CONDITIONS:
            raise ValueError(f"Condition must be one of: {', '.join(CONDITIONS)}")
        self.condition = condition

    def is_expired(self, today=None):
        """True if the item has an expiry date that is before today (FR-13)."""
        today = today or date.today()
        return self.expiry is not None and self.expiry < today

    def is_near_expiry(self, today=None):
        """True if the item hasn't expired yet but will within NEAR_EXPIRY_DAYS (FR-12)."""
        today = today or date.today()
        return (self.expiry is not None
                and today <= self.expiry <= today + timedelta(days=NEAR_EXPIRY_DAYS))

    def is_usable(self, today=None):
        """True if the batch is in good condition and not expired, so it can be packed (FR-13)."""
        return self.condition == "good" and not self.is_expired(today)

    def flags(self, today=None):
        """Warnings staff should see for this batch, e.g. ['near expiry', 'damaged'] (FR-12)."""
        found = []
        if self.is_expired(today):
            found.append("expired")
        elif self.is_near_expiry(today):
            found.append("near expiry")
        if self.condition != "good":
            found.append(self.condition)
        if self.quantity == 0:
            found.append("out of stock")
        return found

    def allergy_conflicts(self, client_allergies):
        """
        Returns a list of reasons this item is unsafe for the client's allergies.
        An empty list means no allergy conflict.

        client_allergies is a dict like {"peanuts": "severe", "dairy": "mild"}.
        - Contains an allergen the client has (any severity)  -> blocked
        - May contain an allergen the client has as severe    -> blocked
        """
        reasons = []
        for allergen, severity in client_allergies.items():
            if allergen in self.allergens:
                reasons.append(f"contains {allergen}")
            elif allergen in self.may_contain and severity == "severe":
                reasons.append(f"may contain {allergen} (severe allergy)")
        return reasons

    def suitable_diets(self):
        """The item's dietary tags, minus any its allergens contradict.

        A batch tagged 'vegan' that lists dairy is never treated as vegan, even if it was
        entered that way before the donation check existed (WF-02).
        """
        return {p for p in self.preferences if not DIET_EXCLUDES.get(p, set()) & self.allergens}

    def is_safe_for(self, client_allergies, client_preferences):
        """True if there are no allergy conflicts and the item meets all the client's preferences."""
        no_conflicts = not self.allergy_conflicts(client_allergies)
        meets_prefs = set(client_preferences).issubset(self.suitable_diets())
        return no_conflicts and meets_prefs

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "allergens": sorted(self.allergens),
            "may_contain": sorted(self.may_contain),
            "preferences": sorted(self.preferences),
            "quantity": self.quantity,
            "expiry": self.expiry.isoformat() if self.expiry else None,
            "condition": self.condition,
        }
