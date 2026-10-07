# Kept for compatibility with the retired ``rentalution.wastaco`` package.
# The active Celery configuration lives at the project package root.
from rentalution.celery import app as celery_app

__all__ = ("celery_app",)
