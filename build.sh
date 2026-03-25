pip install -r requirements.txt

find . -path "./.venv" -prune -o -path "*/migrations/0*.py" -print | xargs rm -f

python manage.py makemigrations core clients accounts etudes formations resources financial

rm -f db.sqlite3

python manage.py migrate

python manage.py collectstatic --noinput -v 0

python manage.py seed_db_minimal

python manage.py seed_formations_catalog     # all 505 specialties
