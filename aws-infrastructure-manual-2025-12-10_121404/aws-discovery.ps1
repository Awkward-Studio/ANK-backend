# AWS Infrastructure Discovery Script
# This script will scan your AWS account and collect information about all resources
# Make sure you have AWS CLI configured with proper credentials

$timestamp = Get-Date -Format "yyyy-MM-dd_HHmmss"
$outputDir = "aws-infrastructure-audit-$timestamp"
New-Item -ItemType Directory -Force -Path $outputDir | Out-Null

Write-Host "🔍 Starting AWS Infrastructure Discovery..." -ForegroundColor Cyan
Write-Host "📁 Output Directory: $outputDir" -ForegroundColor Green
Write-Host ""

# Function to run AWS CLI command and save output
function Invoke-AWSDiscovery {
    param(
        [string]$ServiceName,
        [string]$Command,
        [string]$FileName
    )
    
    Write-Host "🔎 Discovering $ServiceName..." -ForegroundColor Yellow
    try {
        $output = Invoke-Expression "aws $Command --output json 2>&1"
        $output | Out-File -FilePath "$outputDir\$FileName" -Encoding UTF8
        Write-Host "✅ $ServiceName data saved to $FileName" -ForegroundColor Green
    }
    catch {
        Write-Host "❌ Error discovering $ServiceName : $_" -ForegroundColor Red
        "Error: $_" | Out-File -FilePath "$outputDir\$FileName" -Encoding UTF8
    }
}

# Get current region
Write-Host "📍 Getting current AWS region..." -ForegroundColor Yellow
$region = aws configure get region
Write-Host "   Region: $region" -ForegroundColor White
"Region: $region" | Out-File -FilePath "$outputDir\aws-region.txt" -Encoding UTF8
Write-Host ""

# ====== COMPUTE & CONTAINERS ======
Write-Host "═════════════════════════════════════" -ForegroundColor Cyan
Write-Host "  COMPUTE & CONTAINERS" -ForegroundColor Cyan
Write-Host "═════════════════════════════════════" -ForegroundColor Cyan

# ECS Clusters
Invoke-AWSDiscovery -ServiceName "ECS Clusters" -Command "ecs list-clusters" -FileName "ecs-clusters.json"
$clusters = aws ecs list-clusters --output json | ConvertFrom-Json
if ($clusters.clusterArns.Count -gt 0) {
    foreach ($clusterArn in $clusters.clusterArns) {
        $clusterName = $clusterArn.Split('/')[-1]
        Invoke-AWSDiscovery -ServiceName "ECS Cluster Details: $clusterName" -Command "ecs describe-clusters --clusters $clusterArn" -FileName "ecs-cluster-$clusterName.json"
        Invoke-AWSDiscovery -ServiceName "ECS Services: $clusterName" -Command "ecs list-services --cluster $clusterArn" -FileName "ecs-services-$clusterName.json"
        
        # Get service details
        $services = aws ecs list-services --cluster $clusterArn --output json | ConvertFrom-Json
        if ($services.serviceArns.Count -gt 0) {
            $serviceArns = $services.serviceArns -join " "
            Invoke-AWSDiscovery -ServiceName "ECS Service Details: $clusterName" -Command "ecs describe-services --cluster $clusterArn --services $serviceArns" -FileName "ecs-service-details-$clusterName.json"
        }
        
        # Get task definitions
        Invoke-AWSDiscovery -ServiceName "ECS Tasks: $clusterName" -Command "ecs list-tasks --cluster $clusterArn" -FileName "ecs-tasks-$clusterName.json"
    }
}

# ECS Task Definitions
Invoke-AWSDiscovery -ServiceName "ECS Task Definitions" -Command "ecs list-task-definitions" -FileName "ecs-task-definitions.json"

# EC2 Instances (in case you have any)
Invoke-AWSDiscovery -ServiceName "EC2 Instances" -Command "ec2 describe-instances" -FileName "ec2-instances.json"

# ====== NETWORKING ======
Write-Host ""
Write-Host "═════════════════════════════════════" -ForegroundColor Cyan
Write-Host "  NETWORKING" -ForegroundColor Cyan
Write-Host "═════════════════════════════════════" -ForegroundColor Cyan

# VPCs
Invoke-AWSDiscovery -ServiceName "VPCs" -Command "ec2 describe-vpcs" -FileName "vpcs.json"

# Subnets
Invoke-AWSDiscovery -ServiceName "Subnets" -Command "ec2 describe-subnets" -FileName "subnets.json"

# Security Groups
Invoke-AWSDiscovery -ServiceName "Security Groups" -Command "ec2 describe-security-groups" -FileName "security-groups.json"

# Internet Gateways
Invoke-AWSDiscovery -ServiceName "Internet Gateways" -Command "ec2 describe-internet-gateways" -FileName "internet-gateways.json"

# NAT Gateways
Invoke-AWSDiscovery -ServiceName "NAT Gateways" -Command "ec2 describe-nat-gateways" -FileName "nat-gateways.json"

# Route Tables
Invoke-AWSDiscovery -ServiceName "Route Tables" -Command "ec2 describe-route-tables" -FileName "route-tables.json"

# Application Load Balancers
Invoke-AWSDiscovery -ServiceName "Load Balancers (ALB/NLB)" -Command "elbv2 describe-load-balancers" -FileName "load-balancers.json"

# Target Groups
Invoke-AWSDiscovery -ServiceName "Target Groups" -Command "elbv2 describe-target-groups" -FileName "target-groups.json"

# Listeners
$lbs = aws elbv2 describe-load-balancers --output json | ConvertFrom-Json
if ($lbs.LoadBalancers.Count -gt 0) {
    foreach ($lb in $lbs.LoadBalancers) {
        $lbArn = $lb.LoadBalancerArn
        $lbName = $lb.LoadBalancerName
        Invoke-AWSDiscovery -ServiceName "Listeners: $lbName" -Command "elbv2 describe-listeners --load-balancer-arn $lbArn" -FileName "listeners-$lbName.json"
    }
}

# Elastic IPs
Invoke-AWSDiscovery -ServiceName "Elastic IPs" -Command "ec2 describe-addresses" -FileName "elastic-ips.json"

# ====== DATABASES ======
Write-Host ""
Write-Host "═════════════════════════════════════" -ForegroundColor Cyan
Write-Host "  DATABASES" -ForegroundColor Cyan
Write-Host "═════════════════════════════════════" -ForegroundColor Cyan

# RDS Instances
Invoke-AWSDiscovery -ServiceName "RDS Instances" -Command "rds describe-db-instances" -FileName "rds-instances.json"

# RDS Snapshots
Invoke-AWSDiscovery -ServiceName "RDS Snapshots" -Command "rds describe-db-snapshots" -FileName "rds-snapshots.json"

# RDS Subnet Groups
Invoke-AWSDiscovery -ServiceName "RDS Subnet Groups" -Command "rds describe-db-subnet-groups" -FileName "rds-subnet-groups.json"

# RDS Parameter Groups
Invoke-AWSDiscovery -ServiceName "RDS Parameter Groups" -Command "rds describe-db-parameter-groups" -FileName "rds-parameter-groups.json"

# ====== STORAGE ======
Write-Host ""
Write-Host "═════════════════════════════════════" -ForegroundColor Cyan
Write-Host "  STORAGE" -ForegroundColor Cyan
Write-Host "═════════════════════════════════════" -ForegroundColor Cyan

# S3 Buckets
Invoke-AWSDiscovery -ServiceName "S3 Buckets" -Command "s3api list-buckets" -FileName "s3-buckets.json"

# EBS Volumes
Invoke-AWSDiscovery -ServiceName "EBS Volumes" -Command "ec2 describe-volumes" -FileName "ebs-volumes.json"

# ====== AMPLIFY ======
Write-Host ""
Write-Host "═════════════════════════════════════" -ForegroundColor Cyan
Write-Host "  AMPLIFY" -ForegroundColor Cyan
Write-Host "═════════════════════════════════════" -ForegroundColor Cyan

# Amplify Apps
Invoke-AWSDiscovery -ServiceName "Amplify Apps" -Command "amplify list-apps" -FileName "amplify-apps.json"

# Get details for each app
$amplifyApps = aws amplify list-apps --output json 2>$null | ConvertFrom-Json
if ($amplifyApps.apps.Count -gt 0) {
    foreach ($app in $amplifyApps.apps) {
        $appId = $app.appId
        $appName = $app.name
        Invoke-AWSDiscovery -ServiceName "Amplify App: $appName" -Command "amplify get-app --app-id $appId" -FileName "amplify-app-$appName.json"
        Invoke-AWSDiscovery -ServiceName "Amplify Branches: $appName" -Command "amplify list-branches --app-id $appId" -FileName "amplify-branches-$appName.json"
    }
}

# ====== IAM & SECURITY ======
Write-Host ""
Write-Host "═════════════════════════════════════" -ForegroundColor Cyan
Write-Host "  IAM & SECURITY" -ForegroundColor Cyan
Write-Host "═════════════════════════════════════" -ForegroundColor Cyan

# IAM Roles
Invoke-AWSDiscovery -ServiceName "IAM Roles" -Command "iam list-roles" -FileName "iam-roles.json"

# IAM Policies
Invoke-AWSDiscovery -ServiceName "IAM Policies" -Command "iam list-policies --scope Local" -FileName "iam-policies-custom.json"

# ====== LOGS & MONITORING ======
Write-Host ""
Write-Host "═════════════════════════════════════" -ForegroundColor Cyan
Write-Host "  LOGS & MONITORING" -ForegroundColor Cyan
Write-Host "═════════════════════════════════════" -ForegroundColor Cyan

# CloudWatch Log Groups
Invoke-AWSDiscovery -ServiceName "CloudWatch Log Groups" -Command "logs describe-log-groups" -FileName "cloudwatch-log-groups.json"

# CloudWatch Alarms
Invoke-AWSDiscovery -ServiceName "CloudWatch Alarms" -Command "cloudwatch describe-alarms" -FileName "cloudwatch-alarms.json"

# ====== OTHER SERVICES ======
Write-Host ""
Write-Host "═════════════════════════════════════" -ForegroundColor Cyan
Write-Host "  OTHER SERVICES" -ForegroundColor Cyan
Write-Host "═════════════════════════════════════" -ForegroundColor Cyan

# Secrets Manager
Invoke-AWSDiscovery -ServiceName "Secrets Manager" -Command "secretsmanager list-secrets" -FileName "secrets-manager.json"

# ECR Repositories (for Docker images)
Invoke-AWSDiscovery -ServiceName "ECR Repositories" -Command "ecr describe-repositories" -FileName "ecr-repositories.json"

# SNS Topics
Invoke-AWSDiscovery -ServiceName "SNS Topics" -Command "sns list-topics" -FileName "sns-topics.json"

# SQS Queues
Invoke-AWSDiscovery -ServiceName "SQS Queues" -Command "sqs list-queues" -FileName "sqs-queues.json"

# Lambda Functions
Invoke-AWSDiscovery -ServiceName "Lambda Functions" -Command "lambda list-functions" -FileName "lambda-functions.json"

# Route53 Hosted Zones
Invoke-AWSDiscovery -ServiceName "Route53 Hosted Zones" -Command "route53 list-hosted-zones" -FileName "route53-zones.json"

# ACM Certificates
Invoke-AWSDiscovery -ServiceName "ACM Certificates" -Command "acm list-certificates" -FileName "acm-certificates.json"

Write-Host ""
Write-Host "═════════════════════════════════════" -ForegroundColor Green
Write-Host "  ✅ DISCOVERY COMPLETE!" -ForegroundColor Green
Write-Host "═════════════════════════════════════" -ForegroundColor Green
Write-Host ""
Write-Host "📦 All discovery data saved to: $outputDir" -ForegroundColor Cyan
Write-Host "📝 Next steps:" -ForegroundColor Yellow
Write-Host "   1. Review the collected data" -ForegroundColor White
Write-Host "   2. Share the folder with me for analysis" -ForegroundColor White
Write-Host "   3. I'll identify redundancies and create documentation" -ForegroundColor White
Write-Host ""
