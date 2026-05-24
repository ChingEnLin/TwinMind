###############################################################################
# TwinMind — Cloud Run + Artifact Registry + Secret Manager
#
# What this provisions:
#   - Artifact Registry repo to hold the Docker image
#   - Secret Manager entries for ANTHROPIC_API_KEY, API_KEY, GITHUB_TOKEN
#   - Service account for the Cloud Run runtime (least-privilege: only
#     secret-accessor on the three secrets above)
#   - Cloud Run v2 service wired to the image, secrets, and env vars
#
# What this does NOT provision (deferred):
#   - Custom domain mapping (Cloud Run Domain Mappings) — easier to add via
#     console once you've decided on the domain. Add `google_cloud_run_domain_mapping`
#     here when ready.
#   - Cloud Logging dashboards — Cloud Run already ships structured logs and
#     basic metrics out of the box; dashboards can be a follow-up.
#
# State backend: local by default. For collaboration, switch to a GCS backend
# (terraform { backend "gcs" { bucket = "...-tfstate" } }) and bootstrap the
# bucket out-of-band.
###############################################################################

# --- APIs ------------------------------------------------------------------
# Enable everything we depend on. Idempotent — safe to re-apply.
locals {
  required_apis = [
    "artifactregistry.googleapis.com",
    "run.googleapis.com",
    "secretmanager.googleapis.com",
    "iam.googleapis.com",
  ]
}

resource "google_project_service" "required" {
  for_each = toset(local.required_apis)
  service  = each.key

  disable_on_destroy = false
}

# --- Artifact Registry -----------------------------------------------------
resource "google_artifact_registry_repository" "twinmind" {
  location      = var.region
  repository_id = var.service_name
  description   = "Container images for the TwinMind RAG backend"
  format        = "DOCKER"

  depends_on = [google_project_service.required]
}

# --- Service account for the Cloud Run runtime -----------------------------
resource "google_service_account" "runtime" {
  account_id   = "${var.service_name}-runtime"
  display_name = "TwinMind Cloud Run runtime"

  depends_on = [google_project_service.required]
}

# --- Secrets ---------------------------------------------------------------
# One secret per credential. Cloud Run mounts each as an env var.
# Versioning is automatic — each `terraform apply` with a changed value adds
# a new version; older versions remain accessible if you need to roll back.

resource "google_secret_manager_secret" "anthropic_api_key" {
  secret_id = "${var.service_name}-anthropic-api-key"

  replication {
    auto {}
  }

  depends_on = [google_project_service.required]
}

resource "google_secret_manager_secret_version" "anthropic_api_key" {
  secret      = google_secret_manager_secret.anthropic_api_key.id
  secret_data = var.anthropic_api_key
}

resource "google_secret_manager_secret" "api_key" {
  secret_id = "${var.service_name}-api-key"

  replication {
    auto {}
  }

  depends_on = [google_project_service.required]
}

resource "google_secret_manager_secret_version" "api_key" {
  secret      = google_secret_manager_secret.api_key.id
  secret_data = var.api_key
}

resource "google_secret_manager_secret" "github_token" {
  secret_id = "${var.service_name}-github-token"

  replication {
    auto {}
  }

  depends_on = [google_project_service.required]
}

resource "google_secret_manager_secret_version" "github_token" {
  secret = google_secret_manager_secret.github_token.id
  # Secret Manager rejects empty strings; use a single space as a placeholder
  # when the user hasn't provided a token. The app reads "" || " " as falsy.
  secret_data = var.github_token == "" ? " " : var.github_token
}

# --- Grant the runtime SA access to each secret ---------------------------
resource "google_secret_manager_secret_iam_member" "runtime_accessor" {
  for_each = {
    anthropic = google_secret_manager_secret.anthropic_api_key.id
    api       = google_secret_manager_secret.api_key.id
    github    = google_secret_manager_secret.github_token.id
  }

  secret_id = each.value
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.runtime.email}"
}

# --- Cloud Run service -----------------------------------------------------
locals {
  image_uri = "${var.region}-docker.pkg.dev/${var.project_id}/${var.service_name}/${var.service_name}:${var.image_tag}"
}

resource "google_cloud_run_v2_service" "twinmind" {
  name     = var.service_name
  location = var.region
  ingress  = "INGRESS_TRAFFIC_ALL"

  template {
    service_account = google_service_account.runtime.email
    timeout         = "300s" # SSE streams; well under Cloud Run's 60-min hard cap.

    scaling {
      min_instance_count = var.min_instances
      max_instance_count = var.max_instances
    }

    containers {
      image = local.image_uri

      ports {
        container_port = 8080
      }

      resources {
        limits = {
          cpu    = var.cpu
          memory = var.memory
        }
        # Allow CPU bursting during cold start (BGE model load).
        cpu_idle          = true
        startup_cpu_boost = true
      }

      # Non-secret env. Secrets come from secret_manager refs below.
      env {
        name  = "ALLOWED_ORIGIN"
        value = var.allowed_origin
      }
      env {
        name  = "DAILY_BUDGET_USD"
        value = tostring(var.daily_budget_usd)
      }
      env {
        name  = "BOOTSTRAP_SOURCE"
        value = "local"
      }
      env {
        name  = "RERANKER"
        value = "claude"
      }

      # Secrets mounted as env vars. The "latest" version is automatically
      # picked up on the next revision deploy.
      env {
        name = "ANTHROPIC_API_KEY"
        value_source {
          secret_key_ref {
            secret  = google_secret_manager_secret.anthropic_api_key.secret_id
            version = "latest"
          }
        }
      }
      env {
        name = "API_KEY"
        value_source {
          secret_key_ref {
            secret  = google_secret_manager_secret.api_key.secret_id
            version = "latest"
          }
        }
      }
      env {
        name = "GITHUB_TOKEN"
        value_source {
          secret_key_ref {
            secret  = google_secret_manager_secret.github_token.secret_id
            version = "latest"
          }
        }
      }

      startup_probe {
        http_get {
          path = "/v1/healthz"
        }
        initial_delay_seconds = 5
        period_seconds        = 10
        timeout_seconds       = 5
        failure_threshold     = 6 # 60s total; covers BGE-cache load + chroma open.
      }
    }
  }

  depends_on = [
    google_secret_manager_secret_version.anthropic_api_key,
    google_secret_manager_secret_version.api_key,
    google_secret_manager_secret_version.github_token,
    google_secret_manager_secret_iam_member.runtime_accessor,
    google_artifact_registry_repository.twinmind,
  ]
}

# --- Public invocation -----------------------------------------------------
# With static-bearer auth handled inside the app (Vercel proxy attaches it),
# the GCP-level invoker permission is given to allUsers. The app's bearer
# check is what actually gates access.
resource "google_cloud_run_v2_service_iam_member" "public" {
  count = var.allow_unauthenticated ? 1 : 0

  name     = google_cloud_run_v2_service.twinmind.name
  location = google_cloud_run_v2_service.twinmind.location
  role     = "roles/run.invoker"
  member   = "allUsers"
}
