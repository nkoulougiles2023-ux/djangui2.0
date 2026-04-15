from celery import shared_task


@shared_task
def cleanup_expired_otps():
    """Redis already expires OTPs via TTL. This task prunes old audit rows."""
    from datetime import timedelta
    from django.utils import timezone
    from .models import OTPAttempt
    cutoff = timezone.now() - timedelta(days=30)
    deleted, _ = OTPAttempt.objects.filter(created_at__lt=cutoff).delete()
    return deleted
