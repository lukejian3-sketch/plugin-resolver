"""意图匹配器：任务文本 -> 需要的能力列表。

分层匹配：
  L1 规则触发词（manifest.triggers 子串命中，权重高，可解释）
  L2 语义词典（catalog/semantics.json 同义词，处理变体说法）
  L3 字符 bigram 相似度兜底（前两层都无命中时的模糊关联）

可插拔：后续换成 LLM / embedding 匹配器时，只需实现 match() 与 explain()
同样接口即可，其他层（resolver/installer/runtime）不受影响。
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Dict, List, Optional

from .models import Manifest


def _bigrams(s: str) -> set:
    s = re.sub(r"\s+", "", s.lower())
    return {s[i:i + 2] for i in range(len(s) - 1)}


def _jaccard(a: set, b: set) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


class SemanticMatcher:
    def __init__(self, manifests: List[Manifest], semantics_file: Optional[Path] = None):
        self._manifests = manifests
        self._semantics: Dict[str, List[str]] = {}
        if semantics_file is not None and Path(semantics_file).exists():
            data = json.loads(Path(semantics_file).read_text(encoding="utf-8"))
            self._semantics = {k: list(v) for k, v in data.items()}

        self._cap_manifest: Dict[str, Manifest] = {}
        for m in manifests:
            for cap in m.capabilities:
                self._cap_manifest[cap] = m

        # 语义 seed：triggers + semantics（供 L3 相似度使用）
        self._seed_cache: Dict[str, str] = {}
        for cap, m in self._cap_manifest.items():
            parts = list(m.triggers) + self._semantics.get(cap, [])
            self._seed_cache[cap] = " ".join(parts)

    def _score(self, text: str) -> Dict[str, dict]:
        tl = text.lower()
        scored: Dict[str, dict] = {}

        def add(cap: str, layer: str, term: str, weight: int) -> None:
            e = scored.setdefault(cap, {"score": 0, "hits": [], "layers": set()})
            e["score"] += weight
            if term not in e["hits"]:
                e["hits"].append(term)
            e["layers"].add(layer)

        # L1 规则触发词
        for m in self._manifests:
            for cap in m.capabilities:
                for t in m.triggers:
                    if t.lower() in tl:
                        add(cap, "L1-trigger", t, 3)

        # L2 语义同义词
        for cap, terms in self._semantics.items():
            for t in terms:
                if t.lower() in tl:
                    add(cap, "L2-semantic", t, 2)

        return scored

    def match(self, text: str) -> List[str]:
        scored = self._score(text)
        if scored:
            return [cap for cap, _ in sorted(scored.items(), key=lambda kv: -kv[1]["score"])]
        # L3 bigram 相似度兜底
        bigs = _bigrams(text)
        best = []
        for cap, seed in self._seed_cache.items():
            sim = _jaccard(bigs, _bigrams(seed))
            if sim > 0.2:
                best.append((sim, cap))
        best.sort(key=lambda x: -x[0])
        return [cap for _, cap in best]

    def explain(self, text: str) -> List[dict]:
        scored = self._score(text)
        out = []
        for cap, e in scored.items():
            m = self._cap_manifest.get(cap)
            out.append({
                "plugin": m.id if m else cap,
                "capability": cap,
                "score": e["score"],
                "hits": e["hits"],
                "layers": sorted(e["layers"]),
            })
        if not out:
            bigs = _bigrams(text)
            for cap, seed in self._seed_cache.items():
                sim = _jaccard(bigs, _bigrams(seed))
                if sim > 0.2:
                    m = self._cap_manifest.get(cap)
                    out.append({
                        "plugin": m.id if m else cap,
                        "capability": cap,
                        "score": round(sim * 10, 2),
                        "hits": [f"bigram-sim={sim:.2f}"],
                        "layers": ["L3-bigram"],
                    })
        return sorted(out, key=lambda x: -x["score"])