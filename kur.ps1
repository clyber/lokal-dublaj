<#
Lokal Dublaj kurulum betiği (Windows, PowerShell 7). Kipler; parametresiz çalıştırma yalnız denetler:
  pwsh -File kur.ps1 -Denetle          ortamı okur, eksikleri ve planı yazar; hiçbir şeyi değiştirmez
  pwsh -File kur.ps1 -Uygula -WhatIf   yapılacakları gösterir, yine hiçbir şeyi değiştirmez
  pwsh -File kur.ps1 -Uygula           Python ortamı, paketler, ayar dosyası, Firefox köprüsü
  pwsh -File kur.ps1 -Dogrula          öz denetimler, ekran kartı denemesi, sunucu ve güvenlik denetimi
Korunanlar: mevcut ayarlar.toml, is/ (hazırlanmış sesler), model önbelleği. Dokunulmayanlar: ekran kartı sürücüsü,
sistem/güvenlik ayarları, "Windows açılınca başlat", LM Studio. Firefox eklentisini kurmak ve izinleri onaylamak kullanıcıdadır.
#>
[CmdletBinding(SupportsShouldProcess, DefaultParameterSetName = 'Denetle')]
param(
    [Parameter(ParameterSetName = 'Denetle')][switch]$Denetle,
    [Parameter(ParameterSetName = 'Uygula')][switch]$Uygula,
    [Parameter(ParameterSetName = 'Dogrula')][switch]$Dogrula
)
$ErrorActionPreference = 'Stop'
$kok = $PSScriptRoot
$py = Join-Path $kok '.venv\Scripts\python.exe'
$env:PYTHONIOENCODING = 'utf-8'

function Calis([string]$komut) {  # dış komutun çıktısı; yoksa ya da hata verirse $null
    try { $c = Invoke-Expression "$komut 2>&1" | Out-String; if ($LASTEXITCODE) { return $null }; $c.Trim() } catch { $null }
}

function Denetim {
    $s =[System.Collections.Generic.List[object]]::new()
    function Ekle($ad, $durum, $ayrinti) { $s.Add([pscustomobject]@{ Bilesen = $ad; Durum = $durum; Ayrinti = $ayrinti }) }
    Ekle 'Windows 64 bit' ($(if ([Environment]::Is64BitOperatingSystem) { 'tamam' } else { 'eksik' })) ([Environment]::OSVersion.VersionString)
    Ekle 'PowerShell 7' ($(if ($PSVersionTable.PSVersion.Major -ge 7) { 'tamam' } else { 'eksik' })) "$($PSVersionTable.PSVersion)"
    $g = Calis 'git --version'; Ekle 'Git' ($(if ($g) { 'tamam' } else { 'eksik' })) "$g"
    $p = Calis 'py -3.13 -c "import sys,struct;print(sys.version.split()[0], struct.calcsize(''P'')*8, ''bit'')"'
    Ekle 'Python 3.13 (64 bit)' ($(if ($p -match '64 bit') { 'tamam' } else { 'eksik' })) "$(if ($p) { $p } else { 'py -3.13 bulunamadı' })"
    $n = Calis 'node --version'; $nm = if ($n -match 'v(\d+)') { [int]$Matches[1] } else { 0 }
    Ekle 'Node.js 22+' ($(if ($nm -ge 22) { 'tamam' } else { 'eksik' })) "$n"
    $f = Calis 'ffmpeg -version'; Ekle 'ffmpeg' ($(if ($f) { 'tamam' } else { 'eksik' })) "$(if ($f) { ($f -split "`n")[0].Substring(0, [Math]::Min(40, ($f -split "`n")[0].Length)) })"
    $gpu = Calis 'nvidia-smi --query-gpu=name,driver_version,memory.total --format=csv,noheader'
    Ekle 'NVIDIA ekran kartı' ($(if ($gpu) { 'tamam' } else { 'eksik' })) "$(if ($gpu) { $gpu } else { 'nvidia-smi yok: sürücü kurulu mu?' })"
    $bos = [math]::Round((Get-PSDrive (Split-Path $kok -Qualifier).TrimEnd(':')).Free / 1GB, 1)
    Ekle 'Boş disk' ($(if ($bos -ge 12) { 'tamam' } else { 'uyari' })) "$bos GB (ortam ~5 GB + modeller ~2 GB + videolar)"
    $v = Get-Item -LiteralPath (Join-Path $kok '.venv') -Force -ErrorAction SilentlyContinue
    Ekle 'Python ortamı (.venv)' ($(if (-not $v) { 'kurulacak' } elseif ($v.LinkType) { 'uyari' } else { 'var' })) "$(if ($v.LinkType) { "bağlantı -> $($v.Target) (gerçek klasör önerilir)" } elseif ($v) { 'mevcut, paketler güncellenir' })"
    Ekle 'ayarlar.toml' ($(if (Test-Path (Join-Path $kok 'ayarlar.toml')) { 'var' } else { 'kurulacak' })) 'varsa korunur; yoksa örnekten kopyalanır'
    $kopru = Get-ItemProperty 'HKCU:\Software\Mozilla\NativeMessagingHosts\lokal_dublaj' -ErrorAction SilentlyContinue
    Ekle 'Firefox köprüsü' ($(if ($kopru) { 'var' } else { 'kurulacak' })) "$(if ($kopru) { $kopru.'(default)' })"
    # netstat: Get-NetTCPConnection'ın modülü -WhatIf'te yüklenirken "What if: Yeni Diğer Ad" gürültüsü basıyor
    $port = netstat -ano -p TCP | Select-String '^\s*TCP\s+127\.0\.0\.1:8799\s+\S+\s+\S+\s+(\d+)' | Select-Object -First 1
    if ($port) {
        $sahip = (Get-CimInstance Win32_Process -Filter "ProcessId=$($port.Matches[0].Groups[1].Value)").CommandLine
        Ekle 'Port 8799' ($(if ($sahip -like '*sunucu.py*') { 'tamam' } else { 'uyari' })) "$(if ($sahip -like '*sunucu.py*') { 'Lokal Dublaj sunucusu açık' } else { "başka program kullanıyor: $sahip" })"
    } else { Ekle 'Port 8799' 'tamam' 'boş' }
    $adres = 'http://localhost:1234/v1'
    $ayar = Join-Path $kok 'ayarlar.toml'
    if ((Test-Path $ayar) -and ((Get-Content $ayar -Raw) -match '(?m)^adres\s*=\s*"([^"]+)"')) { $adres = $Matches[1] }
    try {
        $m = (Invoke-RestMethod "$($adres.TrimEnd('/'))/models" -TimeoutSec 3).data.id | Where-Object { $_ -notmatch 'embed' }
        Ekle 'Çeviri sunucusu (LM Studio)' ($(if ($m) { 'tamam' } else { 'uyari' })) "$(if ($m) { "$(@($m).Count) model: $(@($m)[0..2] -join ', ')" } else { 'sohbet modeli yok: LM Studio''da bir model indir' })"
    } catch { Ekle 'Çeviri sunucusu (LM Studio)' 'uyari' "$adres yanıt vermiyor: LM Studio'yu aç, Developer -> Start Server (kurulum için şart değil)" }
    $s
}

if ($PSCmdlet.ParameterSetName -eq 'Denetle') {
    $d = Denetim
    $d | Format-Table -AutoSize -Wrap
    $eksik = @($d | Where-Object Durum -eq 'eksik')
    if ($eksik) { "ÖNCE KUR: $($eksik.Bilesen -join ', ') (README → Gerekenler). Sonra yeniden: pwsh -File kur.ps1 -Denetle"; exit 1 }
    'Plan (pwsh -File kur.ps1 -Uygula ile uygulanır; önce -Uygula -WhatIf ile görebilirsin):'
    '  1. .venv yoksa Python 3.13 ile oluştur'
    '  2. PyTorch 2.11.0 (CUDA 12.8) ve requirements.txt paketlerini kur (~5 GB indirme, ilk kurulumda)'
    '  3. ayarlar.toml yoksa ayarlar.ornek.toml''dan kopyala'
    '  4. Firefox köprüsünü bu kullanıcı için kaydet (HKCU, yönetici izni gerekmez)'
    'Kullanıcı adımları: Firefox eklentisini Releases''ten kur ve izinleri onayla; LM Studio''da model indir; simgeden çeviri modelini seç.'
    exit 0
}

if ($PSCmdlet.ParameterSetName -eq 'Uygula') {
    $eksik = @(Denetim | Where-Object Durum -eq 'eksik')
    if ($eksik) { throw "Eksik ön koşul: $($eksik.Bilesen -join ', '). Önce bunları kur (README → Gerekenler)." }
    if (-not (Test-Path (Join-Path $kok '.venv'))) {
        if ($PSCmdlet.ShouldProcess("$kok\.venv", 'Python 3.13 ortamı oluştur')) { py -3.13 -m venv (Join-Path $kok '.venv'); if ($LASTEXITCODE) { throw 'venv oluşturulamadı' } }
    }
    if ($PSCmdlet.ShouldProcess('.venv', 'pip güncelle + PyTorch 2.11.0 (CUDA 12.8) kur')) {
        & $py -m pip install -q --upgrade pip
        & $py -m pip install -q torch==2.11.0 --index-url https://download.pytorch.org/whl/cu128
        if ($LASTEXITCODE) { throw 'PyTorch kurulamadı' }
    }
    if ($PSCmdlet.ShouldProcess('.venv', 'requirements.txt paketlerini kur')) {
        & $py -m pip install -q -r (Join-Path $kok 'requirements.txt'); if ($LASTEXITCODE) { throw 'requirements kurulamadı' }
    }
    if (-not (Test-Path (Join-Path $kok 'ayarlar.toml'))) {
        if ($PSCmdlet.ShouldProcess('ayarlar.toml', 'ayarlar.ornek.toml''dan kopyala')) { Copy-Item (Join-Path $kok 'ayarlar.ornek.toml') (Join-Path $kok 'ayarlar.toml') }
    }
    if ($PSCmdlet.ShouldProcess('HKCU:\Software\Mozilla\NativeMessagingHosts\lokal_dublaj', 'Firefox köprüsünü kaydet')) {
        & (Join-Path $kok 'kopru\kopru-kur.ps1')
    }
    if (-not $WhatIfPreference) {
        'KURULUM TAMAM. Kalan kullanıcı adımları:'
        '  1. Firefox eklentisi: https://github.com/clyber/lokal-dublaj/releases/latest → .xpi dosyasını Firefox''a sürükle, izinleri onayla'
        '  2. LM Studio''da bir sohbet modeli indir (denenen: gemma-4-12b-it), Developer → Start Server'
        '  3. Doğrula: pwsh -File kur.ps1 -Dogrula'
    }
    exit 0
}

if ($PSCmdlet.ParameterSetName -eq 'Dogrula') {
    if (-not (Test-Path $py)) { throw 'Python ortamı yok: önce pwsh -File kur.ps1 -Uygula' }
    $hata = 0
    foreach ($t in 'model_denetimi', 'guvenilirlik_denetimi', 'hata_denetimi', 'gpu_denetimi') {
        "== $t"; & $py (Join-Path $kok "araclar\$t.py"); if ($LASTEXITCODE) { $hata++; "HATA: $t" }
    }
    "== sunucu"
    & $py -c "import sys; sys.path.insert(0, r'$kok'); import baslatici; baslatici.baslat(); print('tamam: sunucu açık' if baslatici.durum()[0] else 'HATA: sunucu açılamadı')"
    "== guvenlik_denetimi"; & $py (Join-Path $kok 'araclar\guvenlik_denetimi.py'); if ($LASTEXITCODE) { $hata++; 'HATA: guvenlik_denetimi' }
    if ($hata) { "$hata denetim başarısız."; exit 1 }
    'OTOMATİK DENETİMLER GEÇTİ. Son adım senin: Firefox''ta bir videoda "TR aç" → "TR hazırla" → "TR dinle"; durdur ve sar.'
    exit 0
}
