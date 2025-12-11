# AWS Infrastructure Discovery - Manual Commands
# Copy and run these commands one by one in PowerShell
# The output will be saved to files for analysis

# Create output directory
$outputDir = "aws-infrastructure-manual-$(Get-Date -Format 'yyyy-MM-dd_HHmmss')"
New-Item -ItemType Directory -Force -Path $outputDir

Write-Host "Collecting AWS infrastructure data..." -ForegroundColor Cyan
Write-Host "Output folder: $outputDir" -ForegroundColor Green
Write-Host ""

# ECS
Write-Host "Collecting ECS data..." -ForegroundColor Yellow
aws ecs list-clusters | Out-File "$outputDir\ecs-clusters.json"
aws ecs list-task-definitions | Out-File "$outputDir\ecs-task-definitions.json"

# Get ECS cluster details (replace CLUSTER_ARN with actual ARN from above)
$clusters = (aws ecs list-clusters | ConvertFrom-Json).clusterArns
foreach ($cluster in $clusters) {
    $name = $cluster.Split('/')[-1]
    aws ecs describe-clusters --clusters $cluster | Out-File "$outputDir\ecs-cluster-$name.json"
    aws ecs list-services --cluster $cluster | Out-File "$outputDir\ecs-services-$name.json"
   $services = (aws ecs list-services --cluster $cluster | ConvertFrom-Json).serviceArns
    if ($services.Count -gt 0) {
        aws ecs describe-services --cluster $cluster --services $($services -join ' ') | Out-File "$outputDir\ecs-service-details-$name.json"
    }
}

# RDS
Write-Host "Collecting RDS data..." -ForegroundColor Yellow
aws rds describe-db-instances | Out-File "$outputDir\rds-instances.json"
aws rds describe-db-subnet-groups | Out-File "$outputDir\rds-subnet-groups.json"

# Load Balancers
Write-Host "Collecting Load Balancer data..." -ForegroundColor Yellow
aws elbv2 describe-load-balancers | Out-File "$outputDir\load-balancers.json"
aws elbv2 describe-target-groups | Out-File "$outputDir\target-groups.json"

$lbs = (aws elbv2 describe-load-balancers | ConvertFrom-Json).LoadBalancers
foreach ($lb in $lbs) {
    aws elbv2 describe-listeners --load-balancer-arn $lb.LoadBalancerArn | Out-File "$outputDir\listeners-$($lb.LoadBalancerName).json"
}

# Amplify
Write-Host "Collecting Amplify data..." -ForegroundColor Yellow
aws amplify list-apps | Out-File "$outputDir\amplify-apps.json"

# VPC & Networking
Write-Host "Collecting VPC and Networking data..." -ForegroundColor Yellow
aws ec2 describe-vpcs | Out-File "$outputDir\vpcs.json"
aws ec2 describe-subnets | Out-File "$outputDir\subnets.json"
aws ec2 describe-security-groups | Out-File "$outputDir\security-groups.json"
aws ec2 describe-internet-gateways | Out-File "$outputDir\internet-gateways.json"
aws ec2 describe-nat-gateways | Out-File "$outputDir\nat-gateways.json"
aws ec2 describe-route-tables | Out-File "$outputDir\route-tables.json"

# S3
Write-Host "Collecting S3 data..." -ForegroundColor Yellow
aws s3api list-buckets | Out-File "$outputDir\s3-buckets.json"

# ECR (Docker images)
Write-Host "Collecting ECR data..." -ForegroundColor Yellow
aws ecr describe-repositories | Out-File "$outputDir\ecr-repositories.json"

# IAM
Write-Host "Collecting IAM data..." -ForegroundColor Yellow
aws iam list-roles | Out-File "$outputDir\iam-roles.json"

# Secrets Manager
Write-Host "Collecting Secrets Manager data..." -ForegroundColor Yellow
aws secretsmanager list-secrets | Out-File "$outputDir\secrets-manager.json"

# CloudWatch Logs
Write-Host "Collecting CloudWatch data..." -ForegroundColor Yellow
aws logs describe-log-groups | Out-File "$outputDir\cloudwatch-log-groups.json"

Write-Host ""
Write-Host "Done! All data saved to: $outputDir" -ForegroundColor Green
Write-Host ""
Write-Host "Please zip this folder and share the files with me." -ForegroundColor Cyan
