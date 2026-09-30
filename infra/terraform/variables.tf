variable "project" {
  type    = string
  default = "threadline"
}

variable "region" {
  type    = string
  default = "eu-west-2" # London
}

variable "image_tag" {
  description = "Container image tag deployed to ECS (CI passes the git SHA)"
  type        = string
  default     = "latest"
}

variable "alert_email" {
  description = "Email for budget alerts"
  type        = string
}

variable "monthly_budget_usd" {
  type    = number
  default = 40
}

variable "db_instance_class" {
  type    = string
  default = "db.t4g.micro"
}

variable "raw_data_s3_prefix" {
  description = "Optional: s3://bucket/prefix holding the real H&M CSVs. Empty = synthetic data."
  type        = string
  default     = ""
}

variable "training_schedule" {
  description = "EventBridge Scheduler expression for retraining"
  type        = string
  default     = "cron(0 3 ? * MON *)" # Mondays 03:00 UTC
}

variable "inference_max_tasks" {
  type    = number
  default = 3
}
