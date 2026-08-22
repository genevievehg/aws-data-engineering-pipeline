variable "ingest_lambda_name" {
  type    = string
  default = "ingest_raw_data"
}

variable "notification_emails" {
  type = set(string)
}

variable "warehouse_db_name" {
  description = "Name of the warehouse PostgreSQL database"
  type        = string
  default     = "jurassic_sparks_warehouse"
}

variable "warehouse_master_username" {
  description = "Master username for the warehouse database"
  type        = string
  default     = "postgres"
}

variable "load_lambda_name" {
  type    = string
  default = "load_lambda"
}

variable "temporary_warehouse_admin_cidrs" {
  description = "Temporary public IPv4 /32 CIDRs permitted to access the RDS warehouse"
  type        = set(string)
  default     = []

  validation {
    condition = alltrue([
      for cidr in var.temporary_warehouse_admin_cidrs :
      can(cidrnetmask(cidr)) && endswith(cidr, "/32")
    ])

    error_message = "Every temporary administrator CIDR must be a valid IPv4 /32, such as 203.0.113.10/32."
  }
}

variable "apply_rds_changes_immediately" {
  description = "Apply RDS modifications immediately instead of waiting for the maintenance window"
  type        = bool
  default     = false
}