resource "aws_ecs_cluster" "main" {
  name = local.name
  setting {
    name  = "containerInsights"
    value = "enabled"
  }
}

resource "aws_service_discovery_private_dns_namespace" "internal" {
  name = local.internal_domain
  vpc  = aws_vpc.main.id
}

resource "aws_service_discovery_service" "svc" {
  for_each = toset(["inference", "mlflow"])
  name     = each.key
  dns_config {
    namespace_id = aws_service_discovery_private_dns_namespace.internal.id
    dns_records {
      ttl  = 10
      type = "A"
    }
    routing_policy = "MULTIVALUE"
  }
  health_check_custom_config {
    failure_threshold = 1
  }
}

resource "aws_cloudwatch_log_group" "svc" {
  for_each          = toset(["app-api", "inference", "mlflow", "trainer"])
  name              = "/ecs/${local.name}/${each.key}"
  retention_in_days = 14
}

locals {
  secret_ref = { for k, p in aws_ssm_parameter.secret : k => p.arn }

  logs = { for k, g in aws_cloudwatch_log_group.svc : k => {
    logDriver = "awslogs"
    options = {
      "awslogs-group"         = g.name
      "awslogs-region"        = var.region
      "awslogs-stream-prefix" = k
    }
  } }

  site_origin = "https://${aws_cloudfront_distribution.storefront.domain_name}"
}

# ---------------------------------------------------------------- task definitions
resource "aws_ecs_task_definition" "app_api" {
  family                   = "${local.name}-app-api"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = 512
  memory                   = 1024
  execution_role_arn       = aws_iam_role.execution.arn
  task_role_arn            = aws_iam_role.task.arn
  runtime_platform {
    operating_system_family = "LINUX"
    cpu_architecture        = "X86_64"
  }
  container_definitions = jsonencode([{
    name         = "app-api"
    image        = local.images.app_api
    essential    = true
    portMappings = [{ containerPort = 8000, protocol = "tcp" }]
    environment = [
      { name = "DJANGO_DEBUG", value = "false" },
      { name = "DJANGO_ALLOWED_HOSTS", value = "*" }, # only CloudFront can reach the ALB
      { name = "CSRF_TRUSTED_ORIGINS", value = "${local.site_origin},https://${aws_cloudfront_distribution.ops.domain_name}" },
      { name = "INFERENCE_URL", value = local.inference_url },
      { name = "MLFLOW_TRACKING_URI", value = local.mlflow_url },
      { name = "SEED_FROM", value = "s3://${aws_s3_bucket.artifacts.bucket}/processed" },
      { name = "GUNICORN_WORKERS", value = "3" },
    ]
    secrets = [
      { name = "DATABASE_URL", valueFrom = local.secret_ref["DATABASE_URL"] },
      { name = "DJANGO_SECRET_KEY", valueFrom = local.secret_ref["DJANGO_SECRET_KEY"] },
      { name = "OPS_TOKEN", valueFrom = local.secret_ref["OPS_TOKEN"] },
      { name = "INFERENCE_ADMIN_TOKEN", valueFrom = local.secret_ref["INFERENCE_ADMIN_TOKEN"] },
    ]
    logConfiguration = local.logs["app-api"]
  }])
}

resource "aws_ecs_task_definition" "inference" {
  family                   = "${local.name}-inference"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = 1024
  memory                   = 2048
  execution_role_arn       = aws_iam_role.execution.arn
  task_role_arn            = aws_iam_role.task.arn
  runtime_platform {
    operating_system_family = "LINUX"
    cpu_architecture        = "X86_64"
  }
  container_definitions = jsonencode([{
    name         = "inference"
    image        = local.images.inference
    essential    = true
    portMappings = [{ containerPort = 8001, protocol = "tcp" }]
    environment = [
      { name = "MODEL_URI", value = "models:/threadline-recommender@champion" },
      { name = "MLFLOW_TRACKING_URI", value = local.mlflow_url },
      { name = "CACHE_TTL_SECONDS", value = "300" },
    ]
    secrets = [
      { name = "INFERENCE_ADMIN_TOKEN", valueFrom = local.secret_ref["INFERENCE_ADMIN_TOKEN"] },
    ]
    logConfiguration = local.logs["inference"]
  }])
}

resource "aws_ecs_task_definition" "mlflow" {
  family                   = "${local.name}-mlflow"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = 512
  memory                   = 1024
  execution_role_arn       = aws_iam_role.execution.arn
  task_role_arn            = aws_iam_role.task.arn
  container_definitions = jsonencode([{
    name         = "mlflow"
    image        = local.images.mlflow
    essential    = true
    portMappings = [{ containerPort = 5000, protocol = "tcp" }]
    environment = [
      { name = "ARTIFACTS_DESTINATION", value = "s3://${aws_s3_bucket.artifacts.bucket}/mlflow" },
    ]
    secrets = [
      { name = "BACKEND_STORE_URI", valueFrom = local.secret_ref["MLFLOW_BACKEND_URI"] },
    ]
    logConfiguration = local.logs["mlflow"]
  }])
}

resource "aws_ecs_task_definition" "trainer" {
  family                   = "${local.name}-trainer"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = 4096
  memory                   = 16384
  execution_role_arn       = aws_iam_role.execution.arn
  task_role_arn            = aws_iam_role.task.arn
  ephemeral_storage {
    size_in_gib = 50
  }
  container_definitions = jsonencode([{
    name      = "trainer"
    image     = local.images.trainer
    essential = true
    environment = [
      { name = "MLFLOW_TRACKING_URI", value = local.mlflow_url },
      { name = "DATA_S3_URI", value = var.raw_data_s3_prefix },
      { name = "PROCESSED_S3_URI", value = "s3://${aws_s3_bucket.artifacts.bucket}/processed" },
      { name = "INFERENCE_RELOAD_URL", value = "${local.inference_url}/admin/reload" },
    ]
    secrets = [
      { name = "INFERENCE_ADMIN_TOKEN", valueFrom = local.secret_ref["INFERENCE_ADMIN_TOKEN"] },
    ]
    logConfiguration = local.logs["trainer"]
  }])
}

# ---------------------------------------------------------------- services
locals {
  network = {
    subnets          = aws_subnet.public[*].id
    security_groups  = [aws_security_group.services.id]
    assign_public_ip = true
  }
}

resource "aws_ecs_service" "mlflow" {
  name            = "mlflow"
  cluster         = aws_ecs_cluster.main.id
  task_definition = aws_ecs_task_definition.mlflow.arn
  desired_count   = 1
  launch_type     = "FARGATE"
  network_configuration {
    subnets          = local.network.subnets
    security_groups  = local.network.security_groups
    assign_public_ip = local.network.assign_public_ip
  }
  service_registries {
    registry_arn = aws_service_discovery_service.svc["mlflow"].arn
  }
}

resource "aws_ecs_service" "inference" {
  name            = "inference"
  cluster         = aws_ecs_cluster.main.id
  task_definition = aws_ecs_task_definition.inference.arn
  desired_count   = 1
  launch_type     = "FARGATE"
  network_configuration {
    subnets          = local.network.subnets
    security_groups  = local.network.security_groups
    assign_public_ip = local.network.assign_public_ip
  }
  service_registries {
    registry_arn = aws_service_discovery_service.svc["inference"].arn
  }
  deployment_circuit_breaker {
    enable   = true
    rollback = true
  }
  lifecycle {
    ignore_changes = [desired_count] # owned by autoscaling
  }
}

resource "aws_ecs_service" "app_api" {
  name            = "app-api"
  cluster         = aws_ecs_cluster.main.id
  task_definition = aws_ecs_task_definition.app_api.arn
  desired_count   = 1
  launch_type     = "FARGATE"
  network_configuration {
    subnets          = local.network.subnets
    security_groups  = local.network.security_groups
    assign_public_ip = local.network.assign_public_ip
  }
  load_balancer {
    target_group_arn = aws_lb_target_group.app_api.arn
    container_name   = "app-api"
    container_port   = 8000
  }
  health_check_grace_period_seconds = 90
  deployment_circuit_breaker {
    enable   = true
    rollback = true
  }
  depends_on = [aws_lb_listener.http]
}

# ---------------------------------------------------------------- autoscaling (inference)
resource "aws_appautoscaling_target" "inference" {
  service_namespace  = "ecs"
  resource_id        = "service/${aws_ecs_cluster.main.name}/${aws_ecs_service.inference.name}"
  scalable_dimension = "ecs:service:DesiredCount"
  min_capacity       = 1
  max_capacity       = var.inference_max_tasks
}

resource "aws_appautoscaling_policy" "inference_cpu" {
  name               = "${local.name}-inference-cpu"
  policy_type        = "TargetTrackingScaling"
  service_namespace  = aws_appautoscaling_target.inference.service_namespace
  resource_id        = aws_appautoscaling_target.inference.resource_id
  scalable_dimension = aws_appautoscaling_target.inference.scalable_dimension
  target_tracking_scaling_policy_configuration {
    target_value       = 60
    scale_in_cooldown  = 120
    scale_out_cooldown = 60
    predefined_metric_specification {
      predefined_metric_type = "ECSServiceAverageCPUUtilization"
    }
  }
}

# ---------------------------------------------------------------- weekly retraining
resource "aws_scheduler_schedule" "retrain" {
  name                = "${local.name}-weekly-retrain"
  schedule_expression = var.training_schedule
  flexible_time_window {
    mode = "OFF"
  }
  target {
    arn      = aws_ecs_cluster.main.arn
    role_arn = aws_iam_role.scheduler.arn
    ecs_parameters {
      task_definition_arn = aws_ecs_task_definition.trainer.arn
      launch_type         = "FARGATE"
      network_configuration {
        subnets          = local.network.subnets
        security_groups  = local.network.security_groups
        assign_public_ip = true
      }
    }
  }
}

# ---------------------------------------------------------------- alarms
resource "aws_cloudwatch_metric_alarm" "alb_5xx" {
  alarm_name          = "${local.name}-api-5xx"
  namespace           = "AWS/ApplicationELB"
  metric_name         = "HTTPCode_Target_5XX_Count"
  dimensions          = { LoadBalancer = aws_lb.main.arn_suffix }
  statistic           = "Sum"
  period              = 300
  evaluation_periods  = 1
  threshold           = 20
  comparison_operator = "GreaterThanThreshold"
  treat_missing_data  = "notBreaching"
  alarm_actions       = [aws_sns_topic.alerts.arn]
}

resource "aws_cloudwatch_metric_alarm" "api_latency" {
  alarm_name          = "${local.name}-api-p95-latency"
  namespace           = "AWS/ApplicationELB"
  metric_name         = "TargetResponseTime"
  dimensions          = { LoadBalancer = aws_lb.main.arn_suffix }
  extended_statistic  = "p95"
  period              = 300
  evaluation_periods  = 2
  threshold           = 0.5
  comparison_operator = "GreaterThanThreshold"
  treat_missing_data  = "notBreaching"
  alarm_actions       = [aws_sns_topic.alerts.arn]
}

resource "aws_sns_topic" "alerts" {
  name = "${local.name}-alerts"
}

resource "aws_sns_topic_subscription" "alerts_email" {
  topic_arn = aws_sns_topic.alerts.arn
  protocol  = "email"
  endpoint  = var.alert_email
}
