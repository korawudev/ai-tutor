"""Text-similarity helpers for deduplicating generated quiz questions."""
import hashlib
import re

_SHINGLE = 3
_NUM_HASHES = 64
_CLEAN_RE = re.compile(r"[\s，。！？、；：“”‘’（）《》〈〉【】「」『』·…—\-—\"'.,!?;:()\[\]{}<>/\\\d]")


def normalize(text: str) -> str:
    return _CLEAN_RE.sub("", (text or "").lower())


def _hash(text: str) -> int:
    return int.from_bytes(hashlib.md5(text.encode("utf-8")).digest()[:8], "big")


def _signature(text: str) -> list:
    cleaned = normalize(text)
    if not cleaned:
        return [0] * _NUM_HASHES
    shingles = [cleaned[i:i + _SHINGLE] for i in range(len(cleaned) - _SHINGLE + 1)]
    hashes = set(_hash(s) for s in shingles)
    sig = []
    for i in range(_NUM_HASHES):
        a, b = 2 * i + 1, 4 * i + 3
        min_v = None
        for h in hashes:
            v = ((a * h + b) % 2 ** 64)
            if min_v is None or v < min_v:
                min_v = v
        sig.append(min_v or 0)
    return sig


def similarity(a: str, b: str) -> float:
    """返回 [0,1] 的文本相似度.MiniHash 采样估计 Jaccard."""
    if not normalize(a) or not normalize(b):
        return 0.0
    sa, sb = _signature(a), _signature(b)
    return sum(1 for x, y in zip(sa, sb) if x == y) / _NUM_HASHES
