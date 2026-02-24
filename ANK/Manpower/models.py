import uuid
from decimal import Decimal
from django.db import models
from django.conf import settings
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils import timezone


class Freelancer(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=200)
    skill_category = models.CharField(max_length=100)
    city = models.CharField(max_length=100)
    address = models.TextField(blank=True)
    parent_name = models.CharField(max_length=200, blank=True, help_text='S/o / D/o')
    id_number = models.CharField(max_length=100, blank=True, help_text='PAN / Aadhar')
    contact_phone = models.CharField(max_length=20, blank=True)
    email = models.EmailField(unique=True, blank=True, null=True)
    base_daily_rate = models.DecimalField(
        max_digits=12, decimal_places=2, default=Decimal("0.00")
    )
    standard_allowance = models.DecimalField(
        max_digits=12, decimal_places=2, default=Decimal("0.00")
    )
    documents = models.JSONField(
        default=dict, blank=True, help_text="Links to documents or metadata"
    )
    average_rating = models.DecimalField(
        max_digits=3, decimal_places=2, default=Decimal("0.00")
    )
    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return f"{self.name} ({self.skill_category})"


class ManpowerRequirement(models.Model):
    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("fulfilled", "Fulfilled"),
        ("cancelled", "Cancelled"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    event_department = models.ForeignKey(
        "Departments.EventDepartment",
        on_delete=models.CASCADE,
        related_name="manpower_requirements",
    )
    skill_category = models.CharField(max_length=100)
    quantity_required = models.PositiveIntegerField(default=1)
    estimated_days = models.DecimalField(
        max_digits=5, decimal_places=1, default=Decimal("1.0")
    )
    max_unit_rate = models.DecimalField(
        max_digits=12, decimal_places=2, default=Decimal("0.00")
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.quantity_required}x {self.skill_category} for {self.event_department}"


class FreelancerAllocation(models.Model):
    STATUS_CHOICES = [
        ("soft_blocked", "Soft Blocked"),
        ("confirmed", "Confirmed"),
        ("released", "Released"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    freelancer = models.ForeignKey(
        Freelancer, on_delete=models.CASCADE, related_name="allocations"
    )
    event_department = models.ForeignKey(
        "Departments.EventDepartment",
        on_delete=models.CASCADE,
        related_name="manpower_allocations",
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="soft_blocked")
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)
    is_rated = models.BooleanField(default=False)
    is_adjustment_editable = models.BooleanField(default=False)
    role_description = models.TextField(blank=True)
    assigned_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("freelancer", "event_department")

    def __str__(self):
        return f"{self.freelancer.name} -> {self.event_department} ({self.status})"

    def clean(self):
        from django.core.exceptions import ValidationError
        if self.status == "confirmed":
            # Check if already has ANY allocation in this event
            event_id = self.event_department.event_id
            exists = FreelancerAllocation.objects.filter(
                freelancer=self.freelancer,
                event_department__event_id=event_id
            ).exclude(pk=self.pk).exists()
            if exists:
                raise ValidationError(f"Freelancer is already allocated to this event.")
            # Check for overlapping confirmed assignments
            current_event = self.event_department.event
            if current_event.start_date and current_event.end_date:
                overlapping = FreelancerAllocation.objects.filter(
                    freelancer=self.freelancer,
                    status="confirmed",
                    event_department__event__start_date__lte=current_event.end_date,
                    event_department__event__end_date__gte=current_event.start_date,
                ).exclude(pk=self.pk)

                if overlapping.exists():
                    events = ", ".join([str(a.event_department.event) for a in overlapping])
                    raise ValidationError(
                        f"Freelancer is already confirmed for overlapping events: {events}"
                    )

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)


class EventCostSheet(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    allocation = models.OneToOneField(
        FreelancerAllocation, on_delete=models.CASCADE, related_name="cost_sheet"
    )
    negotiated_rate = models.DecimalField(
        max_digits=12, decimal_places=2, default=Decimal("0.00")
    )
    days_planned = models.DecimalField(
        max_digits=5, decimal_places=1, default=Decimal("1.0")
    )
    daily_allowance = models.DecimalField(
        max_digits=12, decimal_places=2, default=Decimal("0.00")
    )
    travel_costs = models.DecimalField(
        max_digits=12, decimal_places=2, default=Decimal("0.00")
    )
    total_estimated_cost = models.DecimalField(
        max_digits=15, decimal_places=2, default=Decimal("0.00")
    )
    budget_item = models.ForeignKey(
        "Departments.BudgetLineItem",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="manpower_costs",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        # Auto-compute total_estimated_cost
        self.total_estimated_cost = (
            (self.negotiated_rate * self.days_planned)
            + (self.daily_allowance * self.days_planned)
            + self.travel_costs
        )
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Cost for {self.allocation}"


class MoU(models.Model):
    STATUS_CHOICES = [
        ("draft", "Draft"),
        ("sent", "Sent"),
        ("accepted", "Accepted"),
        ("rejected", "Rejected"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    allocation = models.ForeignKey(
        FreelancerAllocation, on_delete=models.CASCADE, related_name="mous"
    )
    secure_token = models.UUIDField(default=uuid.uuid4, unique=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="draft")
    template_data = models.JSONField(
        default=dict, help_text="Snapshot of terms at time of issue"
    )
    expires_at = models.DateTimeField(null=True, blank=True)
    access_code = models.CharField(max_length=12, blank=True)
    accepted_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"MoU for {self.allocation} ({self.status})"


class PostEventAdjustment(models.Model):
    APPROVAL_STATUS_CHOICES = [
        ("pending", "Pending"),
        ("approved", "Approved"),
        ("disputed", "Disputed"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    allocation = models.OneToOneField(
        FreelancerAllocation, on_delete=models.CASCADE, related_name="adjustment"
    )
    actual_days_worked = models.DecimalField(
        max_digits=5, decimal_places=1, default=Decimal("1.0")
    )
    actual_daily_allowance = models.DecimalField(
        max_digits=12, decimal_places=2, default=Decimal("0.00")
    )
    other_adjustments = models.DecimalField(
        max_digits=12, decimal_places=2, default=Decimal("0.00")
    )
    override_negotiated_rate = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True
    )
    revised_total = models.DecimalField(
        max_digits=15, decimal_places=2, default=Decimal("0.00")
    )
    freelancer_comments = models.TextField(blank=True)
    admin_approval_status = models.CharField(
        max_length=20, choices=APPROVAL_STATUS_CHOICES, default="pending"
    )
    secure_token = models.UUIDField(default=uuid.uuid4, unique=True)
    freelancer_submitted_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        # Auto-compute revised_total
        cost_sheet = self.allocation.cost_sheet
        per_day_rate = self.override_negotiated_rate if self.override_negotiated_rate is not None else cost_sheet.negotiated_rate
        
        self.revised_total = (
            (per_day_rate * self.actual_days_worked)
            + (self.actual_daily_allowance * self.actual_days_worked)
            + cost_sheet.travel_costs
            + self.other_adjustments
        )
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Adjustment for {self.allocation}"


class PostEventAdjustmentRevision(models.Model):
    ACTION_CHOICES = [
        ("prefill", "Admin Pre-fill"),
        ("submission", "Freelancer Submission"),
        ("dispute", "Admin Dispute"),
        ("approval", "Final Approval"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    adjustment = models.ForeignKey(
        PostEventAdjustment, on_delete=models.CASCADE, related_name="revisions"
    )
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True
    )
    actor_name = models.CharField(max_length=200, blank=True)
    action_type = models.CharField(max_length=20, choices=ACTION_CHOICES)
    
    # Snapshot of values
    actual_days_worked = models.DecimalField(max_digits=5, decimal_places=1)
    actual_daily_allowance = models.DecimalField(max_digits=12, decimal_places=2)
    other_adjustments = models.DecimalField(max_digits=12, decimal_places=2)
    override_negotiated_rate = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    revised_total = models.DecimalField(max_digits=15, decimal_places=2)
    
    comments = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]


class FreelancerRating(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    freelancer = models.ForeignKey(
        Freelancer, on_delete=models.CASCADE, related_name="ratings"
    )
    event = models.ForeignKey(
        "Events.Event", on_delete=models.CASCADE, related_name="freelancer_ratings"
    )
    rated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True
    )
    score = models.PositiveIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)]
    )
    feedback = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("freelancer", "event")

    def __str__(self):
        return f"Rating for {self.freelancer} in {self.event} ({self.score}/5)"

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        # Recompute average rating for freelancer
        from django.db.models import Avg
        avg_score = FreelancerRating.objects.filter(freelancer=self.freelancer).aggregate(Avg("score"))["score__avg"]
        if avg_score is not None:
            self.freelancer.average_rating = Decimal(str(round(avg_score, 2)))
            self.freelancer.save(update_fields=["average_rating"])


class EventManpowerLock(models.Model):
    event = models.OneToOneField(
        "Events.Event",
        on_delete=models.CASCADE,
        related_name="manpower_lock",
    )
    is_locked = models.BooleanField(default=False)
    reason = models.TextField(blank=True)
    locked_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="manpower_locks_created",
    )
    locked_at = models.DateTimeField(null=True, blank=True)
    unlocked_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="manpower_locks_released",
    )
    unlocked_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def lock(self, user, reason=""):
        self.is_locked = True
        self.reason = reason or ""
        self.locked_by = user
        self.locked_at = timezone.now()
        self.unlocked_by = None
        self.unlocked_at = None
        self.save()

    def unlock(self, user):
        self.is_locked = False
        self.unlocked_by = user
        self.unlocked_at = timezone.now()
        self.save()


class InvoiceWorkflow(models.Model):
    STATUS_CHOICES = [
        ("draft", "Draft"),
        ("submitted", "Submitted"),
        ("approved", "Approved"),
        ("payable", "Payable"),
        ("paid", "Paid"),
    ]

    VALID_TRANSITIONS = {
        "draft": {"submitted"},
        "submitted": {"approved"},
        "approved": {"payable"},
        "payable": {"paid"},
        "paid": set(),
    }

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    adjustment = models.OneToOneField(
        PostEventAdjustment, on_delete=models.CASCADE, related_name="invoice_workflow"
    )
    event = models.ForeignKey(
        "Events.Event", on_delete=models.CASCADE, related_name="manpower_invoices"
    )
    event_department = models.ForeignKey(
        "Departments.EventDepartment",
        on_delete=models.CASCADE,
        related_name="manpower_invoices",
    )
    freelancer = models.ForeignKey(
        Freelancer, on_delete=models.CASCADE, related_name="invoices"
    )
    invoice_number = models.CharField(max_length=64, unique=True)
    due_date = models.DateField(null=True, blank=True)
    payable_amount = models.DecimalField(
        max_digits=15, decimal_places=2, default=Decimal("0.00")
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="draft")
    approved_at = models.DateTimeField(null=True, blank=True)
    payable_at = models.DateTimeField(null=True, blank=True)
    paid_at = models.DateTimeField(null=True, blank=True)
    paid_reference = models.CharField(max_length=120, blank=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.invoice_number} ({self.status})"

    def transition_to(self, new_status):
        if new_status == self.status:
            return
        if new_status not in self.VALID_TRANSITIONS.get(self.status, set()):
            raise ValueError(f"Invalid transition from {self.status} to {new_status}")
        self.status = new_status
        now = timezone.now()
        if new_status == "approved":
            self.approved_at = now
        elif new_status == "payable":
            self.payable_at = now
        elif new_status == "paid":
            self.paid_at = now


class ManpowerAuditLog(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    event = models.ForeignKey(
        "Events.Event",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="manpower_audit_logs",
    )
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="manpower_audit_actions",
    )
    action = models.CharField(max_length=120)
    target_model = models.CharField(max_length=120)
    target_id = models.CharField(max_length=64)
    details = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
