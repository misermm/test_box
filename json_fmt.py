#!/usr/bin/env python3
"""JSON格式化工具"""

import json
import difflib


def json_format(text):
    """将JSON文本美化（缩进、换行）"""
    obj = json.loads(text)
    return json.dumps(obj, ensure_ascii=False, indent=2)


def json_compact(text):
    """将JSON压缩为一行字符串"""
    obj = json.loads(text)
    return json.dumps(obj, ensure_ascii=False, separators=(',', ':'))


def json_sort(text):
    """将JSON对象的key递归排序后美化输出（数组保持原序）"""
    def _sort(obj):
        if isinstance(obj, dict):
            return {k: _sort(v) for k, v in sorted(obj.items())}
        if isinstance(obj, list):
            return [_sort(i) for i in obj]
        return obj
    return json.dumps(_sort(json.loads(text)), ensure_ascii=False, indent=2)


def json_diff_spans(text1, text2):
    """
    计算两段文本差异，返回 (left_spans, right_spans)

    每个span为 ((行, 列起), (行, 列止), kind)
    行号1-based（对应tk.Text索引），列0-based
    kind: 'line' 整行差异（橙底），'char' 字符差异（红字）
    left对应text1（删除/变更侧），right对应text2（新增/变更侧）
    """
    lines1 = text1.splitlines()
    lines2 = text2.splitlines()
    sm = difflib.SequenceMatcher(None, lines1, lines2, autojunk=False)
    left, right = [], []

    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == 'equal':
            continue
        if tag == 'replace':
            for i in range(i1, i2):
                left.append((((i + 1, 0), (i + 1, "end"), "line")))
            for j in range(j1, j2):
                right.append((((j + 1, 0), (j + 1, "end"), "line")))
            # 字符级对比（按行序一一对应，多余行按整行差异处理）
            n = min(i2 - i1, j2 - j1)
            for k in range(n):
                _char_spans(lines1[i1 + k], lines2[j1 + k],
                            i1 + k, j1 + k, left, right)
        elif tag == 'delete':
            for i in range(i1, i2):
                left.append((((i + 1, 0), (i + 1, "end"), "line")))
        elif tag == 'insert':
            for j in range(j1, j2):
                right.append((((j + 1, 0), (j + 1, "end"), "line")))

    return left, right


def _char_spans(old_line, new_line, li, rj, left, right):
    """对比单行，把差异字符位置追加到left/right"""
    sm = difflib.SequenceMatcher(None, old_line, new_line, autojunk=False)
    for tag, a1, a2, b1, b2 in sm.get_opcodes():
        if tag == 'equal':
            continue
        if a2 > a1:
            left.append((((li + 1, a1), (li + 1, a2), "char")))
        if b2 > b1:
            right.append((((rj + 1, b1), (rj + 1, b2), "char")))


if __name__ == "__main__":
    s = '{"name":"张三","scores":[98,100,null]}'
    print("美化:")
    print(json_format(s))
    print("\n压缩:")
    print(json_compact(s))
