# Değişiklikler

Sürüm numarası Firefox eklentisinin sürümüdür; sunucu tarafı aynı commit'te güncellenir. Eklenti kendiliğinden güncellenir, sunucu tarafı için `git pull` ve `pwsh -File kur.ps1 -Uygula`.

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
