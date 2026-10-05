import json
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import bcrypt
import jwt
from fastapi import Depends, Header, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import Connection, text

from app.config import get_settings
from app.db import get_conn, row

ROLES = ("SUPER_ADMIN", "MUNICIPAL_ADMIN", "ALCALDE", "EMERGENCIAS", "SECPLAN", "COMUNICACIONES", "VIEWER")

PERMISSIONS: dict[str, set[str]] = {
    "upload": {"SUPER_ADMIN", "MUNICIPAL_ADMIN", "EMERGENCIAS", "SECPLAN"},
    "configure": {"SUPER_ADMIN", "MUNICIPAL_ADMIN"},
    "alert:create": {"SUPER_ADMIN", "MUNICIPAL_ADMIN", "EMERGENCIAS"},
    "source:run": {"SUPER_ADMIN", "MUNICIPAL_ADMIN"},
    "audit:read": {"SUPER_ADMIN", "MUNICIPAL_ADMIN"},
}

bearer = HTTPBearer(auto_error=False)


@dataclass(frozen=True)
class Principal:
    user_id: int
    email: str
    name: str
    role: str
    municipality_id: int

    def can(self, permission: str) -> bool:
        return self.role in PERMISSIONS.get(permission, set())


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(password: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode(), hashed.encode())
    except ValueError:
        return False


def issue_token(user: dict) -> str:
    settings = get_settings()
    now = datetime.now(UTC)
    payload = {
        "sub": str(user["id"]),
        "role": user["role"],
        "mid": user["municipality_id"],
        "iat": now,
        "exp": now + timedelta(minutes=settings.jwt_ttl_minutes),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm="HS256")


def current_principal(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
    x_municipality_id: int | None = Header(default=None),
    conn: Connection = Depends(get_conn),
) -> Principal:
    if credentials is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Inicie sesión")
    try:
        payload = jwt.decode(credentials.credentials, get_settings().jwt_secret, algorithms=["HS256"])
    except jwt.PyJWTError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Sesión inválida o expirada")
    user = row(conn, "select id, email, name, role, municipality_id, active from app_user where id = :id", id=int(payload["sub"]))
    if not user or not user["active"]:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Usuario inactivo")
    municipality_id = user["municipality_id"]
    if user["role"] == "SUPER_ADMIN":
        municipality_id = x_municipality_id or municipality_id
        if municipality_id is None:
            municipality_id = row(conn, "select id from municipality order by id limit 1")
            municipality_id = municipality_id["id"] if municipality_id else None
    if municipality_id is None:
        raise HTTPException(status.HTTP_409_CONFLICT, "No hay comunas configuradas")
    return Principal(user["id"], user["email"], user["name"], user["role"], municipality_id)


def require(permission: str):
    def checker(principal: Principal = Depends(current_principal)) -> Principal:
        if not principal.can(permission):
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Su rol no tiene permiso para esta acción")
        return principal

    return checker


def audit(conn: Connection, principal: Principal | None, action: str, target: str | None = None, details: dict | None = None,
          municipality_id: int | None = None) -> None:
    conn.execute(
        text("insert into audit_log (user_id, municipality_id, action, target, details) values (:u, :m, :a, :t, cast(:d as jsonb))"),
        {
            "u": principal.user_id if principal else None,
            "m": municipality_id or (principal.municipality_id if principal else None),
            "a": action,
            "t": target,
            "d": json.dumps(details or {}, ensure_ascii=False, default=str),
        },
    )
