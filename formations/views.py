# formations/views.py

from django.contrib import messages
from django.core.paginator import Paginator
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from core.utils import admin_required, login_and_active_required
from formations.forms import (
    AttestationIssueForm,
    FormationCategoryForm,
    FormationForm,
    ParticipantForm,
    ParticipantImportForm,
    SessionCancelForm,
    SessionFilterForm,
    SessionForm,
    SessionStatusForm,
)
from formations.models import (
    Attestation,
    Formation,
    FormationCategory,
    Participant,
    Session,
)
from formations.utils import (
    bulk_enroll_participants,
    issue_attestations_bulk,
    parse_participant_csv,
    parse_participant_excel,
)


# ---------------------------------------------------------------------------
# Formation catalog — admin only per spec
# ---------------------------------------------------------------------------


@admin_required
def formation_list(request):
    qs = Formation.objects.select_related("category").all()
    q = request.GET.get("q", "").strip()
    category = request.GET.get("category")
    is_active = request.GET.get("is_active")

    if q:
        from django.db.models import Q

        qs = qs.filter(Q(title__icontains=q) | Q(description__icontains=q))
    if category:
        qs = qs.filter(category_id=category)
    if is_active == "1":
        qs = qs.filter(is_active=True)
    elif is_active == "0":
        qs = qs.filter(is_active=False)

    categories = FormationCategory.objects.all()
    paginator = Paginator(qs, 20)
    page_obj = paginator.get_page(request.GET.get("page"))

    return render(
        request,
        "formations/formation_list.html",
        {"page_obj": page_obj, "categories": categories},
    )


@admin_required
def formation_detail(request, pk):
    formation = get_object_or_404(Formation.objects.select_related("category"), pk=pk)
    sessions = formation.sessions.select_related("client", "trainer").order_by(
        "-date_start"
    )[:10]
    return render(
        request,
        "formations/formation_detail.html",
        {"formation": formation, "sessions": sessions},
    )


@admin_required
def formation_create(request):
    form = FormationForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        formation = form.save()
        messages.success(request, f"Formation « {formation.title} » créée.")
        return redirect("formations:formation_detail", pk=formation.pk)
    return render(
        request,
        "formations/formation_form.html",
        {"form": form, "action": "Nouvelle formation"},
    )


@admin_required
def formation_edit(request, pk):
    formation = get_object_or_404(Formation, pk=pk)
    # Accept ?suggest_base_price=XXXXX from session form's smart notification
    initial = {}
    suggest_price = request.GET.get("suggest_base_price")
    if suggest_price and request.method == "GET":
        try:
            from decimal import Decimal

            initial["base_price"] = Decimal(suggest_price).quantize(Decimal("0.01"))
        except Exception:
            pass

    form = FormationForm(
        request.POST or None, instance=formation, initial=initial or None
    )
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Formation mise à jour.")
        return redirect("formations:formation_detail", pk=pk)
    return render(
        request,
        "formations/formation_form.html",
        {"form": form, "action": "Modifier", "formation": formation},
    )


@admin_required
def formation_deactivate(request, pk):
    if request.method != "POST":
        return redirect("formations:formation_detail", pk=pk)
    formation = get_object_or_404(Formation, pk=pk)
    formation.is_active = not formation.is_active
    formation.save(update_fields=["is_active"])
    state = "activée" if formation.is_active else "désactivée"
    messages.success(request, f"Formation « {formation.title} » {state}.")
    return redirect("formations:formation_detail", pk=pk)


# ---------------------------------------------------------------------------
# Categories
# ---------------------------------------------------------------------------


@admin_required
def category_list(request):
    categories = FormationCategory.objects.all()
    return render(request, "formations/category_list.html", {"categories": categories})


@admin_required
def category_create(request):
    form = FormationCategoryForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        category = form.save()
        messages.success(request, f"Catégorie « {category.name} » créée.")
        return redirect("formations:category_list")
    return render(
        request,
        "formations/category_form.html",
        {"form": form, "action": "Nouvelle catégorie"},
    )


@admin_required
def category_edit(request, pk):
    category = get_object_or_404(FormationCategory, pk=pk)
    form = FormationCategoryForm(request.POST or None, instance=category)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Catégorie mise à jour.")
        return redirect("formations:category_list")
    return render(
        request,
        "formations/category_form.html",
        {"form": form, "action": "Modifier", "category": category},
    )


@admin_required
def category_delete(request, pk):
    if request.method != "POST":
        return redirect("formations:category_list")
    category = get_object_or_404(FormationCategory, pk=pk)
    if category.formations.exists():
        messages.error(
            request,
            f"Impossible de supprimer « {category.name} » : des formations y sont associées.",
        )
        return redirect("formations:category_list")
    category.delete()
    messages.success(request, "Catégorie supprimée.")
    return redirect("formations:category_list")


# ---------------------------------------------------------------------------
# Sessions
# ---------------------------------------------------------------------------


@login_and_active_required
def session_list(request):
    qs = Session.objects.select_related("formation", "client", "trainer").all()
    form = SessionFilterForm(request.GET or None)

    if form.is_valid():
        q = form.cleaned_data.get("q")
        status = form.cleaned_data.get("status")
        date_from = form.cleaned_data.get("date_from")
        date_to = form.cleaned_data.get("date_to")
        formation = form.cleaned_data.get("formation")

        if q:
            from django.db.models import Q

            qs = qs.filter(
                Q(formation__title__icontains=q)
                | Q(client__name__icontains=q)
                | Q(trainer__last_name__icontains=q)
                | Q(trainer__first_name__icontains=q)
            )
        if status:
            qs = qs.filter(status=status)
        if date_from:
            qs = qs.filter(date_start__gte=date_from)
        if date_to:
            qs = qs.filter(date_end__lte=date_to)
        if formation:
            qs = qs.filter(formation=formation)

    paginator = Paginator(qs, 20)
    page_obj = paginator.get_page(request.GET.get("page"))

    return render(
        request,
        "formations/session_list.html",
        {"page_obj": page_obj, "filter_form": form},
    )


@login_and_active_required
def session_detail(request, pk):
    session = get_object_or_404(
        Session.objects.select_related("formation", "client", "trainer", "room"), pk=pk
    )
    participants = session.participants.all()
    attestations = (
        session.attestations.select_related("participant")
        if session.status == Session.STATUS_COMPLETED
        else []
    )
    return render(
        request,
        "formations/session_detail.html",
        {
            "session": session,
            "participants": participants,
            "attestations": attestations,
        },
    )


def _session_form_context(exclude_session_pk=None):
    """
    Build JSON-serialisable dicts for the smart-notification JS on the session form.
    Passed to both session_create and session_edit.
    """
    import json
    from django.urls import reverse
    from formations.models import TrainingRoom

    room_capacities = {
        str(r.pk): r.capacity for r in TrainingRoom.objects.filter(is_active=True)
    }

    formation_data = {}
    for f in Formation.objects.filter(is_active=True):
        sessions_qs = f.sessions.exclude(status=Session.STATUS_CANCELLED)
        if exclude_session_pk:
            sessions_qs = sessions_qs.exclude(pk=exclude_session_pk)

        used_days = sum(
            (s.date_end - s.date_start).days + 1
            for s in sessions_qs
            if s.date_start and s.date_end
        )
        # Existing revenue: sum of (effective_price × capacity) for planned/active sessions
        existing_revenue = sum(
            float(s.price_per_participant or f.base_price or 0) * s.capacity
            for s in sessions_qs
        )

        formation_data[str(f.pk)] = {
            "duration_days": float(f.duration_days) if f.duration_days else None,
            "duration_hours": float(f.duration_hours) if f.duration_hours else None,
            "base_price": float(f.base_price) if f.base_price else None,
            "used_days": used_days,
            "existing_revenue": round(existing_revenue, 2),
            "edit_url": reverse("formations:formation_edit", args=[f.pk]),
        }

    return {
        "room_capacities_json": json.dumps(room_capacities),
        "formation_data_json": json.dumps(formation_data),
    }


def session_create(request):
    import math
    from datetime import date, timedelta
    from decimal import Decimal, ROUND_HALF_UP

    prefill_formation = None
    initial = {}
    formation_pk = request.GET.get("formation")
    if formation_pk:
        try:
            prefill_formation = Formation.objects.get(pk=formation_pk, is_active=True)
            initial["formation"] = prefill_formation.pk
            initial["capacity"] = int(prefill_formation.max_participants)

            if prefill_formation.duration_days:
                today = date.today()
                duration = max(1, math.ceil(float(prefill_formation.duration_days)))
                initial["date_start"] = today.strftime("%Y-%m-%d")
                initial["date_end"] = (today + timedelta(days=duration - 1)).strftime(
                    "%Y-%m-%d"
                )

            # Default session_hours = formation total duration_hours
            if prefill_formation.duration_hours:
                initial["session_hours"] = (
                    format(prefill_formation.duration_hours, "f")
                    .rstrip("0")
                    .rstrip(".")
                )

            # Price = base_price / duration_hours × session_hours
            # When pre-filling a single session that covers the whole formation,
            # session_hours == duration_hours → price = base_price
            if prefill_formation.base_price and prefill_formation.duration_hours:
                sh = float(prefill_formation.duration_hours)
                dh = float(prefill_formation.duration_hours)
                price = (
                    Decimal(str(prefill_formation.base_price))
                    * Decimal(str(sh))
                    / Decimal(str(dh))
                )
                price = price.quantize(Decimal("1"), rounding=ROUND_HALF_UP)
                initial["price_per_participant"] = str(price)
            elif prefill_formation.base_price:
                initial["price_per_participant"] = (
                    format(prefill_formation.base_price, "f").rstrip("0").rstrip(".")
                )

        except Formation.DoesNotExist:
            pass

    form = SessionForm(request.POST or None, initial=initial)
    if request.method == "POST" and form.is_valid():
        session = form.save()
        messages.success(request, "Session créée.")
        return redirect("formations:session_detail", pk=session.pk)

    ctx = _session_form_context()
    ctx.update(
        {
            "form": form,
            "action": "Nouvelle session",
            "prefill_formation": prefill_formation,
        }
    )
    return render(request, "formations/session_form.html", ctx)


@admin_required
def session_edit(request, pk):
    session = get_object_or_404(Session, pk=pk)
    form = SessionForm(request.POST or None, instance=session)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Session mise à jour.")
        return redirect("formations:session_detail", pk=pk)

    ctx = _session_form_context(exclude_session_pk=pk)
    ctx.update({"form": form, "action": "Modifier", "session": session})
    return render(request, "formations/session_form.html", ctx)


@admin_required
def session_update_status(request, pk):
    session = get_object_or_404(Session, pk=pk)
    form = SessionStatusForm(request.POST or None, current_status=session.status)

    if request.method == "POST" and form.is_valid():
        new_status = form.cleaned_data["status"]
        session.status = new_status
        if new_status == Session.STATUS_CANCELLED:
            session.cancellation_reason = form.cleaned_data["cancellation_reason"]
        session.save()
        messages.success(
            request, f"Statut mis à jour : {session.get_status_display()}."
        )
        return redirect("formations:session_detail", pk=pk)

    return render(
        request,
        "formations/session_status_form.html",
        {"form": form, "session": session},
    )


@admin_required
def session_cancel(request, pk):
    session = get_object_or_404(Session, pk=pk)
    if session.status not in [Session.STATUS_PLANNED, Session.STATUS_IN_PROGRESS]:
        messages.error(request, "Cette session ne peut plus être annulée.")
        return redirect("formations:session_detail", pk=pk)

    form = SessionCancelForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        session.status = Session.STATUS_CANCELLED
        session.cancellation_reason = form.cleaned_data["cancellation_reason"]
        session.save(update_fields=["status", "cancellation_reason"])
        messages.success(request, "Session annulée.")
        return redirect("formations:session_detail", pk=pk)

    return render(
        request,
        "formations/session_cancel.html",
        {"form": form, "session": session},
    )


# ---------------------------------------------------------------------------
# Participants
# ---------------------------------------------------------------------------


@login_and_active_required
def participant_add(request, session_pk):
    session = get_object_or_404(Session, pk=session_pk)

    if session.is_full:
        messages.error(request, "La session est complète.")
        return redirect("formations:session_detail", pk=session_pk)

    form = ParticipantForm(request.POST or None, session=session)
    if request.method == "POST" and form.is_valid():
        participant = form.save(commit=False)
        participant.session = session
        participant.save()
        messages.success(request, f"Participant « {participant.full_name} » inscrit.")
        return redirect("formations:session_detail", pk=session_pk)

    return render(
        request,
        "formations/participant_form.html",
        {"form": form, "session": session, "action": "Inscrire un participant"},
    )


@login_and_active_required
def participant_edit(request, session_pk, pk):
    session = get_object_or_404(Session, pk=session_pk)
    participant = get_object_or_404(Participant, pk=pk, session=session)
    form = ParticipantForm(request.POST or None, instance=participant, session=session)

    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Participant mis à jour.")
        return redirect("formations:session_detail", pk=session_pk)

    return render(
        request,
        "formations/participant_form.html",
        {"form": form, "session": session, "action": "Modifier le participant"},
    )


@login_and_active_required
def participant_delete(request, session_pk, pk):
    if request.method != "POST":
        return redirect("formations:session_detail", pk=session_pk)
    participant = get_object_or_404(Participant, pk=pk, session_id=session_pk)
    participant.delete()
    messages.success(request, "Participant supprimé.")
    return redirect("formations:session_detail", pk=session_pk)


@admin_required
def participant_toggle_attendance(request, session_pk, pk):
    if request.method != "POST":
        return redirect("formations:session_detail", pk=session_pk)
    participant = get_object_or_404(Participant, pk=pk, session_id=session_pk)
    participant.attended = not participant.attended
    participant.save(update_fields=["attended"])
    state = "présent" if participant.attended else "absent"
    messages.success(request, f"« {participant.full_name} » marqué {state}.")
    return redirect("formations:session_detail", pk=session_pk)


@login_and_active_required
def participant_import(request, session_pk):
    session = get_object_or_404(Session, pk=session_pk)
    form = ParticipantImportForm(request.POST or None, request.FILES or None)

    if request.method == "POST" and form.is_valid():
        uploaded = form.cleaned_data["file"]
        name = uploaded.name.lower()

        if name.endswith(".csv"):
            rows, parse_errors = parse_participant_csv(uploaded)
        else:
            rows, parse_errors = parse_participant_excel(uploaded)

        if parse_errors:
            for err in parse_errors:
                messages.warning(request, err)

        created, skipped, enroll_errors = bulk_enroll_participants(session, rows)
        for err in enroll_errors:
            messages.warning(request, err)

        messages.success(
            request,
            f"{created} participant(s) importé(s), {skipped} ignoré(s) (doublons).",
        )
        return redirect("formations:session_detail", pk=session_pk)

    return render(
        request,
        "formations/participant_import.html",
        {"form": form, "session": session},
    )


# ---------------------------------------------------------------------------
# Attestations
# ---------------------------------------------------------------------------


@admin_required
def attestation_issue_bulk(request, session_pk):
    session = get_object_or_404(Session, pk=session_pk)

    if session.status != Session.STATUS_COMPLETED:
        messages.error(
            request,
            "Les attestations ne peuvent être émises que pour une session terminée.",
        )
        return redirect("formations:session_detail", pk=session_pk)

    form = AttestationIssueForm(request.POST or None, session=session)

    if request.method == "POST" and form.is_valid():
        issue_date = form.cleaned_data["issue_date"]
        participant_ids = form.cleaned_data["participant_ids"].values_list(
            "pk", flat=True
        )
        issued, skipped = issue_attestations_bulk(session, participant_ids, issue_date)
        messages.success(
            request,
            f"{issued} attestation(s) émise(s), {skipped} ignorée(s) (déjà émises).",
        )
        return redirect("formations:session_detail", pk=session_pk)

    return render(
        request,
        "formations/attestation_issue.html",
        {"form": form, "session": session},
    )


@login_and_active_required
def attestation_detail(request, pk):
    attestation = get_object_or_404(
        Attestation.objects.select_related(
            "participant", "session__formation", "session__trainer"
        ),
        pk=pk,
    )
    return render(
        request,
        "formations/attestation_detail.html",
        {"attestation": attestation},
    )


@admin_required
def attestation_print(request, pk):
    """Render a print-ready attestation template."""
    from core.models import FormationInfo, InstituteInfo

    attestation = get_object_or_404(
        Attestation.objects.select_related(
            "participant",
            "session__formation__category",
            "session__trainer",
        ),
        pk=pk,
    )
    institute = InstituteInfo.get_instance()
    formation_info = FormationInfo.get_instance()

    return render(
        request,
        "formations/attestation_print.html",
        {
            "attestation": attestation,
            "institute": institute,
            "formation_info": formation_info,
        },
    )


@admin_required
def attestation_revoke(request, pk):
    if request.method != "POST":
        return redirect("formations:attestation_detail", pk=pk)
    attestation = get_object_or_404(Attestation, pk=pk)
    session_pk = attestation.session_id
    attestation.is_issued = False
    attestation.save(update_fields=["is_issued"])
    messages.success(request, f"Attestation {attestation.reference} révoquée.")
    return redirect("formations:session_detail", pk=session_pk)


# ---------------------------------------------------------------------------
# Analytics
# ---------------------------------------------------------------------------


@admin_required
def formation_analytics(request):
    from django.db.models import Avg, Count, Sum

    sessions = Session.objects.select_related("formation", "trainer")

    total_sessions = sessions.count()
    completed = sessions.filter(status=Session.STATUS_COMPLETED)
    total_completed = completed.count()

    total_participants = Participant.objects.filter(
        session__status=Session.STATUS_COMPLETED
    ).count()
    total_attended = Participant.objects.filter(
        session__status=Session.STATUS_COMPLETED, attended=True
    ).count()

    total_attestations = Attestation.objects.filter(is_issued=True).count()

    # Revenue from completed sessions (effective_price × attended_count is a
    # property, so aggregate in Python — analytics page, acceptable cost)
    revenue = sum(s.total_revenue for s in completed)

    top_formations = Formation.objects.annotate(
        session_count=Count("sessions")
    ).order_by("-session_count")[:5]

    return render(
        request,
        "formations/analytics.html",
        {
            "total_sessions": total_sessions,
            "total_completed": total_completed,
            "total_participants": total_participants,
            "total_attended": total_attended,
            "total_attestations": total_attestations,
            "revenue": revenue,
            "top_formations": top_formations,
        },
    )


@admin_required
def session_fill_rates(request):
    sessions = (
        Session.objects.select_related("formation", "trainer")
        .filter(
            status__in=[
                Session.STATUS_COMPLETED,
                Session.STATUS_IN_PROGRESS,
                Session.STATUS_PLANNED,
            ]
        )
        .order_by("-date_start")
    )
    # fill_rate is a property — evaluate in Python
    data = [
        {
            "session": s,
            "fill_rate": s.fill_rate,
            "participant_count": s.participant_count,
            "available_spots": s.available_spots,
        }
        for s in sessions
    ]
    return render(request, "formations/fill_rates.html", {"data": data})


@admin_required
def trainer_utilization(request):
    from resources.models import Trainer

    trainers = Trainer.objects.filter(is_active=True).prefetch_related("sessions")
    data = [
        {
            "trainer": t,
            "session_count": t.session_count,
            "total_earnings": t.total_earnings,
            "upcoming": t.upcoming_sessions[:3],
        }
        for t in trainers
    ]
    return render(request, "formations/trainer_utilization.html", {"data": data})


# ---------------------------------------------------------------------------
# AJAX
# ---------------------------------------------------------------------------


@login_and_active_required
def sessions_calendar_feed(request):
    """
    Returns sessions as a JSON array for FullCalendar or similar.
    Accepts optional ?start= and ?end= ISO date params.
    """
    qs = Session.objects.select_related("formation").exclude(
        status=Session.STATUS_CANCELLED
    )

    start = request.GET.get("start")
    end = request.GET.get("end")
    if start:
        qs = qs.filter(date_end__gte=start)
    if end:
        qs = qs.filter(date_start__lte=end)

    STATUS_COLORS = {
        Session.STATUS_PLANNED: "#3B82F6",
        Session.STATUS_IN_PROGRESS: "#F59E0B",
        Session.STATUS_COMPLETED: "#10B981",
        Session.STATUS_CANCELLED: "#EF4444",
    }

    events = [
        {
            "id": s.pk,
            "title": s.formation.title,
            "start": s.date_start.isoformat(),
            "end": s.date_end.isoformat(),
            "color": STATUS_COLORS.get(s.status, "#6B7280"),
            "url": f"/formations/sessions/{s.pk}/",
            "extendedProps": {
                "status": s.status,
                "participant_count": s.participant_count,
                "capacity": s.capacity,
            },
        }
        for s in qs
    ]
    return JsonResponse(events, safe=False)


# ─── ADD THESE TO formations/views.py ────────────────────────────────────── #
# (append at the end, or place near the AJAX section)

from django.http import JsonResponse
from django.views.decorators.http import require_GET


@admin_required
@require_GET
def api_formation_list(request):
    """
    Return all active formations for the line-item source selector.
    Optionally filter by ?q= for a live search.
    """
    from formations.models import Formation

    q = request.GET.get("q", "").strip()
    qs = Formation.objects.filter(is_active=True).order_by("title")
    if q:
        qs = qs.filter(title__icontains=q)

    data = [
        {
            "id": f.pk,
            "title": f.title,
            "duration_days": getattr(f, "duration_days", None)
            or getattr(f, "duration", None),
            "base_price": str(
                getattr(f, "base_price", None)
                or getattr(f, "price_per_person", None)
                or ""
            ),
            "description": f.title,  # use title as invoice line description default
        }
        for f in qs
    ]
    return JsonResponse({"results": data})


@admin_required
@require_GET
def api_formation_detail(request, pk):
    """Return a single formation's prepopulation data."""
    from formations.models import Formation

    f = get_object_or_404(Formation, pk=pk)
    return JsonResponse(
        {
            "id": f.pk,
            "title": f.title,
            "description": f.title,
            "duration_days": getattr(f, "duration_days", None)
            or getattr(f, "duration", None),
            "base_price": str(
                getattr(f, "base_price", None)
                or getattr(f, "price_per_person", None)
                or ""
            ),
        }
    )
