# Runs manage.py against the LOCAL browser-QA environment only (.env.browser-qa; Docker Postgres :55460).
Set-Location (Split-Path -Parent $PSScriptRoot)
Get-Content .env.browser-qa | Where-Object { $_ -match '^[A-Z_]+=' } | ForEach-Object {
    $i = $_.IndexOf('='); Set-Item -Path ("Env:" + $_.Substring(0, $i)) -Value $_.Substring($i + 1)
}
$env:PYTHONDONTWRITEBYTECODE = '1'; $env:PYTHONPATH = 'src'
& 'C:\Users\HP\.venvs\fieldops-nexus\Scripts\python.exe' @args
exit $LASTEXITCODE
