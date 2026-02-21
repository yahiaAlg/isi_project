# core/forms.py

from django import forms
from core.models import BureauEtudeInfo, FormationInfo, InstituteInfo


class InstituteInfoForm(forms.ModelForm):
    class Meta:
        model = InstituteInfo
        exclude = ["created_at", "updated_at"]
        labels = {
            "name": "Nom de l'institut",
            "abbreviation": "Abréviation",
            "address": "Adresse",
            "postal_code": "Code postal",
            "city": "Ville",
            "phone": "Téléphone",
            "email": "Email",
            "website": "Site web",
            "registration_number": "Numéro RC",
            "nif": "NIF",
            "nis": "NIS",
            "bank_name": "Banque",
            "bank_account": "Numéro de compte",
            "bank_rib": "RIB",
            "logo": "Logo",
            "director_signature": "Signature du directeur",
            "director_name": "Nom du directeur",
            "director_title": "Titre du directeur",
            "invoice_footer_text": "Pied de page des factures",
        }
        widgets = {
            "address": forms.Textarea(attrs={"rows": 3}),
            "invoice_footer_text": forms.Textarea(attrs={"rows": 3}),
        }

    def clean_name(self):
        name = self.cleaned_data.get("name", "").strip()
        if not name:
            raise forms.ValidationError("Le nom de l'institut est obligatoire.")
        return name


class FormationInfoForm(forms.ModelForm):
    class Meta:
        model = FormationInfo
        exclude = ["created_at", "updated_at"]
        labels = {
            "name": "Nom du centre",
            "description": "Description",
            "address": "Adresse spécifique",
            "phone": "Téléphone",
            "email": "Email",
            "invoice_prefix": "Préfixe des factures",
            "tva_applicable": "TVA applicable",
            "tva_rate": "Taux de TVA",
            "director_name": "Nom du directeur",
            "director_title": "Titre du directeur",
            "director_signature": "Signature",
            "attestation_validity_years": "Validité des attestations (années)",
            "min_attendance_percent": "Présence minimale requise (%)",
        }
        widgets = {
            "description": forms.Textarea(attrs={"rows": 3}),
            "address": forms.Textarea(attrs={"rows": 3}),
        }

    def clean_tva_rate(self):
        rate = self.cleaned_data.get("tva_rate")
        if rate is not None and not (0 <= rate <= 1):
            raise forms.ValidationError(
                "Le taux de TVA doit être compris entre 0 et 1 (ex. 0.19 pour 19%)."
            )
        return rate

    def clean_min_attendance_percent(self):
        val = self.cleaned_data.get("min_attendance_percent")
        if val is not None and not (0 <= val <= 100):
            raise forms.ValidationError(
                "Le pourcentage doit être compris entre 0 et 100."
            )
        return val

    def clean_invoice_prefix(self):
        prefix = self.cleaned_data.get("invoice_prefix", "").strip().upper()
        if not prefix:
            raise forms.ValidationError("Le préfixe est obligatoire.")
        return prefix


class BureauEtudeInfoForm(forms.ModelForm):
    class Meta:
        model = BureauEtudeInfo
        exclude = ["created_at", "updated_at"]
        labels = {
            "name": "Nom du bureau",
            "description": "Description",
            "address": "Adresse spécifique",
            "phone": "Téléphone",
            "email": "Email",
            "invoice_prefix": "Préfixe des factures",
            "tva_applicable": "TVA applicable",
            "tva_rate": "Taux de TVA",
            "chief_engineer_name": "Ingénieur en chef",
            "chief_engineer_title": "Titre",
            "chief_engineer_signature": "Signature",
        }
        widgets = {
            "description": forms.Textarea(attrs={"rows": 3}),
            "address": forms.Textarea(attrs={"rows": 3}),
        }

    def clean_tva_rate(self):
        rate = self.cleaned_data.get("tva_rate")
        if rate is not None and not (0 <= rate <= 1):
            raise forms.ValidationError(
                "Le taux de TVA doit être compris entre 0 et 1 (ex. 0.19 pour 19%)."
            )
        return rate

    def clean_invoice_prefix(self):
        prefix = self.cleaned_data.get("invoice_prefix", "").strip().upper()
        if not prefix:
            raise forms.ValidationError("Le préfixe est obligatoire.")
        # Ensure prefix doesn't clash with the other business line
        from core.models import FormationInfo

        other = FormationInfo.get_instance().invoice_prefix
        if prefix == other:
            raise forms.ValidationError(
                f"Le préfixe « {prefix} » est déjà utilisé par le centre de formation."
            )
        return prefix
