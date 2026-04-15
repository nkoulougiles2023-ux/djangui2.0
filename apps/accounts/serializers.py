from datetime import date

from rest_framework import serializers

from .models import User, Wallet


class PhoneSerializer(serializers.Serializer):
    phone = serializers.RegexField(regex=r"^\+237[0-9]{9}$")


class OTPVerifySerializer(serializers.Serializer):
    phone = serializers.RegexField(regex=r"^\+237[0-9]{9}$")
    code = serializers.RegexField(regex=r"^\d{6}$")


class RegisterSerializer(serializers.Serializer):
    phone = serializers.RegexField(regex=r"^\+237[0-9]{9}$")
    otp = serializers.RegexField(regex=r"^\d{6}$")
    first_name = serializers.CharField(max_length=100)
    last_name = serializers.CharField(max_length=100)
    date_of_birth = serializers.DateField()
    gender = serializers.ChoiceField(choices=("M", "F"))
    address = serializers.CharField()
    city = serializers.CharField(max_length=100)
    pin = serializers.RegexField(regex=r"^\d{4}$")

    def validate_phone(self, value):
        if User.objects.filter(phone=value).exists():
            raise serializers.ValidationError("Numéro déjà utilisé.")
        return value

    def validate_date_of_birth(self, value):
        today = date.today()
        age = today.year - value.year - ((today.month, today.day) < (value.month, value.day))
        if age < 18:
            raise serializers.ValidationError("Âge minimum 18 ans")
        return value


class PinLoginSerializer(serializers.Serializer):
    phone = serializers.RegexField(regex=r"^\+237[0-9]{9}$")
    pin = serializers.RegexField(regex=r"^\d{4}$")


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = (
            "id", "phone", "email",
            "first_name", "last_name", "date_of_birth", "gender",
            "address", "city", "photo_profile",
            "kyc_status", "reputation_score", "tchekele_points",
            "is_active", "created_at",
        )
        read_only_fields = (
            "id", "phone", "kyc_status", "reputation_score",
            "tchekele_points", "is_active", "created_at",
        )


class KYCSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ("cni_number", "cni_front_image", "cni_back_image", "selfie_kyc")

    def validate_cni_number(self, value):
        qs = User.objects.filter(cni_number=value)
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError("CNI déjà enregistrée.")
        return value

    def update(self, instance, validated_data):
        for k, v in validated_data.items():
            setattr(instance, k, v)
        instance.kyc_status = "pending"
        instance.save()
        return instance


class ChangePinSerializer(serializers.Serializer):
    old_pin = serializers.RegexField(regex=r"^\d{4}$")
    new_pin = serializers.RegexField(regex=r"^\d{4}$")


class WalletSerializer(serializers.ModelSerializer):
    class Meta:
        model = Wallet
        fields = ("available_balance", "blocked_balance", "currency", "updated_at")
        read_only_fields = fields
