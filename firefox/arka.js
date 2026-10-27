// Arka plan: Türkçe sesi burada çalar ve sunucuyla burada konuşur.
// Neden burada: YouTube sayfasının güvenlik kuralları (CSP) sayfanın içinden 127.0.0.1'e erişimi engelliyor;
// eklentinin arka planı bu kurallara tabi değil.
const SUNUCU = "http://127.0.0.1:8799";
const SAPMA = 0.3; // saniye; bundan fazla kayarsa sesi videoya yeniden hizala
const sesler = {}; // sekme kimliği -> Audio

browser.runtime.onMessage.addListener(async (m, gonderen) => {
  const sekme = gonderen.tab.id;
  if (m.tip === "sor") {
    try {
      // X-TR-Ses: sunucu iş başlatmayı yalnız bu başlığı yollayan eklentiye açar (web sayfaları yollayamaz)
      const r = await fetch(SUNUCU + m.yol, { method: m.yontem || "GET", headers: { "X-TR-Ses": "1" } });
      return await r.json();
    } catch {
      return { durum: "sunucu-yok" };
    }
  }
  if (m.tip === "sunucuyuAc") { // köprü (kopru/kopru.py) tepsi simgesini ve sunucuyu açar
    try {
      return await browser.runtime.sendNativeMessage("lokal_dublaj", { komut: "baslat" });
    } catch (e) {
      return { hata: "Köprü kurulu değil — lokal-dublaj\\kopru\\kopru-kur.ps1 bir kez çalıştırılmalı" };
    }
  }
  if (m.tip === "ac") {
    sesler[sekme]?.pause();
    const a = new Audio(`${SUNUCU}/ses/${m.vid}.m4a`);
    a.preload = "auto";
    sesler[sekme] = a;
    return true;
  }
  if (m.tip === "kapat") {
    sesler[sekme]?.pause();
    delete sesler[sekme];
    return true;
  }
  if (m.tip === "konum") { // içerik betiği her olayda ve 0,5 sn'de bir videonun durumunu yollar
    const a = sesler[sekme];
    if (!a) return false;
    a.playbackRate = m.hiz;
    a.muted = !!m.sessiz;
    a.volume = m.ses; // Türkçe sesin düzeyi = YouTube'un ses kaydırıcısı
    if (m.zorla || Math.abs(a.currentTime - m.t) > SAPMA) a.currentTime = m.t;
    if (m.oynuyor) { if (a.paused) a.play().catch((e) => console.warn("Lokal Dublaj: Türkçe ses çalınamadı", e)); } else a.pause();
    return true;
  }
});

browser.tabs.onRemoved.addListener((sekme) => { sesler[sekme]?.pause(); delete sesler[sekme]; });
