# Quick Analysis Script
# Run this after aws-discovery.ps1 to get a summary

Write-Host "🔍 AWS Infrastructure Quick Summary" -ForegroundColor Cyan
Write-Host ""

# Find the most recent audit directory
$latestDir = Get-ChildItem -Directory -Filter "aws-infrastructure-audit-*" | Sort-Object Name -Descending | Select-Object -First 1

if (-not $latestDir) {
    Write-Host "❌ No audit directory found. Please run aws-discovery.ps1 first." -ForegroundColor Red
    exit
}

Write-Host "📁 Reading from: $($latestDir.Name)" -ForegroundColor Green
Write-Host ""

# Helper function to count items in JSON
function Get-ResourceCount {
    param([string]$FilePath, [string]$JsonPath)
    
    if (Test-Path "$($latestDir.FullName)\$FilePath") {
        try {
            $content = Get-Content "$($latestDir.FullName)\$FilePath" -Raw | ConvertFrom-Json
            $items = Invoke-Expression "`$content$JsonPath"
            if ($items -is [Array]) {
                return $items.Count
            } elseif ($items) {
                return 1
            }
        } catch {
            return 0
        }
    }
    return 0
}

# ECS Summary
Write-Host "═══ ECS (Elastic Container Service) ═══" -ForegroundColor Yellow
$clusterCount = Get-ResourceCount -FilePath "ecs-clusters.json" -JsonPath ".clusterArns"
Write-Host "  Clusters: $clusterCount"

# RDS Summary
Write-Host ""
Write-Host "═══ RDS (Relational Database) ═══" -ForegroundColor Yellow
$rdsCount = Get-ResourceCount -FilePath "rds-instances.json" -JsonPath ".DBInstances"
Write-Host "  DB Instances: $rdsCount"
if (Test-Path "$($latestDir.FullName)\rds-instances.json") {
    $rds = Get-Content "$($latestDir.FullName)\rds-instances.json" -Raw | ConvertFrom-Json
    foreach ($db in $rds.DBInstances) {
        Write-Host "    - $($db.DBInstanceIdentifier) ($($db.Engine) $($db.EngineVersion)) - $($db.DBInstanceStatus)" -ForegroundColor Gray
    }
}

# ALB Summary
Write-Host ""
Write-Host "═══ Load Balancers ═══" -ForegroundColor Yellow
$lbCount = Get-ResourceCount -FilePath "load-balancers.json" -JsonPath ".LoadBalancers"
Write-Host "  Load Balancers: $lbCount"
if (Test-Path "$($latestDir.FullName)\load-balancers.json") {
    $lbs = Get-Content "$($latestDir.FullName)\load-balancers.json" -Raw | ConvertFrom-Json
    foreach ($lb in $lbs.LoadBalancers) {
        Write-Host "    - $($lb.LoadBalancerName) ($($lb.Type)) - $($lb.State.Code)" -ForegroundColor Gray
    }
}

# Amplify Summary
Write-Host ""
Write-Host "═══ Amplify ═══" -ForegroundColor Yellow
$amplifyCount = Get-ResourceCount -FilePath "amplify-apps.json" -JsonPath ".apps"
Write-Host "  Apps: $amplifyCount"
if (Test-Path "$($latestDir.FullName)\amplify-apps.json") {
    $apps = Get-Content "$($latestDir.FullName)\amplify-apps.json" -Raw | ConvertFrom-Json
    foreach ($app in $apps.apps) {
        Write-Host "    - $($app.name) - $($app.defaultDomain)" -ForegroundColor Gray
    }
}

# VPC Summary
Write-Host ""
Write-Host "═══ Networking ═══" -ForegroundColor Yellow
$vpcCount = Get-ResourceCount -FilePath "vpcs.json" -JsonPath ".Vpcs"
$subnetCount = Get-ResourceCount -FilePath "subnets.json" -JsonPath ".Subnets"
$sgCount = Get-ResourceCount -FilePath "security-groups.json" -JsonPath ".SecurityGroups"
Write-Host "  VPCs: $vpcCount"
Write-Host "  Subnets: $subnetCount"
Write-Host "  Security Groups: $sgCount"

# S3 Summary
Write-Host ""
Write-Host "═══ Storage ═══" -ForegroundColor Yellow
$s3Count = Get-ResourceCount -FilePath "s3-buckets.json" -JsonPath ".Buckets"
$ebsCount = Get-ResourceCount -FilePath "ebs-volumes.json" -JsonPath ".Volumes"
Write-Host "  S3 Buckets: $s3Count"
Write-Host "  EBS Volumes: $ebsCount"

# Other Services
Write-Host ""
Write-Host "═══ Other Services ═══" -ForegroundColor Yellow
$lambdaCount = Get-ResourceCount -FilePath "lambda-functions.json" -JsonPath ".Functions"
$secretsCount = Get-ResourceCount -FilePath "secrets-manager.json" -JsonPath ".SecretList"
$ecrCount = Get-ResourceCount -FilePath "ecr-repositories.json" -JsonPath ".repositories"
Write-Host "  Lambda Functions: $lambdaCount"
Write-Host "  Secrets: $secretsCount"
Write-Host "  ECR Repositories: $ecrCount"

Write-Host ""
Write-Host "═════════════════════════════════════" -ForegroundColor Green
Write-Host "✅ Summary complete!" -ForegroundColor Green
Write-Host ""
Write-Host "📝 Next: Share the '$($latestDir.Name)' folder contents with me" -ForegroundColor Cyan
Write-Host "   for detailed analysis and Terraform configuration" -ForegroundColor Cyan
