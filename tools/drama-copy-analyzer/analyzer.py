from __future__ import annotations

import math
import re
from collections import Counter
from dataclasses import dataclass
from typing import Dict, List, Tuple


MODULE_TITLES = [
    ("A", "开头钩子"),
    ("B", "结构标注"),
    ("C", "冲突点列表"),
    ("D", "情绪起伏"),
    ("E", "句段节奏"),
    ("F", "高频词 Top10 + 金句候选"),
    ("G", "可复用模板"),
    ("H", "改写建议"),
]

STOP_WORDS = {
    "我们", "你们", "他们", "自己", "一个", "这个", "那个", "就是", "不是", "没有", "还有", "已经", "因为", "所以",
    "但是", "然后", "如果", "还是", "什么", "怎么", "可以", "可能", "真的", "现在", "后来", "结果", "时候", "这样",
    "一下", "一直", "开始", "突然", "竟然", "只是", "为了", "的话", "这里", "那里", "今天", "昨天", "明天", "于是",
}

CONFLICT_WORDS = ("却", "但", "但是", "没想到", "谁知", "偏偏", "竟然", "反而", "直到", "突然", "原来", "结果", "不料", "可是", "然而", "才发现", "转身", "下一秒")
NEG_WORDS = ("死", "哭", "恨", "骗", "背叛", "失去", "赶走", "拒绝", "崩溃", "威胁", "失败", "欠", "穷", "痛", "怕", "危险", "秘密", "离婚", "分手", "报复")
POS_WORDS = ("赢", "笑", "爱", "成功", "原谅", "重逢", "救", "真相", "希望", "幸福", "逆袭", "证明", "惊喜", "拿回")
URGENT_WORDS = ("立刻", "马上", "快", "赶紧", "只剩", "最后", "下一秒", "突然", "现在", "来不及", "必须", "倒计时", "冲", "跑")
CTA_WORDS = ("关注", "点赞", "评论", "收藏", "转发", "下一集", "主页", "继续看", "告诉我", "想知道", "点个")
HOOK_WORDS = ("没想到", "竟然", "千万", "如果", "你敢信", "谁能想到", "直到", "第一天", "刚", "只因", "为了", "真相", "秘密", "所有人")


def _clean(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _sentences(text: str) -> List[str]:
    parts = re.split(r"(?<=[。！？!?；;])|\n+", text)
    return [p.strip(" \t\n") for p in parts if p.strip(" \t\n")]


def _paragraphs(text: str) -> List[str]:
    ps = [p.strip() for p in re.split(r"\n\s*\n|\n", text) if p.strip()]
    return ps or ([text] if text else [])


def _visible_len(s: str) -> int:
    return len(re.sub(r"\s|[，。！？、；：“”‘’（）()【】\[\]…—,.!?;:'\"-]", "", s))


def _has_any(s: str, words: Tuple[str, ...] | List[str]) -> bool:
    return any(w in s for w in words)


def _hook_analysis(sentences: List[str]) -> str:
    opening = sentences[:3]
    if not opening:
        return "评分：0/100\n点评：没有可分析文本。"
    joined = "".join(opening)
    score = 38
    reasons = []
    if _has_any(joined, HOOK_WORDS):
        score += 20; reasons.append("有悬念词")
    if _has_any(joined, CONFLICT_WORDS) or _has_any(joined, NEG_WORDS):
        score += 18; reasons.append("冲突/负向情绪较早出现")
    if "？" in joined or "?" in joined:
        score += 10; reasons.append("用提问制造信息差")
    if "！" in joined or "!" in joined:
        score += 5; reasons.append("情绪强度较高")
    if any(_visible_len(s) <= 18 for s in opening):
        score += 7; reasons.append("至少有一句短句")
    if sum(_visible_len(s) for s in opening) > 90:
        score -= 12; reasons.append("前3句偏长")
    score = max(0, min(100, score))
    dimensions = []
    dimensions.append("悬念" if (_has_any(joined, HOOK_WORDS) or "？" in joined) else "悬念偏弱")
    dimensions.append("冲突" if (_has_any(joined, CONFLICT_WORDS) or _has_any(joined, NEG_WORDS)) else "冲突偏弱")
    dimensions.append("利益点" if re.search(r"省|赚|学会|方法|秘诀|免费|避坑|拿到|解决", joined) else "利益点不明显")
    dimensions.append("情绪" if (_has_any(joined, NEG_WORDS) or _has_any(joined, POS_WORDS) or "！" in joined) else "情绪偏平")
    comment = "、".join(dimensions) + "。"
    if reasons:
        comment += " 依据：" + "；".join(reasons) + "。"
    return "前1–3句：\n" + "\n".join(f"- {s}" for s in opening) + f"\n\n评分：{score}/100\n点评：{comment}"


def _structure_analysis(paragraphs: List[str], sentences: List[str]) -> str:
    if not paragraphs:
        return "弱/缺失：无文本。"
    tagged = []
    total = len(paragraphs)
    found = {"钩子": False, "铺垫": False, "冲突": False, "反转": False, "催行动作": False}
    for i, p in enumerate(paragraphs):
        ratio = i / max(1, total - 1)
        if i == 0:
            tag = "钩子"; found[tag] = True
        elif _has_any(p, CTA_WORDS):
            tag = "催行动作"; found[tag] = True
        elif _has_any(p, ("原来", "没想到", "谁知", "竟然", "才发现", "反而", "真正", "真相")) and ratio >= 0.35:
            tag = "反转"; found[tag] = True
        elif _has_any(p, CONFLICT_WORDS) or _has_any(p, NEG_WORDS):
            tag = "冲突"; found[tag] = True
        else:
            tag = "铺垫"; found[tag] = True
        tagged.append(f"[{tag}] {p}")
    missing = [k for k, v in found.items() if not v]
    tail = "\n\n弱/缺失：" + ("、".join(missing) if missing else "无明显缺失")
    return "\n\n".join(tagged) + tail


def _conflicts(sentences: List[str]) -> str:
    items = []
    for s in sentences:
        reason = None
        hit = next((w for w in CONFLICT_WORDS if w in s), None)
        if hit:
            reason = f"包含转折/反转触发词“{hit}”，前后预期发生变化"
        elif _has_any(s, NEG_WORDS):
            reason = "包含损失、对立或压力信息，形成角色目标阻力"
        if reason:
            items.append((s, reason))
    if not items:
        return "未识别到明确冲突/转折句。建议补一个“目标 + 阻力 + 代价”的具体事件。"
    return "\n\n".join(f"{i+1}. {s}\n   为什么算冲突：{r}" for i, (s, r) in enumerate(items[:12]))


def _emotion_label(s: str) -> str:
    scores = {
        "紧迫": sum(s.count(w) for w in URGENT_WORDS),
        "负向": sum(s.count(w) for w in NEG_WORDS),
        "正向": sum(s.count(w) for w in POS_WORDS),
    }
    label, value = max(scores.items(), key=lambda kv: kv[1])
    return label if value > 0 else "中性"


def _emotion(sentences: List[str]) -> str:
    if not sentences:
        return "无文本。"
    labels = [_emotion_label(s) for s in sentences]
    lines = [f"{i+1}. [{labels[i]}] {s}" for i, s in enumerate(sentences)]
    first = labels[:max(1, len(labels)//3)]
    last = labels[-max(1, len(labels)//3):]
    energy = {"紧迫": 3, "负向": 2, "正向": 2, "中性": 1}
    f = sum(energy[x] for x in first) / len(first)
    l = sum(energy[x] for x in last) / len(last)
    if f > l + .35:
        desc = "前紧后松"
    elif l > f + .35:
        desc = "前缓后紧"
    elif labels.count("中性") / len(labels) > .6:
        desc = "整体偏平"
    else:
        desc = "起伏较均衡"
    return f"节奏描述：{desc}。\n\n" + "\n".join(lines)


def _rhythm(text: str, sentences: List[str], paragraphs: List[str]) -> str:
    lengths = [_visible_len(s) for s in sentences]
    total_chars = _visible_len(text)
    avg = (sum(lengths) / len(lengths)) if lengths else 0
    short_ratio = (sum(1 for n in lengths if n <= 15) / len(lengths) * 100) if lengths else 0
    long_ratio = (sum(1 for n in lengths if n >= 35) / len(lengths) * 100) if lengths else 0
    if not lengths:
        verdict = "无可分析句段"
    elif short_ratio >= 70:
        verdict = "短句占比很高，节奏快，但可能过碎；建议保留关键短句，把连续解释句适当合并。"
    elif long_ratio >= 35 or avg >= 30:
        verdict = "句子偏长，口播容易拖；建议拆分因果、动作和反转信息。"
    else:
        verdict = "长短句比例基本可用，重点检查冲突前后的句长变化。"
    return (
        f"总字数：{total_chars}\n句数：{len(sentences)}\n平均句长：{avg:.1f} 字\n"
        f"短句占比（≤15字）：{short_ratio:.1f}%\n长句占比（≥35字）：{long_ratio:.1f}%\n段落数：{len(paragraphs)}\n\n判断：{verdict}"
    )


def _keywords(text: str) -> List[Tuple[str, int]]:
    cleaned = re.sub(r"[^\u4e00-\u9fffA-Za-z0-9]", "", text)
    words = re.findall(r"[A-Za-z0-9]{2,}|[\u4e00-\u9fff]{2,4}", cleaned)
    counter = Counter(w for w in words if w not in STOP_WORDS and not all(ch in "的一了是在我你他她它也都就又而与及把被让很更最还" for ch in w))
    if len(counter) < 10:
        chars = [c for c in cleaned if "\u4e00" <= c <= "\u9fff" and c not in "的一了是在我你他她它也都就又而与及把被让很更最还"]
        counter.update(chars)
    return counter.most_common(10)


def _golden(sentences: List[str]) -> List[str]:
    def score(s: str) -> float:
        n = _visible_len(s)
        length_score = 20 if 10 <= n <= 28 else max(0, 18 - abs(n - 20) * .6)
        trigger = 8 * sum(1 for w in CONFLICT_WORDS + HOOK_WORDS + NEG_WORDS + POS_WORDS if w in s)
        punct = 5 if ("！" in s or "？" in s or "，" in s) else 0
        return length_score + trigger + punct
    ranked = sorted((s for s in sentences if 7 <= _visible_len(s) <= 42), key=score, reverse=True)
    result = []
    for s in ranked:
        if s not in result:
            result.append(s)
        if len(result) == 5:
            break
    return result[:max(3, min(5, len(result)))] if result else []


def _freq_and_quotes(text: str, sentences: List[str]) -> str:
    kws = _keywords(text)
    gold = _golden(sentences)
    kw_text = "、".join(f"{w}({c})" for w, c in kws) if kws else "无"
    gold_text = "\n".join(f"- {s}" for s in gold) if gold else "- 暂无合适金句，建议补一句包含冲突或结果的独立短句。"
    return f"高频词 Top10：\n{kw_text}\n\n金句候选：\n{gold_text}"


def _template(sentences: List[str]) -> str:
    if not sentences:
        return "无文本。"
    return (
        "1. 钩子：[角色/身份] + [异常事件/反常结果] + [信息缺口]\n"
        "   例：所有人都以为【___】，直到【___】发生。\n\n"
        "2. 铺垫：[目标] + [当前处境] + [关键关系]\n"
        "   例：为了【___】，主角只能【___】，而【关键人物】一直【___】。\n\n"
        "3. 冲突：[阻力人物/事件] + [具体动作] + [损失或代价]\n"
        "   例：就在【___】时，【___】突然【___】，主角将失去【___】。\n\n"
        "4. 反转：[隐藏信息/身份/证据] 被揭开 + 前文重新解释\n"
        "   例：可下一秒，众人才发现【___】，原来【___】。\n\n"
        "5. 催行动作：[下一步悬念] + [轻量CTA]\n"
        "   例：【关键问题】到底会怎么解决？下一段继续拆。"
    )


def _advice(text: str, sentences: List[str], paragraphs: List[str]) -> str:
    if not sentences:
        return "1. 先补充正文，再进行针对性改写。"
    advice = []
    opening = "".join(sentences[:3])
    if not (_has_any(opening, HOOK_WORDS) or _has_any(opening, CONFLICT_WORDS) or "？" in opening):
        advice.append("开头第1–3句：把背景说明后移，第一句先抛“异常结果/冲突/秘密”，让观众先产生信息缺口；原因是当前开头进入事件太慢。")
    conflicts = [s for s in sentences if _has_any(s, CONFLICT_WORDS) or _has_any(s, NEG_WORDS)]
    if len(conflicts) < 2:
        advice.append("正文中段：至少补一处具体阻力和代价，不要只写情绪；建议写清“谁阻止谁、做了什么、主角会失去什么”，否则冲突强度不足。")
    reversals = [s for s in sentences if _has_any(s, ("原来", "没想到", "才发现", "竟然", "反而", "真相"))]
    if not reversals:
        advice.append("后半段：增加一次能重新解释前文的反转，优先用身份、证据、误会或目标变化；原因是目前缺少二次留存点。")
    lengths = [_visible_len(s) for s in sentences]
    avg = sum(lengths) / len(lengths)
    if avg > 28:
        advice.append(f"全篇句长：当前平均约 {avg:.1f} 字；把超过35字的句子拆成“动作一句 + 后果一句”，降低口播负担并突出信息点。")
    short_ratio = sum(1 for n in lengths if n <= 15) / len(lengths)
    if short_ratio > .75:
        advice.append("句段连接：短句占比过高，连续三四个解释短句可合并成一个因果句；保留冲突句和反转句为独立短句，避免节奏碎成字幕点读。")
    if not any(_has_any(s, CTA_WORDS) for s in sentences[-3:]):
        advice.append("结尾最后1–3句：补“下一步未解决问题 + 轻CTA”，不要只喊关注；让动作与剧情悬念绑定，减少生硬营销感。")
    if len(paragraphs) <= 2 and len(sentences) >= 8:
        advice.append("段落层级：把正文按“铺垫/冲突/反转”至少切成3段，方便剪辑时直接按情节点找镜头和卡点。")
    kws = _keywords(text)
    if kws:
        top = "、".join(w for w, _ in kws[:3])
        advice.append(f"核心词聚焦：当前高频集中在“{top}”；标题/封面优先提炼其中一个与冲突结果组合，不要把多个信息点同时塞进标题。")
    advice = advice[:8]
    while len(advice) < 3:
        advice.append("关键节点：挑出最强的一句冲突句，把它前移或单独成段，并删掉前后重复解释，让事件本身承担说服力。")
    return "\n\n".join(f"{i+1}. {x}" for i, x in enumerate(advice))


def analyze(text: str) -> Dict[str, str]:
    text = _clean(text)
    sentences = _sentences(text)
    paragraphs = _paragraphs(text)
    return {
        "A": _hook_analysis(sentences),
        "B": _structure_analysis(paragraphs, sentences),
        "C": _conflicts(sentences),
        "D": _emotion(sentences),
        "E": _rhythm(text, sentences, paragraphs),
        "F": _freq_and_quotes(text, sentences),
        "G": _template(sentences),
        "H": _advice(text, sentences, paragraphs),
    }


def build_report(text: str, result: Dict[str, str]) -> str:
    sections = ["# 短剧文案拆解报告", "", "## 原文", "", text.strip() or "（空）", ""]
    for key, title in MODULE_TITLES:
        sections.extend([f"## {key}. {title}", "", result.get(key, ""), ""])
    sections.append("---\n说明：本报告由本地规则/启发式分析生成，用于辅助创作判断，不保证作品成为爆款。")
    return "\n".join(sections).strip() + "\n"
