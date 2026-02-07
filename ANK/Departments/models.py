import uuid
from decimal import Decimal
from django.db import models
from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
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
# Department-to-Model Mapping
# Defines which models/pages each department can access
# ──────────────────────────────────────────────────────────────────────────────


class DepartmentModelAccess(models.Model):
    """
    Maps departments to models they can access.
    Super Admin defines this mapping.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    department = models.ForeignKey(
        Department, on_delete=models.CASCADE, related_name="model_accesses"
    )
    content_type = models.ForeignKey(
        ContentType, on_delete=models.CASCADE,
        help_text="The model type (Event, Guest, Session, TravelDetail, Accommodation, EventRegistration, BudgetLineItem, etc.)"
    )
    can_read = models.BooleanField(default=True)
    can_write = models.BooleanField(default=False)
    can_create = models.BooleanField(default=False)
    can_delete = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = [("department", "content_type")]
        indexes = [
            models.Index(fields=["department", "content_type"]),
        ]
        ordering = ["department", "content_type"]

    def __str__(self) -> str:
        return f"{self.department.name} → {self.content_type.model}"


# ──────────────────────────────────────────────────────────────────────────────
# Staff ↔ EventDepartment assignment
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
        ("billed", "Billed"),
        ("partially_paid", "Partially Paid"),
        ("fully_paid", "Fully Paid"),
        ("due", "Due"),
        ("overdue", "Overdue"),
        ("cancelled", "Cancelled"),
    ]

    APPROVAL_STATUS_CHOICES = [
        ("rough_estimate", "Rough Estimate"),
        ("shared_with_client", "Shared with Client"),
        ("pending_from_family", "Pending from Family"),
        ("pending_from_vendor", "Pending from Vendor"),
        ("negotiation", "Negotiation"),
        ("approved", "Approved"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    event_department = models.ForeignKey(
        EventDepartment, on_delete=models.CASCADE, related_name="budget_items"
    )

    # Context
    category = models.CharField(max_length=100)
    sub_category = models.CharField(max_length=100, blank=True)
    description = models.TextField(blank=True)
    sub_event = models.CharField(max_length=120, blank=True)
    function_name = models.CharField(max_length=120, blank=True)
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

    # Vendor & invoice
    vendor_name = models.CharField(max_length=150, blank=True)
    invoice = models.CharField(max_length=120, blank=True)

    approval_status = models.CharField(
        max_length=40,
        choices=APPROVAL_STATUS_CHOICES,
        default="rough_estimate",
        help_text="Track approval progress of this line item",
    )

    # Payment & notes
    payment_status = models.CharField(
        max_length=20, choices=PAYMENT_STATUS_CHOICES, default="unbilled"
    )
    payment_due_date = models.DateField(null=True, blank=True)
    exchange_rate_to_inr = models.DecimalField(
        max_digits=20,
        decimal_places=4,
        default=Decimal("1.0000"),
        help_text="Conversion rate from item currency to INR (e.g. 83.2500 for USD → INR)",
    )
    remarks = models.TextField(blank=True)

    # Misc
    currency = models.CharField(max_length=3, default="INR")
    is_active = models.BooleanField(default=True)

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
# Consolidated Permission Model
# Replaces all 6 UserEvent*FieldPermission models AND BudgetFieldPermission
# Uses ContentType to support any model type
# ──────────────────────────────────────────────────────────────────────────────


def get_model_fields(model_class):
    """Get all field names from a model, excluding reverse relations."""
    fields = []
    for field in model_class._meta.get_fields():
        # Exclude reverse relations (many_to_many, one_to_many)
        if field.many_to_many or (hasattr(field, 'reverse') and field.reverse):
            continue
        # Include direct fields and ForeignKey
        if hasattr(field, 'name'):
            fields.append(field.name)
    return fields


class ModelPermission(models.Model):
    """
    Generic permission model that replaces:
    - All 6 UserEvent*FieldPermission models
    - BudgetFieldPermission (integrated)
    
    Uses ContentType to support any model type.
    Follows the same pattern as BudgetFieldPermission (event_department + field_name).
    """
    PERMISSION_TYPE_CHOICES = [
        ("read", "Read"),
        ("write", "Write"),
        ("read_write", "Read & Write")
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="model_permissions"
    )
    event_department = models.ForeignKey(
        EventDepartment, on_delete=models.CASCADE, related_name="model_permissions"
    )
    content_type = models.ForeignKey(
        ContentType, on_delete=models.CASCADE,
        help_text="The model type (Event, Guest, Session, TravelDetail, Accommodation, EventRegistration, BudgetLineItem, etc.)"
    )
    field_name = models.CharField(
        max_length=100,
        help_text="The field name (e.g., 'email', 'location', 'unit_rate')"
    )
    permission_type = models.CharField(
        max_length=20,
        choices=PERMISSION_TYPE_CHOICES,
        default="read"
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = [("user", "event_department", "content_type", "field_name")]
        indexes = [
            models.Index(fields=["user", "event_department"]),
            models.Index(fields=["event_department", "content_type", "field_name"]),
            models.Index(fields=["content_type", "field_name"]),
        ]
        ordering = ["event_department", "content_type", "field_name"]
    
    def clean(self):
        """Validate field_name exists on model."""
        if self.content_type and self.field_name:
            model_class = self.content_type.model_class()
            if model_class:
                valid_fields = get_model_fields(model_class)
                if self.field_name not in valid_fields:
                    raise ValidationError(
                        f"Field '{self.field_name}' does not exist on {model_class.__name__}"
                    )
    
    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)
    
    def __str__(self):
        return f"{self.user} · {self.event_department} · {self.content_type.model}.{self.field_name} ({self.permission_type})"


# ──────────────────────────────────────────────────────────────────────────────
# Legacy: BudgetFieldPermission (kept for backward compatibility during migration)
# Will be removed after migration to ModelPermission
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
