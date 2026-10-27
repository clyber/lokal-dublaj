# Firefox köprüsünü bu kullanıcı için kaydeder (yönetici izni gerekmez); -Kaldir ile siler.
# Ne yapar: lokal_dublaj.json'u bu klasörün tam yoluyla yazar, HKCU\Software\Mozilla\NativeMessagingHosts\lokal_dublaj'a yolunu koyar.
param([switch]$Kaldir)
$ErrorActionPreference = 'Stop'
$anahtar = 'HKCU:\Software\Mozilla\NativeMessagingHosts\lokal_dublaj'
$json = Join-Path $PSScriptRoot 'lokal_dublaj.json'
if ($Kaldir) {
    Remove-Item $anahtar -ErrorAction SilentlyContinue
    Remove-Item $json -ErrorAction SilentlyContinue
    "Köprü kaldırıldı."; return
}
[ordered]@{
    name               = 'lokal_dublaj'
    description        = 'Lokal Dublaj: videodaki düğmeden sunucuyu açar'
    path               = (Join-Path $PSScriptRoot 'kopru.bat')
    type               = 'stdio'
    allowed_extensions = @('youtube-turkce-ses@hexa.local')
} | ConvertTo-Json | Set-Content -Encoding utf8NoBOM $json
New-Item $anahtar -Force | Out-Null
Set-ItemProperty $anahtar -Name '(default)' -Value $json
"Köprü kuruldu: $json"
