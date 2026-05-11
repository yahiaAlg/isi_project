# financial/management/commands/seed_expenses.py
"""
Load expense entries from a JSON file into the database.

Usage:
  python manage.py seed_expenses                          # loads default file
  python manage.py seed_expenses --file path/to/file.json
  python manage.py seed_expenses --dry-run                # preview only
"""

import json
from datetime import date
from decimal import Decimal
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

DEFAULT_FILE = (
    Path(__file__).resolve().parent.parent.parent.parent / "expenses_janvier_2026.json"
)


class Command(BaseCommand):
    help = "Seed Expense entries from a JSON file."

    def add_arguments(self, parser):
        parser.add_argument(
            "--file",
            default=str(DEFAULT_FILE),
            help="Path to the JSON file (default: expenses_janvier_2026.json next to manage.py).",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Parse and validate without writing to the database.",
        )

    def handle(self, *args, **options):
        from financial.models import Expense, ExpenseCategory

        filepath = Path(options["file"])
        if not filepath.exists():
            raise CommandError(f"File not found: {filepath}")

        with filepath.open(encoding="utf-8") as f:
            entries = json.load(f)

        dry = options["dry_run"]
        created = skipped = flagged = 0

        for i, row in enumerate(entries, 1):
            # ── Resolve category ────────────────────────────────────────
            cat_name = row.get("category", "Divers")
            try:
                category = ExpenseCategory.objects.get(name=cat_name)
            except ExpenseCategory.DoesNotExist:
                self.stdout.write(
                    self.style.WARNING(
                        f"  [{i}] Category '{cat_name}' not found — skipped."
                    )
                )
                skipped += 1
                continue

            # ── Parse date ──────────────────────────────────────────────
            raw_date = row.get("date")
            entry_date = date.fromisoformat(raw_date) if raw_date else None

            raw_amount = row.get("amount")
            needs_review = (
                row.get("needs_review", False)
                or entry_date is None
                or raw_amount is None
            )

            # ── Preview line ────────────────────────────────────────────
            label = row.get("description") or row.get("vendor_name") or "—"
            amount_display = (
                f"{raw_amount:>12,.2f}" if raw_amount is not None else "        N/A "
            )
            self.stdout.write(
                f"  [{i:>2}] {'[DRY] ' if dry else ''}"
                f"{str(entry_date):10}  {amount_display} DZD  "
                f"{'⚠ ' if needs_review else '  '}"
                f"{cat_name[:30]}  —  {label[:50]}"
            )

            if dry:
                continue

            # ── Map old JSON fields → Expense v4.0 fields ──────────────
            #
            # vendor_name / beneficiary_name → supplier (free-text fallback)
            # invoice_number                 → payment_reference
            # amount_ht                      → gross_amount (pre-tax amount;
            #                                  IRG will be 0 for these entries)
            # needs_review / missing date    → approval_status = PENDING
            # scan_filename absent           → receipt_missing = True
            # vendor_nif, payment_method,
            #   tva_rate                     → folded into notes (no model field)
            # (no session/project context)   → is_overhead = True

            supplier = row.get("vendor_name") or row.get("beneficiary_name") or ""

            # Build notes from fields that have no direct column
            note_parts = []
            if row.get("vendor_nif"):
                note_parts.append(f"NIF fournisseur : {row['vendor_nif']}")
            if row.get("payment_method"):
                note_parts.append(f"Mode de paiement : {row['payment_method']}")
            if row.get("tva_rate") is not None:
                note_parts.append(f"TVA : {row['tva_rate']}%")
            if row.get("scan_filename"):
                note_parts.append(f"Scan : {row['scan_filename']}")

            kwargs = dict(
                date=entry_date or date.today(),
                amount=(
                    Decimal(str(raw_amount)) if raw_amount is not None else Decimal("0")
                ),
                category=category,
                description=row.get("description") or "",
                supplier=supplier,
                payment_reference=row.get("invoice_number") or "",
                is_overhead=True,
                approval_status=(
                    Expense.ApprovalStatus.PENDING
                    if needs_review
                    else Expense.ApprovalStatus.APPROVED
                ),
                receipt_missing=not bool(row.get("scan_filename")),
                notes="\n".join(note_parts),
            )

            # gross_amount: use amount_ht when present; model save() will set
            # irg_amount=0 and confirm amount = gross_amount (no IRG on these entries)
            if row.get("amount_ht") is not None:
                kwargs["gross_amount"] = Decimal(str(row["amount_ht"]))

            Expense.objects.create(**kwargs)
            created += 1
            if needs_review:
                flagged += 1

        # ── Summary ─────────────────────────────────────────────────────
        if dry:
            self.stdout.write(
                self.style.WARNING(
                    f"\n[Dry run] {len(entries)} entries parsed — nothing written."
                )
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(
                    f"\n✓ {created} created, {skipped} skipped, {flagged} flagged for review."
                )
            )
