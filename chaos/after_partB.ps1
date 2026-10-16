Set-Location "C:\Users\manas\OneDrive\Desktop\bangalore_climate_app_final\devops_project"
"$(Get-Date -Format s) [after_partB] waiting for part B" | Add-Content results\phase78.log
while (-not ((Get-Content results\phase56_done.flag -ErrorAction SilentlyContinue) -match 'done|failed')) { Start-Sleep 60 }
Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -match 'chaos\run\.py' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
Start-Sleep 20
powershell -NoProfile -ExecutionPolicy Bypass -File chaos\phase78.ps1
