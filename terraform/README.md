# AWS Infrastructure - Terraform Project

Complete Infrastructure as Code for ANK Backend on AWS

## 📋 Overview

This Terraform configuration creates a complete, cost-optimized AWS infrastructure for the ANK backend application:

- **VPC** with public/private subnets (Single-AZ)
- **RDS PostgreSQL** database (Single-AZ, 20GB)
- **ECS Fargate** cluster and service
- **Application Load Balancer** (ALB)
- **ECR** repository for Docker images
- **Secrets Manager** for sensitive configuration

**Estimated Monthly Cost**: ~$46-76

## 🚀 Quick Start

```powershell
# 1. Copy and edit variables
Copy-Item terraform.tfvars.example terraform.tfvars
notepad terraform.tfvars

# 2. Initialize Terraform
terraform init

# 3. Review plan
terraform plan

# 4. Deploy infrastructure
terraform apply

# 5. Build and push Docker image
# (see full guide for details)
```

## 📁 Project Structure

```
terraform/
├── main.tf                   # Main orchestration
├── variables.tf              # Input variables
├── outputs.tf                # Output values
├── terraform.tfvars.example  # Example configuration
├── networking/               # VPC, subnets, security groups
├── database/                 # RDS PostgreSQL
├── compute/                  # ECS cluster and service
├── loadbalancer/             # ALB and target groups
├── storage/                  # ECR repository
└── secrets/                  # Secrets Manager
```

## 📖 Documentation

- **[Terraform Rebuild Guide](file:///C:/Users/atiqa/.gemini/antigravity/brain/0e0f5ba4-d2ee-4da1-840c-3b3de87d3cff/terraform-rebuild-guide.md)** - Complete step-by-step instructions
- **[AWS Infrastructure Overview](file:/// C:/Users/atiqa/.gemini/antigravity/brain/0e0f5ba4-d2ee-4da1-840c-3b3de87d3cff/aws-infrastructure-overview.md)** - Architecture and resource details

## ⚙️ Configuration

Edit `terraform.tfvars` with your values:

```hcl
# Database (Required)
db_username = "admin"
db_password = "your-secure-password"

# Application (Required after first deploy)
docker_image = "<ECR_URL>:latest"

# Optional
health_check_path = "/health"
certificate_arn   = ""  # For HTTPS
```

## 💰 Cost Optimization

This configuration is optimized for minimal cost:

- ✅ Single-AZ deployment (no Multi-AZ)
- ✅ NO NAT Gateway (~$32/month savings)
- ✅ Small instance sizes (db.t3.micro, 0.25vCPU)
- ✅ ECS Fargate with minimal resources
- ✅ 7-day log retention

**Savings**: ~$40/month vs typical multi-AZ setup

## 🔐 Security

- RDS in private subnet (not publicly accessible)
- Least-privilege security groups
- Secrets in AWS Secrets Manager
- Encrypted RDS storage
- Container scanning enabled on ECR

## 📊 Outputs

After `terraform apply`:

```powershell
terraform output alb_url              # Your application URL
terraform output ecr_repository_url   # Docker push destination
terraform output rds_endpoint         # Database endpoint
```

## 🛠️ Common Commands

```powershell
terraform plan          # Preview changes
terraform apply         # Apply changes
terraform destroy       # Destroy all resources
terraform output        # Show all outputs
terraform fmt           # Format code
terraform validate      # Validate configuration
```

## ⚠️ Important Notes

1. **State File**: `terraform.tfstate` contains sensitive data
   - DO NOT commit to Git
   - Backup regularly
   - Consider using S3 backend for production

2. **Database Password**: Store securely, needed for recovery

3. **First Deploy**: Initially deploys without Docker image
   - Build and push to ECR first
   - Then update `docker_image` variable and reapply

## 📝 Next Steps After Deployment

1. Build and push Docker image to ECR
2. Update `docker_image` in `terraform.tfvars`
3. Run `terraform apply` to deploy container
4. Configure custom domain (optional)
5. Set up monitoring and alerts
6. Configure CI/CD pipeline

## 🆘 Troubleshooting

See [Terraform Rebuild Guide](file:///C:/Users/atiqa/.gemini/antigravity/brain/0e0f5ba4-d2ee-4da1-840c-3b3de87d3cff/terraform-rebuild-guide.md) for detailed troubleshooting steps.

Common issues:
- ECS tasks not starting → Check CloudWatch logs
- Health checks failing → Verify targetgroup health check path
- RDS connection issues → Check security groups

## 📚 Resources

- [Terraform AWS Provider](https://registry.terraform.io/providers/hashicorp/aws/)
- [AWS ECS Best Practices](https://docs.aws.amazon.com/AmazonECS/latest/bestpracticesguide/)
- [Terraform Best Practices](https://www.terraform.io/docs/cloud/guides/recommended-practices/)

---

**Version**: 1.0  
**Last Updated**: 2025-12-10  
**Terraform**: >= 1.0  
**AWS Provider**: ~> 5.0
