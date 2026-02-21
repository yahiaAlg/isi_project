# financial/forms.py

from decimal import Decimal

from django import forms
from django.core.exceptions import ValidationError

from financial.models import (
    CreditNote,
    Expense,
    ExpenseCategory,
    FinancialPeriod,
    Invoice,
    InvoiceItem,
    Payment,
)


# ======================================================================= #
# Invoices
# ======================================================================= #


class InvoiceForm(forms.ModelForm):
    class Meta:
        model = Invoice
        fields = [
            "invoice_type",
            "client",
            "invoice_date",
            "due_date",
            "tva_rate",
            "session",
            "study_project",
            "notes",
            "footer_text",
        ]
        labels = {
            "invoice_type": "Type",
            "client": "Client",
            "invoice_date": "Date",
            "due_date": "Échéance",
            "tva_rate": "Taux TVA",
            "session": "Session",
            "study_project": "Projet",
            "notes": "Notes internes",
            "footer_text": "Pied de page (personnalisé)",
        }
        widgets = {
            "invoice_date": forms.DateInput(attrs={"type": "date"}),
            "due_date": forms.DateInput(attrs={"type": "date"}),
            "notes": forms.Textarea(attrs={"rows": 2}),
            "footer_text": forms.Textarea(attrs={"rows": 2}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["session"].required = False
        self.fields["study_project"].required = False
        self.fields["due_date"].required = False
        self.fields["footer_text"].required = False
        # Limit sessions to invoiceable ones (completed, not yet invoiced)
        from formations.models import Session

        self.fields["session"].queryset = Session.objects.filter(
            status=Session.STATUS_COMPLETED
        )
        from etudes.models import StudyProject

        self.fields["study_project"].queryset = StudyProject.objects.filter(
            status=StudyProject.STATUS_COMPLETED
        )

    def clean_tva_rate(self):
        rate = self.cleaned_data.get("tva_rate")
        if rate is not None and not (0 <= rate <= 1):
            raise ValidationError("Le taux TVA doit être compris entre 0 et 1.")
        return rate

    def clean(self):
        cleaned_data = super().clean()
        inv_type = cleaned_data.get("invoice_type")
        session = cleaned_data.get("session")
        project = cleaned_data.get("study_project")

        if inv_type == Invoice.TYPE_FORMATION and project:
            self.add_error(
                "study_project",
                "Une facture Formation ne doit pas être liée à un projet.",
            )
        if inv_type == Invoice.TYPE_ETUDE and session:
            self.add_error(
                "session", "Une facture Étude ne doit pas être liée à une session."
            )
        if session and project:
            self.add_error(
                "study_project",
                "Liez la facture à une session ou à un projet, pas les deux.",
            )

        due = cleaned_data.get("due_date")
        invoice_date = cleaned_data.get("invoice_date")
        if due and invoice_date and due < invoice_date:
            self.add_error(
                "due_date", "L'échéance doit être postérieure à la date de facturation."
            )
        return cleaned_data


class InvoiceFilterForm(forms.Form):
    q = forms.CharField(
        label="Recherche",
        required=False,
        widget=forms.TextInput(attrs={"placeholder": "Référence, client…"}),
    )
    invoice_type = forms.ChoiceField(
        label="Type",
        required=False,
        choices=[("", "Tous")] + Invoice.TYPE_CHOICES,
    )
    status = forms.ChoiceField(
        label="Statut",
        required=False,
        choices=[("", "Tous")] + Invoice.STATUS_CHOICES,
    )
    date_from = forms.DateField(
        label="Du",
        required=False,
        widget=forms.DateInput(attrs={"type": "date"}),
    )
    date_to = forms.DateField(
        label="Au",
        required=False,
        widget=forms.DateInput(attrs={"type": "date"}),
    )
    overdue_only = forms.BooleanField(label="En retard uniquement", required=False)


class InvoiceVoidForm(forms.Form):
    reason = forms.CharField(
        label="Motif d'annulation",
        widget=forms.Textarea(attrs={"rows": 3}),
    )


# ======================================================================= #
# Invoice line items
# ======================================================================= #


class InvoiceItemForm(forms.ModelForm):
    class Meta:
        model = InvoiceItem
        fields = [
            "description",
            "quantity",
            "unit",
            "unit_price_ht",
            "discount_percent",
            "order",
            "session",
            "project_phase",
        ]
        labels = {
            "description": "Désignation",
            "quantity": "Quantité",
            "unit": "Unité",
            "unit_price_ht": "Prix unitaire HT (DA)",
            "discount_percent": "Remise (%)",
            "order": "Ordre",
            "session": "Session liée",
            "project_phase": "Phase liée",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["unit"].required = False
        self.fields["session"].required = False
        self.fields["project_phase"].required = False

    def clean_quantity(self):
        qty = self.cleaned_data.get("quantity")
        if qty is not None and qty <= 0:
            raise ValidationError("La quantité doit être strictement positive.")
        return qty

    def clean_unit_price_ht(self):
        price = self.cleaned_data.get("unit_price_ht")
        if price is not None and price < 0:
            raise ValidationError("Le prix unitaire ne peut pas être négatif.")
        return price

    def clean_discount_percent(self):
        d = self.cleaned_data.get("discount_percent", Decimal("0"))
        if d is not None and not (0 <= d <= 100):
            raise ValidationError("La remise doit être comprise entre 0 et 100 %.")
        return d


# ======================================================================= #
# Payments
# ======================================================================= #


class PaymentForm(forms.ModelForm):
    class Meta:
        model = Payment
        fields = ["date", "amount", "method", "status", "reference", "notes"]
        labels = {
            "date": "Date",
            "amount": "Montant (DA)",
            "method": "Mode de paiement",
            "status": "Statut",
            "reference": "Référence",
            "notes": "Notes",
        }
        widgets = {
            "date": forms.DateInput(attrs={"type": "date"}),
            "notes": forms.Textarea(attrs={"rows": 2}),
        }

    def __init__(self, *args, invoice=None, **kwargs):
        self.invoice = invoice
        super().__init__(*args, **kwargs)
        self.fields["reference"].required = False
        self.fields["notes"].required = False

    def clean_amount(self):
        amount = self.cleaned_data.get("amount")
        if amount is not None and amount <= 0:
            raise ValidationError("Le montant doit être positif.")
        return amount

    def clean(self):
        cleaned_data = super().clean()
        if self.invoice and cleaned_data.get("amount"):
            amount = cleaned_data["amount"]
            already_paid = self.invoice.amount_paid
            # Subtract own amount when editing
            if self.instance.pk:
                already_paid -= self.instance.amount or Decimal("0")
            if (already_paid + amount) > self.invoice.amount_ttc:
                self.add_error(
                    "amount",
                    f"Ce paiement dépasserait le total de la facture "
                    f"({self.invoice.amount_ttc:,.2f} DA).",
                )
        return cleaned_data


# ======================================================================= #
# Credit notes
# ======================================================================= #


class CreditNoteForm(forms.ModelForm):
    class Meta:
        model = CreditNote
        fields = [
            "date",
            "reason",
            "amount_ht",
            "tva_rate",
            "is_full_reversal",
            "notes",
        ]
        labels = {
            "date": "Date de l'avoir",
            "reason": "Motif",
            "amount_ht": "Montant HT (DA)",
            "tva_rate": "Taux TVA",
            "is_full_reversal": "Annulation totale de la facture",
            "notes": "Notes",
        }
        widgets = {
            "date": forms.DateInput(attrs={"type": "date"}),
            "reason": forms.Textarea(attrs={"rows": 3}),
            "notes": forms.Textarea(attrs={"rows": 2}),
        }

    def __init__(self, *args, invoice=None, **kwargs):
        self.invoice = invoice
        super().__init__(*args, **kwargs)
        self.fields["notes"].required = False
        if invoice:
            self.fields["tva_rate"].initial = invoice.tva_rate

    def clean_amount_ht(self):
        amount = self.cleaned_data.get("amount_ht")
        if amount is not None and amount <= 0:
            raise ValidationError("Le montant doit être positif.")
        if self.invoice and amount and amount > self.invoice.amount_ht:
            raise ValidationError(
                f"Le montant HT de l'avoir ({amount:,.2f} DA) ne peut pas dépasser "
                f"celui de la facture ({self.invoice.amount_ht:,.2f} DA)."
            )
        return amount

    def clean(self):
        cleaned_data = super().clean()
        if cleaned_data.get("is_full_reversal") and self.invoice:
            # Force amount to match original invoice
            cleaned_data["amount_ht"] = self.invoice.amount_ht
        return cleaned_data


# ======================================================================= #
# Expenses
# ======================================================================= #


class ExpenseCategoryForm(forms.ModelForm):
    class Meta:
        model = ExpenseCategory
        fields = ["name", "description", "is_direct_cost", "color"]
        labels = {
            "name": "Catégorie",
            "description": "Description",
            "is_direct_cost": "Coût direct",
            "color": "Couleur",
        }
        widgets = {
            "description": forms.Textarea(attrs={"rows": 2}),
            "color": forms.TextInput(attrs={"type": "color"}),
        }

    def clean_name(self):
        name = self.cleaned_data.get("name", "").strip()
        qs = ExpenseCategory.objects.filter(name__iexact=name)
        if self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise ValidationError("Cette catégorie existe déjà.")
        return name


class ExpenseForm(forms.ModelForm):
    class Meta:
        model = Expense
        fields = [
            "date",
            "category",
            "description",
            "amount",
            "supplier",
            "payment_reference",
            "allocated_to_session",
            "allocated_to_project",
            "is_overhead",
            "receipt",
            "receipt_missing",
            "notes",
        ]
        labels = {
            "date": "Date",
            "category": "Catégorie",
            "description": "Description",
            "amount": "Montant (DA)",
            "supplier": "Fournisseur",
            "payment_reference": "Réf. paiement",
            "allocated_to_session": "Session",
            "allocated_to_project": "Projet",
            "is_overhead": "Frais généraux",
            "receipt": "Justificatif",
            "receipt_missing": "Justificatif manquant",
            "notes": "Notes",
        }
        widgets = {
            "date": forms.DateInput(attrs={"type": "date"}),
            "notes": forms.Textarea(attrs={"rows": 2}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["allocated_to_session"].required = False
        self.fields["allocated_to_project"].required = False
        self.fields["supplier"].required = False
        self.fields["payment_reference"].required = False
        self.fields["receipt"].required = False
        self.fields["notes"].required = False
        # Limit project choices to active ones
        from etudes.models import StudyProject

        self.fields["allocated_to_project"].queryset = StudyProject.objects.filter(
            status=StudyProject.STATUS_IN_PROGRESS
        )
        from formations.models import Session

        self.fields["allocated_to_session"].queryset = Session.objects.filter(
            status__in=[
                Session.STATUS_PLANNED,
                Session.STATUS_IN_PROGRESS,
                Session.STATUS_COMPLETED,
            ]
        )

    def clean_amount(self):
        amount = self.cleaned_data.get("amount")
        if amount is not None and amount <= 0:
            raise ValidationError("Le montant doit être positif.")
        return amount

    def clean(self):
        cleaned_data = super().clean()
        session = cleaned_data.get("allocated_to_session")
        project = cleaned_data.get("allocated_to_project")
        overhead = cleaned_data.get("is_overhead")
        filled = sum([bool(session), bool(project), bool(overhead)])
        if filled == 0:
            raise ValidationError(
                "Imputez la dépense à une session, un projet, ou cochez 'Frais généraux'."
            )
        if filled > 1:
            raise ValidationError(
                "Une dépense ne peut être imputée qu'à un seul centre de coût."
            )
        # If receipt uploaded, clear the missing flag
        if cleaned_data.get("receipt"):
            cleaned_data["receipt_missing"] = False
        return cleaned_data


class ExpenseFilterForm(forms.Form):
    q = forms.CharField(
        label="Recherche",
        required=False,
        widget=forms.TextInput(attrs={"placeholder": "Description, fournisseur…"}),
    )
    category = forms.ModelChoiceField(
        label="Catégorie",
        required=False,
        queryset=ExpenseCategory.objects.all(),
        empty_label="Toutes",
    )
    approval_status = forms.ChoiceField(
        label="Approbation",
        required=False,
        choices=[("", "Tous")] + Expense.APPROVAL_CHOICES,
    )
    date_from = forms.DateField(
        label="Du",
        required=False,
        widget=forms.DateInput(attrs={"type": "date"}),
    )
    date_to = forms.DateField(
        label="Au",
        required=False,
        widget=forms.DateInput(attrs={"type": "date"}),
    )
    needs_action = forms.BooleanField(label="Action requise uniquement", required=False)


class ExpenseApprovalForm(forms.Form):
    approval_status = forms.ChoiceField(
        label="Décision",
        choices=[
            (Expense.APPROVAL_APPROVED, "Approuver"),
            (Expense.APPROVAL_REJECTED, "Refuser"),
        ],
    )
    approval_notes = forms.CharField(
        label="Notes",
        required=False,
        widget=forms.Textarea(attrs={"rows": 2}),
    )


# ======================================================================= #
# Financial periods
# ======================================================================= #


class FinancialPeriodForm(forms.ModelForm):
    class Meta:
        model = FinancialPeriod
        fields = ["name", "period_type", "date_start", "date_end", "notes"]
        labels = {
            "name": "Nom",
            "period_type": "Type",
            "date_start": "Début",
            "date_end": "Fin",
            "notes": "Notes",
        }
        widgets = {
            "date_start": forms.DateInput(attrs={"type": "date"}),
            "date_end": forms.DateInput(attrs={"type": "date"}),
            "notes": forms.Textarea(attrs={"rows": 2}),
        }

    def clean(self):
        cleaned_data = super().clean()
        start = cleaned_data.get("date_start")
        end = cleaned_data.get("date_end")
        if start and end and end <= start:
            self.add_error(
                "date_end", "La date de fin doit être postérieure à la date de début."
            )
        return cleaned_data


class ReportFilterForm(forms.Form):
    """Shared date-range filter for all financial reports."""

    period = forms.ModelChoiceField(
        label="Période",
        required=False,
        queryset=FinancialPeriod.objects.all(),
        empty_label="Période personnalisée",
    )
    date_from = forms.DateField(
        label="Du",
        required=False,
        widget=forms.DateInput(attrs={"type": "date"}),
    )
    date_to = forms.DateField(
        label="Au",
        required=False,
        widget=forms.DateInput(attrs={"type": "date"}),
    )
    invoice_type = forms.ChoiceField(
        label="Ligne métier",
        required=False,
        choices=[("", "Toutes")] + Invoice.TYPE_CHOICES,
    )

    def clean(self):
        cleaned_data = super().clean()
        period = cleaned_data.get("period")
        date_from = cleaned_data.get("date_from")
        date_to = cleaned_data.get("date_to")
        # When no period selected, manual dates are required
        if not period and not (date_from and date_to):
            raise ValidationError(
                "Sélectionnez une période ou renseignez les dates de début et de fin."
            )
        if date_from and date_to and date_to < date_from:
            self.add_error(
                "date_to", "La date de fin doit être postérieure à la date de début."
            )
        return cleaned_data
