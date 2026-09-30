resource "random_id" "suffix" {
  byte_length = 3
}

locals {
  name   = var.project
  suffix = random_id.suffix.hex
  images = {
    app_api   = "${aws_ecr_repository.repo["app-api"].repository_url}:${var.image_tag}"
    inference = "${aws_ecr_repository.repo["inference"].repository_url}:${var.image_tag}"
    mlflow    = "${aws_ecr_repository.repo["mlflow"].repository_url}:${var.image_tag}"
    trainer   = "${aws_ecr_repository.repo["trainer"].repository_url}:${var.image_tag}"
  }
  internal_domain = "${var.project}.internal"
  inference_url   = "http://inference.${local.internal_domain}:8001"
  mlflow_url      = "http://mlflow.${local.internal_domain}:5000"
}

# ---------------------------------------------------------------- container registry
resource "aws_ecr_repository" "repo" {
  for_each             = toset(["app-api", "inference", "mlflow", "trainer"])
  name                 = "${local.name}/${each.key}"
  image_tag_mutability = "MUTABLE"
  force_delete         = true
  image_scanning_configuration {
    scan_on_push = true
  }
}

resource "aws_ecr_lifecycle_policy" "repo" {
  for_each   = aws_ecr_repository.repo
  repository = each.value.name
  policy = jsonencode({
    rules = [{
      rulePriority = 1
      description  = "Keep the last 10 images"
      selection    = { tagStatus = "any", countType = "imageCountMoreThan", countNumber = 10 }
      action       = { type = "expire" }
    }]
  })
}

# ---------------------------------------------------------------- buckets
resource "aws_s3_bucket" "artifacts" {
  bucket        = "${local.name}-artifacts-${local.suffix}"
  force_destroy = true
}

resource "aws_s3_bucket_versioning" "artifacts" {
  bucket = aws_s3_bucket.artifacts.id
  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket" "site" {
  for_each      = toset(["storefront", "ops"])
  bucket        = "${local.name}-${each.key}-${local.suffix}"
  force_destroy = true
}

resource "aws_s3_bucket_public_access_block" "all" {
  for_each                = merge({ artifacts = aws_s3_bucket.artifacts.id }, { for k, b in aws_s3_bucket.site : k => b.id })
  bucket                  = each.value
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_server_side_encryption_configuration" "artifacts" {
  bucket = aws_s3_bucket.artifacts.id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

# ---------------------------------------------------------------- database
resource "random_password" "db" {
  length  = 32
  special = false
}

resource "aws_db_subnet_group" "main" {
  name       = "${local.name}-db"
  subnet_ids = aws_subnet.public[*].id
}

resource "aws_db_instance" "main" {
  identifier              = "${local.name}-db"
  engine                  = "postgres"
  engine_version          = "16"
  instance_class          = var.db_instance_class
  allocated_storage       = 20
  storage_type            = "gp3"
  storage_encrypted       = true
  db_name                 = "threadline"
  username                = "threadline"
  password                = random_password.db.result
  db_subnet_group_name    = aws_db_subnet_group.main.name
  vpc_security_group_ids  = [aws_security_group.db.id]
  publicly_accessible     = false
  backup_retention_period = 1
  skip_final_snapshot     = true # demo project; set false and add final_snapshot_identifier for real data
  apply_immediately       = true
}

# ---------------------------------------------------------------- secrets (SSM Parameter Store)
resource "random_password" "secret" {
  for_each = toset(["django", "ops", "inference_admin"])
  length   = 40
  special  = false
}

locals {
  db_base = "postgresql://threadline:${random_password.db.result}@${aws_db_instance.main.address}:5432"
  secrets = {
    DATABASE_URL          = "${local.db_base}/threadline"
    MLFLOW_BACKEND_URI    = "${local.db_base}/mlflow"
    DJANGO_SECRET_KEY     = random_password.secret["django"].result
    OPS_TOKEN             = random_password.secret["ops"].result
    INFERENCE_ADMIN_TOKEN = random_password.secret["inference_admin"].result
  }
}

resource "aws_ssm_parameter" "secret" {
  for_each = local.secrets
  name     = "/${local.name}/${each.key}"
  type     = "SecureString"
  value    = each.value
}
