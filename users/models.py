from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.db import models

class UserManager(BaseUserManager):
    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError("The Email field must be set")
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("is_broker", True)  # ✅ Ensure superuser can create applications
        extra_fields.setdefault("is_applicant", True)  # ✅ Ensure superuser can complete applications
        extra_fields.setdefault("is_owner", True)  # ✅ Ensure superuser can manage buildings
        return self.create_user(email, password, **extra_fields)


class User(AbstractBaseUser, PermissionsMixin):
    email = models.EmailField(unique=True, verbose_name="Email Address")
    is_active = models.BooleanField(default=True, verbose_name="Active")
    is_staff = models.BooleanField(default=False, verbose_name="Staff Status")  # ✅ Staff have some admin access

    # Access Levels (Independent from admin access)
    is_broker = models.BooleanField(default=False, verbose_name="Broker (Creates Applications)")
    is_applicant = models.BooleanField(default=False, verbose_name="Applicant (Completes Applications)")
    is_owner = models.BooleanField(default=False, verbose_name="Owner (Manages Buildings)")  # 🚫 Owners are NOT admins
    is_superuser = models.BooleanField(default=False, verbose_name="Superuser (Full Admin Access)")

    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Created At")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Updated At")

    objects = UserManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []

    def __str__(self):
        return self.email


# Import profile models to make them discoverable by Django migrations
from .profiles_models import BrokerProfile, OwnerProfile, StaffProfile, AdminProfile

