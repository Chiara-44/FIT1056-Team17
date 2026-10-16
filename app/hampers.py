# filename: hampers.py
# group: Team 17
# names: Chiara
# created: 11/10/26
# last modified: 11/10/26

DRAFT = "draft"
COMPLETED = "completed"


class Hamper:
    """A food hamper being packed for (or already given to) one client.

    Stock is only deducted when the hamper is completed, so a draft can be
    cancelled at any time without touching the storeroom.
    """

    def __init__(self, id, client_id, packer_username, packer_role, items=None,
                 status=DRAFT, allergy_acknowledged=False, substitution_notes=None):
        self.id = id
        self.client_id = client_id
        # IDs overlap between roles, so the packer is identified by role + username
        self.packer_username = packer_username
        self.packer_role = packer_role
        # {item_id: quantity}. JSON keys are strings, so convert back to int on load
        self.items = {int(k): int(v) for k, v in (items or {}).items()}
        self.status = status
        self.allergy_acknowledged = allergy_acknowledged
        self.substitution_notes = list(substitution_notes or [])

    def is_draft(self):
        return self.status == DRAFT

    def quantity_of(self, item_id):
        return self.items.get(item_id, 0)

    def add(self, item_id, quantity):
        self.items[item_id] = self.quantity_of(item_id) + quantity

    def remove(self, item_id, quantity=None):
        """Removes some (or all, if quantity is None) of an item. Returns the amount removed."""
        current = self.quantity_of(item_id)
        if current == 0:
            return 0
        if quantity is None or quantity >= current:
            del self.items[item_id]
            return current
        self.items[item_id] = current - quantity
        return quantity

    def total_items(self):
        return sum(self.items.values())

    def to_dict(self):
        return {
            "id": self.id,
            "client_id": self.client_id,
            "packer_username": self.packer_username,
            "packer_role": self.packer_role,
            "items": {str(k): v for k, v in self.items.items()},
            "status": self.status,
            "allergy_acknowledged": self.allergy_acknowledged,
            "substitution_notes": list(self.substitution_notes),
        }
