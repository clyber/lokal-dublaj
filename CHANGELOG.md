# Değişiklikler

Sürüm numarası Firefox eklentisinin sürümüdür; sunucu tarafı aynı commit'te güncellenir. Eklenti kendiliğinden güncellenir, sunucu tarafı için `git pull` ve `pwsh -File kur.ps1 -Uygula`.

## 0.1.13 — 2026-10-27
- **Model kökeni:** `uretim.json` çeviri sunucusu adresini de kaydeder; yarım çeviri yalnız aynı adres + modelle sürer. Modeli bilinmeyen (eski sürümden) ya da adresi/modeli uyuşmayan yarım çeviri sessizce yeni modelle tamamlanmaz: düğme "TR baştan çevir" olur, basınca yazıya döküm korunarak seçili modelle baştan çevrilir (`cevir.py --yeniden-cevir`). Hazır sese dokunulmaz.
- `uretim.json` ve `parcalar.json` atomik yazılır; sunucu yarım/bozuk kaydı okurken çökmez.
- Sunucu: aynı video için tek iş (kilitli denetim); aynı anda en çok 3 iş, aşınca açık uyarı. Range doğru (taşan aralık kırpılır, karşılanamaz/ters/bozuk aralık 416), ses parça parça gönderilir; geçersiz `sure` 400. ASCII dışı ya da bozuk belirteç/bilet bağlantıyı koparmaz (401); beklenmeyen hata JSON 500 döner. Boş kalmış belirteç dosyası yeniden üretilir.
- Eklenti: eski köprü ayrıca tanınır ("Köprü eski: sunucu tarafını güncelle"); JSON olmayan cevap ve açılamayan ses panelde açıklanır; canlı yayında süre gönderilmez.
- Tepsi: model seçiminde çift tıklama yarışı yok; ayar dosyası her geçerli TOML biçiminde doğru güncellenir. Çıkış bildirimi indiren/sıra bekleyen her işi görür.
- `kur.ps1`: `.venv` bağlantıysa, Python 3.13 64 bit değilse ya da Lokal Dublaj çalışıyorsa `-Uygula` durur (`-Denetle` ve `-Uygula -WhatIf`'te görünür); `-WhatIf` yalnız `-Uygula` ile. `-Dogrula` seçili modelle gerçek deneme çevirisi yapar; model seçilmemişse ya da LM Studio kapalıysa, ya da kontrol atlandıysa çıkış 2 ("kullanıcı adımı bekliyor"), başarı sayılmaz. Dış komutların çıkış kodları denetlenir.

## 0.1.12 — 2026-10-27
- **Güvenlik:** sunucu her istekte kurulum başına üretilen gizli belirteci ister (eklenti onu yalnız Firefox köprüsünden alır); ses adresi yalnız o videoya özel biletle açılır; yabancı Host reddedilir. Eski sabit başlık kaldırıldı. **Sunucu tarafını güncellemek şart.**
- `kur.ps1`: `-Denetle`, `-Uygula` (`-WhatIf` destekli), `-Dogrula` kipleriyle kurulum; `araclar/gpu_denetimi.py`, `araclar/guvenlik_denetimi.py`.
- `AGENTS.md` ve README'de "Ajanınla kur".
- Simgeden çıkarken hazırlanan video varsa bildirim.

## 0.1.11 — 2026-10-27
- Çeviri modeli seçimi: simge menüsünde LM Studio modelleri, seçimden önce 3 cümlelik deneme çevirisi (biçim + sayı denetimi).
- Her videonun çeviri modeli kaydedilir (`uretim.json`) ve ▾ panelinde görünür; yarıda kalan video başladığı modelle tamamlanır.
- Birden çok model varken sessizce ilk model seçilmez; model, video indirilmeden önce denetlenir.

## 0.1.10 — 2026-10-27
- Eklenti güncellenince açık sekmede eski sürümün düğmeleri kalıyor, yenileriyle üst üste biniyordu.

## 0.1.9 — 2026-10-27
- Mozilla veri beyanı düzeltildi (gezinme etkinliği + site içeriği, yalnız yerel sunucuya); gizli pencerede çalışmaz; pakette MIT bildirimi.
- Kurulum tarifi tamamlandı (CUDA kütüphaneleri, yt-dlp EJS, Git/PowerShell 7/Node 22); port 8799 sabit; port doluysa açık hata.

## 0.1.8 — 2026-10-27
- İlk genel sürüm: yerel Türkçe seslendirme (yt-dlp → faster-whisper → LM Studio → EMA Lightning), Firefox eklentisi, tepsi simgesi, Firefox köprüsü, otomatik eklenti güncellemesi.
