# financial/forms.py
# =============================================================================
# All forms for the financial module.
# ISIFormMixin auto-applies Bootstrap 5 CSS classes (form-control /
# form-select / form-check-input) to every widget so that templates can use
# {{ form.field_name }} directly without manual class injection.
# =============================================================================

from decimal import Decimal

from django import forms
from django.core.exceptions import ValidationError

from clients.models import Client
from core.form_mixins import ISIFormMixin
from financial.models import (
    CreditNote,
    Expense,
    ExpenseCategory,
    FinancialPeriod,
    Invoice,
    InvoiceItem,
    Payment,
)


# ---------------------------------------------------------------------------
# Invoice forms
# ---------------------------------------------------------------------------


class InvoiceForm(ISIFormMixin, forms.ModelForm):
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
            "notes": forms.Textarea(attrs={"rows": 3}),
            "footer_text": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Only active clients in the dropdown
        self.fields["client"].queryset = Client.objects.filter(is_active=True).order_by(
            "name"
        )
        self.fields["due_date"].required = False
        self.fields["session"].required = False
        self.fields["study_project"].required = False
        self.fields["notes"].required = False
        self.fields["footer_text"].required = False

    def clean(self):
        cleaned = super().clean()
        inv_type = cleaned.get("invoice_type")
        session = cleaned.get("session")
        project = cleaned.get("study_project")
        # Soft validation: warn when type/link mismatch
        if inv_type == Invoice.TYPE_FORMATION and project:
            self.add_error(
                "study_project",
                "Une facture Formation ne devrait pas être liée à un projet.",
            )
        if inv_type == Invoice.TYPE_ETUDE and session:
            self.add_error(
                "session",
                "Une facture Étude ne devrait pas être liée à une session.",
            )
        return cleaned


class InvoiceFilterForm(ISIFormMixin, forms.Form):
    q = forms.CharField(
        label="Recherche",
        required=False,
        widget=forms.TextInput(attrs={"placeholder": "Référence, client…"}),
    )
    status = forms.ChoiceField(
        label="Statut",
        required=False,
        choices=[("", "Tous")] + Invoice.STATUS_CHOICES,
    )
    invoice_type = forms.ChoiceField(
        label="Type",
        required=False,
        choices=[("", "Tous")] + Invoice.TYPE_CHOICES,
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
    client = forms.ModelChoiceField(
        label="Client",
        required=False,
        queryset=Client.objects.filter(is_active=True).order_by("name"),
        empty_label="Tous les clients",
    )


# ---------------------------------------------------------------------------
# Invoice line-item form
# ---------------------------------------------------------------------------


class InvoiceItemForm(ISIFormMixin, forms.ModelForm):
    class Meta:
        model = InvoiceItem
        fields = [
            "description",
            "quantity",
            "unit_price_ht",
            "discount_percent",
            "order",
        ]
        labels = {
            "description": "Description",
            "quantity": "Qté",
            "unit_price_ht": "P.U. HT (DA)",
            "discount_percent": "Remise (%)",
            "order": "Ordre",
        }
        widgets = {
            "description": forms.TextInput(
                attrs={"placeholder": "Intitulé de la prestation"}
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["discount_percent"].required = False
        self.fields["order"].required = False


# ---------------------------------------------------------------------------
# Payment forms
# ---------------------------------------------------------------------------


class PaymentForm(ISIFormMixin, forms.ModelForm):
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

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["reference"].required = False
        self.fields["notes"].required = False


# ---------------------------------------------------------------------------
# Credit note form
# ---------------------------------------------------------------------------


class CreditNoteForm(ISIFormMixin, forms.ModelForm):
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
            "date": "Date",
            "reason": "Motif",
            "amount_ht": "Montant HT (DA)",
            "tva_rate": "Taux TVA",
            "is_full_reversal": "Annulation totale",
            "notes": "Notes",
        }
        widgets = {
            "date": forms.DateInput(attrs={"type": "date"}),
            "reason": forms.Textarea(attrs={"rows": 3}),
            "notes": forms.Textarea(attrs={"rows": 2}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["notes"].required = False
        self.fields["tva_rate"].initial = Decimal("0.19")

    def clean_amount_ht(self):
        amount = self.cleaned_data.get("amount_ht")
        if amount is not None and amount <= 0:
            raise ValidationError("Le montant doit être positif.")
        return amount


# ---------------------------------------------------------------------------
# Expense forms
# ---------------------------------------------------------------------------


class ExpenseForm(ISIFormMixin, forms.ModelForm):
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
            "supplier": "Fournisseur / bénéficiaire",
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
            "notes": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["supplier"].required = False
        self.fields["payment_reference"].required = False
        self.fields["allocated_to_session"].required = False
        self.fields["allocated_to_project"].required = False
        self.fields["receipt"].required = False
        self.fields["notes"].required = False


class ExpenseFilterForm(ISIFormMixin, forms.Form):
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
    allocation = forms.ChoiceField(
        label="Affectation",
        required=False,
        choices=[
            ("", "Toutes"),
            ("session", "Session"),
            ("project", "Projet"),
            ("overhead", "Frais généraux"),
        ],
    )


class ExpenseCategoryForm(ISIFormMixin, forms.ModelForm):
    class Meta:
        model = ExpenseCategory
        fields = ["name", "description", "is_direct_cost", "color"]
        labels = {
            "name": "Nom",
            "description": "Description",
            "is_direct_cost": "Coût direct",
            "color": "Couleur (hex)",
        }
        widgets = {
            "description": forms.Textarea(attrs={"rows": 2}),
            "color": forms.TextInput(
                attrs={"type": "color", "style": "height:38px;padding:4px 6px;"}
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["description"].required = False


# ---------------------------------------------------------------------------
# Financial period forms
# ---------------------------------------------------------------------------


class FinancialPeriodForm(ISIFormMixin, forms.ModelForm):
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

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["notes"].required = False

    def clean(self):
        cleaned = super().clean()
        date_start = cleaned.get("date_start")
        date_end = cleaned.get("date_end")
        if date_start and date_end and date_end < date_start:
            raise ValidationError(
                "La date de fin doit être postérieure à la date de début."
            )
        return cleaned


# ---------------------------------------------------------------------------
# Reporting filter form
# ---------------------------------------------------------------------------


class ReportFilterForm(ISIFormMixin, forms.Form):
    """
    Used by financial analytics views.
    Either select a named FinancialPeriod OR specify a manual date range.
    """

    period = forms.ModelChoiceField(
        label="Période",
        required=False,
        queryset=FinancialPeriod.objects.order_by("-date_start"),
        empty_label="— Période personnalisée —",
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
        label="Type",
        required=False,
        choices=[("", "Formation + Étude")] + Invoice.TYPE_CHOICES,
    )

    def clean(self):
        cleaned = super().clean()
        period = cleaned.get("period")
        date_from = cleaned.get("date_from")
        date_to = cleaned.get("date_to")
        # If no period selected, both manual dates are required
        if not period:
            if not date_from:
                self.add_error(
                    "date_from",
                    "Sélectionnez une période ou saisissez une date de début.",
                )
            if not date_to:
                self.add_error(
                    "date_to", "Sélectionnez une période ou saisissez une date de fin."
                )
            if date_from and date_to and date_to < date_from:
                raise ValidationError(
                    "La date de fin doit être postérieure à la date de début."
                )
        return cleaned
