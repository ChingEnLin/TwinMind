###############################################################################
# Content bucket — source of truth for the documents that get indexed.
#
# Why this exists: data/samples/private/ is gitignored, so a CI checkout
# doesn't see the private content. Without a separate source, CI would build
# images missing data your local builds include. The bucket gives us one
# place every build (local, CI, future-collaborators) pulls from.
#
# Update flow:
#   1. Edit markdown locally
#   2. `gcloud storage rsync -r data/samples/ gs://<bucket>/`
#   3. Trigger redeploy (push to dev, or workflow_dispatch on the deploy
#      workflow)
#
# Cost: storage is effectively zero at this scale (a few MB of markdown).
# Free tier covers 5 GB and 50k Class B (read) ops per month.
###############################################################################

variable "content_bucket_name" {
  description = "GCS bucket holding the source markdown documents. Globally unique; default uses the project ID as a prefix."
  type        = string
  default     = ""
}

locals {
  content_bucket = var.content_bucket_name != "" ? var.content_bucket_name : "${var.project_id}-twinmind-content"
}

resource "google_storage_bucket" "content" {
  name                        = local.content_bucket
  location                    = var.region
  storage_class               = "STANDARD"
  uniform_bucket_level_access = true
  public_access_prevention    = "enforced"

  # Keep a few prior versions of each object so a bad edit is recoverable.
  versioning {
    enabled = true
  }

  # Stop paying for ancient versions after 30 days.
  lifecycle_rule {
    condition {
      num_newer_versions = 5
    }
    action {
      type = "Delete"
    }
  }

  depends_on = [google_project_service.required]
}

# CI (deploy SA) needs to read objects to pull content into the image build.
resource "google_storage_bucket_iam_member" "deploy_reader" {
  bucket = google_storage_bucket.content.name
  role   = "roles/storage.objectViewer"
  member = "serviceAccount:${google_service_account.deploy.email}"
}

# Local-dev convenience: also grant the runtime SA read access. Not strictly
# required (Docker builds don't run as the runtime SA), but allows the running
# Cloud Run service to fetch content at runtime if we ever add a refresh
# endpoint later.
resource "google_storage_bucket_iam_member" "runtime_reader" {
  bucket = google_storage_bucket.content.name
  role   = "roles/storage.objectViewer"
  member = "serviceAccount:${google_service_account.runtime.email}"
}

output "content_bucket_uri" {
  description = "Bucket URI. Use as BUILD_DATA_FROM in the deploy workflow, and as the destination for `gcloud storage rsync` when uploading edits."
  value       = "gs://${google_storage_bucket.content.name}"
}
