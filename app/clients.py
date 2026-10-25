# filename: clients.py
# group: Team 17
# names: Chiara, Harry
# created: 29/09/26
# last modified: 25/10/26

from datetime import date

from app.storeroom import ALLERGENS, PREFERENCES


# List of severities
SEVERITIES = ("mild", "moderate", "severe")

# How the client would like to be contacted (FR-08)
CONTACT_METHODS = ("sms", "phone call", "email", "in person")

# A phone number can use spaces, brackets, hyphens and a leading + but must have
# this many digits (WF-03). 8 covers landlines without an area code, 12 covers +61.
PHONE_DIGITS = (8, 12)


def clean_phone(phone):
    """Checks a phone number looks real. Blank means no phone. Raises ValueError otherwise."""
    phone = str(phone or "").strip()
    if not phone:
        return ""
    allowed = set("0123456789 ()-")
    body = phone[1:] if phone.startswith("+") else phone
    digits = sum(ch.isdigit() for ch in body)
    if set(body) - allowed or not PHONE_DIGITS[0] <= digits <= PHONE_DIGITS[1]:
        raise ValueError(f"Phone number must have {PHONE_DIGITS[0]} to {PHONE_DIGITS[1]} digits "
                         f"(spaces allowed), got '{phone}'")
    return phone

# Accessibility needs staff can record (FR-07). Kept as a fixed list so they can be
# picked by number instead of typed, which avoids spelling mistakes.
ACCESSIBILITY_NEEDS = ("help carrying", "wheelchair access", "large print",
                       "interpreter", "seated waiting area")

MAX_HOUSEHOLD = 20
MAX_NOTE_LENGTH = 300


class Client:
    """Holds a foodbank client and their needs.

    Only information needed to prepare suitable food and contact the client is
    stored (NFR-03). Private notes are kept separately from what packers see.
    """

    def __init__(self, id, name, phone, allergies, preferences, household_size=1,
                 household=None, email="", contact_method=None, accessibility_needs=(),
                 food_notes="", language="", private_notes=None):
        if not str(name).strip():
            raise ValueError("Client name cannot be empty")
        self.id = id
        self.name = str(name).strip()
        self.phone = clean_phone(phone)
        self.email = str(email or "").strip()
        self.allergies = self._clean_allergies(allergies)  # e.g. {"peanuts": "severe"}
        self.preferences = self._clean_preferences(preferences)  # diets followed, e.g. "vegan"
        # Household composition (FR-06). Older records only have a total, so treat it as adults.
        self.household = self._clean_household(household or {"adults": household_size})
        self.accessibility_needs = self._clean_accessibility(accessibility_needs)
        self.food_notes = self._clean_text(food_notes, "Food preferences")
        self.language = self._clean_text(language, "Preferred language")
        self.contact_method = self._clean_contact_method(contact_method)
        self.private_notes = list(private_notes or [])  # [{"text", "by", "date"}], staff only

    # ---------- Validation helpers ----------

    @staticmethod
    def _clean_preferences(preferences):
        cleaned = {p.strip().lower() for p in preferences if p.strip()}
        unknown = cleaned - PREFERENCES
        if unknown:
            raise ValueError(f"Unknown dietary need(s): {', '.join(sorted(unknown))}. "
                             f"Choose from {', '.join(sorted(PREFERENCES))}")
        return cleaned

    @staticmethod
    def _clean_count(value, label):
        if isinstance(value, bool):
            raise ValueError(f"Number of {label} must be a whole number")
        try:
            value = int(value)
        except (TypeError, ValueError):
            raise ValueError(f"Number of {label} must be a whole number, got '{value}'")
        if value < 0:
            raise ValueError(f"Number of {label} can't be negative")
        return value

    @classmethod
    def _clean_household(cls, household):
        """Checks the number of adults, children and infants. The total must be 1 to 20."""
        if not isinstance(household, dict):
            raise ValueError("Household must list adults, children and infants")
        cleaned = {
            "adults": cls._clean_count(household.get("adults", 0), "adults"),
            "children": cls._clean_count(household.get("children", 0), "children"),
            "infants": cls._clean_count(household.get("infants", 0), "infants"),
        }
        total = sum(cleaned.values())
        if total < 1 or total > MAX_HOUSEHOLD:
            raise ValueError(f"Household size must be between 1 and {MAX_HOUSEHOLD}")
        return cleaned

    @staticmethod
    def _clean_accessibility(needs):
        cleaned = {n.strip().lower() for n in needs if n.strip()}
        unknown = cleaned - set(ACCESSIBILITY_NEEDS)
        if unknown:
            raise ValueError(f"Unknown accessibility need(s): {', '.join(sorted(unknown))}")
        return cleaned

    @staticmethod
    def _clean_text(text, label):
        text = str(text or "").strip()
        if len(text) > MAX_NOTE_LENGTH:
            raise ValueError(f"{label} must be {MAX_NOTE_LENGTH} characters or fewer")
        return text

    def _clean_contact_method(self, method):
        """Checks the contact method and that we have the details needed to use it."""
        if not method:
            method = "sms" if self.phone else "in person"   # sensible default
        method = str(method).strip().lower()
        if method not in CONTACT_METHODS:
            raise ValueError(f"Contact method must be one of: {', '.join(CONTACT_METHODS)}")
        if method in ("sms", "phone call") and not self.phone:
            raise ValueError(f"A phone number is needed to contact this client by {method}")
        if method == "email" and "@" not in self.email:
            raise ValueError("A valid email address is needed to contact this client by email")
        return method

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

    # ---------- Household ----------

    @property
    def household_size(self):
        """Total number of people in the household."""
        return sum(self.household.values())

    def household_text(self):
        """e.g. '3 (2 adults, 1 infant)'."""
        parts = []
        for key, singular in (("adults", "adult"), ("children", "child"), ("infants", "infant")):
            n = self.household[key]
            if n:
                word = singular if n == 1 else key
                parts.append(f"{n} {word}")
        return f"{self.household_size} ({', '.join(parts)})"

    # ---------- Private notes ----------

    def add_private_note(self, text, by, when=None):
        text = self._clean_text(text, "Note")
        if not text:
            raise ValueError("Note can't be empty")
        self.private_notes.append({"text": text, "by": by,
                                   "date": (when or date.today()).isoformat()})

    # ---------- What different people see ----------

    def severe_allergies(self):
        """Allergens marked severe, for the packer warning (FR-15, FR-17)."""
        return sorted(a for a, s in self.allergies.items() if s == "severe")

    def packing_summary(self):
        """What a packer needs to see, without contact details (NFR-02, NFR-15).

        Uses a client number and first name only, so the screen can be seen at a
        shared counter without exposing private details. Contact details,
        accessibility needs and private notes are never included.
        """
        first_name = self.name.split()[0]
        lines = [f"Client #{self.id} ({first_name}), household of {self.household_text()}"]
        diets = ", ".join(sorted(self.preferences)) or "none recorded"
        lines.append(f"  Dietary needs: {diets}")
        if self.allergies:
            allergies = ", ".join(f"{a} ({s})" for a, s in sorted(self.allergies.items()))
            lines.append(f"  Allergies: {allergies}")
        else:
            lines.append("  Allergies: none recorded")
        if self.food_notes:
            lines.append(f"  Food preferences: {self.food_notes}")
        return "\n".join(lines)

    def staff_details(self):
        """Full profile for staff and admins (manage_clients), including private notes."""
        lines = [self.packing_summary(),
                 f"  Full name: {self.name}",
                 f"  Phone: {self.phone or '-'}   Email: {self.email or '-'}",
                 f"  Preferred contact: {self.contact_method}",
                 f"  Preferred language: {self.language or '-'}",
                 f"  Accessibility needs: {', '.join(sorted(self.accessibility_needs)) or 'none recorded'}"]
        if self.private_notes:
            lines.append("  Private notes (staff only):")
            for note in self.private_notes:
                lines.append(f"    [{note['date']}, {note['by']}] {note['text']}")
        return "\n".join(lines)

    def can_have(self, item):
        """True if the foodbank item is safe for this client."""
        return item.is_safe_for(self.allergies, self.preferences)

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "phone": self.phone,
            "email": self.email,
            "contact_method": self.contact_method,
            "allergies": dict(self.allergies),
            "preferences": sorted(self.preferences),
            "household_size": self.household_size,
            "household": dict(self.household),
            "accessibility_needs": sorted(self.accessibility_needs),
            "food_notes": self.food_notes,
            "language": self.language,
            "private_notes": list(self.private_notes),
        }
