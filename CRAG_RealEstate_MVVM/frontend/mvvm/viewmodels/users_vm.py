from mvvm.services.api_client import ApiClient


class UsersViewModel:
    def __init__(self, api: ApiClient):
        self.api = api

    def list_users(self) -> list[dict]:
        return self.api.get("/users")

    def create_user(self, username: str, password: str, name: str, email: str, role: str = "staff") -> dict:
        return self.api.post(
            "/users",
            {"username": username, "password": password, "role": role, "name": name, "email": email},
        )

    def update_user(self, username: str, name: str | None = None, email: str | None = None, password: str | None = None) -> dict:
        payload = {}
        if name is not None:
            payload["name"] = name
        if email is not None:
            payload["email"] = email
        if password is not None:
            payload["password"] = password
        return self.api.put(f"/users/{username}", payload)

    def update_role(self, username: str, role: str) -> dict:
        return self.api.put(f"/users/{username}/role", {"role": role})

    def delete_user(self, username: str) -> dict:
        return self.api.delete(f"/users/{username}")
