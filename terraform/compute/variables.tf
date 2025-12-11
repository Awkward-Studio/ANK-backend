variable "project_name" { type = string }
variable "environment" { type = string }
variable "aws_region" { type = string }
variable "vpc_id" { type = string }
variable "public_subnet_ids" { type = list(string) }
variable "ecs_security_group_id" { type = string }
variable "target_group_arn" { type = string }
variable "db_endpoint" { type = string }
variable "db_name" { type = string }
variable "db_username" { type = string sensitive = true }
variable "db_password" { type = string sensitive = true }
variable "ecs_task_cpu" { type = string }
variable "ecs_task_memory" { type = string }
variable "ecs_desired_count" { type = number }
variable "container_port" { type = number }
variable "docker_image" { type = string }
variable "additional_secrets" { type = map(string) default = {} }
