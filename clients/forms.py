# clients/forms.py  —  v3.0

from django import forms
from django.core.exceptions import ValidationError

from clients.models import Client, ClientContact


class ClientForm(forms.ModelForm):
    class Meta:
        model = Client
        fields = [
            # Identity
            "name",
            "client_type",
            "forme_juridique",
            "activity_sector",
            # Contact
            "address",
            "postal_code",
            "city",
            "phone",
            "email",
            "website",
            # Legacy primary contact
            "contact_name",
            "contact_phone",
            "contact_email",
            # Fiscal IDs — shown/hidden via JS based on client_type
            "nin",
            "nif",
            "nis",
            "rc",
            "article_imposition",
            "rib",
            "carte_auto_entrepreneur",
            # Startup extras
            "label_startup_number",
            "label_startup_date",
            "programme_accompagnement",
            # Flags
            "is_tva_exempt",
            "is_active",
            "notes",
        ]
        labels = {
            "name": "Nom / Raison sociale",
            "client_type": "Type de client",
            "forme_juridique": "Forme juridique",
            "activity_sector": "Secteur d'activité",
            "address": "Adresse",
            "postal_code": "Code postal",
            "city": "Ville",
            "phone": "Téléphone",
            "email": "Email",
            "website": "Site web",
            "contact_name": "Contact principal",
            "contact_phone": "Tél. contact",
            "contact_email": "Email contact",
            "nin": "NIN (Numéro d'Identité Nationale)",
            "nif": "NIF",
            "nis": "NIS",
            "rc": "Numéro RC",
            "article_imposition": "Article d'imposition (A.I.)",
            "rib": "RIB",
            "carte_auto_entrepreneur": "N° Carte Auto-Entrepreneur",
            "label_startup_number": "N° Label Startup",
            "label_startup_date": "Date d'obtention du label",
            "programme_accompagnement": "Programme d'accompagnement",
            "is_tva_exempt": "Exonéré de TVA",
            "is_active": "Actif",
            "notes": "Notes",
        }
        widgets = {
            "address": forms.Textarea(attrs={"rows": 2}),
            "notes": forms.Textarea(attrs={"rows": 3}),
            "label_startup_date": forms.DateInput(attrs={"type": "date"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # All fiscal/type-specific fields are optional at the form level;
        # completeness is enforced at invoice finalization, not here.
        optional_fields = [
            "forme_juridique",
            "nin",
            "nif",
            "nis",
            "rc",
            "article_imposition",
            "rib",
            "carte_auto_entrepreneur",
            "label_startup_number",
            "label_startup_date",
            "programme_accompagnement",
            "contact_name",
            "contact_phone",
            "contact_email",
            "website",
            "notes",
        ]
        for f in optional_fields:
            if f in self.fields:
                self.fields[f].required = False

        # is_tva_exempt is auto-derived on save for standard types;
        # expose it as read-only hint for non-standard overrides.
        if self.instance and self.instance.pk:
            ct = self.instance.client_type
            auto_types = {
                Client.ClientType.PARTICULIER,
                Client.ClientType.AUTO_ENTREPRENEUR,
            }
            if ct in auto_types:
                self.fields["is_tva_exempt"].disabled = True
                self.fields["is_tva_exempt"].help_text = (
                    "Automatiquement exonéré pour ce type de client."
                )

    def clean_name(self):
        name = self.cleaned_data.get("name", "").strip()
        if not name:
            raise ValidationError("Le nom du client est obligatoire.")
        qs = Client.objects.filter(name__iexact=name)
        if self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise ValidationError("Un client portant ce nom existe déjà.")
        return name

    def clean_email(self):
        return self.cleaned_data.get("email", "").strip().lower()

    def clean_nin(self):
        nin = self.cleaned_data.get("nin", "").strip()
        if nin and not nin.isdigit():
            raise ValidationError("Le NIN ne doit contenir que des chiffres.")
        if nin and len(nin) not in (18,):
            raise ValidationError("Le NIN doit comporter 18 chiffres.")
        return nin

    def clean(self):
        cleaned = super().clean()
        client_type = cleaned.get("client_type")

        # For types that are auto-exempt, force is_tva_exempt to True
        # regardless of what was submitted (mirrors model.save() logic).
        if client_type in (
            Client.ClientType.PARTICULIER,
            Client.ClientType.AUTO_ENTREPRENEUR,
        ):
            cleaned["is_tva_exempt"] = True

        # Soft cross-field warnings — hard validation happens at finalization
        if client_type == Client.ClientType.PARTICULIER:
            for field in ("nif", "nis", "rc", "article_imposition"):
                if cleaned.get(field):
                    self.add_error(
                        field,
                        f"Ce champ n'est pas applicable aux particuliers.",
                    )

        if client_type == Client.ClientType.AUTO_ENTREPRENEUR:
            for field in ("nis", "rc"):
                if cleaned.get(field):
                    self.add_error(
                        field,
                        "Ce champ n'est pas applicable aux auto-entrepreneurs.",
                    )

        return cleaned


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
        choices=[("", "Tous")] + Client.ClientType.choices,
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
    is_tva_exempt = forms.ChoiceField(
        label="TVA",
        required=False,
        choices=[
            ("", "Tous"),
            ("1", "Exonéré TVA"),
            ("0", "Assujetti TVA"),
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

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for f in ("job_title", "phone", "email", "notes"):
            self.fields[f].required = False

    def clean(self):
        cleaned = super().clean()
        if not cleaned.get("first_name") and not cleaned.get("last_name"):
            raise ValidationError("Au moins le prénom ou le nom est requis.")
        return cleaned
