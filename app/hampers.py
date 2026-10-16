# filename: hampers.py
# group: Team 17
# names: Chiara, Harry
# created: 11/10/26
# last modified: 16/10/26

DRAFT = "draft"
COMPLETED = "completed"


class HamperItem:
    """One line in a hamper: a stock item and how many of it are packed.

    If the line was added as a replacement for something unavailable,
    substituted_for holds the item number it replaced (FR-18).
    """

    def __init__(self, item_id, quantity, substituted_for=None):
        self.item_id = int(item_id)
        self.quantity = self._check_quantity(quantity)
        self.substituted_for = int(substituted_for) if substituted_for is not None else None

    @staticmethod
    def _check_quantity(quantity):
        if isinstance(quantity, bool) or not isinstance(quantity, int) or quantity < 1:
            raise ValueError("A hamper item needs a quantity of at least 1")
        return quantity

    def add(self, quantity):
        self.quantity += self._check_quantity(quantity)

    def remove(self, quantity):
        """Takes some of this item out. Returns the amount actually removed."""
        removed = min(self._check_quantity(quantity), self.quantity)
        self.quantity -= removed
        return removed


class Hamper:
    """A food hamper being packed for (or already given to) one client.

    A hamper is made up of HamperItem lines (composition: the lines only exist as
    part of their hamper). Stock is only deducted when the hamper is completed, so a
    draft can be cancelled at any time without touching the storeroom.
    """

    def __init__(self, id, client_id, packer_username, packer_role, items=None,
                 status=DRAFT, allergy_acknowledged=False, substitution_notes=None,
                 substitutions=None):
        self.id = id
        self.client_id = client_id
        # IDs overlap between roles, so the packer is identified by role + username
        self.packer_username = packer_username
        self.packer_role = packer_role
        self.lines = []
        # Saved as {item_id: quantity}. JSON keys are strings, so convert back to int on load
        for item_id, quantity in (items or {}).items():
            self.lines.append(HamperItem(int(item_id), int(quantity)))
        # Saved as {new_item_id: replaced_item_id}
        for new_id, old_id in (substitutions or {}).items():
            line = self.line_for(int(new_id))
            if line:
                line.substituted_for = int(old_id)
        self.status = status
        self.allergy_acknowledged = allergy_acknowledged
        self.substitution_notes = list(substitution_notes or [])

    @property
    def items(self):
        """{item_id: quantity} for every line, in the order they were added."""
        return {line.item_id: line.quantity for line in self.lines}

    def is_draft(self):
        return self.status == DRAFT

    def line_for(self, item_id):
        """The HamperItem for this stock item, or None if it isn't in the hamper."""
        for line in self.lines:
            if line.item_id == item_id:
                return line
        return None

    def quantity_of(self, item_id):
        line = self.line_for(item_id)
        return line.quantity if line else 0

    def add(self, item_id, quantity):
        line = self.line_for(item_id)
        if line:
            line.add(quantity)
        else:
            self.lines.append(HamperItem(item_id, quantity))

    def remove(self, item_id, quantity=None):
        """Removes some (or all, if quantity is None) of an item. Returns the amount removed."""
        line = self.line_for(item_id)
        if line is None:
            return 0
        removed = line.remove(quantity if quantity is not None else line.quantity)
        if line.quantity == 0:
            self.lines.remove(line)
        return removed

    def total_items(self):
        return sum(line.quantity for line in self.lines)

    def to_dict(self):
        return {
            "id": self.id,
            "client_id": self.client_id,
            "packer_username": self.packer_username,
            "packer_role": self.packer_role,
            "items": {str(line.item_id): line.quantity for line in self.lines},
            "substitutions": {str(line.item_id): line.substituted_for
                              for line in self.lines if line.substituted_for is not None},
            "status": self.status,
            "allergy_acknowledged": self.allergy_acknowledged,
            "substitution_notes": list(self.substitution_notes),
        }
