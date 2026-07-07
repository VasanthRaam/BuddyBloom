# Backend Deployment and Security Guide

This guide details how to build, test, and deploy the BuddyBloom FastAPI backend to **Google Cloud Run** and **Render**, along with best practices for database migrations and secrets protection.

---

## 🏗️ Part 1: How the Backend Builds (Docker)

The backend is packaged using a containerized environment defined in the `Dockerfile`.

### 🚨 Critical Security: Do Not Leak Secrets
* **`.dockerignore`:** We have configured a `.dockerignore` file. This prevents your local `.env` (which contains your active database passwords and Supabase credentials) and the local Windows `venv` folder from ever being copied into the final Docker image.
* **Production Environments:** Secrets should **never** be hardcoded in the codebase or baked into the Docker image. Instead, inject them at runtime as environment variables in Cloud Run or Render.

---

## 🚀 Part 2: Deployment Platforms

### Option A: Google Cloud Run (Recommended for production)

Google Cloud Run builds your container in the cloud using **Google Cloud Build** and hosts it serverlessly.

1. **Deploying via CLI (Google Cloud SDK):**
   Run the following command from the `backend/` directory to build and deploy:
   ```bash
   gcloud run deploy buddybloom-prod --source . --platform managed --region asia-south1
   ```
   *Note: Using `--source .` automatically triggers Google Cloud Build. It respects the `.dockerignore` file, so your local secrets remain safe.*

2. **Continuous Deployment (GitHub trigger):**
   If you have linked your GitHub repository to Cloud Run:
   * Pushing changes to the `main` branch triggers a Cloud Build workflow.
   * Make sure your environment variables (listed in `gradle.properties` / `.env`) are configured in the **Cloud Run Console > Variables & Secrets** tab, not in your code repository.

---

### Option B: Render Deployment

If you are using Render for hosting the API:

1. Render connects directly to your GitHub repository.
2. In the Render Dashboard, set your **Build Command** to use the Docker environment.
3. Make sure to define all variables (like `DATABASE_URL`, `SUPABASE_URL`, `SUPABASE_JWT_SECRET`, etc.) in the **Environment** section of your Render Web Service settings.

---

## 🔄 Part 3: Startup Database Migrations

When the backend container starts, it automatically executes database table creation and updates defined in [main.py](file:///c:/BuddyBloom/BuddyBloom/backend/main.py#L59-L195):
* It verifies and creates all tables (including points, wallets, and rewards catalog).
* It applies B-tree performance indexes.
* It seeds the default reward catalog items if they do not exist.

You do not need to run manual SQL migrations on the live database; the startup hook handles it automatically.
