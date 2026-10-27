# Lokal Dublaj

Yabancı dildeki YouTube videolarını **kendi bilgisayarında** Türkçe seslendirir ve Firefox'ta videonun kendi düğmeleriyle senkron dinletir. Bulut yok, ücretli API yok: indirme dışında hiçbir veri bilgisayarından çıkmaz.

Videodaki **TR** düğmesine basarsın; video arka planda yazıya dökülür, yerel bir dil modeliyle çevrilir ve Türkçe seslendirilir. Hazır olunca "TR dinle" dersin: oynat, durdur, sar ve hız YouTube'un düğmeleriyle çalışır, Türkçe ses açıkken özgün ses kapanır, ses düzeyi YouTube'un kaydırıcısını izler.

> **Durum: erken sürüm (0.1).** Tek bir bilgisayarda denendi: Windows 10, NVIDIA RTX 5080, Firefox. Başka donanımda sorun çıkarsa issue açman çok değerli.

## Nasıl çalışır

```
YouTube bağlantısı → yt-dlp (ses) → faster-whisper (yazıya dök, GPU) → LM Studio / Ollama (çeviri)
                   → EMA Lightning (Türkçe ses) → zaman çizelgesine yerleştir → turkce.m4a
Firefox eklentisi ⇄ yerel sunucu (127.0.0.1:8799) → sesi videonun saatine bağlı çalar
```

Ölçüm: 24 dakikalık bir video RTX 5080'de yaklaşık 20 dakikada hazır (video süresinin ~0,8 katı).

## Gerekenler

- Windows 10/11 ve CUDA destekli bir NVIDIA ekran kartı
- [Python 3.13](https://www.python.org/downloads/), [ffmpeg](https://ffmpeg.org/download.html) ve [Node.js](https://nodejs.org/) (yt-dlp YouTube için ister) PATH'te
- [LM Studio](https://lmstudio.ai/) ve indirilmiş bir sohbet modeli (denenen: `gemma-4-12b-it`); yerel sunucusu açık olmalı (varsayılan `http://localhost:1234`). Ollama da çalışır: `ayarlar.toml` → `ceviri.adres = "http://localhost:11434/v1"`
- Firefox

## Kurulum

```powershell
git clone https://github.com/clyber/lokal-dublaj.git
cd lokal-dublaj
python -m venv .venv
.venv\Scripts\pip install torch --index-url https://download.pytorch.org/whl/cu128
.venv\Scripts\pip install -r requirements.txt
pwsh -File kopru\kopru-kur.ps1
```

Son satır Firefox köprüsünü kaydeder: böylece videodaki düğme sunucu kapalıyken onu kendisi açar (yalnız bu kullanıcı için, yönetici izni gerekmez; kaldırmak için `-Kaldir`).

Ardından **Firefox eklentisini** [Releases](https://github.com/clyber/lokal-dublaj/releases) sayfasından indirip `.xpi` dosyasını Firefox'a sürükle (Mozilla imzalı; sonraki sürümler kendiliğinden güncellenir).

Ayarları değiştirmek istersen `ayarlar.ornek.toml`'u `ayarlar.toml` adıyla kopyala: büyük dosyaların yeri, çeviri modeli, ses motoru, port.

## Kullanım

1. LM Studio'yu aç, modeli yükle.
2. YouTube'da bir video aç; sağ üstte **TR aç** görünür. Basınca saatin yanında Lokal Dublaj simgesi belirir ve sunucu açılır.
3. **TR hazırla** → ilerleme düğmede ve ▾ panelinde yüzde olarak görünür.
4. Hazır olunca **TR dinle**. Kapatmak için aynı düğme; sunucuyu kapatmak için simgeye sağ tıkla → Çıkış.

Bir oynatma listesini önden hazırlamak: `.venv\Scripts\python toplu.py <liste-bağlantısı>`

## Bilinen sınırlar

- Yalnız İngilizce → Türkçe denendi. Canlı yayın desteklenmez.
- Ekran kartı olmadan hazırlama çalışmaz (yazıya dökme CUDA ister).
- Türkçe cümle özgününden uzunsa en çok 1,35 kat hızlandırılır; nadiren taşabilir.

## Sorumluluk

Kişisel kullanım içindir. İndirdiğin ve seslendirdiğin içeriğin haklarına ve YouTube Hizmet Şartları'na uymak senin sorumluluğundadır. Bu proje YouTube ya da Google ile bağlantılı değildir; "YouTube" Google LLC'nin markasıdır.

## Lisans

[MIT](LICENSE). Kullanılan bileşenlerin kendi lisansları geçerlidir: yt-dlp (Unlicense), faster-whisper (MIT), EMA Lightning (Apache-2.0), PyTorch (BSD); indirdiğin dil modelinin şartları sana aittir.
