# Regenera .env completo (UTF-8 sin BOM) para TradeFlow + Resend.
# Uso:
#   .\scripts\repair_dotenv.ps1 -ResendKey "re_xxxxxxxx"
param(
    [Parameter(Mandatory = $true)]
    [string]$ResendKey
)

$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $Root

$secret = python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
if (-not $secret) { throw "No se pudo generar SECRET_KEY" }

$content = @"
SECRET_KEY=$secret
DEBUG=True
ALLOWED_HOSTS=127.0.0.1,localhost
DATABASE_URL=
DB_SSL=False
RESEND_API_KEY=$ResendKey
DEFAULT_FROM_EMAIL=TradeFlow <onboarding@resend.dev>
PUBLIC_BASE_URL=http://127.0.0.1:8000
REQUIRE_EMAIL_VERIFICATION=true
REQUIRE_APPROVED_APPLICATION=false
ACCESS_GATING_GRANDFATHER_WITHOUT_APPLICATION=true
"@

$path = Join-Path $Root ".env"
$utf8NoBom = New-Object System.Text.UTF8Encoding $false
[System.IO.File]::WriteAllText($path, $content.TrimEnd() + "`n", $utf8NoBom)
Write-Host "Listo: $path"
Write-Host "SECRET_KEY=$($secret.Substring(0, [Math]::Min(20, $secret.Length)))..."
Write-Host "Ejecuta: python manage.py check_email_env"
