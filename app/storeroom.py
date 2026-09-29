ALLERGENS = {"peanuts", "tree nuts", "dairy", "eggs", "gluten", "soy", "fish", "shellfish", "sesame"}
PREFERENCES = {"vegan", "vegetarian", "halal", "kosher"}


def clean_allergens(names):
    """Lowercases allergen names and checks they're in ALLERGENS. Raises ValueError on a typo."""
    cleaned = set()
    for name in names:
        name = name.strip().lower()
        if name not in ALLERGENS:
            raise ValueError(f"Unknown allergen: '{name}'")
        cleaned.add(name)
    return cleaned


class FoodbankItem:
    """Holds an item stored in the foodbank storeroom."""

    def __init__(self, id, name, allergens, may_contain, preferences, quantity=0):
        self.id = id
        self.name = name
        self.allergens = clean_allergens(allergens)      # definitely in the item
        self.may_contain = clean_allergens(may_contain)  # "may contain traces of"
        self.preferences = set(preferences)              # diets the item is suitable for
        self.quantity = quantity

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

    def is_safe_for(self, client_allergies, client_preferences):
        """True if there are no allergy conflicts and the item meets all the client's preferences."""
        no_conflicts = not self.allergy_conflicts(client_allergies)
        meets_prefs = set(client_preferences).issubset(self.preferences)
        return no_conflicts and meets_prefs

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "allergens": sorted(self.allergens),
            "may_contain": sorted(self.may_contain),
            "preferences": sorted(self.preferences),
            "quantity": self.quantity,
        }