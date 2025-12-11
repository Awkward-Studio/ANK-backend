# Monitor ECS Migration to Public Subnet
Write-Host "Monitoring ECS service migration to public subnet..." -ForegroundColor Cyan
Write-Host ""

$maxAttempts = 20
$attempt = 0

do {
    $attempt++
    Write-Host "Check #$attempt of $maxAttempts" -ForegroundColor Yellow
    
    $env:PAGER = ''
    $result = aws ecs describe-services --cluster ank-prod-cluster --services ank-prod-svc --region ap-south-1 --query 'services[0].{Running:runningCount,Pending:pendingCount,Subnet:networkConfiguration.awsvpcConfiguration.subnets[0],PublicIP:networkConfiguration.awsvpcConfiguration.assignPublicIp}' --output json | ConvertFrom-Json
    
    Write-Host "  Running: $($result.Running)"
    Write-Host "  Pending: $($result.Pending)"
    Write-Host "  Subnet: $($result.Subnet)"
    Write-Host "  Public IP: $($result.PublicIP)"
    Write-Host ""
    
    if ($result.Running -eq 1 -and $result.Pending -eq 0 -and $result.PublicIP -eq "ENABLED") {
        Write-Host "✅ SUCCESS! ECS is now running in public subnet!" -ForegroundColor Green
        Write-Host ""
        Write-Host "Verifying target health..." -ForegroundColor Cyan
        
        Start-Sleep -Seconds 10
        
        $health = aws elbv2 describe-target-health --target-group-arn arn:aws:elasticloadbalancing:ap-south-1:912448661225:targetgroup/ank-prod-tg/c62534574d2dc5ad --region ap-south-1 --query 'TargetHealthDescriptions[0].TargetHealth.State' --output text
        
        Write-Host "Target Health: $health" -ForegroundColor $(if ($health -eq "healthy") { "Green" } else { "Yellow" })
        
        if ($health -eq "healthy") {
            Write-Host ""
            Write-Host "🎉 Migration complete! You can now safely delete NAT Gateway!" -ForegroundColor Green
            break
        }
    }
    
    Start-Sleep -Seconds 15
    
} while ($attempt -lt $maxAttempts)

if ($attempt -eq $maxAttempts) {
    Write-Host "⚠️ Migration taking longer than expected. Check AWS Console for details." -ForegroundColor Yellow
}
