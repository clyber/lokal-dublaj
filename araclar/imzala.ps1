# Firefox eklentisini Mozilla'ya "listelenmemiş" (unlisted) imzalatır -> imzali\*.xpi (git dışı).
# Anahtar dosyası: 1. satır JWT issuer, 2. satır JWT secret ("ad=değer" ya da yalnız değer). Değerler ekrana yazılmaz.
# Her yeni imzada firefox\manifest.json "version" artırılmalı (Mozilla aynı sürümü ikinci kez imzalamaz).
# Sonra: imzali\lokal-dublaj-<sürüm>.xpi'yi GitHub'da v<sürüm> sürümüne yükle, guncelleme.json'u commit et;
# kurulu eklentiler (update_url) yeni sürümü kendiliğinden alır.
param([string]$Anahtar = "$env:USERPROFILE\Desktop\amo-anahtar.env.txt")
$ErrorActionPreference = 'Stop'
$kok = Split-Path $PSScriptRoot
$s = @(Get-Content $Anahtar | Where-Object { $_.Trim() } | ForEach-Object { ($_ -split '=', 2)[-1].Trim() })
if ($s.Count -lt 2) { throw "Anahtar dosyasında iki satır yok: $Anahtar" }
$env:WEB_EXT_API_KEY = $s[0]
$env:WEB_EXT_API_SECRET = $s[1]
Copy-Item "$kok\LICENSE" "$kok\firefox\LICENSE" -Force  # MIT bildirimi dağıtılan pakette de olsun (firefox/LICENSE git dışı)
npx --yes web-ext@8 sign --channel unlisted --source-dir "$kok\firefox" --artifacts-dir "$kok\imzali"
if ($LASTEXITCODE) { throw "İmza başarısız" }
$v = (Get-Content "$kok\firefox\manifest.json" -Raw | ConvertFrom-Json).version
Copy-Item (Get-ChildItem "$kok\imzali\*-$v.xpi" | Select-Object -First 1) "$kok\imzali\lokal-dublaj-$v.xpi" -Force
$g = Get-Content "$kok\guncelleme.json" -Raw | ConvertFrom-Json
$g.addons.'youtube-turkce-ses@hexa.local'.updates = @([ordered]@{
    version = $v; update_link = "https://github.com/clyber/lokal-dublaj/releases/download/v$v/lokal-dublaj-$v.xpi" })
$g | ConvertTo-Json -Depth 5 | Set-Content -Encoding utf8NoBOM "$kok\guncelleme.json"
"Hazır: imzali\lokal-dublaj-$v.xpi + guncelleme.json ($v)"
