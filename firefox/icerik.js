// Lokal Dublaj — içerik betiği.
// Her videoda oynatıcının sağ üstüne bir düğme koyar; basınca o videonun bilgi paneli açılır
// (durum ya da ilerleme çubuğu, ekran kartında ne var) ve oradan hazırlatılır / dinlenir.
// Türkçe ses arka planda (arka.js) çalar, videonun saatini takip eder: oynat/durdur/sar/hız YouTube'un düğmeleriyle.
(() => {
  const STIL = "position:absolute;right:10px;z-index:99;padding:6px 10px;border:0;border-radius:6px;color:#fff;font:600 13px Arial;cursor:pointer;opacity:.45;transition:opacity .2s";
  // Düğmeler normalde yarı saydam; fare üstüne gelince belirginleşir
  const belirgin = (e) => { e.addEventListener("mouseenter", () => (e.style.opacity = "1")); e.addEventListener("mouseleave", () => (e.style.opacity = ".45")); };

  let vid = null, video = null, dugme = null, bilgiDugme = null, panel = null;
  let acik = false, eskiSes = 1, sayac = null, son = {};

  const videoId = () => new URLSearchParams(location.search).get("v");
  const reklamVar = () => document.querySelector("#movie_player")?.classList.contains("ad-showing");
  const sor = (yol, yontem) => browser.runtime.sendMessage({ tip: "sor", yol, yontem });
  const baslik = () => (document.title || vid).replace(/^\(\d+\)\s*/, "").replace(/ - YouTube$/, "");
  // Sunucunun "· 3/4 çeviri %40" yazısından toplam yüzde: her aşama çeyrek sayılır.
  // Sınır: aşamalar eşit ağırlıklı varsayılır (çeviri/seslendirme uzun sürer), gerçek süreye göre ağırlık gerekirse sunucu yüzde göndersin.
  function toplamYuzde(ilerleme) {
    const a = (ilerleme || "").match(/(\d)\/4[^%]*(?:%(\d+))?/);
    if (a) return Math.min(99, Math.round(((a[1] - 1) + (a[2] || 0) / 100) * 25));
    return /birleştiriliyor/.test(ilerleme || "") ? 99 : 0;
  }

  // Türkçe açıkken özgün ses hep kapalı
  function ozgunUygula() {
    if (video && acik) video.volume = 0;
  }

  // YouTube sarınca (ve kaydırıcı oynayınca) sesi kendi değerine geri çeker [ölçüm 10-27: 0,053 → 0,353] → yeniden kapat.
  // Kapatmadan önceki değer eskiSes'te durur, Türkçe kapanınca geri verilir.
  function sesDegisti() {
    if (!acik) return;
    if (video.volume > 0.002) {
      eskiSes = video.volume;
      ozgunUygula();
    }
    konum();
  }

  function konum(zorla = false) {
    if (!acik || !video) return;
    browser.runtime.sendMessage({
      tip: "konum", t: video.currentTime, hiz: video.playbackRate,
      oynuyor: !video.paused && !reklamVar() && video.readyState >= 3, zorla, // video tampon beklerken Türkçe de beklesin
      sessiz: video.muted, // YouTube'un sessiz düğmesi Türkçe sesi de sustursun (K04)
      // Türkçe ses düzeyi = YouTube kaydırıcısının yüzdesi. video.volume değil: YouTube onu videoya göre kısıyor
      // [ölçüm 10-27: kaydırıcı %60 → video.volume 0,21]; kaydırıcı 0'a inince YouTube sessize alır (sessiz alanı)
      ses: Number(document.querySelector(".ytp-volume-panel")?.getAttribute("aria-valuenow") ?? 100) / 100,
    });
  }

  const olaylar = {
    play: () => konum(true), pause: () => konum(), seeked: () => konum(true), ratechange: () => konum(),
    volumechange: sesDegisti, waiting: () => konum(),
  };

  async function ac() {
    video = document.querySelector("#movie_player video");
    if (!video) return;
    await browser.runtime.sendMessage({ tip: "ac", vid });
    eskiSes = video.volume;
    for (const [o, f] of Object.entries(olaylar)) video.addEventListener(o, f);
    acik = true;
    ozgunUygula();
    sayac = setInterval(konum, 500);
    konum(true);
  }

  function kapat() {
    if (video && acik) {
      for (const [o, f] of Object.entries(olaylar)) video.removeEventListener(o, f);
      video.volume = eskiSes;
    }
    clearInterval(sayac);
    if (acik) browser.runtime.sendMessage({ tip: "kapat" });
    acik = false;
  }

  // Ana düğme yapılacak işi söyler ve tek basışta yapar; ayrıntı için yanındaki ▾ paneli açar
  function dugmeYaz() {
    const d = son;
    // Kısa yazı; ayrıntı ▾ panelinde
    const [metin, renk] =
      acik ? ["TR kapat", "#0a7d3b"] :
      d.durum === "hazir" ? ["TR dinle", "#1f5fbf"] :
      d.durum === "hazirlaniyor" ? [`TR %${toplamYuzde(d.ilerleme)}`, "#b36b00"] :
      d.durum === "sirada" ? ["TR sırada", "#b36b00"] :
      d.durum === "sunucu-yok" ? ["TR aç", "#444"] :
      d.durum === "aciliyor" ? ["TR açılıyor…", "#b36b00"] :
      d.durum === "hata" ? ["TR hata · yeniden dene", "#8a1c1c"] :
      d.durum === "yarim" ? ["TR devam et", "#b36b00"] :
      d.durum === "turkce" ? ["Zaten TR", "#444"] :
      d.durum === "yok" ? ["TR hazırla", "#444"] : ["TR …", "#444"];
    dugme.textContent = metin;
    dugme.style.background = renk;
    if (bilgiDugme) bilgiDugme.style.background = renk;
  }

  async function anaEylem() {
    const d = son;
    if (acik) kapat();
    else if (d.durum === "sunucu-yok") {
      // Sunucu kapalı: köprü tepsi simgesini ve sunucuyu açar
      son = { durum: "aciliyor" };
      dugmeYaz();
      const r = await browser.runtime.sendMessage({ tip: "sunucuyuAc" });
      if (r?.hata) { son = { durum: "hata", ilerleme: r.hata }; dugmeYaz(); return paneliAcKapa(); }
    }
    else if (d.durum === "hazir") await ac();
    else if (["yok", "hata", "yarim"].includes(d.durum)) await sor(`/hazirla/${vid}?ad=${encodeURIComponent(baslik())}`, "POST");
    else return paneliAcKapa(); // hazırlanıyor / sırada / sunucu kapalı: ayrıntıyı göster
    yenile();
  }

  function satir(etiket, deger) {
    const s = document.createElement("div");
    s.style.cssText = "margin:3px 0";
    const e = document.createElement("span");
    e.style.cssText = "color:#aaa";
    e.textContent = etiket + ": ";
    s.append(e, deger);
    return s;
  }

  function eylem(metin, renk, f) {
    const b = document.createElement("button");
    b.textContent = metin;
    b.style.cssText = `margin:8px 6px 0 0;padding:6px 10px;border:0;border-radius:5px;background:${renk};color:#fff;font:600 13px Arial;cursor:pointer`;
    b.addEventListener("click", async (e) => { e.stopPropagation(); await f(); yenile(); });
    return b;
  }

  function panelCiz() {
    if (!panel) return;
    const d = son;
    panel.replaceChildren();
    const b = document.createElement("div");
    b.style.cssText = "font-weight:700;margin-bottom:6px";
    b.textContent = baslik();
    panel.append(b);
    if (d.durum === "hazirlaniyor") {
      // Hazırlanırken yalnız ilerleme çubuğu ve yüzde
      const y = toplamYuzde(d.ilerleme);
      const s = document.createElement("div");
      s.style.cssText = "display:flex;align-items:center;gap:8px;margin:6px 0";
      const cubuk = document.createElement("div");
      cubuk.style.cssText = "flex:1;height:8px;border-radius:4px;background:#444;overflow:hidden";
      const dolu = document.createElement("div");
      dolu.style.cssText = `width:${y}%;height:100%;background:#e09a2b`;
      cubuk.append(dolu);
      const sayi = document.createElement("span");
      sayi.textContent = `%${y}`;
      s.append(cubuk, sayi);
      panel.append(s);
    } else panel.append(satir("Durum",
      d.durum === "hazir" ? (acik ? "Türkçe ses açık" : "Türkçe ses hazır") :
      d.durum === "yok" ? "Bu video için Türkçe ses yok" :
      d.durum === "turkce" ? "Video zaten Türkçe konuşuyor, çeviriye gerek yok" :
      d.durum === "hata" ? `Hata: ${d.ilerleme} — üstteki düğmeyle yeniden dene` :
      d.durum === "sunucu-yok" ? "Sunucu kapalı — üstteki düğmeye basınca açılır" :
      d.ilerleme || "Hazırlanıyor"));
    if (d.gpu_mesgul && d.durum !== "hazir")
      panel.append(satir("Ekran kartında şimdi", `${d.gpu_mesgul.ad} · ${d.gpu_mesgul.ilerleme || ""}`));
    // Panel yalnız bilgi verir; iş yapan tek düğme üstteki ana düğme
    if (d.durum === "yok") {
      const not = document.createElement("div");
      not.style.cssText = "color:#aaa;margin-top:4px";
      not.textContent = d.gpu_mesgul ? "Üstteki düğmeye basarsan bu video, ekran kartındaki iş biter bitmez başlar (sıradakilerin önüne geçer)." : "Üstteki düğmeye basarsan hemen başlar.";
      panel.append(not);
    }
    panel.append(eylem("Kapat ✕", "#333", async () => { panel.remove(); panel = null; }));
  }

  async function yenile() {
    const sure = document.querySelector("#movie_player video")?.duration || 0;
    const istenen = vid;
    son = await sor(`/bilgi/${vid}?sure=${Math.round(sure)}`);
    if (istenen !== videoId() || !dugme) return;
    dugmeYaz();
    panelCiz();
  }

  function paneliAcKapa() {
    if (panel) { panel.remove(); panel = null; return; }
    panel = document.createElement("div");
    panel.style.cssText = "position:absolute;top:44px;right:10px;z-index:100;width:340px;padding:10px 12px;border-radius:8px;background:rgba(20,20,20,.94);color:#fff;font:13px Arial;line-height:1.35";
    panel.addEventListener("click", (e) => e.stopPropagation());
    document.querySelector("#movie_player").appendChild(panel);
    panelCiz();
    yenile();
  }

  function kur() {
    const yeni = videoId();
    if (yeni === vid && dugme?.isConnected) return;
    kapat();
    vid = yeni;
    for (const e of [dugme, bilgiDugme, panel]) e?.remove();
    dugme = bilgiDugme = panel = null;
    son = {};
    if (!vid || !location.pathname.startsWith("/watch")) return;
    const oyuncu = document.querySelector("#movie_player");
    if (!oyuncu) return setTimeout(kur, 1000);
    dugme = document.createElement("button");
    dugme.style.cssText = STIL + ";top:10px;right:44px;border-radius:6px 0 0 6px";
    dugme.addEventListener("click", (e) => { e.stopPropagation(); anaEylem(); });
    bilgiDugme = document.createElement("button");
    bilgiDugme.style.cssText = STIL + ";top:10px;width:32px;padding:6px 0;border-radius:0 6px 6px 0;border-left:1px solid rgba(255,255,255,.3)";
    bilgiDugme.textContent = "▾";
    bilgiDugme.title = "Bu video için ayrıntı";
    bilgiDugme.addEventListener("click", (e) => { e.stopPropagation(); paneliAcKapa(); });
    [dugme, bilgiDugme].forEach(belirgin);
    oyuncu.append(dugme, bilgiDugme);
    dugmeYaz();
    yenile();
  }

  // Durum değişebilir (hazırlanıyor → hazır): 5 sn'de bir tazele
  setInterval(() => { if (vid && dugme?.isConnected) yenile(); }, 5000);
  document.addEventListener("yt-navigate-finish", kur); // YouTube sayfa yenilemeden video değiştirir
  kur();
})();
