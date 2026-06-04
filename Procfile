web: python manage.py migrate --noinput && gunicorn tradeflow_colon.wsgi --bind 0.0.0.0:$PORT --workers 2 --timeout 120
release: python manage.py migrate --noinput