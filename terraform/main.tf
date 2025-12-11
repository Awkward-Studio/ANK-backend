# =====================================
# Main Terraform Configuration
# =====================================
# This is the root configuration file that orchestrates all modules
# for the ANK Backend infrastructure on AWS.
#
# Usage:
#   terraform init
#   terraform plan
#   terraform apply

terraform {
  required_version = ">= 1.0"
  
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }

  # Optional: Configure S3 backend for state storage
  # Uncomment and configure after creating S3 bucket
  # backend "s3" {
  #   bucket         = "ank-terraform-state"
  #   key            = "prod/terraform.tfstate"
  #   region         = "ap-south-1"
  #   encrypt        = true
  #   dynamodb_table = "terraform-locks"
  # }
}

# =====================================
# Provider Configuration
# =====================================

provider "aws" {
  region = var.aws_region

  default_tags {
    tags = {
      Project     = var.project_name
      Environment = var.environment
      ManagedBy   = "Terraform"
      CostCenter  = var.project_name
    }
  }
}

# =====================================
# Networking Module
# =====================================

module "networking" {
  source = "./networking"

  project_name = var.project_name
  environment  = var.environment
  aws_region   = var.aws_region
  
  vpc_cidr = var.vpc_cidr
  availability_zone = var.availability_zone
  
  public_subnet_cidr  = var.public_subnet_cidr
  private_subnet_cidr = var.private_subnet_cidr
}

# =====================================
# Database Module
# =====================================

module "database" {
  source = "./database"

  project_name = var.project_name
  environment  = var.environment
  
  vpc_id                = module.networking.vpc_id
  private_subnet_ids    = module.networking.private_subnet_ids
  db_security_group_id  = module.networking.rds_security_group_id
  
  db_name     = var.db_name
  db_username = var.db_username
  db_password = var.db_password
  
  db_instance_class   = var.db_instance_class
  db_allocated_storage = var.db_allocated_storage
  db_engine_version   = var.db_engine_version
}

# =====================================
# Load Balancer Module
# =====================================

module "loadbalancer" {
  source = "./loadbalancer"

  project_name = var.project_name
  environment  = var.environment
  
  vpc_id             = module.networking.vpc_id
  public_subnet_ids  = module.networking.public_subnet_ids
  alb_security_group_id = module.networking.alb_security_group_id
  
  health_check_path = var.health_check_path
  certificate_arn   = var.certificate_arn   # Optional for HTTPS
}

# =====================================
# Storage Module (ECR)
# =====================================

module "storage" {
  source = "./storage"

  project_name = var.project_name
  environment  = var.environment
  
  ecr_repository_name = var.ecr_repository_name
}

# =====================================
# Compute Module (ECS)
# =====================================

module "compute" {
  source = "./compute"

  project_name = var.project_name
  environment  = var.environment
  aws_region   = var.aws_region
  
  vpc_id              = module.networking.vpc_id
  public_subnet_ids   = module.networking.public_subnet_ids
  ecs_security_group_id = module.networking.ecs_security_group_id
  
  # Load Balancer
  target_group_arn = module.loadbalancer.target_group_arn
  
  # Database connection
  db_endpoint = module.database.db_endpoint
  db_name     = var.db_name
  db_username = var.db_username
  db_password = var.db_password
  
  # ECS Configuration
  ecs_task_cpu          = var.ecs_task_cpu
  ecs_task_memory       = var.ecs_task_memory
  ecs_desired_count     = var.ecs_desired_count
  container_port        = var.container_port
  docker_image          = var.docker_image
  
  # Secrets (optional)
  additional_secrets = var.additional_secrets
}

# =====================================
# Secrets Module
# =====================================

module "secrets" {
  source = "./secrets"

  project_name = var.project_name
  environment  = var.environment
  
  db_connection_string = "postgresql://${var.db_username}:${var.db_password}@${module.database.db_endpoint}/${var.db_name}"
  additional_secrets   = var.additional_secrets
}

# =====================================
# Amplify Module (Optional)
# =====================================

# Note: Amplify is typically configured via Console or Amplify CLI
# Uncomment if you want to manage via Terraform

# module "amplify" {
#   source = "./amplify"
#
#   project_name = var.project_name
#   environment  = var.environment
#   
#   repository_url = var.amplify_repository_url
#   branch_name    = var.amplify_branch_name
#   build_spec     = var.amplify_build_spec
# }
