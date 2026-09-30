output "storefront_url" {
  value = "https://${aws_cloudfront_distribution.storefront.domain_name}"
}

output "ops_console_url" {
  value = "https://${aws_cloudfront_distribution.ops.domain_name}"
}

output "ecr_repositories" {
  value = { for k, r in aws_ecr_repository.repo : k => r.repository_url }
}

output "site_buckets" {
  value = { for k, b in aws_s3_bucket.site : k => b.bucket }
}

output "cloudfront_ids" {
  value = { storefront = aws_cloudfront_distribution.storefront.id, ops = aws_cloudfront_distribution.ops.id }
}

output "artifacts_bucket" {
  value = aws_s3_bucket.artifacts.bucket
}

output "ecs_cluster" {
  value = aws_ecs_cluster.main.name
}

output "run_training_command" {
  description = "Start a training run now instead of waiting for the schedule"
  value = join(" ", [
    "aws ecs run-task --cluster ${aws_ecs_cluster.main.name} --launch-type FARGATE",
    "--task-definition ${aws_ecs_task_definition.trainer.family}",
    "--network-configuration 'awsvpcConfiguration={subnets=[${join(",", aws_subnet.public[*].id)}],securityGroups=[${aws_security_group.services.id}],assignPublicIp=ENABLED}'",
  ])
}

output "ops_token_parameter" {
  description = "Read the ops console token with: aws ssm get-parameter --with-decryption --name <this>"
  value       = aws_ssm_parameter.secret["OPS_TOKEN"].name
}
