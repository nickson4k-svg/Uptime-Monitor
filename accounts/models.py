"""
Custom User model.

Design decisions:
- email as USERNAME_FIELD (no username field) — cleaner UX
- AbstractBaseUser for full control, not AbstractUser
- timezone field for future "notify in my timezone" feature
"""

import uuid

from django.contrib.auth.models import (
    AbstractBaseUser,
    BaseUserManager,
    PermissionsMixin,
)
from django.db import models
from django.utils import timezone as dj_timezone


class UserManager(BaseUserManager):
    """Manager for email-based authentication."""

    def create_user(self, email: str, password: str | None = None, **extra_fields):
        if not email:
            raise ValueError("Email is required")
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email: str, password: str, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        return self.create_user(email, password, **extra_fields)


class User(AbstractBaseUser, PermissionsMixin):
    """
    Custom user model with email as primary identifier.

    UUID primary key prevents enumeration attacks via sequential IDs.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email = models.EmailField(unique=True, db_index=True)
    full_name = models.CharField(max_length=255, blank=True)
    timezone = models.CharField(max_length=50, default="UTC")

    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    date_joined = models.DateTimeField(default=dj_timezone.now)

    objects = UserManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []

    class Meta:
        db_table = "accounts_user"
        verbose_name = "User"
        verbose_name_plural = "Users"

    def __str__(self) -> str:
        return str(self.email)

    @property
    def short_name(self) -> str:
        full_name_str = str(self.full_name or "")
        email_str = str(self.email or "")
        return full_name_str.split()[0] if full_name_str else email_str.split("@")[0]
