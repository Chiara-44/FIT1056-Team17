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
