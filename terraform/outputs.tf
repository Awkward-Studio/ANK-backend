# =====================================
# Output Values
# =====================================
# These values are displayed after terraform apply
# and can be used by other systems or for reference

# =====================================
# Networking Outputs
# =====================================

output "vpc_id" {
  description = "ID of the VPC"
  value       = module.networking.vpc_id
}

output "public_subnet_ids" {
  description = "IDs of public subnets"
  value       = module.networking.public_subnet_ids
}

output "private_subnet_ids" {
  description = "IDs of private subnets"
  value       = module.networking.private_subnet_ids
}

# =====================================
# Database Outputs
# =====================================

output "rds_endpoint" {
  description = "PostgreSQL RDS endpoint"
  value       = module.database.db_endpoint
}

output "rds_port" {
  description = "PostgreSQL RDS port"
  value       = module.database.db_port
}

output "database_connection_string" {
  description = "Database connection string (sensitive)"
  value       = "postgresql://${var.db_username}:${var.db_password}@${module.database.db_endpoint}/${var.db_name}"
  sensitive   = true
}

# =====================================
# Load Balancer Outputs
# =====================================

output "alb_dns_name" {
  description = "DNS name of the Application Load Balancer"
  value       = module.loadbalancer.alb_dns_name
}

output "alb_zone_id" {
  description = "Route53 Zone ID of the ALB"
  value       = module.loadbalancer.alb_zone_id
}

output "alb_url" {
  description = "Full URL to access the application"
  value       = "http://${module.loadbalancer.alb_dns_name}"
}

# =====================================
# ECS Outputs
# =====================================

output "ecs_cluster_name" {
  description = "Name of the ECS cluster"
  value       = module.compute.ecs_cluster_name
}

output "ecs_service_name" {
  description = "Name of the ECS service"
  value       = module.compute.ecs_service_name
}

output "ecs_task_definition_arn" {
  description = "ARN of the latest task definition"
  value       = module.compute.task_definition_arn
}

# =====================================
# ECR Outputs
# =====================================

output "ecr_repository_url" {
  description = "URL of the ECR repository"
  value       = module.storage.ecr_repository_url
}

output "docker_push_command" {
  description = "Command to push Docker image to ECR"
  value       = "aws ecr get-login-password --region ${var.aws_region} | docker login --username AWS --password-stdin ${module.storage.ecr_repository_url} && docker push ${module.storage.ecr_repository_url}:latest"
}

# =====================================
# Secrets Outputs
# =====================================

output "secrets_arns" {
  description = "ARNs of created secrets"
  value       = module.secrets.secrets_arns
  sensitive   = true
}

# =====================================
# Deployment Instructions
# =====================================

output "next_steps" {
  description = "Next steps after infrastructure creation"
  value = <<-EOT
  
  ========================================
  Infrastructure Created Successfully!
  ========================================
  
  Next Steps:
  
  1. Build and push your Docker image:
     cd <your-app-directory>
     docker buildx build --platform linux/amd64 -t ${module.storage.ecr_repository_url}:latest .
     aws ecr get-login-password --region ${var.aws_region} | docker login --username AWS --password-stdin ${module.storage.ecr_repository_url}
     docker push ${module.storage.ecr_repository_url}:latest
  
  2. Update ECS service to use the new image:
     terraform apply -var="docker_image=${module.storage.ecr_repository_url}:latest"
  
  3. Access your application:
     http://${module.loadbalancer.alb_dns_name}
  
  4. Configure your domain (optional):
     - Create Route53 A record pointing to ALB
     - Request ACM certificate for HTTPS
     - Update ALB listener with certificate
  
  5. Monitor your application:
     - CloudWatch Logs: /ecs/${var.project_name}-${var.environment}-service
     - ECS Console: Check service health
  
  ========================================
  EOT
}
