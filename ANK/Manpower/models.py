import uuid
from decimal import Decimal
from django.db import models
from django.conf import settings
from django.core.validators import MinValueValidator, MaxValueValidator


class Freelancer(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=200)
    skill_category = models.CharField(max_length=100)
    city = models.CharField(max_length=100)
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
    accepted_at = models.DateTimeField(null=True, blank=True)
    signed_pdf = models.FileField(upload_to="mous/", null=True, blank=True)

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
    extra_allowances = models.DecimalField(
        max_digits=12, decimal_places=2, default=Decimal("0.00")
    )
    revised_total = models.DecimalField(
        max_digits=15, decimal_places=2, default=Decimal("0.00")
    )
    freelancer_comments = models.TextField(blank=True)
    admin_approval_status = models.CharField(
        max_length=20, choices=APPROVAL_STATUS_CHOICES, default="pending"
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        # Auto-compute revised_total from allocation cost sheet and adjustments
        cost_sheet = self.allocation.cost_sheet
        self.revised_total = (
            (cost_sheet.negotiated_rate * self.actual_days_worked)
            + (cost_sheet.daily_allowance * self.actual_days_worked)
            + cost_sheet.travel_costs
            + self.extra_allowances
        )
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Adjustment for {self.allocation}"


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