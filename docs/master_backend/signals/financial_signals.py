# =============================================================================
# financial/signals.py  —  v3.0
# =============================================================================
"""
Keep Invoice.amount_paid / amount_remaining / status in sync whenever a
Payment record is created, modified, or deleted.

Design notes
────────────
* Payment.save() and Payment.delete() already call invoice.refresh_payment_totals()
  directly. The post_save / post_delete signals below add a second sync layer
  that fires on bulk ORM updates (Payment.objects.filter(...).update(...)),
  which do NOT trigger model.save().

* InvoiceItem signals are intentionally NOT present here because:
  - InvoiceItem.save() / delete() already call invoice.recalculate_amounts()
    and raise ValidationError when the invoice is locked.
  - Adding signals on top would cause a double-recalculation on every item save.

* Phase guard: payment signals only recalculate when the invoice is in the
  FINALE phase. Proforma invoices have no payments; the guard is a safety net.
"""

from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from financial.models import Invoice, Payment


@receiver(post_save, sender=Payment)
def payment_saved(sender, instance, **kwargs):
    """Refresh invoice totals after any payment save (catches bulk updates)."""
    if not instance.invoice_id:
        return
    try:
        invoice = Invoice.objects.get(pk=instance.invoice_id)
        if invoice.phase == Invoice.Phase.FINALE:
            invoice.refresh_payment_totals()
    except Invoice.DoesNotExist:
        pass


@receiver(post_delete, sender=Payment)
def payment_deleted(sender, instance, **kwargs):
    """Refresh invoice totals after a payment is removed."""
    if not instance.invoice_id:
        return
    try:
        invoice = Invoice.objects.get(pk=instance.invoice_id)
        if invoice.phase == Invoice.Phase.FINALE:
            invoice.refresh_payment_totals()
    except Invoice.DoesNotExist:
        pass  # Invoice itself was deleted — nothing to update
