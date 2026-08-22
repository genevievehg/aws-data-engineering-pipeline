# PostgreSQL data warehouse for the transformed ToteSys data.
resource "aws_db_instance" "warehouse" {
  identifier = "jurassic-sparks-warehouse"

  # Database engine
  engine                   = "postgres"
  engine_version           = "18.3"
  engine_lifecycle_support = "open-source-rds-extended-support-disabled"

  instance_class = "db.t4g.micro"

  # Initial warehouse database and master user.
  db_name  = var.warehouse_db_name
  username = var.warehouse_master_username

  # Let RDS generate and manage the master password in Secrets Manager.
  manage_master_user_password = true

  # Storage
  allocated_storage = 20
  storage_type      = "gp3"
  storage_encrypted = true

  # Disable storage autoscaling so this development DB stays bounded.
  max_allocated_storage = 0

  # Networking
  db_subnet_group_name = aws_db_subnet_group.rds.name

  vpc_security_group_ids = [
    aws_security_group.warehouse_rds.id
  ]

  # Single-AZ development database.
  # availability_zone is deliberately omitted so AWS can choose
  # any suitable AZ within eu-west-2.
  multi_az = false
  # publicly_accessible = false
  # Public access exists only while a temporary administrator CIDR is provided.
  publicly_accessible = length(var.temporary_warehouse_admin_cidrs) > 0
  apply_immediately   = var.apply_rds_changes_immediately

  port = 5432

  # Automated backups
  backup_retention_period  = 1
  copy_tags_to_snapshot    = true
  delete_automated_backups = true

  # This is development/rebuildable infrastructure.
  skip_final_snapshot = true
  deletion_protection = false

  # Maintenance
  auto_minor_version_upgrade = true

  # PostgreSQL logs are exported into CloudWatch.
  enabled_cloudwatch_logs_exports = [
    "postgresql"
  ]

  # Database Insights / Performance Insights
  database_insights_mode                = "standard"
  performance_insights_enabled          = true
  performance_insights_retention_period = 7

  # We are using password authentication via Secrets Manager,
  # not IAM database authentication.
  iam_database_authentication_enabled = false

  tags = {
    Name      = "jurassic-sparks-warehouse"
    Project   = "jurassic-sparks"
    Component = "warehouse"
  }
}

resource "aws_db_subnet_group" "rds" {
  name = "rds-subnet-group"

  subnet_ids = data.aws_subnets.default.ids

  tags = {
    Name = "my-rds-subnet-group"
  }
}