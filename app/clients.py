# filename: clients.py
# group: Team 17
# names: Chiara
# created: 29/09/26
# last modified: 11/10/26

from app.storeroom import ALLERGENS, PREFERENCES


# List of severities
SEVERITIES = ("mild", "moderate", "severe")


class Client:
    """Holds a foodbank client and their dietary needs."""

    def __init__(self, id, name, phone, allergies, preferences, household_size=1):
        # TODO [FR-06..08]: Add household composition, accessibility needs, food
        # preferences and preferred communication method; distinguish these from diets.
        if not str(name).strip():
            raise ValueError("Client name cannot be empty")
        self.id = id
        self.name = str(name).strip()
        self.phone = str(phone).strip()
        self.allergies = self._clean_allergies(allergies)  # e.g. {"peanuts": "severe"}
        self.preferences = self._clean_preferences(preferences)  # diets followed, e.g. "vegan"
        self.household_size = self._clean_household_size(household_size)

    @staticmethod
    def _clean_preferences(preferences):
        cleaned = {p.strip().lower() for p in preferences if p.strip()}
        unknown = cleaned - PREFERENCES
        if unknown:
            raise ValueError(f"Unknown dietary need(s): {', '.join(sorted(unknown))}. "
                             f"Choose from {', '.join(sorted(PREFERENCES))}")
        return cleaned

    @staticmethod
    def _clean_household_size(size):
        if isinstance(size, bool):
            raise ValueError("Household size must be a whole number")
        try:
            size = int(size)
        except (TypeError, ValueError):
            raise ValueError(f"Household size must be a whole number, got '{size}'")
        if size < 1 or size > 20:
            raise ValueError("Household size must be between 1 and 20")
        return size

    def _clean_allergies(self, allergies):
        """Checks allergen names and severities. Raises ValueError on anything invalid."""
        if not isinstance(allergies, dict):
            raise ValueError("Allergies must be recorded with a severity, "
                             "e.g. {\"peanuts\": \"severe\"}")
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

    def packing_summary(self):
        """What a packer needs to see, without contact details (NFR-02, NFR-15).

        Uses a client number and first name only, so the screen can be seen at a
        shared counter without exposing private details.
        """
        first_name = self.name.split()[0]
        lines = [f"Client #{self.id} ({first_name}), household of {self.household_size}"]
        diets = ", ".join(sorted(self.preferences)) or "none recorded"
        lines.append(f"  Dietary needs: {diets}")
        if self.allergies:
            allergies = ", ".join(f"{a} ({s})" for a, s in sorted(self.allergies.items()))
            lines.append(f"  Allergies: {allergies}")
        else:
            lines.append("  Allergies: none recorded")
        return "\n".join(lines)

    def can_have(self, item):
        """True if the foodbank item is safe for this client."""
        return item.is_safe_for(self.allergies, self.preferences)

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "phone": self.phone,
            "allergies": dict(self.allergies),
            "preferences": sorted(self.preferences),
            "household_size": self.household_size,
        }