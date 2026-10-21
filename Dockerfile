# ---------- Stage 1: build the React frontend ----------
FROM node:22-alpine AS frontend
WORKDIR /frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# ---------- Stage 2: the Django backend ----------
FROM python:3.14-slim
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/ .
COPY --from=frontend /frontend/dist ./frontend_dist

# Collect admin/DRF static files (the secret key is only needed to load settings)
RUN DJANGO_SECRET_KEY=build-only python manage.py collectstatic --noinput

# Don't run as root
RUN useradd --create-home appuser && chown -R appuser /app && chmod +x start.sh
USER appuser

CMD ["./start.sh"]
