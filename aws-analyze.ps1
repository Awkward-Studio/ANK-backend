# Infrastructure Analysis Script
# Analyzes the collected AWS data and creates a summary

$dir = "aws-infrastructure-manual-2025-12-10_121404"

Write-Host "#" -ForegroundColor Cyan
Write-Host "# AWS Infrastructure Summary" -ForegroundColor Cyan
Write-Host "#" -ForegroundColor Cyan
Write-Host ""

# ECS
Write-Host "=" -Repeat 50 -ForegroundColor Yellow
Write-Host "ECS (Elastic Container Service)" -ForegroundColor Yellow
Write-Host "=" -Repeat 50 -ForegroundColor Yellow

$ecsClust = Get-Content "$dir\ecs-clusters.json" -Encoding UTF8 | ConvertFrom-Json
Write-Host "Clusters: $($ecsClust.clusterArns.Count)"
foreach ($clusterArn in $ecsClust.clusterArns) {
    $name = $clusterArn.Split('/')[-1]
    Write-Host "  - $name"
    
    $svcDetails = Get-Content "$dir\ecs-service-details-$name.json" -Encoding UTF8 | ConvertFrom-Json
    foreach ($svc in $svcDetails.services) {
        Write-Host "    Service: $($svc.serviceName)"
        Write-Host "      Desired: $($svc.desiredCount) | Running: $($svc.runningCount)"
        Write-Host "      Task Def: $($svc.taskDefinition.Split('/')[-1])"
        Write-Host "      Launch Type: $($svc.launchType)"
    }
}

$taskDefs = Get-Content "$dir\ecs-task-definitions.json" -Encoding UTF8 | ConvertFrom-Json
Write-Host "`nTask Definitions: $($taskDefs.taskDefinitionArns.Count)"

# RDS
Write-Host "`n" + ("=" * 50) -ForegroundColor Yellow
Write-Host "RDS (Databases)" -ForegroundColor Yellow
Write-Host "=" -Repeat 50 -ForegroundColor Yellow

$rds = Get-Content "$dir\rds-instances.json" -Encoding UTF8 | ConvertFrom-Json
Write-Host "DB Instances: $($rds.DBInstances.Count)"
foreach ($db in $rds.DBInstances) {
    Write-Host "  - $($db.DBInstanceIdentifier)"
    Write-Host "    Engine: $($db.Engine) $($db.EngineVersion)"
    Write-Host "    Class: $($db.DBInstanceClass)"
    Write-Host "    Status: $($db.DBInstanceStatus)"
    Write-Host "    Storage: $($db.AllocatedStorage) GB"
    Write-Host "    Multi-AZ: $($db.MultiAZ)"
}

# ALB
Write-Host "`n" + ("=" * 50) -ForegroundColor Yellow
Write-Host "Load Balancers" -ForegroundColor Yellow
Write-Host "=" -Repeat 50 -ForegroundColor Yellow

$lbs = Get-Content "$dir\load-balancers.json" -Encoding UTF8 | ConvertFrom-Json
Write-Host "Load Balancers: $($lbs.LoadBalancers.Count)"
foreach ($lb in $lbs.LoadBalancers) {
    Write-Host "  - $($lb.LoadBalancerName)"
    Write-Host "    Type: $($lb.Type)"
    Write-Host "    Scheme: $($lb.Scheme)"
    Write-Host "    DNS: $($lb.DNSName)"
    Write-Host "    State: $($lb.State.Code)"
}

$tgs = Get-Content "$dir\target-groups.json" -Encoding UTF8 | ConvertFrom-Json
Write-Host "`nTarget Groups: $($tgs.TargetGroups.Count)"
foreach ($tg in $tgs.TargetGroups) {
    Write-Host "  - $($tg.TargetGroupName)"
    Write-Host "    Protocol: $($tg.Protocol):$($tg.Port)"
    Write-Host "    Health Check: $($tg.HealthCheckPath)"
}

# Amplify
Write-Host "`n" + ("=" * 50) -ForegroundColor Yellow
Write-Host "Amplify" -ForegroundColor Yellow
Write-Host "=" -Repeat 50 -ForegroundColor Yellow

$amplify = Get-Content "$dir\amplify-apps.json" -Encoding UTF8 | ConvertFrom-Json
Write-Host "Apps: $($amplify.apps.Count)"
foreach ($app in $amplify.apps) {
    Write-Host "  - $($app.name)"
    Write-Host "    Domain: $($app.defaultDomain)"
    Write-Host "    Platform: $($app.platform)"
}

# VPC
Write-Host "`n" + ("=" * 50) -ForegroundColor Yellow
Write-Host "Networking" -ForegroundColor Yellow
Write-Host "=" -Repeat 50 -ForegroundColor Yellow

$vpcs = Get-Content "$dir\vpcs.json" -Encoding UTF8 | ConvertFrom-Json
Write-Host "VPCs: $($vpcs.Vpcs.Count)"
foreach ($vpc in $vpcs.Vpcs) {
    Write-Host "  - $($vpc.VpcId) (CIDR: $($vpc.CidrBlock))"
}

$subnets = Get-Content "$dir\subnets.json" -Encoding UTF8 | ConvertFrom-Json
Write-Host "`nSubnets: $($subnets.Subnets.Count)"

$sgs = Get-Content "$dir\security-groups.json" -Encoding UTF8 | ConvertFrom-Json
Write-Host "Security Groups: $($sgs.SecurityGroups.Count)"

$igws = Get-Content "$dir\internet-gateways.json" -Encoding UTF8 | ConvertFrom-Json
Write-Host "Internet Gateways: $($igws.InternetGateways.Count)"

$nats = Get-Content "$dir\nat-gateways.json" -Encoding UTF8 | ConvertFrom-Json
Write-Host "NAT Gateways: $($nats.NatGateways.Count)"

# S3
Write-Host "`n" + ("=" * 50) -ForegroundColor Yellow
Write-Host "Storage" -ForegroundColor Yellow
Write-Host "=" -Repeat 50 -ForegroundColor Yellow

$s3 = Get-Content "$dir\s3-buckets.json" -Encoding UTF8 | ConvertFrom-Json
Write-Host "S3 Buckets: $($s3.Buckets.Count)"
foreach ($bucket in $s3.Buckets) {
    Write-Host "  - $($bucket.Name)"
}

# ECR
$ecr = Get-Content "$dir\ecr-repositories.json" -Encoding UTF8 | ConvertFrom-Json
Write-Host "`nECR Repositories: $($ecr.repositories.Count)"
foreach ($repo in $ecr.repositories) {
    Write-Host "  - $($repo.repositoryName)"
}

# Secrets
Write-Host "`n" + ("=" * 50) -ForegroundColor Yellow
Write-Host "Secrets & Configuration" -ForegroundColor Yellow
Write-Host "=" -Repeat 50 -ForegroundColor Yellow

$secrets = Get-Content "$dir\secrets-manager.json" -Encoding UTF8 | ConvertFrom-Json
Write-Host "Secrets Manager: $($secrets.SecretList.Count) secrets"
foreach ($secret in $secrets.SecretList) {
    Write-Host "  - $($secret.Name)"
}

# CloudWatch
$logs = Get-Content "$dir\cloudwatch-log-groups.json" -Encoding UTF8 | ConvertFrom-Json
Write-Host "`nCloudWatch Log Groups: $($logs.logGroups.Count)"

Write-Host "`n" + ("=" * 50) -ForegroundColor Green
Write-Host "Summary Complete" -ForegroundColor Green
Write-Host "=" -Repeat 50 -ForegroundColor Green
