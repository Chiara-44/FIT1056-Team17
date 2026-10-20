# filename: tasks.py
# group: Team 17
# names: Chiara
# created: 20/10/26
# last modified: 20/10/26
#
# Volunteer tasks (FR-20 to FR-24) and stock problems reported by volunteers (FR-25).

from datetime import date

TODO = "to do"
IN_PROGRESS = "in progress"
DONE = "done"
TASK_STATUSES = (TODO, IN_PROGRESS, DONE)

# What a volunteer can report about stock (FR-25)
STOCK_PROBLEMS = ("damaged", "expired", "missing")

MAX_TITLE_LENGTH = 100
MAX_TEXT_LENGTH = 300


def _clean_text(text, label, max_length, required=False):
    text = str(text or "").strip()
    if required and not text:
        raise ValueError(f"{label} can't be empty")
    if len(text) > max_length:
        raise ValueError(f"{label} must be {max_length} characters or fewer")
    return text


def _clean_date(value):
    """Accepts a date, an ISO date string or None. Returns an ISO string."""
    if value is None:
        return date.today().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    try:
        return date.fromisoformat(str(value)).isoformat()
    except ValueError:
        raise ValueError(f"Dates must look like YYYY-MM-DD, got '{value}'")


class Task:
    """A job staff give to a volunteer, e.g. 'Check tinned food expiry dates'.

    assigned_to is a volunteer's username. Tasks can only be assigned to
    volunteers, so the username is enough to identify them.
    """

    def __init__(self, id, title, description="", assigned_to="", status=TODO,
                 progress_note="", created_by="", created_on=None, updated_on=None):
        self.id = id
        self.title = _clean_text(title, "Task title", MAX_TITLE_LENGTH, required=True)
        self.description = _clean_text(description, "Description", MAX_TEXT_LENGTH)
        self.assigned_to = str(assigned_to or "").strip()
        if status not in TASK_STATUSES:
            raise ValueError(f"Task status must be one of: {', '.join(TASK_STATUSES)}")
        self.status = status
        self.progress_note = _clean_text(progress_note, "Progress note", MAX_TEXT_LENGTH)
        self.created_by = created_by
        self.created_on = _clean_date(created_on)
        self.updated_on = _clean_date(updated_on or self.created_on)

    def is_done(self):
        return self.status == DONE

    def assign(self, username):
        """Gives the task to a volunteer, or moves it to a different one (FR-21, FR-22)."""
        if self.is_done():
            raise ValueError("This task is already done, so it can't be reassigned")
        if username == self.assigned_to:
            raise ValueError(f"This task is already assigned to {username}")
        self.assigned_to = username
        self.updated_on = date.today().isoformat()

    def update_progress(self, status, note=""):
        """Changes the status and, optionally, the progress note (FR-24)."""
        if status not in TASK_STATUSES:
            raise ValueError(f"Task status must be one of: {', '.join(TASK_STATUSES)}")
        note = _clean_text(note, "Progress note", MAX_TEXT_LENGTH)
        self.status = status
        if note:
            self.progress_note = note
        self.updated_on = date.today().isoformat()

    def summary(self):
        """One line for task lists."""
        who = self.assigned_to or "not assigned yet"
        return f"#{self.id:<3} [{self.status}] {self.title} ({who})"

    def to_dict(self):
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "assigned_to": self.assigned_to,
            "status": self.status,
            "progress_note": self.progress_note,
            "created_by": self.created_by,
            "created_on": self.created_on,
            "updated_on": self.updated_on,
        }


class StockReport:
    """A volunteer's report that some stock is damaged, expired or missing (FR-25).

    Reporting doesn't change the stock count. Staff check the report and adjust
    stock themselves, so one mistaken report can't wipe out real stock.
    """

    def __init__(self, id, item_id, problem, quantity, note="", reported_by="",
                 reported_on=None, resolved=False):
        if problem not in STOCK_PROBLEMS:
            raise ValueError(f"Problem must be one of: {', '.join(STOCK_PROBLEMS)}")
        if isinstance(quantity, bool) or not isinstance(quantity, int) or quantity < 1:
            raise ValueError("Quantity must be a whole number of at least 1")
        self.id = id
        self.item_id = item_id
        self.problem = problem
        self.quantity = quantity
        self.note = _clean_text(note, "Note", MAX_TEXT_LENGTH)
        self.reported_by = reported_by
        self.reported_on = _clean_date(reported_on)
        self.resolved = bool(resolved)

    def to_dict(self):
        return {
            "id": self.id,
            "item_id": self.item_id,
            "problem": self.problem,
            "quantity": self.quantity,
            "note": self.note,
            "reported_by": self.reported_by,
            "reported_on": self.reported_on,
            "resolved": self.resolved,
        }