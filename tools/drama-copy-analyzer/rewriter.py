from __future__ import annotations

import re
from typing import Dict, List, Tuple


HOOK_WORDS = ("没想到", "谁也没想到", "竟然", "直到", "真相", "秘密", "所有人都以为", "你敢信")
CONFLICT_WORDS = ("嘲笑", "威胁", "拒绝", "赶走", "背叛", "抢走", "换掉", "离婚", "分手", "看不起", "不许", "必须", "否则")
REVERSAL_WORDS = ("原来", "才发现", "真正", "正是", "竟然", "没想到", "名字", "身份", "负责人", "甲方", "合同", "证据")
CTA_WORDS = ("下一集", "继续看", "关注", "点赞", "评论", "收藏")
FILLERS = ("其实", "然后", "就是", "真的", "可以说", "我们都知道", "大家都知道")


def _sentences(text: str) -> List[str]:
    text = text.replace("\r\n", "\n").replace("\r", "\n").strip()
    parts = re.split(r"(?<=[。！？!?；;])|\n+", text)
    return [p.strip() for p in parts if p.strip()]


def _clip(s: str, n: int = 42) -> str:
    s = re.sub(r"\s+", " ", s).strip()
    return s if len(s) <= n else s[: n - 1] + "…"


def _score(s: str, words: Tuple[str, ...]) -> int:
    return sum(3 for w in words if w in s) + (2 if "？" in s or "?" in s else 0) + (1 if len(s) <= 34 else 0)


def _clean_sentence(s: str) -> str:
    out = s.strip()
    for filler in FILLERS:
        out = out.replace(filler, "")
    out = re.sub(r"，{2,}", "，", out)
    out = re.sub(r"^[，。；、\s]+", "", out)
    return out.strip()


def _ensure_punct(s: str) -> str:
    if not s:
        return s
    return s if s[-1] in "。！？!?；;”’" else s + "。"


def _pick_best(sentences: List[str], words: Tuple[str, ...], start: int = 0) -> int:
    if not sentences:
        return -1
    candidates = range(start, len(sentences))
    return max(candidates, key=lambda i: (_score(sentences[i], words), i))


def generate_rewrite(text: str, analysis: Dict[str, str] | None = None) -> str:
    """纯本地规则 + 模板生成完整改写稿，不调用任何远程服务。"""
    sentences = _sentences(text)
    if not sentences:
        return ""

    hook_pool = sentences[: min(3, len(sentences))]
    hook_idx = max(range(len(hook_pool)), key=lambda i: _score(hook_pool[i], HOOK_WORDS + CONFLICT_WORDS))
    conflict_idx = _pick_best(sentences, CONFLICT_WORDS)
    reversal_start = max(1, len(sentences) // 3)
    reversal_idx = _pick_best(sentences, REVERSAL_WORDS, reversal_start)

    ending_idx = len(sentences) - 1
    if not ("？" in sentences[ending_idx] or "?" in sentences[ending_idx] or any(w in sentences[ending_idx] for w in CTA_WORDS)):
        for i in range(len(sentences) - 1, max(-1, len(sentences) - 4), -1):
            if "？" in sentences[i] or "?" in sentences[i] or any(w in sentences[i] for w in CTA_WORDS):
                ending_idx = i
                break

    used = set()
    rewritten: List[str] = []
    changes: List[str] = []

    original_hook = _clean_sentence(sentences[hook_idx])
    if _score(original_hook, HOOK_WORDS + CONFLICT_WORDS) >= 4:
        new_hook = original_hook
        changes.append(f"钩子：保留原文强钩子「{_clip(sentences[hook_idx])}」，只做口播去赘词。")
    else:
        source_idx = reversal_idx if reversal_idx >= 0 and _score(sentences[reversal_idx], REVERSAL_WORDS) >= 3 else conflict_idx
        source = _clean_sentence(sentences[source_idx]) if source_idx >= 0 else original_hook
        new_hook = f"谁也没想到，{source.rstrip('。！？!?')}。"
        changes.append(f"钩子：原句「{_clip(sentences[hook_idx])}」偏铺垫，改为提前预告「{_clip(source)}」制造信息差。")
    rewritten.append(_ensure_punct(new_hook))
    used.add(hook_idx)

    # 钩子后最多保留两句必要铺垫，避免一上来堆背景。
    setup_candidates = [i for i in range(len(sentences)) if i not in {hook_idx, conflict_idx, reversal_idx, ending_idx}]
    for i in setup_candidates[:2]:
        cleaned = _clean_sentence(sentences[i])
        if cleaned:
            rewritten.append(_ensure_punct(cleaned))
            used.add(i)

    if conflict_idx >= 0 and conflict_idx not in used:
        conflict = _clean_sentence(sentences[conflict_idx])
        if len(conflict) > 44 and "，" in conflict:
            left, right = conflict.split("，", 1)
            rewritten.extend([_ensure_punct(left), _ensure_punct(right)])
            changes.append(f"冲突：把长句「{_clip(sentences[conflict_idx])}」拆成动作一句、后果一句，让剪辑更好卡点。")
        else:
            rewritten.append(_ensure_punct(conflict))
            changes.append(f"冲突：把原文最强冲突句「{_clip(sentences[conflict_idx])}」前置并单独成段。")
        used.add(conflict_idx)

    # 其余剧情按原顺序补回，但把明确反转留到后面单独兑现。
    for i, s in enumerate(sentences):
        if i in used or i in {reversal_idx, ending_idx}:
            continue
        cleaned = _clean_sentence(s)
        if cleaned:
            rewritten.append(_ensure_punct(cleaned))
            used.add(i)

    if reversal_idx >= 0 and reversal_idx not in used:
        reversal = _clean_sentence(sentences[reversal_idx])
        if not re.match(r"^(可|但|直到|原来|下一秒)", reversal):
            reversal = "可下一秒，" + reversal
        rewritten.append(_ensure_punct(reversal))
        changes.append(f"反转：把「{_clip(sentences[reversal_idx])}」独立兑现，并用“可下一秒”拉出第二个留存点。")
        used.add(reversal_idx)

    ending = _clean_sentence(sentences[ending_idx]) if 0 <= ending_idx < len(sentences) else ""
    if ending:
        if "？" in ending or "?" in ending or any(w in ending for w in CTA_WORDS):
            rewritten.append(_ensure_punct(ending))
            changes.append(f"收尾：保留原文悬念「{_clip(sentences[ending_idx])}」，不额外叠加多个平台动作。")
        else:
            rewritten.append(_ensure_punct(ending))
            rewritten.append("事情还没结束。下一步，他会怎么选？")
            changes.append(f"收尾：原句「{_clip(sentences[ending_idx])}」收得太死，补一个未解问题做续看钩子。")

    # 去掉连续重复句。
    compact: List[str] = []
    seen = set()
    for s in rewritten:
        key = re.sub(r"[\s，。！？!?；;：:'‘’“”\"]", "", s)
        if not key or key in seen:
            continue
        seen.add(key)
        compact.append(s)

    script = "\n".join(compact)
    change_text = "\n".join(f"{i+1}. {item}" for i, item in enumerate(changes[:6]))
    return (
        "【完整改写稿｜可直接试拍】\n"
        + script
        + "\n\n【相对原文的关键改动】\n"
        + (change_text or "1. 主要做了去赘词、重排信息顺序和口播断句。")
        + "\n\n说明：改写稿由本地规则与模板启发式生成，建议试拍前再按人物设定和账号语气做人工微调。"
    )
