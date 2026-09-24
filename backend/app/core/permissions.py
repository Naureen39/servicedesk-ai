"""Permission codes and the role -> permission matrix (Section 2.3)."""

from __future__ import annotations

# Permission codes, grouped by resource. `resource:action` convention.
PERM_ANALYTICS_READ = "analytics:read"
PERM_ANALYTICS_EXPORT = "analytics:export"
PERM_APPOINTMENTS_READ = "appointments:read"
PERM_APPOINTMENTS_WRITE = "appointments:write"
PERM_CONVERSATIONS_READ = "conversations:read"
PERM_CONVERSATIONS_TAKEOVER = "conversations:takeover"
PERM_ESCALATIONS_READ = "escalations:read"
PERM_ESCALATIONS_WRITE = "escalations:write"
PERM_KB_READ = "kb:read"
PERM_KB_WRITE = "kb:write"
PERM_ASSISTANT_SETTINGS_WRITE = "assistant_settings:write"
PERM_USERS_MANAGE = "users:manage"
PERM_ROLES_MANAGE = "roles:manage"
PERM_SETTINGS_MANAGE = "settings:manage"
PERM_AUDIT_READ = "audit:read"
PERM_TEST_CONSOLE_USE = "test_console:use"

ALL_PERMISSIONS = [
    PERM_ANALYTICS_READ,
    PERM_ANALYTICS_EXPORT,
    PERM_APPOINTMENTS_READ,
    PERM_APPOINTMENTS_WRITE,
    PERM_CONVERSATIONS_READ,
    PERM_CONVERSATIONS_TAKEOVER,
    PERM_ESCALATIONS_READ,
    PERM_ESCALATIONS_WRITE,
    PERM_KB_READ,
    PERM_KB_WRITE,
    PERM_ASSISTANT_SETTINGS_WRITE,
    PERM_USERS_MANAGE,
    PERM_ROLES_MANAGE,
    PERM_SETTINGS_MANAGE,
    PERM_AUDIT_READ,
    PERM_TEST_CONSOLE_USE,
]

ROLE_ADMIN = "admin"
ROLE_SERVICE_MANAGER = "service_manager"
ROLE_SERVICE_ADVISOR = "service_advisor"
ROLE_ANALYST = "analyst"

ALL_ROLES = [ROLE_ADMIN, ROLE_SERVICE_MANAGER, ROLE_SERVICE_ADVISOR, ROLE_ANALYST]

# Section 2.3 role -> permission matrix.
ROLE_PERMISSIONS: dict[str, list[str]] = {
    ROLE_ADMIN: list(ALL_PERMISSIONS),
    ROLE_SERVICE_MANAGER: [
        PERM_ANALYTICS_READ,
        PERM_ANALYTICS_EXPORT,
        PERM_APPOINTMENTS_READ,
        PERM_APPOINTMENTS_WRITE,
        PERM_CONVERSATIONS_READ,
        PERM_CONVERSATIONS_TAKEOVER,
        PERM_ESCALATIONS_READ,
        PERM_ESCALATIONS_WRITE,
        PERM_KB_READ,
        PERM_KB_WRITE,
        PERM_ASSISTANT_SETTINGS_WRITE,
        PERM_TEST_CONSOLE_USE,
    ],
    ROLE_SERVICE_ADVISOR: [
        PERM_CONVERSATIONS_READ,
        PERM_ESCALATIONS_READ,
        PERM_ESCALATIONS_WRITE,
        PERM_APPOINTMENTS_READ,
        PERM_APPOINTMENTS_WRITE,
        PERM_TEST_CONSOLE_USE,
    ],
    ROLE_ANALYST: [
        PERM_ANALYTICS_READ,
        PERM_ANALYTICS_EXPORT,
    ],
}

# TOTP MFA is mandatory for admin, optional for everyone else (Section 2.2).
MFA_MANDATORY_ROLES = {ROLE_ADMIN}
