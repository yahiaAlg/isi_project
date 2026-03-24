# ISI Backend - Système de Gestion de l'Institut de Sécurité Industrielle

A Django backend implementation for an Industrial Safety Institute management system.

## Features

### Business Lines

- **Formations** - Professional safety training & certification
- **Études** - Industrial safety consulting & study projects

### Core Modules

- **Clients** - Client records, contact info, activity history
- **Formations** - Training catalog, sessions, enrollments, attestations
- **Études** - Study projects, phases, deliverables
- **Financial** - Invoices, payments, expenses
- **Resources** - Trainers, rooms, equipment, maintenance logs
- **Reporting** - Dashboard, KPIs, revenue reports

### User Roles

- **Administrateur** - Full access to all modules and financials
- **Réceptionniste** - Data entry access only (clients, enrollments, basic project info)

## Project Structure

```
config/
├── config/          # Project settings
│   ├── settings.py
│   ├── urls.py
│   ├── wsgi.py
│   └── asgi.py
├── core/                 # Institute information
│   ├── models.py         # InstituteInfo, BureauEtudeInfo, FormationInfo
│   ├── admin.py
│   └── context_processors.py
├── accounts/             # User authentication & profiles
│   ├── models.py         # UserProfile
│   ├── signals.py
│   ├── forms.py
│   ├── views.py
│   └── urls.py
├── clients/              # Client management
│   ├── models.py
│   ├── forms.py
│   ├── views.py
│   └── urls.py
├── formations/           # Training management
│   ├── models.py         # Formation, Session, Participant, Attestation
│   ├── forms.py
│   ├── views.py
│   └── urls.py
├── etudes/               # Study projects
│   ├── models.py         # StudyProject, ProjectPhase, ProjectDeliverable
│   ├── forms.py
│   ├── views.py
│   └── urls.py
├── financial/            # Invoicing & expenses
│   ├── models.py         # Invoice, Payment, Expense
│   ├── forms.py
│   ├── views.py
│   └── urls.py
├── resources/            # Resources management
│   ├── models.py         # Trainer, TrainingRoom, Equipment, EquipmentUsage, MaintenanceLog
│   ├── forms.py
│   ├── views.py
│   └── urls.py
└── reporting/            # Dashboard & reports
    ├── views.py
    └── urls.py
```

## Installation

1. Create a virtual environment:

```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

2. Install dependencies:

```bash
pip install -r requirements.txt
```

3. Run migrations:

```bash
python manage.py migrate
```

4. Create a superuser:

```bash
python manage.py createsuperuser
```

5. Run the development server:

```bash
python manage.py runserver
```

## Configuration

### Institute Information

After creating the superuser, access the Django admin at `/admin/` and configure:

1. **InstituteInfo** - General institute information (name, address, TVA, etc.)
2. **BureauEtudeInfo** - Consulting-specific information
3. **FormationInfo** - Training-specific information

### TVA Rate

The default TVA rate is 19% (Algerian standard). This can be configured in:

- `settings.py` - `TVA_RATE` setting
- Individual business line settings in `BureauEtudeInfo` and `FormationInfo`

## Business Rules

1. A session cannot be invoiced before its status is "Terminée"
2. A project phase should be marked complete before the project is closed
3. Participants cannot be enrolled beyond session capacity
4. Invoice numbers are auto-generated, sequential, and unique per business line
5. TVA is applied on all invoices (standard Algerian rate)
6. Currency: Algerian Dinar (DA)

## API Endpoints

### Accounts

- `GET/POST /accounts/login/` - Login
- `POST /accounts/logout/` - Logout
- `GET /accounts/users/` - User list (admin only)
- `GET/POST /accounts/users/create/` - Create user (admin only)
- `GET/POST /accounts/users/<id>/edit/` - Edit user (admin only)

### Clients

- `GET /clients/` - Client list
- `GET/POST /clients/create/` - Create client
- `GET /clients/<id>/` - Client detail
- `GET/POST /clients/<id>/edit/` - Edit client
- `POST /clients/<id>/delete/` - Delete client (admin only)

### Formations

- `GET /formations/` - Formation catalog
- `GET /formations/sessions/` - Session list
- `GET /formations/sessions/<id>/` - Session detail
- `GET/POST /formations/sessions/create/` - Create session (admin only)
- `GET/POST /formations/sessions/<id>/participants/add/` - Add participant
- `GET /formations/participants/<id>/attestation/` - View attestation

### Financial

- `GET /financial/invoices/` - Invoice list (admin only)
- `GET /financial/invoices/<id>/` - Invoice detail (admin only)
- `GET /financial/invoices/<id>/print/` - Printable invoice (admin only)
- `GET /financial/outstanding/` - Outstanding payments (admin only)
- `GET /financial/expenses/` - Expense list (admin only)

### Reporting

- `GET /` - Dashboard
- `GET /reporting/revenue/` - Revenue report (admin only)
- `GET /reporting/margins/` - Margins report (admin only)

## Print Templates

The system uses HTML/CSS templates for printable documents:

- **Invoices** - `/financial/invoices/<id>/print/` with print-specific CSS
- **Attestations** - `/formations/participants/<id>/attestation/`

Use `@media print` CSS rules for print optimization.

## Development Notes

### Function-Based Views

All views are implemented as function-based views following Django best practices.

### Post-Redirect-Get Pattern

All POST requests redirect to a GET request to prevent duplicate submissions.

### Minimal AJAX

AJAX is used sparingly via `JsonResponse` only when explicitly required.

### Role-Based Access

Views check `request.user.profile.is_admin` to restrict access to financial data.

## License

Proprietary - Institut de Sécurité Industrielle

# Run from your project root (Git Bash)

```bash
find . -path "./.venv" -prune -o -path "*/migrations/0*.py" -print | xargs rm -f

python manage.py makemigrations core clients accounts etudes formations resources financial

rm -f db.sqlite3

python manage.py migrate

python manage.py seed_db
```
