variable "project_id" {
  description = "GCP project ID that hosts the TwinMind backend."
  type        = string
}

variable "region" {
  description = "GCP region for Cloud Run, Artifact Registry, and Secret Manager. Pick one close to your portfolio's primary audience."
  type        = string
  default     = "us-central1"
}

variable "service_name" {
  description = "Cloud Run service name. Also used as the Artifact Registry repo name."
  type        = string
  default     = "twinmind"
}

variable "image_tag" {
  description = "Image tag deployed to Cloud Run. CI overrides this with the commit SHA on each deploy."
  type        = string
  default     = "latest"
}

variable "allowed_origin" {
  description = "CORS allow-origin. Set to the portfolio's production URL (e.g. https://chingenlin.com). Multiple origins can be comma-separated; the app splits on commas."
  type        = string
}

variable "daily_budget_usd" {
  description = "Daily Anthropic spend cap. Trips the circuit breaker when exceeded."
  type        = number
  default     = 0.50
}

variable "min_instances" {
  description = "Cloud Run min instances. 0 = scale-to-zero (free tier friendly, cold starts). 1 = always warm (~$5/mo extra, instant first response)."
  type        = number
  default     = 0
}

variable "max_instances" {
  description = "Cloud Run max instances. Hard ceiling to prevent runaway scale (and runaway bills)."
  type        = number
  default     = 3
}

variable "cpu" {
  description = "vCPUs per Cloud Run instance."
  type        = string
  default     = "1"
}

variable "memory" {
  description = "Memory per Cloud Run instance. BGE-small + chroma fits comfortably in 1Gi; reranker is API-call only."
  type        = string
  default     = "1Gi"
}

variable "anthropic_api_key" {
  description = "Anthropic API key. Stored in Secret Manager and mounted as an env var. Do NOT check this into git — set it via TF_VAR_anthropic_api_key or a .tfvars file that's in .gitignore."
  type        = string
  sensitive   = true
}

variable "api_key" {
  description = "Static bearer token the Vercel proxy uses to authenticate to this backend. Rotate by changing this value and re-applying."
  type        = string
  sensitive   = true
}

variable "github_token" {
  description = "Optional: GitHub PAT for ingesting public repos. Empty disables GitHub ingestion at runtime."
  type        = string
  sensitive   = true
  default     = ""
}

variable "allow_unauthenticated" {
  description = "Whether to allow unauthenticated invocations of the Cloud Run service. With static-bearer auth (handled by the app, not GCP IAM), this MUST be true — the Vercel proxy attaches the bearer; IAM auth would block it without an additional service-account dance."
  type        = bool
  default     = true
}
