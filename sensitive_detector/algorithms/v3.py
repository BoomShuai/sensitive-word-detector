"""Extracted experimental V3 quote classifier; heuristic predictions require review."""

from collections import Counter
from .v1 import levenshtein_distance
from .v2 import _char_bigram_jaccard, _char_cosine, _char_unigram_overlap
_CLAUSE_DELIMS = '，。！？、；,.!?;：'
_PARTICLES = set('啊呀呢吧了嘛哦噢嗯哈呐哟啦')
_WARN_PHRASES = ['这种说法不严谨', '说法不严谨', '不严谨', '应当予以纠正', '予以纠正', '需要进行查错核对', '查错核对']
_NEUTRAL_FRAMES = ['大家要注意', '系统检测到', '文献中写道', '我认为']
_VALID_TRANSFORM_PHRASES = ['转化为', '变成', '建设成', '真正转化', '确实变成', '转化', '就是最宝贵', '简直就是', '也就等于', '等于守护', '赖以生存']
_CTX_MIN = 4

class V3HybridDetector:

    def __init__(self, a_thresh=0.12, c_thresh=0.25, d_thresh=0.28, ctx_min=_CTX_MIN):
        self.sensitive_templates = [('绿水青山就是金山银山', ['绿水青山', '金山银山']), ('纸上得来终觉浅绝知此事要躬行', ['纸上得来', '躬行']), ('谦受益满招损', ['谦受益', '满招损'])]
        self.a_thresh = a_thresh
        self.c_thresh = c_thresh
        self.d_thresh = d_thresh
        self.ctx_min = ctx_min

    def _coarse_pass(self, text, temp, kws):
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

    @staticmethod
    def _strip_frames(s):
        for f in _NEUTRAL_FRAMES:
            s = s.replace(f, '')
        return s

    @staticmethod
    def _content_len(s):
        return sum((1 for ch in s if ch not in _PARTICLES and ch not in _CLAUSE_DELIMS))

    @staticmethod
    def _best_window_ed(core, temp):
        tlen = len(temp)
        if len(core) <= tlen:
            return levenshtein_distance(core, temp)
        best = len(core) + tlen
        for i in range(len(core) - tlen + 1):
            d = levenshtein_distance(core[i:i + tlen], temp)
            if d < best:
                best = d
                if best == 0:
                    break
        return best

    def _anchor_span(self, text, temp, kws):
        pos = []
        for kw in kws:
            idx = text.find(kw)
            if idx >= 0:
                pos.append((idx, idx + len(kw)))
        if len(pos) >= 2:
            s = min((p[0] for p in pos))
            e = max((p[1] for p in pos))
            return (text[s:e], text[:s], text[e:])
        if len(pos) == 1:
            (s0, e0) = pos[0]
            kw = text[s0:e0]
            it = temp.find(kw)
            s = max(0, s0 - it)
            e = min(len(text), s + len(temp))
            return (text[s:e], text[:s], text[e:])
        return ('', text, '')

    def _classify_fine(self, text, temp, kws, anchor_hit):
        has_warn = any((p in text for p in _WARN_PHRASES))
        has_transform = any((p in text for p in _VALID_TRANSFORM_PHRASES))
        if anchor_hit:
            (span, pre, post) = self._anchor_span(text, temp, kws)
            ed_span = self._best_window_ed(span, temp)
            outside = self._strip_frames(pre + post)
            for w in _WARN_PHRASES:
                outside = outside.replace(w, '')
            ctx = self._content_len(outside)
        else:
            ed_span = self._best_window_ed(text, temp)
            ctx = 0
        if has_warn:
            return 1
        if has_transform:
            return 2
        if not anchor_hit:
            if ed_span > len(temp) * 0.5:
                return 0
            return 1
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

    def predict_single(self, text):
        if not text:
            return 0
        (best_class, best_ed) = (0, float('inf'))
        for (temp, kws) in self.sensitive_templates:
            (passes, anchor_hit) = self._coarse_pass(text, temp, kws)
            if not passes:
                continue
            cls = self._classify_fine(text, temp, kws, anchor_hit)
            if cls > 0:
                (span, _, _) = self._anchor_span(text, temp, kws) if anchor_hit else (text, '', '')
                ed = self._best_window_ed(span if span else text, temp)
                if ed < best_ed:
                    best_ed = ed
                    best_class = cls
        return best_class

    def predict(self, texts):
        return [self.predict_single(t) for t in texts]
