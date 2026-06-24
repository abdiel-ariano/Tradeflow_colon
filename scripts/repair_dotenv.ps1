# Regenera .env mínimo (UTF-8 sin BOM) para TradeFlow — Gmail SMTP.
# Uso:
#   .\scripts\repair_dotenv.ps1 -GmailUser "tu@gmail.com" -GmailAppPassword "xxxx xxxx xxxx xxxx"
param(
    [Parameter(Mandatory = $true)]
    [string]$GmailUser,
    [Parameter(Mandatory = $true)]
    [string]$GmailAppPassword
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
SUPABASE_EMAIL_ENABLED=false
EMAIL_HOST_USER=$GmailUser
EMAIL_HOST_PASSWORD=$GmailAppPassword
DEFAULT_FROM_EMAIL=TradeFlow <$GmailUser>
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
Write-Host "Ejecuta: python manage.py verify_integrations --email $GmailUser"
