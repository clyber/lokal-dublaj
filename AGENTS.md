# Lokal Dublaj — ajanlar için kurulum sözleşmesi

(English: installer contract for coding agents. Windows + NVIDIA + Firefox only. Use `kur.ps1`; never invent steps.)

**Amaç:** kullanıcının kendi Windows bilgisayarında, bu deponun yayımlanmış sürümünü kurmak. Kod geliştirme, commit ya da push bu görevin parçası değildir.

## Sıra

1. `README.md` (Gerekenler, Kurulum, Bilinen sınırlar, Gizlilik) ve `kur.ps1`'i oku. Hangi commit'i kurduğunu kaydet.
2. `pwsh -File kur.ps1 -Denetle` çalıştır. Çıktıdaki tabloyu kullanıcıya Türkçe ve kısa özetle. **eksik** satırı varsa dur: o ön koşulu (Git, PowerShell 7, Python 3.13 64 bit, Node.js 22+, ffmpeg, NVIDIA sürücüsü) nasıl kuracağını resmî kaynakla söyle; kendi kendine sürücü kurma.
3. `pwsh -File kur.ps1 -Uygula -WhatIf` çalıştır; yapılacakları, indirme boyutunu (ilk kurulumda ~5 GB Python paketi, ilk kullanımda ~1,6 GB yazıya dökme modeli) ve Firefox köprüsünün HKCU kaydını göster. **Kullanıcının açık onayını al.**
4. Onaydan sonra `pwsh -File kur.ps1 -Uygula`. Kapsam değişirse (örn. betik farklı bir şey istiyorsa) yeniden sor.
5. `pwsh -File kur.ps1 -Dogrula`. Başarısız satırı olduğu gibi bildir; tahminle yeni paket deneme zinciri kurma.
6. Kullanıcı adımlarını yönlendir, bunları kendin yaptığını iddia etme:
   - Firefox eklentisi: https://github.com/clyber/lokal-dublaj/releases/latest → `.xpi` dosyasını Firefox'a sürükle, izinleri **kullanıcı** onaylar.
   - LM Studio: bir sohbet modeli indir (denenen: `gemma-4-12b-it`), Developer → Start Server.
   - Saatin yanındaki Lokal Dublaj simgesi → Çeviri modeli → model seç (deneme çevirisi yapılır).
   - Kabul: bir videoda "TR aç" → "TR hazırla" → "TR dinle"; durdur ve sar.

## Sınırlar

- Mevcut `ayarlar.toml`, `is/` (hazırlanmış sesler) ve model önbelleğini koru; silme, üzerine yazma.
- Yalnız bu depodaki `.venv`'i kullan. Sistem Python'una, PowerShell yürütme politikasına, güvenlik yazılımına, ekran kartı sürücüsüne dokunma.
- "Windows açılınca başlat"ı kendiliğinden açma.
- `.belirtec` dosyası gizlidir: okuma, yazdırma, sohbete ya da günlüğe koyma.
- Bulut ya da WSL ortamında kurmak kullanıcının Windows kurulumu yerine geçmez.
- Sonuçta otomatik denetimleri (geçti/başarısız) ve kullanıcının yapması gereken adımları ayrı yaz; doğrulanmayanı açıkça söyle.
