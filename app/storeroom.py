ALLERGENS = {"peanuts", "tree nuts", "dairy", "eggs", "gluten", "soy", "fish", "shellfish", "sesame"}
PREFERENCES = {"vegan", "vegetarian", "halal", "kosher"}


class FoodbankItem:
    """Holds an item stored in the foodbank."""

    def __init__(self, name, allergens, preferences):
        self.name = name
        self.allergens = set(allergens)      # allergens the item contains
        self.preferences = set(preferences)  # diets the item is suitable for

    def is_safe_for(self, client_allergies, client_preferences):
        """True if the item has none of the client's allergens and meets all their preferences."""
        no_allergens = self.allergens.isdisjoint(client_allergies)
        meets_prefs = set(client_preferences).issubset(self.preferences)
        return no_allergens and meets_prefs

    def to_dict(self):
        return {
            "name": self.name,
            "allergens": sorted(self.allergens),
            "preferences": sorted(self.preferences),
        }
