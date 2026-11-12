"""Extracted experimental V1 quote classifier; heuristic predictions require review."""


def levenshtein_distance(s1, s2):
    if len(s1) < len(s2):
        return levenshtein_distance(s2, s1)
    if len(s2) == 0:
        return len(s1)
    previous_row = list(range(len(s2) + 1))
    for (i, c1) in enumerate(s1):
        current_row = [i + 1]
        for (j, c2) in enumerate(s2):
            insertions = previous_row[j + 1] + 1
            deletions = current_row[j] + 1
            substitutions = previous_row[j] + (c1 != c2)
            current_row.append(min(insertions, deletions, substitutions))
        previous_row = current_row
    return previous_row[-1]

class HybridDetector:

    def __init__(self):
        self.sensitive_templates = [('绿水青山就是金山银山', ['绿水青山', '金山银山']), ('纸上得来终觉浅绝知此事要躬行', ['纸上得来', '躬行']), ('谦受益满招损', ['谦受益', '满招损'])]

    def get_anchored_quote(self, text, temp, kws):
        if kws[0] in text and kws[1] in text:
            idx1 = text.find(kws[0])
            idx2 = text.find(kws[1])
            start = min(idx1, idx2)
            end = max(idx1 + len(kws[0]), idx2 + len(kws[1]))
            return text[start:end]
        for kw in kws:
            if kw in text:
                idx_text = text.find(kw)
                idx_temp = temp.find(kw)
                start = max(0, idx_text - idx_temp)
                end = min(len(text), start + len(temp))
                return text[start:end]
        return None

    def predict_single(self, text):
        if not text:
            return 0
        text_chars = set(text)
        max_ratio = 0.0
        matched_temp = ''
        matched_kws = []
        for (temp, kws) in self.sensitive_templates:
            temp_chars = set(temp)
            common_chars = text_chars.intersection(temp_chars)
            ratio = len(common_chars) / len(temp)
            if ratio > max_ratio:
                max_ratio = ratio
                matched_temp = temp
                matched_kws = kws
        if max_ratio < 0.35:
            return 0
        quote = self.get_anchored_quote(text, matched_temp, matched_kws)
        if quote is None:
            return 0
        edit_dist = levenshtein_distance(quote, matched_temp)
        if edit_dist == 0:
            return 2
        elif edit_dist <= 4:
            if '而' in quote or '，' in quote or '转化为' in quote or ('变成' in quote) or ('建设成' in quote):
                return 2
            return 1
        else:
            if matched_kws[0] in text and matched_kws[1] in text:
                return 2
            return 0

    def predict(self, texts):
        return [self.predict_single(t) for t in texts]
