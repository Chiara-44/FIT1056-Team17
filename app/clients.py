# filename: clients.py
# group: Team 17
# names: Chiara
# created: 29/09/26
# last modified: 29/09/26

from app.storeroom import ALLERGENS


# List of severities
SEVERITIES = ("mild", "moderate", "severe")


class Client:
    """Holds a foodbank client and their dietary needs."""

    def __init__(self, id, name, phone, allergies, preferences, household_size=1):
        # TODO [FR-06..08]: Add household composition, accessibility needs, food
        # preferences and preferred communication method; distinguish these from diets.
        # TODO: Validate name/phone, positive household size and supported dietary tags.
        self.id = id
        self.name = name
        self.phone = phone
        self.allergies = self._clean_allergies(allergies)  # e.g. {"peanuts": "severe"}
        self.preferences = set(preferences)                # diets the client follows, e.g. "vegan"
        self.household_size = household_size

    def _clean_allergies(self, allergies):
        """Checks allergen names and severities. Raises ValueError on anything invalid."""
        cleaned = {}
        for allergen, severity in allergies.items():
            allergen = allergen.strip().lower()
            severity = severity.strip().lower()
            if allergen not in ALLERGENS:
                raise ValueError(f"Unknown allergen: '{allergen}'")
            if severity not in SEVERITIES:
                raise ValueError(f"Severity for {allergen} must be one of {SEVERITIES}, got '{severity}'")
            cleaned[allergen] = severity
        return cleaned

    def severe_allergies(self):
        """Allergens marked severe, for the packer warning (FR-15, FR-17)."""
        return sorted(a for a, s in self.allergies.items() if s == "severe")

    def can_have(self, item):
        """True if the foodbank item is safe for this client."""
        return item.is_safe_for(self.allergies, self.preferences)

    # TODO: Persist new client fields here and load them in ScheduleManager._build_clients.
    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "phone": self.phone,
            "allergies": dict(self.allergies),
            "preferences": sorted(self.preferences),
            "household_size": self.household_size,
        }