import uuid
import os
from django.db import models
from django.utils import timezone
from django.conf import settings
from Events.models.event_registration_model import EventRegistration
from Events.models.event_model import Event
from cryptography.fernet import Fernet
import logging

logger = logging.getLogger(__name__)


class MessageTemplate(models.Model):
    """
    A message template scoped (optionally) to an Event.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    event = models.ForeignKey(
        Event,
        on_delete=models.CASCADE,
        related_name="message_templates",
        null=True,
        blank=True,
    )
    name = models.CharField(max_length=200, db_index=True)
    message = models.TextField()
    desc = models.TextField(blank=True, null=True)
    is_rsvp_message = models.BooleanField(default=False)

    # Media attachment fields for template messages
    MEDIA_TYPE_CHOICES = [
        ('image', 'Image'),
        ('video', 'Video'),
        ('document', 'Document'),
    ]
    media_type = models.CharField(
        max_length=20,
        choices=MEDIA_TYPE_CHOICES,
        null=True,
        blank=True,
        help_text='Type of media attached to this template'
    )
    media_url = models.URLField(
        max_length=500,
        null=True,
        blank=True,
        help_text='Original media file URL'
    )
    media_id = models.CharField(
        max_length=255,
        null=True,
        blank=True,
        help_text='WhatsApp Business API media ID returned after upload'
    )

    created_at = models.DateTimeField(default=timezone.now, editable=False)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = (("event", "name"),)
        ordering = ("name",)

    def __str__(self):
        return f"{self.name} ({'RSVP' if self.is_rsvp_message else 'General'})"


class MessageTemplateVariable(models.Model):
    """
    A variable belonging to a MessageTemplate, with an optional default value and ordering.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    template = models.ForeignKey(
        MessageTemplate, on_delete=models.CASCADE, related_name="variables"
    )
    variable_name = models.CharField(max_length=100)
    variable_value = models.TextField(blank=True)  # optional default/fallback
    variable_description = models.TextField(blank=True)
    variable_position = models.PositiveIntegerField(default=0)

    class Meta:
        unique_together = (("template", "variable_name"),)
        ordering = ("variable_position", "variable_name")

    def __str__(self):
        return f"{self.variable_name} (template={self.template_id})"


class QueuedMessage(models.Model):
    """
    Stores the final rendered local message we wanted to send but couldn't
    because the 24h WhatsApp window was closed.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    event = models.ForeignKey(
        Event, on_delete=models.CASCADE, related_name="queued_messages"
    )
    registration = models.ForeignKey(
        EventRegistration, on_delete=models.CASCADE, related_name="queued_messages"
    )

    template = models.ForeignKey(
        MessageTemplate, on_delete=models.SET_NULL, null=True, blank=True
    )

    # Final text already rendered with {{vars}}. No surprises later.
    rendered_text = models.TextField()

    sent = models.BooleanField(default=False)
    created_at = models.DateTimeField(default=timezone.now)
    sent_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        indexes = [
            models.Index(fields=["registration", "sent"]),
        ]

    def mark_sent(self):
        self.sent = True
        self.sent_at = timezone.now()
        self.save(update_fields=["sent", "sent_at"])

    def __str__(self):
        return f"QueuedMessage(reg={self.registration_id}, sent={self.sent})"


class WhatsAppBusinessAccount(models.Model):
    """
    Stores WhatsApp Business Account (WABA) credentials.
    One WABA can have multiple phone numbers.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    waba_id = models.CharField(
        max_length=100,
        unique=True,
        db_index=True,
        help_text="WhatsApp Business Account ID (e.g., 864800316406577)",
    )
    name = models.CharField(
        max_length=200, blank=True, help_text="Business account display name"
    )
    _encrypted_token = models.TextField(
        blank=True, help_text="Fernet-encrypted permanent system user access token"
    )
    is_active = models.BooleanField(default=True, db_index=True)
    created_at = models.DateTimeField(default=timezone.now, editable=False)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["is_active", "-created_at"]),
        ]
        verbose_name = "WhatsApp Business Account"
        verbose_name_plural = "WhatsApp Business Accounts"

    def get_token(self) -> str:
        """
        Decrypt and return the access token.
        Returns empty string if no token is set or decryption fails.
        """
        if not self._encrypted_token:
            return ""
        try:
            encryption_key = getattr(settings, "WHATSAPP_ENCRYPTION_KEY", None)
            if not encryption_key:
                logger.warning(
                    "[WABA] WHATSAPP_ENCRYPTION_KEY not set, cannot decrypt token"
                )
                return ""
            fernet = Fernet(encryption_key.encode())
            return fernet.decrypt(self._encrypted_token.encode()).decode()
        except Exception as e:
            logger.exception(f"[WABA] Failed to decrypt token: {e}")
            return ""

    def set_token(self, token: str):
        """
        Encrypt and store the access token.
        """
        if not token:
            self._encrypted_token = ""
            return
        try:
            encryption_key = getattr(settings, "WHATSAPP_ENCRYPTION_KEY", None)
            if not encryption_key:
                raise ValueError("WHATSAPP_ENCRYPTION_KEY not configured in settings")
            fernet = Fernet(encryption_key.encode())
            self._encrypted_token = fernet.encrypt(token.encode()).decode()
        except Exception as e:
            logger.exception(f"[WABA] Failed to encrypt token: {e}")
            raise

    def __str__(self):
        return f"{self.name or self.waba_id} ({'Active' if self.is_active else 'Inactive'})"


class WhatsAppPhoneNumber(models.Model):
    """
    Registry of WhatsApp phone numbers with their credentials and metadata.
    Each number can optionally belong to a WABA.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    business_account = models.ForeignKey(
        WhatsAppBusinessAccount,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="phone_numbers",
        help_text="Parent WhatsApp Business Account",
    )
    phone_number_id = models.CharField(
        max_length=100,
        unique=True,
        db_index=True,
        help_text="Phone Number ID from Meta (e.g., 2485856308207334)",
    )
    asset_id = models.CharField(
        max_length=100,
        db_index=True,
        blank=True,
        help_text="Asset ID if applicable",
    )
    waba_id = models.CharField(
        max_length=100,
        db_index=True,
        blank=True,
        help_text="WABA ID (denormalized for quick lookup)",
    )
    display_phone_number = models.CharField(
        max_length=20, help_text="Display format (e.g., +919876543210)"
    )
    verified_name = models.CharField(
        max_length=200, blank=True, help_text="Verified business name on WhatsApp"
    )
    quality_rating = models.CharField(
        max_length=20,
        blank=True,
        choices=[
            ("GREEN", "Green"),
            ("YELLOW", "Yellow"),
            ("RED", "Red"),
            ("UNKNOWN", "Unknown"),
        ],
        default="UNKNOWN",
        help_text="Quality rating from Meta",
    )
    messaging_limit_tier = models.CharField(
        max_length=50,
        blank=True,
        help_text="Messaging limit tier (e.g., TIER_1K, TIER_10K, TIER_100K)",
    )
    _encrypted_user_token = models.TextField(
        blank=True,
        help_text="Fernet-encrypted 60-day user token (optional, for specific number)",
    )
    token_expires_at = models.DateTimeField(
        null=True, blank=True, help_text="Expiry of the 60-day token"
    )
    is_active = models.BooleanField(default=True, db_index=True)
    is_default = models.BooleanField(
        default=False,
        db_index=True,
        help_text="Default number to use when none specified",
    )
    created_at = models.DateTimeField(default=timezone.now, editable=False)
    updated_at = models.DateTimeField(auto_now=True)
    last_used_at = models.DateTimeField(null=True, blank=True, db_index=True)

    class Meta:
        ordering = ["-is_default", "-last_used_at", "-created_at"]
        indexes = [
            models.Index(fields=["is_active", "is_default"]),
            models.Index(fields=["waba_id", "is_active"]),
            models.Index(fields=["-last_used_at"]),
        ]
        verbose_name = "WhatsApp Phone Number"
        verbose_name_plural = "WhatsApp Phone Numbers"

    def get_access_token(self) -> str:
        """
        Get the access token to use for this phone number.
        Priority:
          1. Per-number 60-day token (if not expired)
          2. WABA system token (permanent)
          3. Environment variable fallback
          4. Empty string
        """
        # Try per-number token first
        if self._encrypted_user_token and self.token_expires_at:
            if timezone.now() < self.token_expires_at:
                try:
                    encryption_key = getattr(settings, "WHATSAPP_ENCRYPTION_KEY", None)
                    if encryption_key:
                        fernet = Fernet(encryption_key.encode())
                        token = fernet.decrypt(self._encrypted_user_token.encode()).decode()
                        if token:
                            return token
                except Exception as e:
                    logger.warning(
                        f"[PHONE] Failed to decrypt user token for {self.phone_number_id}: {e}"
                    )

        # Fall back to WABA token
        if self.business_account:
            waba_token = self.business_account.get_token()
            if waba_token:
                return waba_token

        # Final fallback to env var
        env_token = os.getenv("WABA_ACCESS_TOKEN", "")
        if env_token:
            logger.warning(
                f"[PHONE] Using env token for {self.phone_number_id} (no DB token)"
            )
            return env_token

        logger.warning(f"[PHONE] No token available for {self.phone_number_id}")
        return ""

    def set_user_token(self, token: str, expires_at=None):
        """
        Encrypt and store a 60-day user token for this specific number.
        """
        if not token:
            self._encrypted_user_token = ""
            self.token_expires_at = None
            return
        try:
            encryption_key = getattr(settings, "WHATSAPP_ENCRYPTION_KEY", None)
            if not encryption_key:
                raise ValueError("WHATSAPP_ENCRYPTION_KEY not configured in settings")
            fernet = Fernet(encryption_key.encode())
            self._encrypted_user_token = fernet.encrypt(token.encode()).decode()
            self.token_expires_at = expires_at
        except Exception as e:
            logger.exception(f"[PHONE] Failed to encrypt user token: {e}")
            raise

    def save(self, *args, **kwargs):
        """
        Override save to ensure only one default per WABA.
        """
        if self.is_default and self.waba_id:
            # Unset other defaults in same WABA
            WhatsAppPhoneNumber.objects.filter(
                waba_id=self.waba_id, is_default=True
            ).exclude(id=self.id).update(is_default=False)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.display_phone_number} ({self.verified_name or self.phone_number_id})"


class WhatsAppBusinessAccount(models.Model):
    """
    Stores WhatsApp Business Account (WABA) level credentials.
    One WABA can have multiple phone numbers.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    waba_id = models.CharField(
        max_length=100,
        unique=True,
        db_index=True,
        help_text="WhatsApp Business Account ID from Meta"
    )
    
    name = models.CharField(
        max_length=200,
        help_text="Business account name (e.g., 'ANK Wedding Services')"
    )
    
    _encrypted_token = models.TextField(
        help_text="Fernet-encrypted permanent system user access token",
        blank=True
    )
    
    is_active = models.BooleanField(default=True, db_index=True)
    
    created_at = models.DateTimeField(default=timezone.now, editable=False)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]
        verbose_name = "WhatsApp Business Account"
        verbose_name_plural = "WhatsApp Business Accounts"

    def get_token(self) -> str:
        """
        Decrypt and return the access token.
        Returns empty string if decryption fails or no token exists.
        """
        if not self._encrypted_token:
            return ""
        
        try:
            encryption_key = getattr(settings, "WHATSAPP_ENCRYPTION_KEY", None)
            if not encryption_key:
                logger.warning("[WABA] WHATSAPP_ENCRYPTION_KEY not configured")
                return ""
            
            cipher = Fernet(encryption_key.encode())
            decrypted = cipher.decrypt(self._encrypted_token.encode())
            return decrypted.decode()
        except Exception as e:
            logger.exception(f"[WABA] Failed to decrypt token for {self.waba_id}: {e}")
            return ""

    def set_token(self, token: str):
        """
        Encrypt and store the access token.
        """
        if not token:
            self._encrypted_token = ""
            return
        
        try:
            encryption_key = getattr(settings, "WHATSAPP_ENCRYPTION_KEY", None)
            if not encryption_key:
                raise ValueError("WHATSAPP_ENCRYPTION_KEY not configured in settings")
            
            cipher = Fernet(encryption_key.encode())
            encrypted = cipher.encrypt(token.encode())
            self._encrypted_token = encrypted.decode()
        except Exception as e:
            logger.exception(f"[WABA] Failed to encrypt token: {e}")
            raise

    def __str__(self):
        return f"{self.name} ({self.waba_id})"


class WhatsAppPhoneNumber(models.Model):
    """
    Registry of all available WhatsApp phone numbers with metadata.
    Each number can have its own credentials or inherit from WABA.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    business_account = models.ForeignKey(
        WhatsAppBusinessAccount,
        on_delete=models.CASCADE,
        related_name="phone_numbers",
        null=True,
        blank=True,
        help_text="Parent WABA (optional)"
    )
    
    phone_number_id = models.CharField(
        max_length=100,
        unique=True,
        db_index=True,
        help_text="Phone Number ID from Meta (unique identifier)"
    )
    
    asset_id = models.CharField(
        max_length=100,
        db_index=True,
        help_text="Asset ID from embedded signup"
    )
    
    waba_id = models.CharField(
        max_length=100,
        db_index=True,
        help_text="WABA ID (denormalized for quick lookup)"
    )
    
    display_phone_number = models.CharField(
        max_length=20,
        help_text="Human-readable phone number (e.g., '+919876543210')"
    )
    
    verified_name = models.CharField(
        max_length=200,
        help_text="Verified business name shown to customers"
    )
    
    quality_rating = models.CharField(
        max_length=20,
        default="UNKNOWN",
        help_text="Quality rating: GREEN, YELLOW, RED, UNKNOWN"
    )
    
    messaging_limit_tier = models.CharField(
        max_length=20,
        default="TIER_1K",
        help_text="Daily messaging limit tier (e.g., TIER_1K, TIER_10K, TIER_100K)"
    )
    
    _encrypted_user_token = models.TextField(
        blank=True,
        help_text="Optional per-number 60-day user token (Fernet-encrypted)"
    )
    
    token_expires_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Expiration time for user token (if applicable)"
    )
    
    is_active = models.BooleanField(
        default=True,
        db_index=True,
        help_text="Whether this number is active and available for use"
    )
    
    is_default = models.BooleanField(
        default=False,
        db_index=True,
        help_text="Default number to use when none specified"
    )
    
    last_used_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Last time this number was used to send a message"
    )
    
    created_at = models.DateTimeField(default=timezone.now, editable=False)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-is_default", "-last_used_at", "display_phone_number"]
        verbose_name = "WhatsApp Phone Number"
        verbose_name_plural = "WhatsApp Phone Numbers"
        indexes = [
            models.Index(fields=["is_active", "is_default"]),
            models.Index(fields=["waba_id", "is_active"]),
        ]

    def get_access_token(self) -> str:
        """
        Get access token for this phone number.
        Priority:
          1. Per-number token (if not expired)
          2. WABA system token
          3. Environment variable fallback
        """
        # Try per-number token first (if not expired)
        if self._encrypted_user_token and self.token_expires_at:
            if timezone.now() < self.token_expires_at:
                try:
                    encryption_key = getattr(settings, "WHATSAPP_ENCRYPTION_KEY", None)
                    if encryption_key:
                        cipher = Fernet(encryption_key.encode())
                        decrypted = cipher.decrypt(self._encrypted_user_token.encode())
                        return decrypted.decode()
                except Exception as e:
                    logger.warning(f"[PHONE] Failed to decrypt user token for {self.phone_number_id}: {e}")
        
        # Try WABA token
        if self.business_account:
            token = self.business_account.get_token()
            if token:
                return token
        
        # Fallback to env var (backward compatibility)
        env_token = os.getenv("WABA_ACCESS_TOKEN", "")
        if env_token:
            logger.info(f"[PHONE] Using env var fallback for {self.phone_number_id}")
            return env_token
        
        logger.warning(f"[PHONE] No access token available for {self.phone_number_id}")
        return ""

    def set_user_token(self, token: str, expires_at=None):
        """
        Encrypt and store a per-number user token (60-day tokens).
        """
        if not token:
            self._encrypted_user_token = ""
            self.token_expires_at = None
            return
        
        try:
            encryption_key = getattr(settings, "WHATSAPP_ENCRYPTION_KEY", None)
            if not encryption_key:
                raise ValueError("WHATSAPP_ENCRYPTION_KEY not configured in settings")
            
            cipher = Fernet(encryption_key.encode())
            encrypted = cipher.encrypt(token.encode())
            self._encrypted_user_token = encrypted.decode()
            self.token_expires_at = expires_at
        except Exception as e:
            logger.exception(f"[PHONE] Failed to encrypt user token: {e}")
            raise

    def save(self, *args, **kwargs):
        """
        Ensure only one is_default per WABA.
        """
        if self.is_default and self.waba_id:
            # Remove is_default from other numbers in the same WABA
            WhatsAppPhoneNumber.objects.filter(
                waba_id=self.waba_id,
                is_default=True
            ).exclude(id=self.id).update(is_default=False)
        
        super().save(*args, **kwargs)

    def __str__(self):
        default_marker = " [DEFAULT]" if self.is_default else ""
        return f"{self.display_phone_number} - {self.verified_name}{default_marker}"
