class Client:
    """Holds a foodbank client and their dietary needs."""

    def __init__(self, id, name, phone, allergies, preferences, household_size=1):
        self.id = id
        self.name = name
        self.phone = phone
        self.allergies = set(allergies)      # allergens the client must avoid
        self.preferences = set(preferences)  # diets the client follows, e.g. "vegan"
        self.household_size = household_size

    def can_have(self, item):
        """True if the foodbank item is safe for this client."""
        return item.is_safe_for(self.allergies, self.preferences)

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "phone": self.phone,
            "allergies": sorted(self.allergies),
            "preferences": sorted(self.preferences),
            "household_size": self.household_size,
        }