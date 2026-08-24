"""Users, sign-in and what each role is allowed to touch.

Three roles cover a shop this size:

* **admin**    — the owner: everything, including users, settings and backups.
* **manager**  — a senior pharmacist: stock, purchases, reports, returns.
* **cashier**  — the counter: sell, look up medicines, take customer details.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from .. import security
from ..db import Database
from ..errors import AuthError, NotFoundError, ValidationError
from .audit import AuditService

ROLES = ("admin", "manager", "cashier")
ROLE_LABELS = {
    "admin": "Administrator (owner)",
    "manager": "Manager / Senior pharmacist",
    "cashier": "Cashier / Salesman",
}

# A permission missing from this table is denied to everyone but the admin.
PERMISSIONS: dict[str, tuple[str, ...]] = {
    "pos.sell": ("admin", "manager", "cashier"),
    "pos.discount_override": ("admin", "manager"),
    "pos.price_override": ("admin", "manager"),
    "catalog.view": ("admin", "manager", "cashier"),
    "catalog.manage": ("admin", "manager"),
    "stock.view": ("admin", "manager", "cashier"),
    "stock.manage": ("admin", "manager"),
    "purchases.view": ("admin", "manager"),
    "purchases.manage": ("admin", "manager"),
    "parties.view": ("admin", "manager", "cashier"),
    "parties.manage": ("admin", "manager", "cashier"),
    "parties.payments": ("admin", "manager"),
    "returns.manage": ("admin", "manager"),
    "reports.view": ("admin", "manager"),
    "sales.history": ("admin", "manager", "cashier"),
    "sales.delete": ("admin",),
    "users.manage": ("admin",),
    "settings.manage": ("admin",),
    "backup.manage": ("admin",),
}


@dataclass(frozen=True)
class User:
    id: int
    username: str
    full_name: str
    role: str
    is_active: bool = True
    must_change_password: bool = False

    @property
    def role_label(self) -> str:
        return ROLE_LABELS.get(self.role, self.role.title())

    def can(self, permission: str) -> bool:
        if self.role == "admin":
            return True
        return self.role in PERMISSIONS.get(permission, ())


def _user_from_row(row) -> User:
    return User(
        id=row["id"],
        username=row["username"],
        full_name=row["full_name"],
        role=row["role"],
        is_active=bool(row["is_active"]),
        must_change_password=bool(row["must_change_password"]),
    )


class AuthService:
    """Sign-in plus user administration. Holds the currently signed-in user."""

    def __init__(self, db: Database, audit: AuditService | None = None):
        self.db = db
        self.audit = audit or AuditService(db)
        self.current_user: User | None = None

    # ------------------------------------------------------------ bootstrap
    def ensure_default_admin(self) -> None:
        """First run has no users; create ``admin`` / ``admin123``.

        The account is flagged so the first sign-in must set a real password.
        """
        if self.db.scalar("SELECT COUNT(*) FROM users"):
            return
        self.db.insert(
            "users",
            {
                "username": "admin",
                "full_name": "Pharmacy Owner",
                "password_hash": security.hash_password("admin123"),
                "role": "admin",
                "is_active": 1,
                "must_change_password": 1,
                "created_at": datetime.now().isoformat(timespec="seconds"),
            },
        )

    # --------------------------------------------------------------- sign in
    def login(self, username: str, password: str) -> User:
        row = self.db.query_one(
            "SELECT * FROM users WHERE username = ? COLLATE NOCASE", (username.strip(),)
        )
        if row is None or not security.verify_password(password, row["password_hash"]):
            raise AuthError("Incorrect username or password.")
        if not row["is_active"]:
            raise AuthError("This account has been disabled. Ask the owner to enable it.")
        user = _user_from_row(row)
        self.db.update(
            "users",
            user.id,
            {"last_login_at": datetime.now().isoformat(timespec="seconds")},
        )
        self.current_user = user
        self.audit.log("login", user=user, entity="user", entity_id=user.id)
        return user

    def logout(self) -> None:
        if self.current_user:
            self.audit.log("logout", user=self.current_user)
        self.current_user = None

    def require(self, permission: str) -> None:
        user = self.current_user
        if user is None:
            raise AuthError("You are signed out. Please sign in again.")
        if not user.can(permission):
            raise AuthError(
                f"Your role ({user.role_label}) is not allowed to do this. "
                "Ask the owner to sign in."
            )

    # ------------------------------------------------------------ user admin
    def list_users(self, include_inactive: bool = True) -> list:
        sql = "SELECT * FROM users"
        if not include_inactive:
            sql += " WHERE is_active = 1"
        return self.db.query(sql + " ORDER BY is_active DESC, username")

    def get_user(self, user_id: int) -> User:
        row = self.db.query_one("SELECT * FROM users WHERE id = ?", (user_id,))
        if row is None:
            raise NotFoundError("That user no longer exists.")
        return _user_from_row(row)

    def create_user(
        self,
        username: str,
        full_name: str,
        password: str,
        role: str,
        *,
        must_change_password: bool = True,
    ) -> int:
        username = (username or "").strip()
        full_name = (full_name or "").strip()
        if not username:
            raise ValidationError("Username is required.")
        if " " in username:
            raise ValidationError("Username cannot contain spaces.")
        if not full_name:
            raise ValidationError("Full name is required.")
        if role not in ROLES:
            raise ValidationError(f"Unknown role: {role}")
        problem = security.password_problem(password)
        if problem:
            raise ValidationError(problem)
        if self.db.query_one(
            "SELECT id FROM users WHERE username = ? COLLATE NOCASE", (username,)
        ):
            raise ValidationError(f"The username '{username}' is already taken.")
        user_id = self.db.insert(
            "users",
            {
                "username": username,
                "full_name": full_name,
                "password_hash": security.hash_password(password),
                "role": role,
                "is_active": 1,
                "must_change_password": 1 if must_change_password else 0,
                "created_at": datetime.now().isoformat(timespec="seconds"),
            },
        )
        self.audit.log(
            "user.create",
            user=self.current_user,
            entity="user",
            entity_id=user_id,
            details=f"{username} ({role})",
        )
        return user_id

    def update_user(
        self, user_id: int, *, full_name: str | None = None, role: str | None = None
    ) -> None:
        values: dict = {}
        if full_name is not None:
            if not full_name.strip():
                raise ValidationError("Full name is required.")
            values["full_name"] = full_name.strip()
        if role is not None:
            if role not in ROLES:
                raise ValidationError(f"Unknown role: {role}")
            if role != "admin" and self._is_last_active_admin(user_id):
                raise ValidationError(
                    "This is the only administrator left — change another user to "
                    "administrator first."
                )
            values["role"] = role
        self.db.update("users", user_id, values)
        self.audit.log("user.update", user=self.current_user, entity="user", entity_id=user_id)

    def set_password(self, user_id: int, password: str, *, force_change: bool = False) -> None:
        problem = security.password_problem(password)
        if problem:
            raise ValidationError(problem)
        self.db.update(
            "users",
            user_id,
            {
                "password_hash": security.hash_password(password),
                "must_change_password": 1 if force_change else 0,
            },
        )
        if self.current_user and self.current_user.id == user_id:
            self.current_user = self.get_user(user_id)
        self.audit.log(
            "user.password", user=self.current_user, entity="user", entity_id=user_id
        )

    def change_own_password(self, current_password: str, new_password: str) -> None:
        if self.current_user is None:
            raise AuthError("You are signed out.")
        row = self.db.query_one(
            "SELECT password_hash FROM users WHERE id = ?", (self.current_user.id,)
        )
        if row is None or not security.verify_password(current_password, row["password_hash"]):
            raise AuthError("Your current password is not correct.")
        if current_password == new_password:
            raise ValidationError("The new password must be different from the old one.")
        self.set_password(self.current_user.id, new_password)

    def set_active(self, user_id: int, active: bool) -> None:
        if not active and self._is_last_active_admin(user_id):
            raise ValidationError("You cannot disable the only administrator.")
        if not active and self.current_user and self.current_user.id == user_id:
            raise ValidationError("You cannot disable the account you are signed in with.")
        self.db.update("users", user_id, {"is_active": 1 if active else 0})
        self.audit.log(
            "user.enable" if active else "user.disable",
            user=self.current_user,
            entity="user",
            entity_id=user_id,
        )

    def _is_last_active_admin(self, user_id: int) -> bool:
        row = self.db.query_one("SELECT role, is_active FROM users WHERE id = ?", (user_id,))
        if row is None or row["role"] != "admin" or not row["is_active"]:
            return False
        others = self.db.scalar(
            "SELECT COUNT(*) FROM users WHERE role = 'admin' AND is_active = 1 AND id != ?",
            (user_id,),
        )
        return others == 0
