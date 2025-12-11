# =====================================
# Input Variables
# =====================================
# Define all configurable parameters for the infrastructure.
# Override these values in terraform.tfvars

# =====================================
# General Configuration
# =====================================

variable "project_name" {
  description = "Project name used for resource naming"
  type        = string
  default     = "ank"
}

variable "environment" {
  description =  "Environment (dev, staging, prod)"
  type        = string
  default     = "prod"
}

variable "aws_region" {
  description = "AWS Region"
  type        = string
  default     = "ap-south-1"
}

variable "availability_zone" {
  description = "Single availability zone for cost optimization"
  type        = string
  default     = "ap-south-1a"
}

# =====================================
# Networking Variables
# =====================================

variable "vpc_cidr" {
  description = "CIDR block for VPC"
  type        = string
  default     = "10.0.0.0/16"
}

variable "public_subnet_cidr" {
  description = "CIDR block for public subnet"
  type        = string
  default     = "10.0.1.0/24"
}

variable "private_subnet_cidr" {
  description = "CIDR block for private subnet (RDS only)"
  type        = string
  default     = "10.0.2.0/24"
}

# =====================================
# Database Variables
# =====================================

variable "db_name" {
  description = "Database name"
  type        = string
  default     = "ankdb"
}

variable "db_username" {
  description = "Database master username"
  type        = string
  sensitive   = true
}

variable "db_password" {
  description = "Database master password"
  type        = string
  sensitive   = true
}

variable "db_instance_class" {
  description = "RDS instance class"
  type        = string
  default     = "db.t3.micro"  # Free tier eligible
}

variable "db_allocated_storage" {
  description = "Allocated storage in GB"
  type        = number
  default     = 20
}

variable "db_engine_version" {
  description = "PostgreSQL version"
  type        = string
  default     = "15.4"
}

# =====================================
# ECS Variables
# =====================================

variable "ecs_task_cpu" {
  description = "Fargate task CPU units"
  type        = string
  default     = "256"  # 0.25 vCPU
}

variable "ecs_task_memory" {
  description = "Fargate task memory in MB"
  type        = string
  default     = "512"  # 0.5 GB
}

variable "ecs_desired_count" {
  description = "Desired number of ECS tasks"
  type        = number
  default     = 1
}

variable "container_port" {
  description = "Container port for the application"
  type        = number
  default     = 8000
}

variable "docker_image" {
  description = "Docker image URL (ECR image)"
  type        = string
  default     = ""  # Will be set after initial ECR push
}

variable "ecr_repository_name" {
  description = "ECR repository name"
  type        = string
  default     = "ank-backend"
}

# =====================================
# Load Balancer Variables
# =====================================

variable "health_check_path" {
  description = "Health check path for target group"
  type        = string
  default     = "/health"  # Adjust based on your app
}

variable "certificate_arn" {
  description = "ACM certificate ARN for HTTPS (optional)"
  type        = string
  default     = ""  # Leave empty for HTTP only
}

# =====================================
# Secrets Variables
# =====================================

variable "additional_secrets" {
  description = "Additional application secrets"
  type        = map(string)
  sensitive   = true
  default     = {}
  # Example:
  # {
  #   "DJANGO_SECRET_KEY" = "your-secret-key"
  #   "MANGO_RSVP_SEC" = "your-api-secret"
  # }
}

# =====================================
# Amplify Variables (Optional)
# =====================================

variable "amplify_repository_url" {
  description = "Git repository URL for Amplify"
  type        = string
  default     = ""
}

variable "amplify_branch_name" {
  description = "Git branch name for Amplify"
  type        = string
  default     = "main"
}

variable "amplify_build_spec" {
  description = "Amplify build specification"
  type        = string
  default     = ""
}
