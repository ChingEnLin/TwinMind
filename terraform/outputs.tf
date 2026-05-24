output "service_url" {
  description = "Cloud Run service URL. Use this as VITE_TWINMIND_API_BASE in the portfolio repo (or point a custom domain at it)."
  value       = google_cloud_run_v2_service.twinmind.uri
}

output "image_uri" {
  description = "Full image URI Cloud Run is pulling. CI pushes new tags here."
  value       = local.image_uri
}

output "runtime_service_account" {
  description = "Service account the runtime executes as. CI deploy workflow will impersonate this if you wire workload-identity federation."
  value       = google_service_account.runtime.email
}

output "artifact_registry_path" {
  description = "Docker push target for CI: REGION-docker.pkg.dev/PROJECT/REPO"
  value       = "${var.region}-docker.pkg.dev/${var.project_id}/${var.service_name}"
}
