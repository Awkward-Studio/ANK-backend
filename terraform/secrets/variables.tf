variable "project_name" { type = string }
variable "environment" { type = string }
variable "db_connection_string" { type = string sensitive = true }
variable "additional_secrets" { type = map(string) default = {} sensitive = true }
