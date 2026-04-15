import os

from celery import Celery
from celery.schedules import crontab

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "djangui.settings")

app = Celery("djangui")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()

app.conf.beat_schedule = {
    "check_loan_expiry": {
        "task": "apps.loans.tasks.check_loan_expiry",
        "schedule": crontab(minute=0),  # hourly
    },
    "check_loan_default": {
        "task": "apps.loans.tasks.check_loan_default",
        "schedule": crontab(minute=5),  # hourly
    },
    "send_loan_reminders": {
        "task": "apps.loans.tasks.send_loan_reminders",
        "schedule": crontab(hour=9, minute=0),  # daily 09:00
    },
    "check_tontine_contributions": {
        "task": "apps.tontines.tasks.check_tontine_contributions",
        "schedule": crontab(minute=0, hour="*/6"),
    },
    "calculate_monthly_returns": {
        "task": "apps.investments.tasks.calculate_monthly_returns",
        "schedule": crontab(day_of_month=1, hour=1, minute=0),
    },
    "update_honor_board": {
        "task": "apps.rewards.tasks.update_honor_board",
        "schedule": crontab(day_of_month=1, hour=2, minute=0),
    },
    "reconcile_wallets": {
        "task": "apps.transactions.tasks.reconcile_wallets",
        "schedule": crontab(hour=3, minute=0),
    },
    "cleanup_expired_otps": {
        "task": "apps.accounts.tasks.cleanup_expired_otps",
        "schedule": crontab(minute="*/15"),
    },
    "generate_daily_report": {
        "task": "apps.admin_dashboard.tasks.generate_daily_report",
        "schedule": crontab(hour=6, minute=0),
    },
    "check_suspicious_activity": {
        "task": "apps.admin_dashboard.tasks.check_suspicious_activity",
        "schedule": crontab(minute=30),
    },
}
