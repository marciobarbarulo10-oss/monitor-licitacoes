"""
core/scorer.py
Calcula o score de aderência entre uma licitação e a config de um tenant.
Score 0–10. Tenants recebem alertas apenas acima de config.min_score.
"""
from dataclasses import dataclass
from typing import Optional
import re

@dataclass
class ScoreDetail:
    keywords_must: float
    keywords_want: float
    segment: float
    value_fit: float
    total: float

    def to_dict(self) -> dict:
        return {"keywords_must": round(self.keywords_must, 2), "keywords_want": round(self.keywords_want, 2), "segment": round(self.segment, 2), "value_fit": round(self.value_fit, 2), "total": round(self.total, 2)}

def score_licitacao(titulo: str, descricao: Optional[str], valor_estimado: Optional[float], config: dict) -> ScoreDetail:
    text = _normalize(f"{titulo} {descricao or ''}")
    for kw in config.get("keywords_skip", []):
        if _match(kw, text): return ScoreDetail(0, 0, 0, 0, 0.0)
    must = config.get("keywords_must", [])
    if must:
        hits = sum(1 for kw in must if _match(kw, text))
        km_score = (hits / len(must)) * 4.0
    else:
        km_score = 2.0
    want = config.get("keywords_want", [])
    if want:
        hits = sum(1 for kw in want if _match(kw, text))
        kw_score = min(hits / max(len(want) * 0.4, 1), 1.0) * 3.0
    else:
        kw_score = 1.5
    from scrapers.scraper_pncp import SEGMENT_KEYWORDS
    seg_score = 0.0
    for seg in config.get("segments", []):
        seg_kws = SEGMENT_KEYWORDS.get(seg, [])
        if any(_match(kw, text) for kw in seg_kws):
            seg_score = 2.0
            break
    vfit = 1.0
    if valor_estimado and valor_estimado > 0:
        min_v = config.get("min_value") or 0
        max_v = config.get("max_value")
        if valor_estimado < min_v: vfit = 0.3
        elif max_v and valor_estimado > max_v: vfit = 0.5
    total = round(min(km_score + kw_score + seg_score + vfit, 10.0), 2)
    return ScoreDetail(km_score, kw_score, seg_score, vfit, total)

def _normalize(text: str) -> str:
    text = text.lower()
    replacements = {"á":"a","à":"a","â":"a","ã":"a","é":"e","ê":"e","í":"i","ó":"o","ô":"o","õ":"o","ú":"u","ç":"c"}
    for k, v in replacements.items(): text = text.replace(k, v)
    return text

def _match(keyword: str, normalized_text: str) -> bool:
    kw = _normalize(keyword)
    if len(kw) <= 3: return bool(re.search(rf"\b{re.escape(kw)}\b", normalized_text))
    return kw in normalized_text
