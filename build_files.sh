#!/bin/bash
echo "Building TradeFlow Colón for Vercel..."
pip install -r requirements.txt
python manage.py collectstatic --noinput
echo "Build complete."
