"""
Forms for resources app.
"""

from django import forms
from django.core.exceptions import ValidationError
from django.utils import timezone
from formations.models import Trainer, TrainingRoom
from .models import (
    EquipmentBooking,
    Equipment,
    EquipmentUsage,
    MaintenanceLog,
)


class TrainerForm(forms.ModelForm):
    """Form for creating/editing Trainer."""

    class Meta:
        model = Trainer
        fields = [
            "first_name",
            "last_name",
            "specialty",
            "daily_rate",
            "phone",
            "email",
            "notes",
            "is_active",
        ]
        widgets = {
            "first_name": forms.TextInput(attrs={"class": "form-control"}),
            "last_name": forms.TextInput(attrs={"class": "form-control"}),
            "specialty": forms.TextInput(attrs={"class": "form-control"}),
            "daily_rate": forms.NumberInput(attrs={"class": "form-control"}),
            "phone": forms.TextInput(attrs={"class": "form-control"}),
            "email": forms.EmailInput(attrs={"class": "form-control"}),
            "notes": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
            "is_active": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }


class TrainingRoomForm(forms.ModelForm):
    """Form for creating/editing TrainingRoom."""

    class Meta:
        model = TrainingRoom
        fields = ["name", "capacity", "location", "description", "is_active"]
        widgets = {
            "name": forms.TextInput(attrs={"class": "form-control"}),
            "capacity": forms.NumberInput(attrs={"class": "form-control"}),
            "location": forms.TextInput(attrs={"class": "form-control"}),
            "description": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
            "is_active": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }


class EquipmentForm(forms.ModelForm):
    """Form for creating/editing Equipment."""

    class Meta:
        model = Equipment
        fields = [
            "name",
            "category",
            "purchase_date",
            "purchase_cost",
            "current_value",
            "condition",
            "status",
            "location",
            "maintenance_interval_days",
            "notes",
        ]
        widgets = {
            "name": forms.TextInput(attrs={"class": "form-control"}),
            "category": forms.TextInput(attrs={"class": "form-control"}),
            "purchase_date": forms.DateInput(
                attrs={"class": "form-control", "type": "date"}
            ),
            "purchase_cost": forms.NumberInput(attrs={"class": "form-control"}),
            "current_value": forms.NumberInput(attrs={"class": "form-control"}),
            "condition": forms.Select(attrs={"class": "form-select"}),
            "status": forms.Select(attrs={"class": "form-select"}),
            "location": forms.TextInput(attrs={"class": "form-control"}),
            "maintenance_interval_days": forms.NumberInput(
                attrs={"class": "form-control"}
            ),
            "notes": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        """Initialize form with default date."""
        super().__init__(*args, **kwargs)

        if not self.instance.pk:
            self.fields["purchase_date"].initial = timezone.now().date()
            self.fields["maintenance_interval_days"].initial = 180


class EquipmentUsageForm(forms.ModelForm):
    """Form for creating/editing EquipmentUsage."""

    class Meta:
        model = EquipmentUsage
        fields = [
            "equipment",
            "assigned_to_session",
            "assigned_to_project",
            "date",
            "duration_hours",
            "context",
        ]
        widgets = {
            "equipment": forms.Select(attrs={"class": "form-select"}),
            "assigned_to_session": forms.Select(attrs={"class": "form-select"}),
            "assigned_to_project": forms.Select(attrs={"class": "form-select"}),
            "date": forms.DateInput(attrs={"class": "form-control", "type": "date"}),
            "duration_hours": forms.NumberInput(
                attrs={"class": "form-control", "step": "0.5"}
            ),
            "context": forms.Textarea(attrs={"class": "form-control", "rows": 2}),
        }

    def __init__(self, *args, equipment=None, **kwargs):
        """Initialize form with optional equipment."""
        super().__init__(*args, **kwargs)

        if equipment:
            self.fields["equipment"].initial = equipment.id
            self.fields["equipment"].widget.attrs["readonly"] = True

        # Set default date
        if not self.instance.pk:
            self.fields["date"].initial = timezone.now().date()

    def clean(self):
        """Validate assignment."""
        cleaned_data = super().clean()
        assigned_to_session = cleaned_data.get("assigned_to_session")
        assigned_to_project = cleaned_data.get("assigned_to_project")

        if not assigned_to_session and not assigned_to_project:
            raise ValidationError("Veuillez sélectionner une session ou un projet.")

        if assigned_to_session and assigned_to_project:
            raise ValidationError(
                "Veuillez sélectionner soit une session, soit un projet, pas les deux."
            )

        return cleaned_data


class MaintenanceLogForm(forms.ModelForm):
    """Form for creating/editing MaintenanceLog."""

    class Meta:
        model = MaintenanceLog
        fields = [
            "equipment",
            "date",
            "maintenance_type",
            "cost",
            "performed_by",
            "description",
            "next_due_date",
        ]
        widgets = {
            "equipment": forms.Select(attrs={"class": "form-select"}),
            "date": forms.DateInput(attrs={"class": "form-control", "type": "date"}),
            "maintenance_type": forms.Select(attrs={"class": "form-select"}),
            "cost": forms.NumberInput(attrs={"class": "form-control"}),
            "performed_by": forms.TextInput(attrs={"class": "form-control"}),
            "description": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
            "next_due_date": forms.DateInput(
                attrs={"class": "form-control", "type": "date"}
            ),
        }

    def __init__(self, *args, equipment=None, **kwargs):
        """Initialize form with optional equipment."""
        super().__init__(*args, **kwargs)

        if equipment:
            self.fields["equipment"].initial = equipment.id

        # Set default date
        if not self.instance.pk:
            self.fields["date"].initial = timezone.now().date()


class _BookingForm(forms.ModelForm):
    class Meta:
        model = EquipmentBooking
        fields = [
            "reserved_for_session",
            "reserved_for_project",
            "date_from",
            "date_to",
            "notes",
        ]
        widgets = {
            "date_from": forms.DateInput(
                attrs={"type": "date", "class": "form-control"}
            ),
            "date_to": forms.DateInput(attrs={"type": "date", "class": "form-control"}),
            "notes": forms.Textarea(attrs={"rows": 2, "class": "form-control"}),
        }

    def __init__(self, *args, equipment=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.equipment = equipment
        self.fields["reserved_for_session"].required = False
        self.fields["reserved_for_project"].required = False

    def clean(self):
        cleaned_data = super().clean()
        session = cleaned_data.get("reserved_for_session")
        project = cleaned_data.get("reserved_for_project")
        if not session and not project:
            raise forms.ValidationError(
                "Associez la réservation à une session ou à un projet."
            )
        if session and project:
            raise forms.ValidationError(
                "Choisissez soit une session, soit un projet — pas les deux."
            )
        date_from = cleaned_data.get("date_from")
        date_to = cleaned_data.get("date_to")
        if date_from and date_to and date_to < date_from:
            raise forms.ValidationError(
                "La date de fin doit être après la date de début."
            )
        return cleaned_data
