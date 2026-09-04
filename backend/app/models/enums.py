import enum


class DayOfWeek(enum.StrEnum):
    mon = "mon"
    tue = "tue"
    wed = "wed"
    thu = "thu"
    fri = "fri"


class OrderSource(enum.StrEnum):
    catalog = "catalog"
    custom_request = "custom_request"


class OrderStatus(enum.StrEnum):
    pending = "pending"
    confirmed = "confirmed"
    completed = "completed"
    cancelled = "cancelled"


class AdminRole(enum.StrEnum):
    owner = "owner"
    staff = "staff"
