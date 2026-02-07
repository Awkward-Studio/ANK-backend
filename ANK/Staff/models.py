import uuid
from django.db import models
from django.contrib.auth.models import (
    AbstractBaseUser,
    BaseUserManager,
    PermissionsMixin,
)


class UserManager(BaseUserManager):
    use_in_migrations = True

    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError("Email is required")

        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)

        if extra_fields.get("is_staff") is not True:
            raise ValueError("Superuser must have is_staff=True")
        if extra_fields.get("is_superuser") is not True:
            raise ValueError("Superuser must have is_superuser=True")

        return self.create_user(email, password, **extra_fields)


class User(AbstractBaseUser, PermissionsMixin):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=200, blank=True)
    email = models.EmailField(unique=True, blank=True)
    contact_phone = models.CharField(max_length=20, blank=True)

    ROLE_CHOICES = [
        ("admin", "Admin"),  # can assign staff
        ("staff", "Staff"),  # regular operational user
        ("super_admin", "Super Admin"),  # can assign staff and super admin
        ("department_head", "Department Head"),  # can assign staff and department head
    ]
    role = models.CharField(max_length=20, choices=ROLE_CHOICES)

    # Department this user heads (for department_head role)
    department = models.ForeignKey(
        "Departments.Department",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="department_heads",
        help_text="Department this user heads (for department_head role)"
    )

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)  # Required by Django admin
    objects = UserManager()

    def __str__(self):
        return f"{self.name} ({self.get_role_display()})"
