# clients/forms.py

from django import forms
from django.core.exceptions import ValidationError

from clients.models import Client, ClientContact


class ClientForm(forms.ModelForm):
    class Meta:
        model = Client
        fields = [
            "name",
            "client_type",
            "address",
            "postal_code",
            "city",
            "phone",
            "email",
            "website",
            "contact_name",
            "contact_phone",
            "contact_email",
            "registration_number",
            "nif",
            "nis",
            "activity_sector",
            "notes",
            "is_active",
        ]
        labels = {
            "name": "Nom",
            "client_type": "Type",
            "address": "Adresse",
            "postal_code": "Code postal",
            "city": "Ville",
            "phone": "Téléphone",
            "email": "Email",
            "website": "Site web",
            "contact_name": "Contact principal",
            "contact_phone": "Tél. contact",
            "contact_email": "Email contact",
            "registration_number": "N° RC",
            "nif": "NIF",
            "nis": "NIS",
            "activity_sector": "Secteur d'activité",
            "notes": "Notes",
            "is_active": "Actif",
        }
        widgets = {
            "address": forms.Textarea(attrs={"rows": 2}),
            "notes": forms.Textarea(attrs={"rows": 3}),
        }

    def clean_name(self):
        name = self.cleaned_data.get("name", "").strip()
        if not name:
            raise ValidationError("Le nom du client est obligatoire.")
        qs = Client.objects.filter(name__iexact=name)
        if self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise ValidationError(f"Un client portant ce nom existe déjà.")
        return name

    def clean_email(self):
        email = self.cleaned_data.get("email", "").strip().lower()
        return email

    def clean(self):
        cleaned_data = super().clean()
        client_type = cleaned_data.get("client_type")
        # RC / NIF / NIS only make sense for companies
        if client_type == Client.TYPE_INDIVIDUAL:
            cleaned_data.setdefault("registration_number", "")
            cleaned_data.setdefault("nif", "")
            cleaned_data.setdefault("nis", "")
        return cleaned_data


class ClientFilterForm(forms.Form):
    """Drives the client list search/filter bar."""

    q = forms.CharField(
        label="Recherche",
        required=False,
        widget=forms.TextInput(attrs={"placeholder": "Nom, ville, secteur…"}),
    )
    client_type = forms.ChoiceField(
        label="Type",
        required=False,
        choices=[("", "Tous")] + Client.TYPE_CHOICES,
    )
    has_balance = forms.ChoiceField(
        label="Solde",
        required=False,
        choices=[
            ("", "Tous"),
            ("yes", "Solde impayé"),
            ("no", "Aucun impayé"),
        ],
    )
    is_active = forms.ChoiceField(
        label="Statut",
        required=False,
        choices=[
            ("", "Tous"),
            ("1", "Actif"),
            ("0", "Inactif"),
        ],
    )


class ClientContactForm(forms.ModelForm):
    class Meta:
        model = ClientContact
        fields = [
            "first_name",
            "last_name",
            "job_title",
            "phone",
            "email",
            "is_primary",
            "notes",
        ]
        labels = {
            "first_name": "Prénom",
            "last_name": "Nom",
            "job_title": "Fonction",
            "phone": "Téléphone",
            "email": "Email",
            "is_primary": "Contact principal",
            "notes": "Notes",
        }
        widgets = {
            "notes": forms.Textarea(attrs={"rows": 2}),
        }

    def clean(self):
        cleaned_data = super().clean()
        if not cleaned_data.get("first_name") and not cleaned_data.get("last_name"):
            raise ValidationError("Au moins le prénom ou le nom est requis.")
        return cleaned_data
