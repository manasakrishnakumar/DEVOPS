# Release pipeline for signed golden outputs (Extra 3).
#   1. compute the reference outputs + model-file hashes INSIDE the release image (same libraries as production)
#   2. sign golden.json with cosign (key stays on the release machine; NO transparency-log upload)
#   3. publish golden.json, golden.json.bundle and cosign.pub as the ConfigMap signed-golden
# Also builds two deliberately broken variants for the fail-closed tests:
#   gold_tamper     golden.json edited after signing                 (signature no longer verifies)
#   gold_wronghash  manifest names a different model-file hash, validly signed (model replaced after signing)
param(
  [string]$Image = 'climate-inference:14',
  [string]$Work = 'C:\work\gold',
  [string]$Key = 'C:\project_keys\cosign.key',
  [string]$Cosign = "$env:LOCALAPPDATA\Microsoft\WinGet\Packages\Sigstore.Cosign_Microsoft.Winget.Source_8wekyb3d8bbwe\cosign-windows-amd64.exe",
  [switch]$Publish
)
$ErrorActionPreference = 'Stop'
if (-not $env:COSIGN_PASSWORD) { throw 'set COSIGN_PASSWORD (the password of the cosign key)' }
foreach ($d in 'gold_good', 'gold_tamper', 'gold_wronghash') { Remove-Item "$Work\$d" -Recurse -Force -ErrorAction SilentlyContinue; New-Item -ItemType Directory -Force "$Work\$d" | Out-Null }

# 1. reference outputs from the healthy models of the image
docker run --rm -v "${Work}\gold_good:/out" $Image python make_signed_golden.py /out
if ($LASTEXITCODE) { throw 'make_signed_golden failed' }

function Sign($dir) {
  $prev = $ErrorActionPreference; $ErrorActionPreference = 'Continue'          # cosign prints a deprecation warning on stderr
  & $Cosign sign-blob --yes --key $Key --use-signing-config=false --tlog-upload=false --new-bundle-format --bundle "$dir\golden.json.bundle" "$dir\golden.json" 2>&1 | Out-Null
  $code = $LASTEXITCODE; $ErrorActionPreference = $prev
  if ($code) { throw "cosign sign-blob failed for $dir" }
  Copy-Item ([IO.Path]::ChangeExtension($Key, 'pub')) "$dir\cosign.pub" -Force
  # second, independent verifier: cosign itself must accept what the service's own (cryptography-based) check will accept
  $ErrorActionPreference = 'Continue'
  & $Cosign verify-blob --key "$dir\cosign.pub" --bundle "$dir\golden.json.bundle" --insecure-ignore-tlog=true "$dir\golden.json" 2>&1 | Out-Null
  $v = $LASTEXITCODE; $ErrorActionPreference = $prev
  if ($v) { throw "cosign verify-blob rejected the freshly signed $dir" }
}
# 2. sign the good release
Sign "$Work\gold_good"

# broken variants
Copy-Item "$Work\gold_good\*" "$Work\gold_tamper" -Force
$j = Get-Content "$Work\gold_tamper\golden.json" -Raw | ConvertFrom-Json
$j.golden.lstm.Rainfall[0] = $j.golden.lstm.Rainfall[0] * 0.5                       # edit AFTER signing; the old bundle is kept
[IO.File]::WriteAllText("$Work\gold_tamper\golden.json", ($j | ConvertTo-Json -Depth 8), (New-Object Text.UTF8Encoding($false)))

Copy-Item "$Work\gold_good\golden.json" "$Work\gold_wronghash\golden.json" -Force
$j = Get-Content "$Work\gold_wronghash\golden.json" -Raw | ConvertFrom-Json
$j.files.'lstm/lstm_rainfall.h5' = ('0' * 64)                                       # a different model file than the one shipped
[IO.File]::WriteAllText("$Work\gold_wronghash\golden.json", ($j | ConvertTo-Json -Depth 8), (New-Object Text.UTF8Encoding($false)))
Sign "$Work\gold_wronghash"

if ($Publish) { kubectl -n climate create configmap signed-golden --from-file="$Work\gold_good" --dry-run=client -o yaml | kubectl apply -f - }
"signed golden ready: $Work\gold_good (good), gold_tamper, gold_wronghash"
