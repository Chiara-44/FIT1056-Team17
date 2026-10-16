# filename: pickups.py
# group: Team 17
# names: Harry
# created: 16/10/26
# last modified: 16/10/26

from datetime import datetime

SCHEDULED = "scheduled"
COLLECTED = "collected"
CANCELLED = "cancelled"
STATUSES = (SCHEDULED, COLLECTED, CANCELLED)

# Formats staff can type. DD/MM/YYYY is included because that's how Australians write dates.
TIME_FORMATS = ("%Y-%m-%d %H:%M", "%d/%m/%Y %H:%M")


def parse_pickup_time(value):
    """Turns 'YYYY-MM-DD HH:MM' or 'DD/MM/YYYY HH:MM' (or a datetime) into a datetime.

    Raises ValueError with a plain message if the text can't be read.
    """
    if isinstance(value, datetime):
        return value.replace(second=0, microsecond=0)
    text = str(value).strip()
    for fmt in TIME_FORMATS:
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            pass
    raise ValueError(f"Pickup time must look like 25/10/2026 14:30 or 2026-10-25 14:30, got '{text}'")


class Pickup:
    """A scheduled time for a client to collect a completed hamper (FR-26, FR-27)."""

    def __init__(self, id, hamper_id, client_id, scheduled_at, status=SCHEDULED,
                 collected_at=None, collected_by=""):
        if status not in STATUSES:
            raise ValueError(f"Pickup status must be one of {', '.join(STATUSES)}")
        self.id = id
        self.hamper_id = hamper_id
        self.client_id = client_id
        self.scheduled_at = parse_pickup_time(scheduled_at)
        self.status = status
        self.collected_at = parse_pickup_time(collected_at) if collected_at else None
        self.collected_by = collected_by  # username of whoever handed the hamper over

    def is_active(self):
        """True while the pickup is still waiting to be collected."""
        return self.status == SCHEDULED

    def is_overdue(self, now=None):
        """True if the pickup time has passed and the hamper still hasn't been collected."""
        now = now or datetime.now()
        return self.is_active() and self.scheduled_at < now

    def mark_collected(self, username, when=None):
        if self.status == COLLECTED:
            raise ValueError("This hamper has already been collected")
        if self.status == CANCELLED:
            raise ValueError("This pickup was cancelled")
        self.status = COLLECTED
        self.collected_at = parse_pickup_time(when or datetime.now())
        self.collected_by = username

    def cancel(self):
        if not self.is_active():
            raise ValueError(f"Only scheduled pickups can be cancelled (this one is {self.status})")
        self.status = CANCELLED

    def to_dict(self):
        return {
            "id": self.id,
            "hamper_id": self.hamper_id,
            "client_id": self.client_id,
            "scheduled_at": self.scheduled_at.strftime("%Y-%m-%d %H:%M"),
            "status": self.status,
            "collected_at": self.collected_at.strftime("%Y-%m-%d %H:%M") if self.collected_at else None,
            "collected_by": self.collected_by,
        }
