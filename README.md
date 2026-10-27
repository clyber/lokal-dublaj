# Lokal Dublaj

Yabancı dildeki YouTube videolarını **kendi bilgisayarında** Türkçe seslendirir ve Firefox'ta videonun kendi düğmeleriyle senkron dinletir. Bulut yok, ücretli API yok.

Kimin için: Windows + NVIDIA ekran kartı + Firefox kullanan, yerel model kurmaya ve videonun önceden hazırlanmasını beklemeye razı olanlar.

Tanıtım videosu (1,5 dk, yapay zekâ sesli anlatım): https://youtu.be/bO6gXYwNcIw

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

## Kurulum

```powershell
git clone https://github.com/clyber/lokal-dublaj.git
cd lokal-dublaj
pwsh -File kur.ps1 -Denetle          # neyin eksik olduğunu söyler, hiçbir şeyi değiştirmez
pwsh -File kur.ps1 -Uygula -WhatIf   # yapılacakları gösterir (yine değişiklik yok)
pwsh -File kur.ps1 -Uygula           # Python ortamı + paketler (~5 GB) + ayar dosyası + Firefox köprüsü
pwsh -File kur.ps1 -Dogrula          # öz denetimler, ekran kartı ve gerçek çeviri denemesi, güvenlik denetimi (çıkış 2: senin adımın bekliyor)
```

`kur.ps1` mevcut ayarlarını, hazırlanmış seslerini ve model önbelleğini korur; ekran kartı sürücüsüne, sistem ayarlarına ve "Windows açılınca başlat"a dokunmaz. Firefox köprüsü, videodaki düğmenin sunucu kapalıyken onu kendisi açmasını ve eklentinin sunucuyla güvenli konuşmasını sağlar (yalnız bu kullanıcı için, yönetici izni gerekmez; kaldırmak için `pwsh -File kopru\kopru-kur.ps1 -Kaldir`; klasörü taşırsan `-Uygula`'yı yeniden çalıştır).

<details><summary>Elle kurulum (betik yerine)</summary>

```powershell
py -3.13 -m venv .venv
.venv\Scripts\pip install torch==2.11.0 --index-url https://download.pytorch.org/whl/cu128
.venv\Scripts\pip install -r requirements.txt
pwsh -File kopru\kopru-kur.ps1
```
</details>

### Ajanınla kur

Bilgisayarında komut çalıştırabilen bir yapay zekâ ajanına (Claude Code, Codex, Cursor) kurdurabilirsin; depodaki `AGENTS.md` ona sırayı ve sınırları söyler. Ajan önce denetler ve planı gösterir; senin onayın olmadan kurmaz. Firefox eklentisini kurmak ve izinleri onaylamak her durumda sende. Ajana şunu ver:

```text
https://github.com/clyber/lokal-dublaj deposunu bu Windows bilgisayara kur. Önce AGENTS.md, README ve kur.ps1'i oku;
olmayan bir adımı varmış gibi uydurma. Önce yalnız "kur.ps1 -Denetle" ve "-Uygula -WhatIf" çalıştır, ne kurulacağını,
indirme boyutunu ve Firefox köprü kaydını bana göster; onayımdan sonra "-Uygula" ve "-Dogrula". Ayarlarımı, modellerimi
ve hazırlanmış seslerimi koru; kodu değiştirme. Sonunda geçen/geçmeyen denetimleri ve benim yapmam gereken adımları ayrı yaz.
```

Ardından **Firefox eklentisini** [Releases](https://github.com/clyber/lokal-dublaj/releases) sayfasından indirip `.xpi` dosyasını Firefox'a sürükle (Mozilla imzalı). Araçları yeni kurduysan Firefox'u bir kez kapatıp aç ki yeni PATH'i görsün.

Ayarları değiştirmek istersen `ayarlar.ornek.toml`'u `ayarlar.toml` adıyla kopyala: büyük dosyaların yeri, çeviri modeli. Port bu sürümde 8799'da sabittir (eklenti bu adrese bağlıdır).

### Güncelleme

Firefox eklentisi kendiliğinden güncellenir. Bilgisayardaki sunucu tarafı güncellenmez; yeni sürüm notunda gerekiyorsa önce simgeden Çıkış yap (hazırlanan video varsa bitmesini bekle; `kur.ps1` Lokal Dublaj çalışırken paket kurmaz), sonra şunu çalıştır ve videoda "TR aç"a bas (ayarların ve hazırlanmış seslerin korunur):

```powershell
git pull
pwsh -File kur.ps1 -Uygula
```

## Kullanım

1. LM Studio'yu aç, yerel sunucusunu başlat. İlk kullanımda saatin yanındaki Lokal Dublaj simgesine sağ tıkla → **Çeviri modeli** → listeden bir model seç: üç kısa cümlelik deneme çevirisi yapılır, geçerse seçilir (sonuç bildirimle görünür). Birden çok model varken seçim yapılmazsa hazırlama başlamaz; hangi modelin kullanıldığı ▾ panelinde yazar. Yarıda kalan bir video, model değişse de başladığı modelle (aynı çeviri adresinde) tamamlanır; önceki modeli bilinmiyorsa ya da artık yoksa düğme **TR baştan çevir** olur: yazıya döküm korunur, çeviri seçili modelle baştan yapılır.
2. YouTube'da bir video aç; sağ üstte **TR aç** görünür. Basınca saatin yanında Lokal Dublaj simgesi belirir ve sunucu açılır.
3. **TR hazırla** → ilerleme düğmede ve ▾ panelinde yüzde olarak görünür.
4. Hazır olunca **TR dinle**. Kapatmak için aynı düğme; sunucuyu kapatmak için simgeye sağ tıkla → Çıkış. O sırada indirilen ya da hazırlanan video varsa arka planda bitmeye devam eder (simge bunu çıkarken bildirir); sunucu kapalıyken düğme kendiliğinden "TR dinle" olmaz, videoda **TR aç**'a basınca sunucu açılır ve hazır ses görünür.

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

Sunucu yalnız bu bilgisayardan erişilebilir ve her istekte kuruluma özel gizli bir belirteç ister; eklenti onu yalnız Firefox köprüsünden alır. Ayrıntı ve güvenlik açığı bildirimi: [SECURITY.md](SECURITY.md).

## Sorumluluk

Yalnız hak sahibi olduğun ya da gerekli izinlere sahip olduğun içerikleri, platformun koşullarına uygun biçimde kullan; bunun sorumluluğu sana aittir. Bu, yazılımın MIT lisansını kısıtlamaz; içerik hakları ayrı bir konudur. Bu proje YouTube ya da Google ile bağlantılı değildir; "YouTube" Google LLC'nin markasıdır.

## In English

Lokal Dublaj dubs foreign-language YouTube videos into **Turkish entirely on your own PC** and plays the Turkish track in sync with YouTube's own controls in Firefox. Pipeline: yt-dlp → faster-whisper (GPU) → a local LLM via LM Studio → EMA Lightning Turkish TTS. No cloud, no paid API. Requirements: Windows 10/11, an NVIDIA GPU with CUDA, Python 3.13, Node.js 22+, ffmpeg, LM Studio, Firefox. Install with `pwsh -File kur.ps1 -Denetle`, then `-Uygula`, then `-Dogrula`; get the signed Firefox add-on from [Releases](https://github.com/clyber/lokal-dublaj/releases). Coding agents can follow [AGENTS.md](AGENTS.md). Only English → Turkish has been tested; the UI is Turkish. Issues and pull requests are welcome in English or Turkish.

## Değişiklikler

[CHANGELOG.md](CHANGELOG.md). Hata bildirmek için [issue aç](https://github.com/clyber/lokal-dublaj/issues/new/choose) (şablon, gereken bilgileri sorar).

## Lisans

[MIT](LICENSE). Kullanılan bileşenlerin kendi lisansları geçerlidir: yt-dlp (Unlicense), faster-whisper (MIT), EMA Lightning (Apache-2.0), PyTorch (BSD); indirdiğin dil modelinin şartları sana aittir.
