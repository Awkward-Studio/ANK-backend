# AWS Infrastructure Discovery Script - Simple Version
# Scan AWS resources and save to timestamped folder

$timestamp = Get-Date -Format "yyyy-MM-dd_HHmmss"
$outputDir = "aws-infrastructure-audit-$timestamp"
New-Item -ItemType Directory -Force -Path $outputDir | Out-Null

Write-Host "Starting AWS Infrastructure Discovery..." -ForegroundColor Cyan
Write-Host "Output Directory: $outputDir" -ForegroundColor Green
Write-Host ""

# Function to run AWS CLI and save output
function Get-AWSResource {
    param([string]$Name, [string]$Cmd, [string]$File)
    Write-Host "Discovering $Name..." -ForegroundColor Yellow
    try {
        aws $Cmd --output json 2>&1 | Out-File -FilePath "$outputDir\$File" -Encoding UTF8
        Write-Host "  Saved to $File" -ForegroundColor Green
    } catch {
        "Error: $_" | Out-File -FilePath "$outputDir\$File" -Encoding UTF8
    }
}

# Get region
$region = aws configure get region
"Region: $region" | Out-File -FilePath "$outputDir\aws-region.txt" -Encoding UTF8

# ECS
Write-Host "`n=== COMPUTE & CONTAINERS ===" -ForegroundColor Cyan
Get-AWSResource "ECS Clusters" "ecs list-clusters" "ecs-clusters.json"
Get-AWSResource "ECS Task Definitions" "ecs list-task-definitions" "ecs-task-definitions.json"
Get-AWSResource "EC2 Instances" "ec2 describe-instances" "ec2-instances.json"

# Get cluster details
$clusters = aws ecs list-clusters --output json | ConvertFrom-Json
foreach ($clusterArn in $clusters.clusterArns) {
    $clusterName = $clusterArn.Split('/')[-1]
    Get-AWSResource "ECS Cluster $clusterName" "ecs describe-clusters --clusters $clusterArn" "ecs-cluster-$clusterName.json"
    Get-AWSResource "ECS Services $clusterName" "ecs list-services --cluster $clusterArn" "ecs-services-$clusterName.json"
    
    $services = aws ecs list-services --cluster $clusterArn --output json | ConvertFrom-Json
    if ($services.serviceArns.Count -gt 0) {
        $serviceArns = $services.serviceArns -join " "
        Get-AWSResource "ECS Service Details $clusterName" "ecs describe-services --cluster $clusterArn --services $serviceArns" "ecs-service-details-$clusterName.json"
    }
    
    Get-AWSResource "ECS Tasks $clusterName" "ecs list-tasks --cluster $clusterArn" "ecs-tasks-$clusterName.json"
}

# Networking
Write-Host "`n=== NETWORKING ===" -ForegroundColor Cyan
Get-AWSResource "VPCs" "ec2 describe-vpcs" "vpcs.json"
Get-AWSResource "Subnets" "ec2 describe-subnets" "subnets.json"
Get-AWSResource "Security Groups" "ec2 describe-security-groups" "security-groups.json"
Get-AWSResource "Internet Gateways" "ec2 describe-internet-gateways" "internet-gateways.json"
Get-AWSResource "NAT Gateways" "ec2 describe-nat-gateways" "nat-gateways.json"
Get-AWSResource "Route Tables" "ec2 describe-route-tables" "route-tables.json"
Get-AWSResource "Load Balancers" "elbv2 describe-load-balancers" "load-balancers.json"
Get-AWSResource "Target Groups" "elbv2 describe-target-groups" "target-groups.json"
Get-AWSResource "Elastic IPs" "ec2 describe-addresses" "elastic-ips.json"

# Get ALB listeners
$lbs = aws elbv2 describe-load-balancers --output json | ConvertFrom-Json
foreach ($lb in $lbs.LoadBalancers) {
    $lbName = $lb.LoadBalancerName
    $lbArn = $lb.LoadBalancerArn
    Get-AWSResource "Listeners $lbName" "elbv2 describe-listeners --load-balancer-arn $lbArn" "listeners-$lbName.json"
}

# Databases
Write-Host "`n=== DATABASES ===" -ForegroundColor Cyan
Get-AWSResource "RDS Instances" "rds describe-db-instances" "rds-instances.json"
Get-AWSResource "RDS Snapshots" "rds describe-db-snapshots" "rds-snapshots.json"
Get-AWSResource "RDS Subnet Groups" "rds describe-db-subnet-groups" "rds-subnet-groups.json"
Get-AWSResource "RDS Parameter Groups" "rds describe-db-parameter-groups" "rds-parameter-groups.json"

# Storage
Write-Host "`n=== STORAGE ===" -ForegroundColor Cyan
Get-AWSResource "S3 Buckets" "s3api list-buckets" "s3-buckets.json"
Get-AWSResource "EBS Volumes" "ec2 describe-volumes" "ebs-volumes.json"

# Amplify
Write-Host "`n=== AMPLIFY ===" -ForegroundColor Cyan
Get-AWSResource "Amplify Apps" "amplify list-apps" "amplify-apps.json"

$amplifyApps = aws amplify list-apps --output json 2>$null | ConvertFrom-Json
foreach ($app in $amplifyApps.apps) {
    $appId = $app.appId
    $appName = $app.name
    Get-AWSResource "Amplify App $appName" "amplify get-app --app-id $appId" "amplify-app-$appName.json"
    Get-AWSResource "Amplify Branches $appName" "amplify list-branches --app-id $appId" "amplify-branches-$appName.json"
}

# IAM
Write-Host "`n=== IAM & SECURITY ===" -ForegroundColor Cyan
Get-AWSResource "IAM Roles" "iam list-roles" "iam-roles.json"
Get-AWSResource "IAM Policies" "iam list-policies --scope Local" "iam-policies-custom.json"

# Monitoring
Write-Host "`n=== LOGS & MONITORING ===" -ForegroundColor Cyan
Get-AWSResource "CloudWatch Log Groups" "logs describe-log-groups" "cloudwatch-log-groups.json"
Get-AWSResource "CloudWatch Alarms" "cloudwatch describe-alarms" "cloudwatch-alarms.json"

# Other Services
Write-Host "`n=== OTHER SERVICES ===" -ForegroundColor Cyan
Get-AWSResource "Secrets Manager" "secretsmanager list-secrets" "secrets-manager.json"
Get-AWSResource "ECR Repositories" "ecr describe-repositories" "ecr-repositories.json"
Get-AWSResource "SNS Topics" "sns list-topics" "sns-topics.json"
Get-AWSResource "SQS Queues" "sqs list-queues" "sqs-queues.json"
Get-AWSResource "Lambda Functions" "lambda list-functions" "lambda-functions.json"
Get-AWSResource "Route53 Zones" "route53 list-hosted-zones" "route53-zones.json"
Get-AWSResource "ACM Certificates" "acm list-certificates" "acm-certificates.json"

Write-Host "`n=== DISCOVERY COMPLETE ===" -ForegroundColor Green
Write-Host "All data saved to: $outputDir" -ForegroundColor Cyan
Write-Host ""
