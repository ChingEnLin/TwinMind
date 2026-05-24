###############################################################################
# Workload Identity Federation for GitHub Actions
#
# Lets GitHub Actions impersonate a deploy service account WITHOUT a long-lived
# JSON key checked into repo secrets. The flow:
#
#   1. GitHub Actions runs `google-github-actions/auth@v2` with our WIF pool +
#      provider names and the deploy SA email.
#   2. Google exchanges the GitHub OIDC token for a short-lived (1h) access
#      token scoped to the deploy SA.
#   3. The workflow uses that token for `gcloud` / `docker push` / etc.
#
# Security model:
#   - The provider's `attribute_condition` pins access to a single GitHub repo,
#     so OIDC tokens from any other repo are rejected even if their owner
#     somehow points at this pool.
#   - The deploy SA gets only the roles it needs: AR writer (push images),
#     Cloud Run admin (deploy new revisions), and serviceAccountUser on the
#     runtime SA (so the deploy can attach it to new revisions).
###############################################################################

variable "github_repository" {
  description = "GitHub repository in `owner/name` form. Used to pin the WIF provider so only this repo can mint tokens for the deploy SA."
  type        = string
}

# --- The pool ---------------------------------------------------------------
resource "google_iam_workload_identity_pool" "github" {
  workload_identity_pool_id = "${var.service_name}-github"
  display_name              = "${var.service_name} GitHub OIDC"
  description               = "Workload Identity Pool for GitHub Actions CI"

  depends_on = [google_project_service.required]
}

# --- The provider ----------------------------------------------------------
# Maps GitHub OIDC claims (repo, actor, ref) onto attributes Google can
# evaluate in IAM policies.
resource "google_iam_workload_identity_pool_provider" "github" {
  workload_identity_pool_id          = google_iam_workload_identity_pool.github.workload_identity_pool_id
  workload_identity_pool_provider_id = "github"
  display_name                       = "GitHub Actions"

  attribute_mapping = {
    "google.subject"       = "assertion.sub"
    "attribute.repository" = "assertion.repository"
    "attribute.ref"        = "assertion.ref"
    "attribute.actor"      = "assertion.actor"
  }

  # Without this condition the provider would mint tokens for ANY GitHub repo —
  # required to be explicit since the Aug 2024 GCP policy change.
  attribute_condition = "assertion.repository == \"${var.github_repository}\""

  oidc {
    issuer_uri = "https://token.actions.githubusercontent.com"
  }
}

# --- The deploy service account --------------------------------------------
resource "google_service_account" "deploy" {
  account_id   = "${var.service_name}-deploy"
  display_name = "TwinMind CI deploy"

  depends_on = [google_project_service.required]
}

# --- Bind the WIF pool to the deploy SA ------------------------------------
# Two role grants are needed:
#   - workloadIdentityUser: lets the WIF principal mint OIDC ID tokens scoped
#     to the deploy SA (the basic WIF handshake).
#   - serviceAccountTokenCreator: lets the WIF principal call
#     iam.serviceAccounts.getAccessToken on the deploy SA so that subprocess
#     CLIs (`gcloud storage`, `docker push` via gcloud creds, etc.) can
#     impersonate it for normal API calls. Without this, OIDC handshake
#     succeeds but actual GCP API calls fail with PERMISSION_DENIED.
locals {
  github_principal_set = "principalSet://iam.googleapis.com/${google_iam_workload_identity_pool.github.name}/attribute.repository/${var.github_repository}"
}

resource "google_service_account_iam_member" "wif_deploy_oidc" {
  service_account_id = google_service_account.deploy.name
  role               = "roles/iam.workloadIdentityUser"
  member             = local.github_principal_set
}

resource "google_service_account_iam_member" "wif_deploy_token_creator" {
  service_account_id = google_service_account.deploy.name
  role               = "roles/iam.serviceAccountTokenCreator"
  member             = local.github_principal_set
}

# --- Roles for the deploy SA -----------------------------------------------
# Least-privilege set: enough to push to AR and deploy new Cloud Run revisions
# wired to the runtime SA.
resource "google_project_iam_member" "deploy_ar_writer" {
  project = var.project_id
  role    = "roles/artifactregistry.writer"
  member  = "serviceAccount:${google_service_account.deploy.email}"
}

resource "google_project_iam_member" "deploy_run_admin" {
  project = var.project_id
  role    = "roles/run.admin"
  member  = "serviceAccount:${google_service_account.deploy.email}"
}

# Required so the deploy SA can attach the runtime SA to the new revision
# (`gcloud run deploy --service-account=...` needs actAs on the runtime SA).
resource "google_service_account_iam_member" "deploy_actas_runtime" {
  service_account_id = google_service_account.runtime.name
  role               = "roles/iam.serviceAccountUser"
  member             = "serviceAccount:${google_service_account.deploy.email}"
}

# --- Outputs CI needs ------------------------------------------------------
output "wif_provider" {
  description = "Full WIF provider resource name. Paste into the GitHub Actions auth step as `workload_identity_provider`."
  value       = google_iam_workload_identity_pool_provider.github.name
}

output "deploy_service_account" {
  description = "Deploy SA email. Paste into the GitHub Actions auth step as `service_account`."
  value       = google_service_account.deploy.email
}
