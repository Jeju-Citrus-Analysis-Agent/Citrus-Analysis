$ErrorActionPreference = 'Stop'
$runtimePath = Join-Path $PSScriptRoot 'runtime'
if (-not (Test-Path -LiteralPath (Join-Path $runtimePath 'server/dist/index.js'))) {
    throw 'FreeLLMAPI server files are missing. Restore the runtime installation first.'
}
if (-not (Get-Command node.exe -ErrorAction SilentlyContinue)) {
    throw 'Node.js is missing. Install Node.js, then try again.'
}
$listener = Get-NetTCPConnection -State Listen -LocalPort 3001 -ErrorAction SilentlyContinue
if (-not $listener) {
    Start-Process -FilePath (Get-Command node.exe).Source -ArgumentList 'server/dist/index.js' -WorkingDirectory $runtimePath -WindowStyle Hidden -RedirectStandardOutput (Join-Path $PSScriptRoot 'server.log') -RedirectStandardError (Join-Path $PSScriptRoot 'server-error.log')
}
for ($attempt = 0; $attempt -lt 20; $attempt++) {
    try {
        $response = Invoke-WebRequest -Uri 'http://127.0.0.1:3001/api/auth/status' -TimeoutSec 2 -UseBasicParsing
        if ($response.StatusCode -eq 200) {
            $status = $response.Content | ConvertFrom-Json
            if (-not ($status.PSObject.Properties.Name -contains 'needsSetup')) {
                throw 'Port 3001 belongs to a different service.'
            }
            Write-Output 'FreeLLMAPI ready: http://127.0.0.1:3001'
            return
        }
    } catch {
        if ($_.Exception.Message -like '*different service*') { throw }
        Start-Sleep -Milliseconds 500
    }
}
throw 'FreeLLMAPI did not start. Check server-error.log in this folder.'
