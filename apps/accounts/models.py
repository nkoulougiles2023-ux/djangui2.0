import re
import uuid
from datetime import date
from decimal import Decimal

import bcrypt
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator, RegexValidator
from django.db import models

PHONE_REGEX = RegexValidator(
    regex=r"^\+237[0-9]{9}$",
    message="Numéro camerounais requis au format +237XXXXXXXXX",
)


class UserManager(BaseUserManager):
    def create_user(self, phone, password=None, **extra):
        if not phone:
            raise ValueError("phone is required")
        user = self.model(phone=phone, **extra)
        if password:
            user.set_password(password)
        else:
            user.set_unusable_password()
        user.save(using=self._db)
        return user

    def create_superuser(self, phone, password=None, **extra):
        extra.setdefault("is_staff", True)
        extra.setdefault("is_superuser", True)
        extra.setdefault("is_active", True)
        extra.setdefault("kyc_status", "verified")
        extra.setdefault("first_name", "admin")
        extra.setdefault("last_name", "admin")
        extra.setdefault("date_of_birth", date(1990, 1, 1))
        extra.setdefault("gender", "M")
        extra.setdefault("address", "—")
        extra.setdefault("city", "Yaoundé")
        return self.create_user(phone, password, **extra)


class User(AbstractBaseUser, PermissionsMixin):
    KYC_STATUSES = (("pending", "pending"), ("verified", "verified"), ("rejected", "rejected"))
    GENDERS = (("M", "M"), ("F", "F"))

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    phone = models.CharField(max_length=15, unique=True, validators=[PHONE_REGEX])
    email = models.EmailField(unique=True, null=True, blank=True)

    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    date_of_birth = models.DateField()
    gender = models.CharField(max_length=1, choices=GENDERS)
    address = models.TextField()
    city = models.CharField(max_length=100)
    photo_profile = models.ImageField(upload_to="profiles/", null=True, blank=True)

    cni_number = models.CharField(max_length=20, unique=True, null=True, blank=True)
    cni_front_image = models.ImageField(upload_to="kyc/", null=True, blank=True)
    cni_back_image = models.ImageField(upload_to="kyc/", null=True, blank=True)
    selfie_kyc = models.ImageField(upload_to="kyc/", null=True, blank=True)
    kyc_status = models.CharField(max_length=20, choices=KYC_STATUSES, default="pending")

    is_active = models.BooleanField(default=True)
    is_banned = models.BooleanField(default=False)
    is_staff = models.BooleanField(default=False)

    reputation_score = models.IntegerField(
        default=50, validators=[MinValueValidator(0), MaxValueValidator(100)]
    )
    tchekele_points = models.IntegerField(default=0, validators=[MinValueValidator(0)])

    # Hashed 4-digit PIN (bcrypt)
    pin_hash = models.CharField(max_length=128, null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = UserManager()

    USERNAME_FIELD = "phone"
    REQUIRED_FIELDS = ["first_name", "last_name", "date_of_birth", "gender", "address", "city"]

    class Meta:
        indexes = [
            models.Index(fields=["phone"]),
            models.Index(fields=["kyc_status"]),
            models.Index(fields=["reputation_score"]),
        ]

    def __str__(self):
        return f"{self.first_name} {self.last_name} ({self.phone})"

    def clean(self):
        super().clean()
        if self.date_of_birth:
            today = date.today()
            age = today.year - self.date_of_birth.year - (
                (today.month, today.day) < (self.date_of_birth.month, self.date_of_birth.day)
            )
            if age < 18:
                raise ValidationError({"date_of_birth": "Âge minimum 18 ans"})

    # --- PIN handling (bcrypt, separate from auth password) ---
    def set_pin(self, pin: str):
        if not re.fullmatch(r"\d{4}", pin):
            raise ValidationError("PIN doit être 4 chiffres")
        if pin in {"0000", "1111", "2222", "3333", "4444", "5555", "6666", "7777",
                   "8888", "9999", "1234", "4321"}:
            raise ValidationError("PIN trop trivial")
        self.pin_hash = bcrypt.hashpw(pin.encode(), bcrypt.gensalt(rounds=12)).decode()

    def check_pin(self, pin: str) -> bool:
        if not self.pin_hash:
            return False
        try:
            return bcrypt.checkpw(pin.encode(), self.pin_hash.encode())
        except ValueError:
            return False

    # --- business guards ---
    def can_borrow(self) -> tuple[bool, str]:
        from django.conf import settings
        if self.is_banned or not self.is_active:
            return False, "Compte inactif"
        if self.kyc_status != "verified":
            return False, "KYC non vérifié"
        if self.reputation_score < settings.DJANGUI["MIN_REPUTATION_TO_BORROW"]:
            return False, "Score de réputation insuffisant"
        return True, ""

    def can_guarantee(self) -> tuple[bool, str]:
        if self.is_banned or not self.is_active:
            return False, "Compte inactif"
        if self.kyc_status != "verified":
            return False, "KYC non vérifié"
        return True, ""


class Wallet(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="wallet")
    available_balance = models.DecimalField(
        max_digits=14, decimal_places=2, default=Decimal("0.00"),
        validators=[MinValueValidator(Decimal("0"))],
    )
    blocked_balance = models.DecimalField(
        max_digits=14, decimal_places=2, default=Decimal("0.00"),
        validators=[MinValueValidator(Decimal("0"))],
    )
    currency = models.CharField(max_length=5, default="XAF")
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [models.Index(fields=["user"])]

    def __str__(self):
        return f"Wallet<{self.user.phone}> {self.available_balance}/{self.blocked_balance}"

    @property
    def total_balance(self) -> Decimal:
        return self.available_balance + self.blocked_balance


class OTPAttempt(models.Model):
    """Audit trail of OTP requests. The code itself lives in Redis."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    phone = models.CharField(max_length=15)
    ip = models.GenericIPAddressField(null=True, blank=True)
    purpose = models.CharField(max_length=20, default="login")  # login | register
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [models.Index(fields=["phone", "created_at"])]


class AuditLog(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name="audit_logs")
    action = models.CharField(max_length=80)
    ip = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(null=True, blank=True)
    details = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["user", "created_at"]),
            models.Index(fields=["action", "created_at"]),
        ]
