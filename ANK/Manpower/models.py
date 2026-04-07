import uuid
from decimal import Decimal
from django.db import models
from django.conf import settings
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils import timezone


class Skill(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(max_length=120, unique=True, blank=True)

    def save(self, *args, **kwargs):
        if not self.slug:
            from django.utils.text import slugify
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name

    class Meta:
        ordering = ["name"]


class Freelancer(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=200)
    skills = models.ManyToManyField(
        Skill, blank=True, related_name="freelancers"
    )
    skill_category = models.CharField(max_length=100, blank=True)
    city = models.CharField(max_length=100)
    address = models.TextField(blank=True)
    parent_name = models.CharField(max_length=200, blank=True, help_text='S/o / D/o')
    id_type = models.CharField(max_length=20, choices=[('PAN', 'PAN'), ('AADHAR', 'Aadhar')], default='PAN')
    id_number = models.CharField(max_length=100, blank=True, help_text='PAN / Aadhar Number')
    
    # Banking Details
    bank_account_name = models.CharField(max_length=200, blank=True)
    bank_name = models.CharField(max_length=200, blank=True)
    bank_account_number = models.CharField(max_length=100, blank=True)
    bank_branch = models.CharField(max_length=200, blank=True)
    bank_ifsc = models.CharField(max_length=50, blank=True)
    
    contact_phone = models.CharField(max_length=20, blank=True)
    email = models.EmailField(unique=True, blank=True, null=True)
    base_daily_rate = models.DecimalField(
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
    skill = models.ForeignKey(
        Skill, on_delete=models.SET_NULL, null=True, blank=True, related_name="requirements"
    )
    skill_category = models.CharField(max_length=100, blank=True)
    quantity_required = models.PositiveIntegerField(default=1)
    estimated_days = models.DecimalField(
        max_digits=5, decimal_places=1, default=Decimal("1.0")
    )
    max_unit_rate = models.DecimalField(
        max_digits=12, decimal_places=2, default=Decimal("0.00")
    )
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
    is_extra = models.BooleanField(default=False)
    sessions = models.ManyToManyField(
        "Events.Session",
        related_name="manpower_requirements",
        blank=True,
        help_text="Sessions this requirement is applicable for"
    )

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
    requirement = models.ForeignKey(
        ManpowerRequirement,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="allocations",
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
    is_extra = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("freelancer", "event_department")

    def __str__(self):
        return f"{self.freelancer.name} -> {self.event_department} ({self.status})"

    def clean(self):
        from django.core.exceptions import ValidationError
        if self.status in ["confirmed", "soft_blocked"]:
            # Check if already has ANY allocation in this event (excluding itself)
            event_id = self.event_department.event_id
            exists = FreelancerAllocation.objects.filter(
                freelancer=self.freelancer,
                event_department__event_id=event_id
            ).exclude(pk=self.pk).exists()
            
            if exists:
                raise ValidationError(f"Freelancer is already allocated to this event.")

            # Use allocation dates if set, otherwise fallback to event dates
            current_start = self.start_date or self.event_department.event.start_date
            current_end = self.end_date or self.event_department.event.end_date

            if current_start and current_end:
                # Find overlapping allocations that are not released
                overlapping = FreelancerAllocation.objects.filter(
                    freelancer=self.freelancer,
                ).exclude(pk=self.pk).exclude(status="released")

                conflicts = []
                for other in overlapping:
                    other_start = other.start_date or other.event_department.event.start_date
                    other_end = other.end_date or other.event_department.event.end_date
                    
                    if other_start and other_end:
                        # Standard overlap: (StartA <= EndB) and (EndA >= StartB)
                        if other_start <= current_end and other_end >= current_start:
                            conflicts.append(other)

                # Gracefully handle based on status
                confirmed_conflicts = [c for c in conflicts if c.status == "confirmed"]
                
                if self.status == "confirmed" and confirmed_conflicts:
                    events = ", ".join([str(c.event_department.event) for c in confirmed_conflicts])
                    raise ValidationError(
                        f"Freelancer is already CONFIRMED for overlapping dates in: {events}"
                    )
                
                # If we are soft blocking, we just warn or allow, but the backend clean 
                # should probably prevent double CONFIRMED. 
                # For now, let's keep it strict for confirmed status.

    def save(self, *args, **kwargs):
        self.full_clean()
        
        # Check if the instance already exists to track changes
        old_start_date = None
        old_end_date = None
        is_new = self._state.adding
        
        if not is_new:
            try:
                old_instance = FreelancerAllocation.objects.get(pk=self.pk)
                old_start_date = old_instance.start_date
                old_end_date = old_instance.end_date
            except FreelancerAllocation.DoesNotExist:
                pass

        super().save(*args, **kwargs)

        # Sync daily meals if dates changed or it's a new allocation
        # Only sync if both dates are set
        if self.start_date and self.end_date:
            if is_new or self.start_date != old_start_date or self.end_date != old_end_date:
                self.sync_daily_meals()

    def sync_daily_meals(self):
        """
        Synchronizes AllocationDailyMeal records with the allocation's start and end dates.
        Adds records for new days and removes them for removed days.
        """
        from datetime import timedelta
        
        # 1. Identify current dates in the range
        current_dates = set()
        delta = (self.end_date - self.start_date).days
        for i in range(delta + 1):
            current_dates.add(self.start_date + timedelta(days=i))

        # 2. Identify existing meal records for this allocation
        existing_meals = AllocationDailyMeal.objects.filter(allocation=self)
        existing_dates = set(m.date for m in existing_meals)

        # 3. Remove records for dates no longer in the range
        to_delete = existing_dates - current_dates
        if to_delete:
            AllocationDailyMeal.objects.filter(allocation=self, date__in=to_delete).delete()

        # 4. Add records for new dates in the range
        to_add = sorted(list(current_dates - existing_dates))
        for d in to_add:
            AllocationDailyMeal.objects.get_or_create(allocation=self, date=d)

        # Trigger cost sheet update if it exists
        if hasattr(self, "cost_sheet"):
            self.cost_sheet.save()

    @property
    def total_meal_allowance(self):
        from django.db.models import Sum
        # Note: Summing over aggregate might be more efficient
        result = self.daily_meals.aggregate(
            b_sum=Sum("breakfast_amount"),
            l_sum=Sum("lunch_amount"),
            d_sum=Sum("dinner_amount")
        )
        total = (result.get("b_sum") or Decimal("0.00")) + \
                (result.get("l_sum") or Decimal("0.00")) + \
                (result.get("d_sum") or Decimal("0.00"))
        return total


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
        # Auto-compute total_estimated_cost using meal logistics
        self.total_estimated_cost = (
            (self.negotiated_rate * self.days_planned)
            + (self.allocation.total_meal_allowance)
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
        max_digits=5, decimal_places=1, default=Decimal("1.0"),
        help_text="Used for meal allowance calculations (set number of days)"
    )
    total_engagement_days = models.DecimalField(
        max_digits=5, decimal_places=1, default=Decimal("1.0"),
        help_text="Sum of days from all engagement periods for rate calculation"
    )
    engagement_periods = models.JSONField(
        default=list, blank=True,
        help_text="List of periods: [{'start': 'YYYY-MM-DD', 'end': 'YYYY-MM-DD', 'days': 1.0}]"
    )
    travel_adjustments = models.DecimalField(
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
        # 1. Capture state
        old_actual_days_worked = None
        old_engagement_periods = []
        is_new = self._state.adding
        if not is_new:
            try:
                old_instance = PostEventAdjustment.objects.get(pk=self.pk)
                old_actual_days_worked = old_instance.actual_days_worked
                old_engagement_periods = old_instance.engagement_periods
            except PostEventAdjustment.DoesNotExist:
                pass

        # 2. Expand allocation dates if periods changed
        if self.engagement_periods and self.engagement_periods != old_engagement_periods:
            try:
                starts = [p['start'] for p in self.engagement_periods if p.get('start')]
                ends = [p['end'] for p in self.engagement_periods if p.get('end')]
                if starts and ends:
                    new_min_start = min([models.DateField().to_python(s) for s in starts])
                    new_max_end = max([models.DateField().to_python(e) for e in ends])
                    
                    alloc = self.allocation
                    date_changed = False
                    if not alloc.start_date or new_min_start < alloc.start_date:
                        alloc.start_date = new_min_start
                        date_changed = True
                    if not alloc.end_date or new_max_end > alloc.end_date:
                        alloc.end_date = new_max_end
                        date_changed = True
                    
                    if date_changed:
                        alloc.save(update_fields=['start_date', 'end_date'])
            except Exception as e:
                print(f"Error syncing allocation dates: {e}")

        # 3. Sync worked status for meals BEFORE calculating total
        if is_new or self.actual_days_worked != old_actual_days_worked or self.engagement_periods != old_engagement_periods:
            self.sync_worked_days()

        # 4. Auto-compute revised_total
        cost_sheet = self.allocation.cost_sheet
        per_day_rate = self.override_negotiated_rate if self.override_negotiated_rate is not None else cost_sheet.negotiated_rate
        
        self.revised_total = (
            (per_day_rate * self.total_engagement_days)
            + (self.actual_meal_allowance)
            + cost_sheet.travel_costs
            + self.travel_adjustments
            + self.other_adjustments
        )
        super().save(*args, **kwargs)

    def sync_worked_days(self):
        """
        Updates the is_worked status of AllocationDailyMeal records based on engagement_periods.
        A day is marked as worked if it falls within ANY of the engagement periods.
        """
        meals = self.allocation.daily_meals.all()
        periods = self.engagement_periods or []
        
        # Convert periods to date objects for comparison
        parsed_periods = []
        for p in periods:
            try:
                s = models.DateField().to_python(p.get('start'))
                e = models.DateField().to_python(p.get('end'))
                if s and e:
                    parsed_periods.append((s, e))
            except:
                continue

        for meal in meals:
            # Check if this meal date falls in any period
            worked = False
            for s, e in parsed_periods:
                if s <= meal.date <= e:
                    worked = True
                    break
            
            if meal.is_worked != worked:
                meal.is_worked = worked
                meal.save(update_fields=["is_worked"])

    @property
    def actual_meal_allowance(self):
        from django.db.models import Sum
        # Only sum allowances for days marked as worked
        result = self.allocation.daily_meals.filter(is_worked=True).aggregate(
            b_sum=Sum("breakfast_amount"),
            l_sum=Sum("lunch_amount"),
            d_sum=Sum("dinner_amount")
        )
        total = (result.get("b_sum") or Decimal("0.00")) + \
                (result.get("l_sum") or Decimal("0.00")) + \
                (result.get("d_sum") or Decimal("0.00"))
        return total

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
    total_engagement_days = models.DecimalField(max_digits=5, decimal_places=1, default=Decimal("1.0"))
    engagement_periods = models.JSONField(default=list, blank=True)
    travel_adjustments = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    actual_meal_allowance = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
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
        "submitted": {"approved", "draft"},
        "approved": {"payable", "draft"},
        "payable": {"paid", "draft"},
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
    secure_token = models.UUIDField(default=uuid.uuid4, unique=True, null=True)
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

    def save(self, *args, **kwargs):
        if not self.secure_token:
            self.secure_token = uuid.uuid4()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.invoice_number} ({self.status})"

    def transition_to(self, new_status):
        if new_status == self.status:
            return
        if new_status not in self.VALID_TRANSITIONS.get(self.status, set()):
            raise ValueError(f"Invalid transition from {self.status} to {new_status}")
        
        self.status = new_status
        now = timezone.now()
        
        if new_status == "draft":
            # Reset timeline
            self.approved_at = None
            self.payable_at = None
            self.paid_at = None
        elif new_status == "approved":
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


class ManpowerSettings(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    default_breakfast_rate = models.DecimalField(
        max_digits=10, decimal_places=2, default=Decimal("0.00")
    )
    default_lunch_rate = models.DecimalField(
        max_digits=10, decimal_places=2, default=Decimal("0.00")
    )
    default_dinner_rate = models.DecimalField(
        max_digits=10, decimal_places=2, default=Decimal("0.00")
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Manpower Settings"
        verbose_name_plural = "Manpower Settings"

    def __str__(self):
        return "Global Manpower Settings"

    def save(self, *args, **kwargs):
        if not self.pk and ManpowerSettings.objects.exists():
            return
        super().save(*args, **kwargs)

    @classmethod
    def get_settings(cls):
        obj, created = cls.objects.get_or_create()
        return obj


class AllocationDailyMeal(models.Model):
    MEAL_TYPE_CHOICES = [
        ("crew_meal", "Crew Meal"),
        ("allowance", "Allowance"),
        ("cash", "Cash (Paid on Spot)"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    allocation = models.ForeignKey(
        FreelancerAllocation, on_delete=models.CASCADE, related_name="daily_meals"
    )
    date = models.DateField()
    is_worked = models.BooleanField(default=True)

    breakfast_type = models.CharField(
        max_length=20, choices=MEAL_TYPE_CHOICES, default="allowance"
    )
    lunch_type = models.CharField(
        max_length=20, choices=MEAL_TYPE_CHOICES, default="allowance"
    )
    dinner_type = models.CharField(
        max_length=20, choices=MEAL_TYPE_CHOICES, default="allowance"
    )

    breakfast_amount = models.DecimalField(
        max_digits=10, decimal_places=2, default=Decimal("0.00")
    )
    lunch_amount = models.DecimalField(
        max_digits=10, decimal_places=2, default=Decimal("0.00")
    )
    dinner_amount = models.DecimalField(
        max_digits=10, decimal_places=2, default=Decimal("0.00")
    )

    class Meta:
        unique_together = ("allocation", "date")
        ordering = ["date"]

    def __str__(self):
        return f"Meals for {self.allocation.freelancer.name} on {self.date}"

    def save(self, *args, **kwargs):
        settings = ManpowerSettings.get_settings()
        if self.breakfast_type == "allowance":
            self.breakfast_amount = settings.default_breakfast_rate
        else:
            self.breakfast_amount = Decimal("0.00")

        if self.lunch_type == "allowance":
            self.lunch_amount = settings.default_lunch_rate
        else:
            self.lunch_amount = Decimal("0.00")

        if self.dinner_type == "allowance":
            self.dinner_amount = settings.default_dinner_rate
        else:
            self.dinner_amount = Decimal("0.00")

        super().save(*args, **kwargs)

