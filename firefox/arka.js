// Arka plan: Türkçe sesi burada çalar ve sunucuyla burada konuşur.
// Neden burada: YouTube sayfasının güvenlik kuralları (CSP) sayfanın içinden 127.0.0.1'e erişimi engelliyor;
// eklentinin arka planı bu kurallara tabi değil.
const SUNUCU = "http://127.0.0.1:8799";
const SAPMA = 0.3; // saniye; bundan fazla kayarsa sesi videoya yeniden hizala
const sesler = {}; // sekme kimliği -> Audio
const KOPRU_YOK = "Köprü kurulu değil — lokal-dublaj\\kopru\\kopru-kur.ps1 bir kez çalıştırılmalı";

// Sunucu her istekte kurulum belirtecini ister; eklenti onu yalnız köprüden alır (Firefox o kanalı yalnız bu eklentiye açar).
let belirtec = null, belirtecHatasi = 0;
async function belirtecAl(yenile) {
  if (belirtec && !yenile) return belirtec;
  if (!yenile && Date.now() - belirtecHatasi < 30000) return null; // köprü yoksa her 5 sn'de süreç açmasın
  try {
    belirtec = (await browser.runtime.sendNativeMessage("lokal_dublaj", { komut: "belirtec" })).belirtec || null;
  } catch {
    belirtec = null;
  }
  if (!belirtec) belirtecHatasi = Date.now();
  return belirtec;
}

async function sor(yol, yontem) {
  for (const yenile of [false, true]) { // 401: belirteç değişmiş olabilir (kurulum yenilendi), bir kez tazele
    const b = await belirtecAl(yenile);
    if (!b) return { durum: "hata", ilerleme: KOPRU_YOK };
    let r;
    try {
      r = await fetch(SUNUCU + yol, { method: yontem || "GET", headers: { "X-TR-Belirtec": b } });
    } catch {
      return { durum: "sunucu-yok" };
    }
    if (r.status !== 401) return await r.json();
  }
  return { durum: "hata", ilerleme: "Sunucu belirteci kabul etmedi; sunucu tarafını güncelle (git pull)" };
}

browser.runtime.onMessage.addListener(async (m, gonderen) => {
  const sekme = gonderen.tab.id;
  if (m.tip === "sor") return sor(m.yol, m.yontem);
  if (m.tip === "sunucuyuAc") { // köprü (kopru/kopru.py) tepsi simgesini ve sunucuyu açar, belirteci de verir
    try {
      const r = await browser.runtime.sendNativeMessage("lokal_dublaj", { komut: "baslat" });
      if (r.belirtec) belirtec = r.belirtec;
      return r;
    } catch (e) {
      return { hata: KOPRU_YOK };
    }
  }
  if (m.tip === "ac") {
    sesler[sekme]?.pause();
    const d = await sor(`/durum/${m.vid}`); // ses adresi videoya özel biletle açılır
    if (!d.bilet) return false;
    const a = new Audio(`${SUNUCU}/ses/${m.vid}.m4a?b=${d.bilet}`);
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
