from enum import Enum


class UserRole(str, Enum):
    ADMIN = "Admin"
    USER = "User"


class PermissionRole(str, Enum):
    OWNER = "Owner"
    EDITOR = "Editor"
    VIEWER = "Viewer"
