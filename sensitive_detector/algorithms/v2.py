"""Extracted experimental V2 quote classifier; heuristic predictions require review."""

from .v1 import levenshtein_distance

def _char_bigram_jaccard(a: str, b: str) -> float:

    def bg(s):
        return set((s[i:i + 2] for i in range(len(s) - 1)))
    (ga, gb) = (bg(a), bg(b))
    if not gb:
        return 0.0
    u = len(ga | gb)
    return len(ga & gb) / u if u > 0 else 0.0

def _char_cosine(a, b):
    from collections import Counter
    from math import sqrt
    (ca, cb) = (Counter(a), Counter(b))
    denominator = sqrt(sum((v * v for v in ca.values())) * sum((v * v for v in cb.values())))
    return sum((v * cb[k] for (k, v) in ca.items())) / denominator if denominator else 0.0

def _char_unigram_overlap(a: str, b: str) -> float:
    (sa, sb) = (set(a), set(b))
    if not sb:
        return 0.0
    return len(sa & sb) / len(sb)
_VALID_TRANSFORM_PHRASES = ['转化为', '变成', '建设成', '真正转化', '确实变成', '就是最宝贵', '简直就是', '也就等于']
_WARN_CONTEXT_PHRASES = ['这种说法不严谨', '应当予以纠正', '需要查错', '说法不严谨', '大家要注意', '系统检测到', '不严谨']

class V2HybridDetector:

    def __init__(self, a_thresh: float=0.12, c_thresh: float=0.25, d_thresh: float=0.28):
        self.sensitive_templates = [('绿水青山就是金山银山', ['绿水青山', '金山银山']), ('纸上得来终觉浅绝知此事要躬行', ['纸上得来', '躬行']), ('谦受益满招损', ['谦受益', '满招损'])]
        self.a_thresh = a_thresh
        self.c_thresh = c_thresh
        self.d_thresh = d_thresh

    def _coarse_pass(self, text: str, temp: str, kws: list) -> tuple:
        anchor = any((kw in text for kw in kws))
        if anchor:
            return (True, True)
        if _char_unigram_overlap(text, temp) >= self.c_thresh:
            return (True, False)
        if _char_bigram_jaccard(text, temp) >= self.a_thresh:
            return (True, False)
        if _char_cosine(text, temp) >= self.d_thresh:
            return (True, False)
        return (False, False)

    def _get_window(self, text: str, temp: str, kws: list) -> str:
        positions = []
        for kw in kws:
            idx = text.find(kw)
            if idx >= 0:
                positions.append((idx, idx + len(kw)))
        if len(positions) >= 2:
            start = min((p[0] for p in positions))
            end = max((p[1] for p in positions))
            return text[start:end]
        if positions:
            idx_text = positions[0][0]
            kw = kws[0] if text.find(kws[0]) >= 0 else kws[1]
            idx_temp = temp.find(kw)
            start = max(0, idx_text - idx_temp)
            end = min(len(text), start + len(temp))
            return text[start:end]
        (best_win, best_dist) = (text, len(text) + len(temp))
        tlen = len(temp)
        for i in range(max(1, len(text) - tlen + 1)):
            win = text[i:i + tlen]
            d = levenshtein_distance(win, temp)
            if d < best_dist:
                best_dist = d
                best_win = win
        return best_win

    def _classify_fine(self, text: str, window: str, temp: str, kws: list, ed: int, anchor_hit: bool) -> int:
        both_anchors = all((kw in text for kw in kws))
        len_ratio = len(text) / max(len(temp), 1)
        if ed == 0:
            return 2
        if 1 <= ed <= 5:
            if any((p in text for p in _VALID_TRANSFORM_PHRASES)):
                return 2
            return 1
        if both_anchors:
            if any((p in text for p in _VALID_TRANSFORM_PHRASES)):
                return 2
            if len_ratio >= 1.8:
                return 2
            if len_ratio >= 1.3 and ed > 10:
                return 2
            return 1
        if anchor_hit:
            if any((p in text for p in _WARN_CONTEXT_PHRASES)):
                return 1
            if any((p in text for p in _VALID_TRANSFORM_PHRASES)) and len_ratio >= 1.8:
                return 2
            return 1
        return 0

    def predict_single(self, text: str) -> int:
        if not text:
            return 0
        best_class = 0
        best_ed = float('inf')
        for (temp, kws) in self.sensitive_templates:
            (passes, anchor_hit) = self._coarse_pass(text, temp, kws)
            if not passes:
                continue
            window = self._get_window(text, temp, kws)
            ed = levenshtein_distance(window, temp)
            cls = self._classify_fine(text, window, temp, kws, ed, anchor_hit)
            if cls > 0 and ed < best_ed:
                best_ed = ed
                best_class = cls
        return best_class

    def predict(self, texts):
        return [self.predict_single(t) for t in texts]
