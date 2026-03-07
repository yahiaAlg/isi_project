# =============================================================================
# financial/forms.py  —  v3.1
# =============================================================================
# Changes in v3.1:
# * FinalizeInvoiceForm — added mode_reglement (required) + due_date (optional).
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
# Proforma creation form
# ---------------------------------------------------------------------------


class ProformaCreateForm(ISIFormMixin, forms.ModelForm):
    """
    Used when creating a new proforma invoice.
    Only fields relevant to the PROFORMA phase are exposed.
    reference / proforma_reference are auto-generated; amounts are computed
    from line items.
    """

    class Meta:
        model = Invoice
        fields = [
            "invoice_type",
            "client",
            "invoice_date",
            "validity_date",
            "tva_rate",
            "page_ref",
            "session",
            "study_project",
            "notes",
            "footer_text",
        ]
        labels = {
            "invoice_type": "Type de prestation",
            "client": "Client",
            "invoice_date": "Date d'émission",
            "validity_date": "Date de validité",
            "tva_rate": "Taux TVA",
            "page_ref": "Réf. interne (en-tête)",
            "session": "Session liée (optionnel)",
            "study_project": "Projet lié (optionnel)",
            "notes": "Notes internes",
            "footer_text": "Pied de page (personnalisé)",
        }
        widgets = {
            "invoice_date": forms.DateInput(attrs={"type": "date"}),
            "validity_date": forms.DateInput(attrs={"type": "date"}),
            "notes": forms.Textarea(attrs={"rows": 3}),
            "footer_text": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["client"].queryset = Client.objects.filter(is_active=True).order_by(
            "name"
        )
        for f in (
            "validity_date",
            "page_ref",
            "session",
            "study_project",
            "notes",
            "footer_text",
        ):
            self.fields[f].required = False

    def clean(self):
        cleaned = super().clean()
        inv_type = cleaned.get("invoice_type")
        client = cleaned.get("client")
        session = cleaned.get("session")
        project = cleaned.get("study_project")

        if client and client.is_tva_exempt:
            cleaned["tva_rate"] = Decimal("0.00")

        if inv_type == Invoice.InvoiceType.FORMATION and project:
            self.add_error(
                "study_project",
                "Une facture Formation ne devrait pas être liée à un projet d'étude.",
            )
        if inv_type == Invoice.InvoiceType.ETUDE and session:
            self.add_error(
                "session",
                "Une facture Étude ne devrait pas être liée à une session.",
            )
        return cleaned


# Backward-compatible alias used by generic edit views
InvoiceForm = ProformaCreateForm


# ---------------------------------------------------------------------------
# Bon de Commande recording form
# ---------------------------------------------------------------------------


class BonCommandeForm(ISIFormMixin, forms.ModelForm):
    """Records the client's purchase order against an existing proforma."""

    class Meta:
        model = Invoice
        fields = [
            "bon_commande_number",
            "bon_commande_date",
            "bon_commande_amount",
            "bon_commande_scan",
        ]
        labels = {
            "bon_commande_number": "N° Bon de Commande",
            "bon_commande_date": "Date du BC",
            "bon_commande_amount": "Montant BC (DA) — vérification",
            "bon_commande_scan": "Scan / document BC",
        }
        widgets = {
            "bon_commande_date": forms.DateInput(attrs={"type": "date"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for f in ("bon_commande_date", "bon_commande_amount", "bon_commande_scan"):
            self.fields[f].required = False

    def clean_bon_commande_number(self):
        number = self.cleaned_data.get("bon_commande_number", "").strip()
        if not number:
            raise ValidationError("Le numéro de Bon de Commande est obligatoire.")
        return number


# ---------------------------------------------------------------------------
# Invoice finalization confirmation form  (v3.1)
# ---------------------------------------------------------------------------


class FinalizeInvoiceForm(ISIFormMixin, forms.Form):
    """
    Shown on the finalization confirmation page (GET).

    v3.1 additions:
      * mode_reglement — required; espèce selection triggers timbre fiscal
        preview in the JS sidebar.
      * due_date        — optional; helper text clarifies it is not required.
      * amount_in_words — pre-filled textarea, editable before submit.
    """

    mode_reglement = forms.ChoiceField(
        label="Mode de règlement",
        choices=[("", "— Sélectionner —")] + Invoice.PaymentMode.choices,
        required=True,
        widget=forms.Select(),
    )
    amount_in_words = forms.CharField(
        label="Montant en lettres",
        required=False,
        widget=forms.Textarea(
            attrs={
                "rows": 2,
                "placeholder": "Généré automatiquement — vérifiez si nécessaire",
            }
        ),
    )
    due_date = forms.DateField(
        label="Date d'échéance",
        required=False,
        widget=forms.DateInput(attrs={"type": "date"}),
        help_text="Optionnel — si vide, n'apparaît pas sur la facture imprimée.",
    )

    def clean_mode_reglement(self):
        value = self.cleaned_data.get("mode_reglement", "").strip()
        if not value:
            raise ValidationError("Veuillez sélectionner un mode de règlement.")
        valid = [choice[0] for choice in Invoice.PaymentMode.choices]
        if value not in valid:
            raise ValidationError("Mode de règlement invalide.")
        return value


# ---------------------------------------------------------------------------
# Invoice filter form
# ---------------------------------------------------------------------------


class InvoiceFilterForm(ISIFormMixin, forms.Form):
    q = forms.CharField(
        label="Recherche",
        required=False,
        widget=forms.TextInput(attrs={"placeholder": "Référence, client…"}),
    )
    phase = forms.ChoiceField(
        label="Phase",
        required=False,
        choices=[("", "Toutes")] + Invoice.Phase.choices,
    )
    status = forms.ChoiceField(
        label="Statut",
        required=False,
        choices=[("", "Tous")] + Invoice.Status.choices,
    )
    invoice_type = forms.ChoiceField(
        label="Type",
        required=False,
        choices=[("", "Tous")] + Invoice.InvoiceType.choices,
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
            "order",
            "description",
            "pricing_mode",
            "nb_persons",
            "nb_days",
            "unit_price_ht",
            "discount_percent",
        ]
        labels = {
            "order": "Ordre",
            "description": "Désignation",
            "pricing_mode": "Mode",
            "nb_persons": "Nb personnes",
            "nb_days": "Nb jours",
            "unit_price_ht": "P.U. HT (DA)",
            "discount_percent": "Remise (%)",
        }
        widgets = {
            "description": forms.TextInput(
                attrs={"placeholder": "Intitulé de la prestation"}
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["order"].required = False
        self.fields["discount_percent"].required = False

    def clean(self):
        cleaned = super().clean()
        mode = cleaned.get("pricing_mode")
        nb_persons = cleaned.get("nb_persons") or Decimal("0")
        nb_days = cleaned.get("nb_days") or Decimal("0")

        if mode == InvoiceItem.PricingMode.PER_PERSON and nb_persons <= 0:
            self.add_error("nb_persons", "Indiquez le nombre de personnes.")
        if mode == InvoiceItem.PricingMode.PER_DAY and nb_days <= 0:
            self.add_error("nb_days", "Indiquez le nombre de jours.")
        if mode == InvoiceItem.PricingMode.PER_PERSON_PER_DAY:
            if nb_persons <= 0:
                self.add_error("nb_persons", "Indiquez le nombre de personnes.")
            if nb_days <= 0:
                self.add_error("nb_days", "Indiquez le nombre de jours.")
        return cleaned


# ---------------------------------------------------------------------------
# Payment form
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
        self.fields["tva_rate"].initial = Decimal("0.09")

    def clean_amount_ht(self):
        amount = self.cleaned_data.get("amount_ht")
        if amount is not None and amount <= 0:
            raise ValidationError("Le montant doit être positif.")
        return amount

    def clean(self):
        cleaned = super().clean()
        tva_rate = cleaned.get("tva_rate") or Decimal("0")
        if tva_rate < 0 or tva_rate > 1:
            self.add_error(
                "tva_rate",
                "Le taux de TVA doit être compris entre 0 et 1 (ex. 0.09 pour 9%).",
            )
        return cleaned


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
            "approval_status",
            "approval_notes",
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
            "approval_status": "Statut d'approbation",
            "approval_notes": "Notes d'approbation",
            "notes": "Notes",
        }
        widgets = {
            "date": forms.DateInput(attrs={"type": "date"}),
            "notes": forms.Textarea(attrs={"rows": 3}),
            "approval_notes": forms.Textarea(attrs={"rows": 2}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for f in (
            "supplier",
            "payment_reference",
            "allocated_to_session",
            "allocated_to_project",
            "receipt",
            "approval_notes",
            "notes",
        ):
            self.fields[f].required = False


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
        choices=[("", "Tous")] + Expense.ApprovalStatus.choices,
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
# Financial period form
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
        choices=[("", "Formation + Étude")] + Invoice.InvoiceType.choices,
    )
    phase = forms.ChoiceField(
        label="Phase",
        required=False,
        choices=[("", "Toutes")] + Invoice.Phase.choices,
    )

    def clean(self):
        cleaned = super().clean()
        period = cleaned.get("period")
        date_from = cleaned.get("date_from")
        date_to = cleaned.get("date_to")
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
