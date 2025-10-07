# Events/models/budget_models.py

import uuid
from decimal import Decimal
from django.db import models
from django.contrib.auth import get_user_model

# Adjust this import if your Event is defined elsewhere
from Events.models.event_model import Event

User = get_user_model()


# ──────────────────────────────────────────────────────────────────────────────
# Global Department master (reused across events)
# ──────────────────────────────────────────────────────────────────────────────


class Department(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=120, unique=True)
    slug = models.SlugField(max_length=140, unique=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name


# ──────────────────────────────────────────────────────────────────────────────
# EventDepartment = (Event × Department)
# Owns the budget sheet (its line items)
# ──────────────────────────────────────────────────────────────────────────────


class EventDepartment(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    event = models.ForeignKey(
        Event, on_delete=models.CASCADE, related_name="event_departments"
    )
    department = models.ForeignKey(
        Department, on_delete=models.PROTECT, related_name="event_departments"
    )
    display_name = models.CharField(
        max_length=150,
        blank=True,
        help_text="Optional override name for this department within the event.",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = [("event", "department")]
        indexes = [
            models.Index(fields=["event", "department"]),
        ]
        ordering = ["event_id", "department_id"]

    def __str__(self) -> str:
        return f"{self.event_id} · {self.department.name}"


# ──────────────────────────────────────────────────────────────────────────────
# Staff ↔ EventDepartment assignment  ← (this is the one you asked for)
# (Separate from your EventStaff/SessionStaff — scoped to a single EventDepartment)
# ──────────────────────────────────────────────────────────────────────────────


class EventDepartmentStaffAssignment(models.Model):
    ROLE_CHOICES = [
        ("manager", "Manager"),
        ("editor", "Editor"),
        ("viewer", "Viewer"),
        ("other", "Other"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    event_department = models.ForeignKey(
        EventDepartment, on_delete=models.CASCADE, related_name="staff_assignments"
    )
    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="event_department_assignments"
    )
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default="viewer")

    assigned_on = models.DateTimeField(auto_now_add=True)
    removed_on = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = [("event_department", "user")]
        indexes = [
            models.Index(fields=["event_department", "user"]),
        ]
        ordering = ["event_department_id", "user_id"]

    def __str__(self) -> str:
        return f"{self.user_id} -> {self.event_department_id} ({self.role})"


# ──────────────────────────────────────────────────────────────────────────────
# Budget sheet line item (attached ONLY to EventDepartment)
# Tax is always percent: keep ONLY tax_rate_pct
# ──────────────────────────────────────────────────────────────────────────────


class BudgetLineItem(models.Model):
    MARKUP_MODE_CHOICES = [
        ("none", "None"),
        ("percent", "Percent"),
        ("flat", "Flat"),
    ]
    PAYMENT_STATUS_CHOICES = [
        ("unbilled", "Unbilled"),
        ("due", "Due"),
        ("partially_paid", "Partially Paid"),
        ("paid", "Paid"),
        ("overdue", "Overdue"),
        ("cancelled", "Cancelled"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    event_department = models.ForeignKey(
        EventDepartment, on_delete=models.CASCADE, related_name="budget_items"
    )

    # Context
    category = models.CharField(max_length=100)
    sub_category = models.CharField(max_length=100, blank=True)
    description = models.TextField(blank=True)
    sub_event = models.CharField(max_length=120, blank=True)  # "Sub Event / Day"
    function_name = models.CharField(max_length=120, blank=True)  # "Function"
    venue = models.CharField(max_length=120, blank=True)

    # Quantities & rates
    quantity = models.DecimalField(
        max_digits=10, decimal_places=2, default=Decimal("1.00")
    )
    unit = models.CharField(max_length=40, default="unit")
    shifts_or_days = models.DecimalField(
        max_digits=10, decimal_places=2, default=Decimal("1.00")
    )

    unit_rate = models.DecimalField(
        max_digits=12, decimal_places=2, default=Decimal("0.00")
    )  # base vendor rate

    # Tax (always percent)
    tax_rate_pct = models.DecimalField(
        max_digits=7,
        decimal_places=4,
        default=Decimal("0.0000"),
        help_text="Tax percentage (e.g., 18.0 for 18%)",
    )

    # Markup
    markup_mode = models.CharField(
        max_length=10, choices=MARKUP_MODE_CHOICES, default="none"
    )
    markup_value = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True
    )  # percent or flat

    # Commercials (manual for now; calcs can be added later)
    advance_amount = models.DecimalField(
        max_digits=12, decimal_places=2, default=Decimal("0.00")
    )
    balance_amount = models.DecimalField(
        max_digits=12, decimal_places=2, default=Decimal("0.00")
    )

    # Vendor & invoice (no Vendor model; single invoice ref)
    vendor_name = models.CharField(max_length=150, blank=True)
    invoice = models.CharField(max_length=120, blank=True)

    # Payment & notes
    payment_status = models.CharField(
        max_length=20, choices=PAYMENT_STATUS_CHOICES, default="unbilled"
    )
    payment_due_date = models.DateField(null=True, blank=True)
    remarks = models.TextField(blank=True)

    # Misc
    currency = models.CharField(max_length=3, default="INR")
    is_active = models.BooleanField(default=True)

    # Timestamps only (as requested)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["created_at"]
        indexes = [
            models.Index(fields=["event_department"]),
            models.Index(fields=["category", "sub_category"]),
            models.Index(fields=["payment_status"]),
        ]

    def __str__(self) -> str:
        return f"{self.category} / {self.sub_category} · {self.description[:30]}"


# ──────────────────────────────────────────────────────────────────────────────
# Per-user, per-event-department, per-field access (view access)
# Store field keys as plain text (e.g., "unit_rate", "vendor_name", …)
# ──────────────────────────────────────────────────────────────────────────────


class BudgetFieldPermission(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="budget_field_perms"
    )
    event_department = models.ForeignKey(
        EventDepartment, on_delete=models.CASCADE, related_name="budget_field_perms"
    )
    field_key = models.SlugField(
        max_length=80,
        help_text="Machine key of the field (e.g., 'unit_rate', 'vendor_name').",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = [("user", "event_department", "field_key")]
        indexes = [
            models.Index(fields=["user", "event_department"]),
            models.Index(fields=["event_department", "field_key"]),
        ]

    def __str__(self) -> str:
        return f"{self.user_id} · {self.event_department_id} · {self.field_key}"
