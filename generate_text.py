#!/usr/bin/env python3
"""生成指定长度类型的随机文本"""

import random

CHINESE_PUNCT = "，。、；：？！""''（）【】《》〈〉…—·"
ENGLISH_PUNCT = ",.!?;:'\"()[]-_"
ENGLISH_LETTERS = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"
DIGITS = "0123456789"

TEXT_TYPES = [
    "纯汉字",
    "纯英文",
    "纯数字",
    "汉字+英文",
    "汉字+英文+中英文标点",
    "全类型混合",
]


def _chinese_pool():
    """生成GB2312一级常用汉字（约3755个常见汉字，拼音排序）"""
    chars = []
    for high in range(0xB0, 0xD8):
        for low in range(0xA1, 0xFF):
            try:
                char = bytes([high, low]).decode('gb2312')
                chars.append(char)
            except Exception:
                continue
    return "".join(chars)


_CHINESE_CACHE = None


def _get_chinese_pool():
    global _CHINESE_CACHE
    if _CHINESE_CACHE is None:
        _CHINESE_CACHE = _chinese_pool()
    return _CHINESE_CACHE


def generate_text(length, text_type="汉字+英文+中英文标点"):
    length = int(length)
    if length < 1:
        raise ValueError("长度必须大于0")

    if text_type == "纯汉字":
        return "".join(random.choices(_get_chinese_pool(), k=length))
    if text_type == "纯英文":
        return "".join(random.choices(ENGLISH_LETTERS, k=length))
    if text_type == "纯数字":
        return "".join(random.choices(DIGITS, k=length))
    if text_type == "汉字+英文":
        cjk = _get_chinese_pool()
        return "".join(random.choices(cjk + ENGLISH_LETTERS, k=length))

    # 汉字+英文+中英文标点 / 全类型混合 → 分层抽样，保证各类别都有
    if text_type == "汉字+英文+中英文标点":
        pools = [
            (_get_chinese_pool(), 0.50),
            (ENGLISH_LETTERS, 0.30),
            (CHINESE_PUNCT, 0.10),
            (ENGLISH_PUNCT, 0.10),
        ]
    else:  # 全类型混合
        pools = [
            (_get_chinese_pool(), 0.40),
            (ENGLISH_LETTERS, 0.25),
            (DIGITS, 0.15),
            (CHINESE_PUNCT, 0.10),
            (ENGLISH_PUNCT, 0.10),
        ]

    chars = []
    remaining = length
    for pool, ratio in pools:
        n = int(length * ratio)
        if n > remaining:
            n = remaining
        if n > 0:
            chars.extend(random.choices(pool, k=n))
        remaining -= n

    # 补齐剩余（浮点误差等）
    fallback = _get_chinese_pool() + ENGLISH_LETTERS
    while len(chars) < length:
        chars.append(random.choice(fallback))

    random.shuffle(chars)
    return "".join(chars)


if __name__ == "__main__":
    import sys

    n = int(sys.argv[1]) if len(sys.argv) > 1 else 100
    t = sys.argv[2] if len(sys.argv) > 2 else "全类型混合"
    print(generate_text(n, t))
