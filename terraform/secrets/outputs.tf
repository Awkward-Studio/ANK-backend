output "secrets_arns" {
  value = merge(
    { database_url = aws_secretsmanager_secret.database_url.arn },
    { for k, v in aws_secretsmanager_secret.app_secrets : k => v.arn }
  )
}
