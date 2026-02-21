# =============================================================================
# financial/signals.py
# =============================================================================
"""
Keep Invoice.amount_paid / amount_remaining / status in sync whenever a
Payment record is created, modified, or deleted.

Although Payment.save() already calls invoice.refresh_payment_totals(), using
signals ensures the sync also fires when payments are bulk-updated via the ORM
(e.g. Payment.objects.filter(...).update(...)), and provides a clear audit trail.
"""

from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from financial.models import Invoice, InvoiceItem, Payment


@receiver(post_save, sender=Payment)
def payment_saved(sender, instance, **kwargs):
    """Refresh invoice totals after any payment save."""
    instance.invoice.refresh_payment_totals()


@receiver(post_delete, sender=Payment)
def payment_deleted(sender, instance, **kwargs):
    """Refresh invoice totals after a payment is removed."""
    try:
        instance.invoice.refresh_payment_totals()
    except Invoice.DoesNotExist:
        pass  # Invoice itself was deleted — nothing to update


@receiver(post_save, sender=InvoiceItem)
def item_saved(sender, instance, **kwargs):
    """Recalculate invoice header amounts when a line item changes."""
    instance.invoice.recalculate_amounts()


@receiver(post_delete, sender=InvoiceItem)
def item_deleted(sender, instance, **kwargs):
    """Recalculate invoice header amounts when a line item is removed."""
    try:
        instance.invoice.recalculate_amounts()
    except Invoice.DoesNotExist:
        pass
