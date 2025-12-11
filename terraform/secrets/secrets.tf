# Database URL Secret
resource "aws_secretsmanager_secret" "database_url" {
  name = "${var.project_name}/${var.environment}/DATABASE_URL"
  description = "PostgreSQL database connection string"
}

resource "aws_secretsmanager_secret_version" "database_url" {
  secret_id     = aws_secretsmanager_secret.database_url.id
  secret_string = var.db_connection_string
}

# Additional application secrets
resource "aws_secretsmanager_secret" "app_secrets" {
  for_each = var.additional_secrets

  name        = "${var.project_name}/${var.environment}/${each.key}"
  description = "Application secret: ${each.key}"
}

resource "aws_secretsmanager_secret_version" "app_secrets" {
  for_each = var.additional_secrets

  secret_id     = aws_secretsmanager_secret.app_secrets[each.key].id
  secret_string = each.value
}
