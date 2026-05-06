Write-Host "Building Alfred's Docker Skill Sandbox..." -ForegroundColor Cyan
docker build -t alfred-sandbox .
Write-Host "Build complete! Alfred can now safely execute custom skills." -ForegroundColor Green
pause
