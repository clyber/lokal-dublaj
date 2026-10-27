# Lokal Dublaj

Yabancı dildeki YouTube videolarını **kendi bilgisayarında** Türkçe seslendirir ve Firefox'ta videonun kendi düğmeleriyle senkron dinletir. Bulut yok, ücretli API yok.

Kimin için: Windows + NVIDIA ekran kartı + Firefox kullanan, yerel model kurmaya ve videonun önceden hazırlanmasını beklemeye razı olanlar.

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

- Windows 10/11 ve güncel sürücülü, CUDA destekli bir NVIDIA ekran kartı
- [Git](https://git-scm.com/download/win) ve [PowerShell 7](https://learn.microsoft.com/powershell/scripting/install/installing-powershell-on-windows) (`pwsh`; Windows'la gelen PowerShell 5.1 yetmez)
- [Python 3.13, 64 bit](https://www.python.org/downloads/), [Node.js 22 ya da üstü](https://nodejs.org/) (yt-dlp YouTube için ister) ve [ffmpeg](https://ffmpeg.org/download.html) PATH'te
- [LM Studio](https://lmstudio.ai/) ve indirilmiş bir sohbet modeli (denenen: `gemma-4-12b-it`); Developer sekmesinden yerel sunucusu açık olmalı (varsayılan `http://localhost:1234`). Ollama aynı arayüzü sunar (`ayarlar.toml` → `ceviri.adres = "http://localhost:11434/v1"`) ama bu sürümde denenmedi.
- Firefox
- Disk: ilk kullanımda yazıya dökme modeli (~1,6 GB) ve ses modeli (~34 MB) indirilir (varsayılan yer `%USERPROFILE%\.cache\huggingface`); çeviri modeli LM Studio'nun kendi klasöründedir. Her video için birkaç yüz MB geçici dosya oluşur.

Kurmadan önce araçların göründüğünü denetle (hepsi bir sürüm yazmalı):

```powershell
git --version; pwsh --version; py -3.13 --version; node --version; ffmpeg -version
```

## Kurulum

```powershell
git clone https://github.com/clyber/lokal-dublaj.git
cd lokal-dublaj
py -3.13 -m venv .venv
.venv\Scripts\pip install torch --index-url https://download.pytorch.org/whl/cu128
.venv\Scripts\pip install -r requirements.txt
pwsh -File kopru\kopru-kur.ps1
```

Son satır Firefox köprüsünü kaydeder: böylece videodaki düğme sunucu kapalıyken onu kendisi açar (yalnız bu kullanıcı için, yönetici izni gerekmez; kaldırmak için `-Kaldir`; klasörü taşırsan yeniden çalıştır).

Ardından **Firefox eklentisini** [Releases](https://github.com/clyber/lokal-dublaj/releases) sayfasından indirip `.xpi` dosyasını Firefox'a sürükle (Mozilla imzalı). Araçları yeni kurduysan Firefox'u bir kez kapatıp aç ki yeni PATH'i görsün.

Ayarları değiştirmek istersen `ayarlar.ornek.toml`'u `ayarlar.toml` adıyla kopyala: büyük dosyaların yeri, çeviri modeli. Port bu sürümde 8799'da sabittir (eklenti bu adrese bağlıdır).

### Güncelleme

Firefox eklentisi kendiliğinden güncellenir. Bilgisayardaki sunucu tarafı güncellenmez; yeni sürüm notunda gerekiyorsa şunu çalıştır (ayarların ve hazırlanmış seslerin korunur):

```powershell
git pull
.venv\Scripts\pip install -r requirements.txt
```

## Kullanım

1. LM Studio'yu aç, yerel sunucusunu başlat. İlk kullanımda saatin yanındaki Lokal Dublaj simgesine sağ tıkla → **Çeviri modeli** → listeden bir model seç: üç kısa cümlelik deneme çevirisi yapılır, geçerse seçilir (sonuç bildirimle görünür). Birden çok model varken seçim yapılmazsa hazırlama başlamaz; hangi modelin kullanıldığı ▾ panelinde yazar. Yarıda kalan bir video, model değişse de başladığı modelle tamamlanır.
2. YouTube'da bir video aç; sağ üstte **TR aç** görünür. Basınca saatin yanında Lokal Dublaj simgesi belirir ve sunucu açılır.
3. **TR hazırla** → ilerleme düğmede ve ▾ panelinde yüzde olarak görünür.
4. Hazır olunca **TR dinle**. Kapatmak için aynı düğme; sunucuyu kapatmak için simgeye sağ tıkla → Çıkış. O sırada hazırlanan bir video varsa arka planda bitmeye devam eder.

Bir oynatma listesini önden hazırlamak (bağlantıyı tırnak içine al):

```powershell
.venv\Scripts\python toplu.py "https://www.youtube.com/playlist?list=..."
```

`sunucu-baslat.bat` yalnız sorun giderme içindir: simge olmadan sunucuyu açar, günlüğü `is\sunucu.log`'a yazar.

## Bilinen sınırlar

- Yalnız İngilizce → Türkçe denendi. Canlı yayın desteklenmez.
- Ekran kartı olmadan hazırlama çalışmaz (yazıya dökme CUDA ister).
- Türkçe cümle özgününden uzunsa en çok 1,35 kat hızlandırılır; nadiren taşabilir.
- Türkçe açıkken özgün sesin tamamı kapanır; müzik ve efektler de duyulmaz (konuşma ayrıştırılmıyor).
- Düğme yalnız normal video sayfasında (`/watch`) çıkar; Shorts arayüzü desteklenmez.
- Çeviri makine çevirisidir; özellikle sayı ve birimleri kontrol et.
- Tek Windows kullanıcısı ve tek kurulum için tasarlandı. Ses motoru olarak yalnız EMA Lightning desteklenir.

## Gizlilik

Varsayılan ayarlarla yazıya dökme, çeviri ve seslendirme senin bilgisayarında çalışır. Eklenti, açtığın videonun kimliğini, süresini ve hazırlatırken başlığını yalnız bilgisayarındaki Lokal Dublaj sunucusuna (127.0.0.1) gönderir; Firefox bunu kurulumda "gezinme etkinliği" ve "site içeriği" olarak gösterir. İnternete çıkanlar: YouTube'dan ses indirme, ilk kullanımda model indirmeleri (Hugging Face) ve eklentinin güncelleme denetimi (GitHub). Ayarlarda başka bir çeviri adresi yazarsan metin o adrese gider. Gizli pencerede eklenti çalışmaz.

## Sorumluluk

Yalnız hak sahibi olduğun ya da gerekli izinlere sahip olduğun içerikleri, platformun koşullarına uygun biçimde kullan; bunun sorumluluğu sana aittir. Bu, yazılımın MIT lisansını kısıtlamaz; içerik hakları ayrı bir konudur. Bu proje YouTube ya da Google ile bağlantılı değildir; "YouTube" Google LLC'nin markasıdır.

## Lisans

[MIT](LICENSE). Kullanılan bileşenlerin kendi lisansları geçerlidir: yt-dlp (Unlicense), faster-whisper (MIT), EMA Lightning (Apache-2.0), PyTorch (BSD); indirdiğin dil modelinin şartları sana aittir.
