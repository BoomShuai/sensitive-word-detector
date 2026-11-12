"""Extracted experimental V4 quote classifier; heuristic predictions require review."""

import numpy as np
from .v3 import V3HybridDetector, _WARN_PHRASES, _VALID_TRANSFORM_PHRASES, _PARTICLES, _CLAUSE_DELIMS, _NEUTRAL_FRAMES
from .semantic import SemanticBackend
_CLASS2_FRAMES = ['的道理', '的真理', '这是常识', '是常识', '告诉我们', '印证了', '正所谓', '古往今来', '古人讲', '古语', '千古', '也就等于', '赖以生存', '简直就是', '就是最宝贵', '真正转化', '转化为', '变成', '建设成', '确实变成']

class V4HybridDetector(V3HybridDetector):

    def __init__(self, backend: SemanticBackend=None, lean_ambiguous_to_warn: bool=True, a_thresh=0.12, c_thresh=0.25, d_thresh=0.28, ctx_min=4, templates=None):
        super().__init__(a_thresh, c_thresh, d_thresh, ctx_min)
        if backend is None:
            raise ValueError("V4 requires an explicit local semantic backend")
        self.backend = backend
        if templates is not None:
            self.sensitive_templates = templates
        self.lean_ambiguous_to_warn = lean_ambiguous_to_warn
        templates = [t for (t, _) in self.sensitive_templates]
        self._temp_embs = self.backend.precompute_templates(templates)

    def _coarse_pass_semantic(self, text, temp, kws, temp_idx, sim):
        (passes, anchor_hit) = self._coarse_pass(text, temp, kws)
        if passes:
            return (True, anchor_hit, sim)
        if sim >= self.backend.sim_threshold:
            return (True, False, sim)
        return (False, False, sim)

    def _classify_fine(self, text, temp, kws, anchor_hit, sim=0.0):
        has_warn = any((p in text for p in _WARN_PHRASES))
        has_transform = any((p in text for p in _VALID_TRANSFORM_PHRASES))
        if has_warn:
            return 1
        if has_transform:
            return 2
        if anchor_hit:
            (span, pre, post) = self._anchor_span(text, temp, kws)
            ed_span = self._best_window_ed(span, temp)
            outside = self._strip_frames(pre + post)
            for w in _WARN_PHRASES:
                outside = outside.replace(w, '')
            ctx = self._content_len(outside)
            if ctx >= self.ctx_min:
                return 2
            if ed_span == 0:
                if anchor_hit:
                    (span, pre, post) = self._anchor_span(text, temp, kws)
                    exterior = self._strip_frames(pre + post)
                    if any((ch in _PARTICLES for ch in exterior)):
                        return 1
                return 2
            return 1
        ed_span = self._best_window_ed(text, temp)
        if ed_span > len(temp) * 0.5:
            if sim < self.backend.sim_threshold:
                return 0
            has_class2_frame = any((f in text for f in _CLASS2_FRAMES))
            if has_class2_frame:
                return 2
            if sim >= self.backend.high_sim_threshold:
                return 1
            return 1 if self.lean_ambiguous_to_warn else 2
        return 1

    def predict_single(self, text, sims=None):
        if not text:
            return 0
        if sims is None and self._temp_embs is not None:
            emb = self.backend.encode_batch([text])
            if emb is not None:
                sims = (emb[0] @ self._temp_embs.T).astype(float)
        (best_class, best_ed) = (0, float('inf'))
        for (i, (temp, kws)) in enumerate(self.sensitive_templates):
            sim = float(sims[i]) if sims is not None else 0.0
            (passes, anchor_hit, sim) = self._coarse_pass_semantic(text, temp, kws, i, sim)
            if not passes:
                continue
            cls = self._classify_fine(text, temp, kws, anchor_hit, sim)
            if cls > 0:
                (span, _, _) = self._anchor_span(text, temp, kws) if anchor_hit else (text, '', '')
                ed = self._best_window_ed(span if span else text, temp)
                if ed < best_ed:
                    best_ed = ed
                    best_class = cls
        return best_class

    def predict(self, texts):
        if self._temp_embs is None:
            raise RuntimeError("Semantic embeddings unavailable; no implicit fallback")
        embs = self.backend.encode_batch(list(texts))
        if embs is None:
            raise RuntimeError("Semantic embeddings unavailable; no implicit fallback")
        with np.errstate(divide='ignore', invalid='ignore'):
            sims_all = embs @ self._temp_embs.T
            sims_all = np.nan_to_num(sims_all, nan=0.0)
        return np.array([self.predict_single(t, sims=sims_all[i]) for (i, t) in enumerate(texts)])
