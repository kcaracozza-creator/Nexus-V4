#!/usr/bin/env pwsh
# ============================================================
# DANIELSON DEPLOY — Push all scanner station files
# Run from Windows: .\deploy_danielson.ps1
# ============================================================
# What this ships:
#   danielson_server.py     — unified scanner + all endpoints
#   nexus_auth/             — auth pipeline + NFT minter
#   launch_shop.py          — TCG mode launcher
#   launch_venue.py         — auth mode launcher
#   deploy.sh               — Linux-side install script
# ============================================================

$DANIELSON_HOST = "danielson@192.168.1.219"
$REPO_ROOT = $PSScriptRoot
$REMOTE_STAGE = "/tmp/nexus_deploy"

Write-Host ""
Write-Host "============================================"
Write-Host "  DANIELSON DEPLOY"
Write-Host "  Target: $DANIELSON_HOST"
Write-Host "============================================"
Write-Host ""

# --- Stage files locally ---
$stage = "$env:TEMP\nexus_danielson_stage"
if (Test-Path $stage) { Remove-Item -Recurse -Force $stage }
New-Item -ItemType Directory -Path $stage | Out-Null
New-Item -ItemType Directory -Path "$stage\nexus_auth" | Out-Null

# Core server
Copy-Item "$REPO_ROOT\src\scanner\danielson\danielson_server.py" "$stage\"
Copy-Item "$REPO_ROOT\src\scanner\danielson\deploy.sh" "$stage\"

# nexus_auth pipeline
foreach ($f in @("auth_engine.py","auth_ui.py","item_types.py","nft_minter.py","__init__.py")) {
    $src = "$REPO_ROOT\nexus_auth\$f"
    if (Test-Path $src) {
        Copy-Item $src "$stage\nexus_auth\"
        Write-Host "  Staged: nexus_auth\$f"
    } else {
        Write-Host "  WARN: nexus_auth\$f not found"
    }
}

# Launchers
foreach ($f in @("launch_shop.py","launch_venue.py")) {
    $src = "$REPO_ROOT\$f"
    if (Test-Path $src) {
        Copy-Item $src "$stage\"
        Write-Host "  Staged: $f"
    }
}

Write-Host ""
Write-Host "Pushing to Danielson..."

# SCP everything
scp -r "$stage\*" "${DANIELSON_HOST}:${REMOTE_STAGE}/"
if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: SCP failed. Check SSH access to $DANIELSON_HOST" -ForegroundColor Red
    exit 1
}

Write-Host "Files transferred. Running deploy.sh on Danielson..."

# SSH — run deploy.sh then restart service
ssh $DANIELSON_HOST @"
set -e
cd $REMOTE_STAGE
bash deploy.sh
echo '--- Restarting DANIELSON service ---'
sudo systemctl restart danielson 2>/dev/null || echo 'systemd restart skipped'
sleep 2
curl -s http://localhost:5001/status | python3 -m json.tool 2>/dev/null || curl -s http://localhost:5001/status
"@

if ($LASTEXITCODE -eq 0) {
    Write-Host ""
    Write-Host "============================================" -ForegroundColor Green
    Write-Host "  DEPLOY COMPLETE" -ForegroundColor Green
    Write-Host "  Verify: http://192.168.1.219:5001/status" -ForegroundColor Green
    Write-Host "============================================" -ForegroundColor Green
} else {
    Write-Host "Deploy had errors — check SSH output above" -ForegroundColor Yellow
}

# Cleanup
Remove-Item -Recurse -Force $stage
