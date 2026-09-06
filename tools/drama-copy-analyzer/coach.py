from __future__ import annotations

import re
from typing import Dict, List

from analyzer import MODULE_TITLES, analyze as base_analyze
from rewriter import generate_rewrite


def _sentences(text: str) -> List[str]:
    parts = re.split(r"(?<=[。！？!?；;])|\n+", text.replace("\r\n", "\n").replace("\r", "\n"))
    return [p.strip() for p in parts if p.strip()]


def _clip(s: str, n: int = 46) -> str:
    s = re.sub(r"\s+", " ", s).strip()
    return s if len(s) <= n else s[: n - 1] + "…"


def _longest(sentences: List[str]) -> str:
    return max(sentences, key=lambda s: len(re.sub(r"\s", "", s))) if sentences else ""


def _first_quote(text: str) -> str:
    m = re.search(r"[-\d.\s]*([^\n]{6,80}[。！？!?])", text)
    return m.group(1).strip() if m else ""


def _coach_a(raw: str, sentences: List[str]) -> str:
    first = sentences[0] if sentences else ""
    score_match = re.search(r"评分：(\d+)/100", raw)
    score = int(score_match.group(1)) if score_match else 0
    if score >= 75:
        verdict = "这个开头能用，先别继续堆背景。"
        improve = "只删解释词，把最反常的结果和人物动作留在第一句。"
    elif score >= 55:
        verdict = "有钩子，但第一口还不够狠。"
        improve = "把后面最强的冲突/反转提前半句，让观众先看到结果，再补原因。"
    else:
        verdict = "开头偏交代，短剧口播容易在前3秒掉人。"
        improve = "第一句不要先介绍人物背景，直接抛异常结果、冲突或身份信息差。"
    return (
        f"【老师批改】\n原句：「{_clip(first)}」\n"
        f"判断：{verdict}\n怎么改一句更好：{improve}\n\n{raw}"
    )


def _coach_b(raw: str) -> str:
    lines = raw.splitlines()
    out: List[str] = ["【老师批改】结构不是看段落位置硬套标签，要看这一段在剧情里干什么。"]
    for line in lines:
        if not line.startswith("["):
            if line.strip():
                out.append(line)
            continue
        out.append(line)
        tag = line[1:].split("｜", 1)[0].split("]", 1)[0]
        quote = line.split("]", 1)[-1].strip()
        if tag == "钩子":
            note = "这段承担留人任务。好处是先给异常/冲突；如果还能再短一点，口播会更利落。"
        elif tag == "铺垫":
            note = "这是交代信息，不是钩子。只留后面冲突必须知道的背景，其余能删就删。"
        elif tag == "冲突":
            note = "这段有对立动作。最好再补清失败代价，让冲突不只是嘴上吵。"
        elif tag == "反转":
            note = "这段负责翻预期。前面要埋一点线索，这里再一次揭开，反转会更站得住。"
        elif tag == "催行动作":
            note = "这段负责续看。优先留剧情问题，不要同时喊点赞关注评论。"
        else:
            note = "作用不够明确。要么并到前后段，要么补一个明确动作。"
        out.append(f"↳ 批改「{_clip(quote)}」：{note}")
    return "\n".join(out)


def _coach_c(raw: str) -> str:
    if "未识别到明确冲突" in raw:
        return "【老师批改】这篇最大问题是没有能拍出来的对立动作。不要只写情绪，补“谁做了什么、主角会失去什么”。\n\n" + raw
    return "【老师批改】下面这些句子是能直接拿来做冲突镜头的。优先保留动作最具体、代价最清楚的那一条，弱冲突不要重复堆。\n\n" + raw


def _coach_d(raw: str, sentences: List[str]) -> str:
    urgent = raw.count("[紧迫]")
    neutral = raw.count("[中性]")
    if neutral > max(2, len(sentences) // 2):
        note = "中性句偏多，画面会像顺叙。把冲突前后的两三句压短，给反转留一个明显峰值。"
    elif urgent >= 2:
        note = "紧迫点够，但别全程都顶着。冲突前留一小段安静铺垫，反转会更炸。"
    else:
        note = "情绪有起伏，但峰值还可以更清楚。冲突句、反转句尽量独立成段。"
    return f"【老师批改】{note}\n\n{raw}"


def _coach_e(raw: str, sentences: List[str]) -> str:
    longest = _longest(sentences)
    if longest:
        note = f"最长的一句是「{_clip(longest)}」。如果配音时一口气读不顺，直接按逗号拆成“动作一句 + 后果一句”。"
    else:
        note = "没有可批改句子。"
    return f"【老师批改】{note}\n短剧口播不是越碎越好：冲突和反转要短，解释句可以稍长，但别连续三四句都一个节奏。\n\n{raw}"


def _coach_f(raw: str) -> str:
    quote = _first_quote(raw)
    note = f"封面/卡点优先从「{_clip(quote)}」这类有结果或反差的句子里挑，不要拿纯背景句做标题。" if quote else "金句优先选有结果、反差、身份差或明确问题的句子。"
    return f"【老师批改】{note}\n高频词只代表这篇文案反复在讲什么，不代表这些词本身就有流量。\n\n{raw}"


def _coach_g(raw: str) -> str:
    return "【老师批改】这里不是让你照抄原文，而是把这篇为什么能成立拆成“人物关系 + 冲突动作 + 反转证据 + 收尾问题”。换题材时换人、换事、换证据，只保留信息顺序。\n\n" + raw


def _coach_h(raw: str) -> str:
    return "【老师批改】下面每条都按原句下刀。优先先改前3条，再重新念一遍口播；不要一次把全文改得面目全非。\n\n" + raw


def analyze(text: str) -> Dict[str, str]:
    result = base_analyze(text)
    sentences = _sentences(text)
    result["A"] = _coach_a(result["A"], sentences)
    result["B"] = _coach_b(result["B"])
    result["C"] = _coach_c(result["C"])
    result["D"] = _coach_d(result["D"], sentences)
    result["E"] = _coach_e(result["E"], sentences)
    result["F"] = _coach_f(result["F"])
    result["G"] = _coach_g(result["G"])
    result["H"] = _coach_h(result["H"])
    return result


def build_report(text: str, result: Dict[str, str], rewrite: str = "") -> str:
    sections = ["# 短剧文案拆解报告｜加强版", "", "## 原文", "", text.strip() or "（空）", ""]
    for key, title in MODULE_TITLES:
        sections.extend([f"## {key}. {title}", "", result.get(key, ""), ""])
    if rewrite:
        sections.extend(["## 一键改写稿", "", rewrite.strip(), ""])
    sections.append("---\n说明：本报告与改写稿均由本地规则/模板启发式生成，不调用远程 API、不上传文案；用于辅助试拍与改稿，不保证爆款。")
    return "\n".join(sections).strip() + "\n"


def analyze_and_rewrite(text: str) -> tuple[Dict[str, str], str]:
    result = analyze(text)
    rewrite = generate_rewrite(text, result)
    return result, rewrite
