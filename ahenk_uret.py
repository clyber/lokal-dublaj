"""Ahenk TTS (VoxCPM2 + Türkçe LoRA) ile bir işin parçalarını seslendirir. cevir.py bunu Ahenk'in KENDİ Python ortamıyla çalıştırır:
    <ahenk_python> ahenk_uret.py <iş-klasörü> --depo <ahenk-snapshot> [--hf <HF_HOME>] [--trnorm <src>]
parcalar.json + ceviri.json okur, eksik <iş-klasörü>/tts-ahenk/<id>.wav dosyalarını yazar (var olana dokunmaz)."""
import argparse, json, os, sys
from pathlib import Path

ap = argparse.ArgumentParser()
ap.add_argument("klasor")
ap.add_argument("--depo", required=True)
ap.add_argument("--hf", default="")
ap.add_argument("--trnorm", default="")
g = ap.parse_args()
if g.hf:
    os.environ["HF_HOME"] = g.hf
if g.trnorm:
    sys.path.insert(0, g.trnorm)
sys.path.insert(0, g.depo)

import re
import numpy as np, soundfile as sf, torch
from instruction_pick import compose, pick
from pause_clean import clean
from trnorm import normalize
from voxcpm import VoxCPM
from voxcpm.model.voxcpm import LoRAConfig

d = Path(g.klasor)
p = json.loads((d / "parcalar.json").read_text(encoding="utf-8"))
tr = json.loads((d / "ceviri.json").read_text(encoding="utf-8"))
sd = d / "tts-ahenk"
sd.mkdir(exist_ok=True)
lora = json.loads(Path(g.depo, "lora_config.json").read_text(encoding="utf-8"))["lora_config"]
tts = VoxCPM.from_pretrained("openbmb/VoxCPM2", load_denoiser=False, optimize=False, lora_config=LoRAConfig(**lora), lora_weights_path=g.depo)
SR = tts.tts_model.sample_rate


def gruplar(m, sinir=190):  # uzun metinde cümle sonu yutulmasın diye cümleler ~190 karakterlik gruplara bölünür
    cikti, cur = [], ""
    for c in re.split(r"(?<=[.!?])\s+", m.strip()):
        if cur and len(cur) + 1 + len(c) > sinir:
            cikti.append(cur)
            cur = c
        else:
            cur = (cur + " " + c).strip()
    return cikti + [cur] if cur else cikti


def uret(t):
    talimat, model_metin, _ = pick("", t, "auto")
    torch.manual_seed(1234)
    parca = [np.asarray(x).squeeze() for x in tts.generate_streaming(text=compose(talimat, model_metin), cfg_value=2.0, inference_timesteps=16, normalize=False)]
    torch.cuda.synchronize()
    return clean(np.concatenate(parca), SR)[0]


eksik = [x for x in p if tr.get(str(x["id"]), "").strip() and not (sd / f'{x["id"]}.wav').exists()]
for n, x in enumerate(eksik, 1):
    ses = []
    for j, t in enumerate(gruplar(normalize(tr[str(x["id"])].strip()))):
        if j:
            ses.append(np.zeros(int(SR * 0.2), np.float32))
        ses.append(uret(t).astype(np.float32))
    sf.write(sd / f'{x["id"]}.wav', np.concatenate(ses), SR)
    print(f"ses {n}/{len(eksik)}", flush=True)
