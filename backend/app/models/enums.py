from enum import StrEnum


class SocietyStatus(StrEnum):
    ACTIVE = "active"
    SUSPENDED = "suspended"
    DELETED = "deleted"


class Role(StrEnum):
    OWNER = "owner"
    ADMIN = "admin"
    VOLUNTEER = "volunteer"
    MEMBER = "member"


# Higher number == more privilege. super_admin is a platform flag on users, not a society role.
ROLE_RANK = {Role.MEMBER: 1, Role.VOLUNTEER: 2, Role.ADMIN: 3, Role.OWNER: 4}


class MembershipStatus(StrEnum):
    PENDING = "pending"
    ACTIVE = "active"
    REMOVED = "removed"


class EventStatus(StrEnum):
    DRAFT = "draft"
    PUBLISHED = "published"
    CLOSED = "closed"
    CANCELLED = "cancelled"


class ValidDays(StrEnum):
    ALL = "all"
    SPECIFIC = "specific"


class OrderStatus(StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    CANCELLED = "cancelled"


class HolderType(StrEnum):
    MEMBER = "member"
    GUEST = "guest"


class PassStatus(StrEnum):
    ACTIVE = "active"
    REVOKED = "revoked"


class GalleryStatus(StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class OrderFlag(StrEnum):
    DUPLICATE_UTR = "duplicate_utr"
    AMOUNT_MISMATCH = "amount_mismatch"
    MISSING_UTR = "missing_utr"


class UploadPurpose(StrEnum):
    SCREENSHOT = "screenshot"  # private bucket
    BANNER = "banner"
    GALLERY = "gallery"
    LOGO = "logo"
    AVATAR = "avatar"
