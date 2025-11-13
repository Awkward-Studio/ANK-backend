from django.db import models
import uuid


class TaxSlab(models.Model):
    """
    Defines a tax slab for a particular financial year or regime.
    Example:
        0 - 250000  → 0%
        250001 - 500000 → 5%
        500001 - 1000000 → 20%
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    name = models.CharField(
        max_length=100,
        help_text="Label for this slab set, e.g. 'FY 2024-25 New Regime'",
    )

    regime = models.CharField(
        max_length=50,
        blank=True,
        null=True,
        help_text="Optional tag for tax regime type (e.g. 'old', 'new', 'corporate')",
    )

    financial_year = models.CharField(
        max_length=20,
        help_text="Financial year this slab applies to (e.g. '2024-25')",
        null=True,
        blank=True,
    )

    lower_limit = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        help_text="Minimum income for this slab (inclusive)",
        null=True,
        blank=True,
    )

    upper_limit = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Maximum income for this slab (exclusive). Leave blank for 'no upper limit'.",
    )

    tax_rate = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        help_text="Tax rate percentage for this slab (e.g. 5.00 for 5%)",
    )

    surcharge_rate = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=0,
        help_text="Optional surcharge percentage applied above this slab, if any",
        null=True,
        blank=True,
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["financial_year", "lower_limit"]
        verbose_name = "Tax Slab"
        verbose_name_plural = "Tax Slabs"
        unique_together = ("financial_year", "regime", "lower_limit")

    def __str__(self):
        upper = (
            f"{self.upper_limit:,.2f}" if self.upper_limit is not None else "No Limit"
        )
        return f"{self.name}: ₹{self.lower_limit:,.2f} - ₹{upper} @ {self.tax_rate}%"
