class User:
    def __init__(self, id, name, username, password, role):
        self.id = id
        self.name = name
        self.username = username
        self.password = password
        self.role = role

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "username": self.username,
            "password": self.password,
            "role": self.role,
        }


class volunteerUser(User):
    """Represents a volunteer."""
    # Implement the volunteerUser class, inheriting from User.
    def __init__(self, name):
        super().__init__(name)


class staffUser(User):
    """Represents a member of staff."""
    # Implement the staffUser class, inheriting from User.
    def __init__(self, name):
        super().__init__(name)


class adminUser(User):
    """Represents an admin."""
    # Implement the adminUser class, inheriting from User.
    def __init__(self, name):
        super().__init__(name)