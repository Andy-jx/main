from __future__ import annotations

import re
from collections import Counter
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

CONFLICT_WORDS = ("却", "但", "但是", "没想到", "谁知", "偏偏", "竟然", "反而", "突然", "结果", "不料", "可是", "然而", "转身", "下一秒")
REVERSAL_WORDS = ("原来", "才发现", "真正", "真相", "没想到", "竟然", "反而", "直到这时", "身份", "其实")
BACKGROUND_WORDS = ("三年前", "从前", "以前", "当时", "一直", "原本", "原来", "曾经", "为了", "因为", "从小", "每天", "这些年", "之前")
NEG_WORDS = ("死", "哭", "恨", "骗", "背叛", "失去", "赶走", "拒绝", "崩溃", "威胁", "失败", "欠", "穷", "痛", "怕", "危险", "秘密", "离婚", "分手", "报复", "嘲笑", "看不起")
POS_WORDS = ("赢", "笑", "爱", "成功", "原谅", "重逢", "救", "真相", "希望", "幸福", "逆袭", "证明", "惊喜", "拿回")
URGENT_WORDS = ("立刻", "马上", "快", "赶紧", "只剩", "最后", "下一秒", "突然", "现在", "来不及", "必须", "倒计时", "冲", "跑")
CTA_WORDS = ("关注", "点赞", "评论", "收藏", "转发", "下一集", "主页", "继续看", "告诉我", "想知道", "点个", "下集")
HOOK_WORDS = ("没想到", "竟然", "千万", "如果", "你敢信", "谁能想到", "直到", "第一天", "刚", "只因", "真相", "秘密", "所有人", "谁也没想到", "万万没想到")
IDENTITY_WORDS = ("总裁", "老板", "董事长", "甲方", "负责人", "继承人", "千金", "少爷", "身份", "主位", "合同", "名字", "秘书")
PRESSURE_WORDS = ("威胁", "拒绝", "赶走", "嘲笑", "逼", "抢", "打", "骂", "背叛", "离婚", "分手", "看不起", "羞辱")


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


def _clip(s: str, limit: int = 72) -> str:
    s = s.strip()
    return s if len(s) <= limit else s[: limit - 1] + "…"


def _hook_score_sentence(s: str, index: int = 0) -> int:
    score = 24
    if index <= 1:
        score += 12
    if _has_any(s, HOOK_WORDS):
        score += 22
    if _has_any(s, CONFLICT_WORDS) or _has_any(s, NEG_WORDS):
        score += 18
    if "？" in s or "?" in s:
        score += 12
    if "！" in s or "!" in s:
        score += 5
    if _visible_len(s) <= 24:
        score += 8
    if _visible_len(s) > 55:
        score -= 10
    return max(0, min(100, score))


def _hook_analysis(sentences: List[str]) -> str:
    opening = sentences[:3]
    if not opening:
        return "评分：0/100\n点评：没有可分析文本。"
    joined = "".join(opening)
    score = max(_hook_score_sentence(s, i) for i, s in enumerate(opening))
    if len(opening) >= 2 and (_has_any(joined, HOOK_WORDS) or _has_any(joined, CONFLICT_WORDS)):
        score = min(100, score + 5)
    dimensions = []
    dimensions.append("有悬念" if (_has_any(joined, HOOK_WORDS) or "？" in joined or "?" in joined) else "悬念偏弱")
    dimensions.append("有冲突" if (_has_any(joined, CONFLICT_WORDS) or _has_any(joined, NEG_WORDS)) else "冲突偏弱")
    dimensions.append("有利益点" if re.search(r"省|赚|学会|方法|秘诀|免费|避坑|拿到|解决", joined) else "利益点不明显")
    dimensions.append("有情绪" if (_has_any(joined, NEG_WORDS) or _has_any(joined, POS_WORDS) or "！" in joined) else "情绪偏平")
    if sum(_visible_len(s) for s in opening) > 90:
        dimensions.append("前3句信息偏满")
    return "前1–3句：\n" + "\n".join(f"- {s}" for s in opening) + f"\n\n评分：{score}/100\n点评：" + "、".join(dimensions) + "。"


def _structure_scores(p: str, index: int, total: int) -> Dict[str, int]:
    ratio = index / max(1, total - 1)
    length = _visible_len(p)
    has_question = "？" in p or "?" in p

    hook = 0
    if ratio <= 0.30:
        hook += 3
    if _has_any(p, HOOK_WORDS):
        hook += 4
    if has_question and ratio <= 0.35:
        hook += 2
    if _has_any(p, CONFLICT_WORDS) or _has_any(p, NEG_WORDS):
        hook += 2
    if length <= 55:
        hook += 1

    setup = 0
    if ratio <= 0.65:
        setup += 2
    if _has_any(p, BACKGROUND_WORDS):
        setup += 4
    if re.search(r"为了|因为|原本|曾经|一直|当时|三年前|之前", p):
        setup += 2
    if not (_has_any(p, CONFLICT_WORDS) or _has_any(p, REVERSAL_WORDS) or _has_any(p, CTA_WORDS)):
        setup += 2

    conflict = 0
    if _has_any(p, PRESSURE_WORDS):
        conflict += 5
    if _has_any(p, CONFLICT_WORDS):
        conflict += 3
    if _has_any(p, NEG_WORDS):
        conflict += 3
    if re.search(r"不要|不许|必须|否则|失去|换掉|离开|当众|抢走", p):
        conflict += 2

    reversal = 0
    if _has_any(p, REVERSAL_WORDS):
        reversal += 5
    if ratio >= 0.30:
        reversal += 2
    if _has_any(p, IDENTITY_WORDS) and _has_any(p, ("真正", "原来", "才", "竟然", "名字", "主位")):
        reversal += 3
    if re.search(r"可.{0,12}(真正|却|竟|原来|才)", p):
        reversal += 2

    cta = 0
    if ratio >= 0.70:
        cta += 3
    if _has_any(p, CTA_WORDS):
        cta += 6
    if has_question and ratio >= 0.65:
        cta += 4

    return {"钩子": hook, "铺垫": setup, "冲突": conflict, "反转": reversal, "催行动作": cta}


def _structure_analysis(paragraphs: List[str], sentences: List[str]) -> str:
    if not paragraphs:
        return "弱/缺失：无文本。"

    tagged = []
    found = {"钩子": False, "铺垫": False, "冲突": False, "反转": False, "催行动作": False}
    total = len(paragraphs)

    for i, p in enumerate(paragraphs):
        scores = _structure_scores(p, i, total)
        tag, best = max(scores.items(), key=lambda kv: kv[1])
        thresholds = {"钩子": 5, "铺垫": 4, "冲突": 5, "反转": 6, "催行动作": 6}
        if best < thresholds[tag]:
            tag = "铺垫"
            best = scores["铺垫"]
        if tag == "钩子" and i > max(1, total // 3):
            tag = "铺垫"
        if tag == "催行动作" and i < max(1, total // 2):
            tag = "冲突" if scores["冲突"] >= 5 else "铺垫"

        found[tag] = True
        confidence = "强" if best >= 8 else "中" if best >= 5 else "弱"
        tagged.append(f"[{tag}｜{confidence}] {p}")

    explanations = {
        "钩子": "开头未检测到明显悬念/冲突/信息差",
        "铺垫": "缺少人物处境、关系或目标交代",
        "冲突": "缺少明确阻力、对立动作或损失",
        "反转": "缺少能重新解释前文的事实变化",
        "催行动作": "结尾缺少未解问题或轻量行动引导",
    }
    missing = [f"{key}（{explanations[key]}）" for key, ok in found.items() if not ok]
    return "\n\n".join(tagged) + "\n\n弱/缺失：" + ("；".join(missing) if missing else "无明显缺失")


def _conflict_score(s: str) -> int:
    score = 0
    score += 4 * sum(1 for w in PRESSURE_WORDS if w in s)
    score += 2 * sum(1 for w in CONFLICT_WORDS if w in s)
    score += 2 * sum(1 for w in NEG_WORDS if w in s)
    if re.search(r"不要|不许|必须|否则|失去|换掉|离开|当众", s):
        score += 2
    return score


def _conflicts(sentences: List[str]) -> str:
    items = []
    for s in sentences:
        reason = None
        hit = next((w for w in PRESSURE_WORDS if w in s), None)
        turn = next((w for w in CONFLICT_WORDS if w in s), None)
        if hit:
            reason = f"出现明确对立动作“{hit}”，角色目标受到直接阻力"
        elif turn:
            reason = f"包含转折/变化词“{turn}”，前后预期发生变化"
        elif _has_any(s, NEG_WORDS):
            reason = "包含损失、压力或关系破裂信息，形成剧情阻力"
        if reason:
            items.append((s, reason, _conflict_score(s)))
    if not items:
        return "未识别到明确冲突/转折句。建议补一个“目标 + 阻力 + 代价”的具体事件。"
    items.sort(key=lambda x: x[2], reverse=True)
    return "\n\n".join(f"{i+1}. {s}\n   为什么算冲突：{r}" for i, (s, r, _) in enumerate(items[:12]))


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
    chunks = re.findall(r"[A-Za-z0-9]{2,}|[\u4e00-\u9fff]{2,8}", text)
    counter: Counter[str] = Counter()
    for chunk in chunks:
        if re.fullmatch(r"[A-Za-z0-9]{2,}", chunk):
            counter[chunk.lower()] += 1
            continue
        if chunk in STOP_WORDS:
            continue
        max_n = min(4, len(chunk))
        for n in range(2, max_n + 1):
            for i in range(0, len(chunk) - n + 1):
                token = chunk[i:i+n]
                if token in STOP_WORDS:
                    continue
                if all(ch in "的一了是在我你他她它也都就又而与及把被让很更最还才会" for ch in token):
                    continue
                counter[token] += 1
    ranked = sorted(counter.items(), key=lambda kv: (kv[1], len(kv[0])), reverse=True)
    result = []
    for token, count in ranked:
        if any(token in existing or existing in token for existing, _ in result):
            continue
        result.append((token, count))
        if len(result) == 10:
            break
    return result


def _golden(sentences: List[str]) -> List[str]:
    def score(s: str) -> float:
        n = _visible_len(s)
        length_score = 20 if 10 <= n <= 28 else max(0, 18 - abs(n - 20) * .6)
        trigger = 8 * sum(1 for w in CONFLICT_WORDS + HOOK_WORDS + NEG_WORDS + POS_WORDS + REVERSAL_WORDS if w in s)
        punct = 5 if ("！" in s or "？" in s or "，" in s) else 0
        return length_score + trigger + punct
    ranked = sorted((s for s in sentences if 7 <= _visible_len(s) <= 46), key=score, reverse=True)
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


def _find_best(sentences: List[str], scorer) -> str:
    if not sentences:
        return ""
    return max(sentences, key=scorer)


def _hook_pattern(s: str) -> Tuple[str, str]:
    if "以为" in s and _has_any(s, ("直到", "没想到", "却", "竟然")):
        return "认知误判 → 反常事实", "【旁观者/对手】以为【主角的表面处境】，直到【打破认知的事实】出现。"
    if "？" in s or "?" in s:
        return "问题悬念 → 延迟答案", "【核心问题】先抛出来，但先不给答案，马上接【异常事件/风险】。"
    if _has_any(s, ("秘密", "真相", "身份")):
        return "秘密预告 → 信息差", "先告诉观众【存在一个秘密/隐藏身份】，但只揭一半，留下【关键缺口】。"
    if _has_any(s, CONFLICT_WORDS) or _has_any(s, NEG_WORDS):
        return "冲突先行 → 留结果", "第一句直接出现【对立动作/损失】，暂时不解释原因，把【结果】往后压。"
    return "异常状态 → 未解释原因", "先给【不正常的状态/结果】，再补【人物与原因】，不要从背景介绍起笔。"


def _conflict_pattern(s: str) -> Tuple[str, str]:
    if _has_any(s, PRESSURE_WORDS):
        return "角色施压 → 主角受阻", "【对手】用【具体动作】压制【主角目标】，并让主角面临【明确代价】。"
    if re.search(r"离婚|分手|背叛|前男友|前女友|丈夫|妻子", s):
        return "关系对立 → 公开碰撞", "先交代【旧关系】，再让【旧关系中的矛盾】在公开场合爆发。"
    return "目标出现阻力 → 代价升级", "【主角想要的东西】遇到【阻力】，如果失败就会失去【具体代价】。"


def _reversal_pattern(s: str) -> Tuple[str, str]:
    if _has_any(s, IDENTITY_WORDS):
        return "身份/权力揭示 → 强弱倒置", "前面先让观众相信【主角处于弱势】，后面用【身份/职位/权力证据】完成强弱翻转。"
    if re.search(r"证据|合同|名字|照片|录音|视频|真相", s):
        return "证据揭示 → 前文重解释", "先埋【误会/指控】，再用【证据】一次性重解释前文。"
    return "隐藏事实揭露 → 预期翻转", "在冲突后揭开【此前隐藏的信息】，让观众重新理解【前面的事件】。"


def _cta_pattern(s: str) -> Tuple[str, str]:
    if "？" in s or "?" in s:
        return "未解问题 → 下一段承诺", "结尾只留一个【二选一/结果问题】，再接【下一集/下一段】承诺。"
    if _has_any(s, CTA_WORDS):
        return "结果未揭晓 → 轻CTA", "先停在【未完成动作/未揭晓结果】，再给一个轻量【关注/下一集】动作。"
    return "未完成动作 → 留白", "停在【下一步即将发生的关键动作】，不要把结果一次说完。"


def _template(text: str, sentences: List[str]) -> str:
    if not sentences:
        return "无文本。"

    opening_pool = sentences[: min(3, len(sentences))]
    hook = max(enumerate(opening_pool), key=lambda x: _hook_score_sentence(x[1], x[0]))[1]
    conflict_candidates = [s for s in sentences if _conflict_score(s) > 0]
    conflict = _find_best(conflict_candidates, _conflict_score) if conflict_candidates else ""
    reversal_candidates = [s for s in sentences if _has_any(s, REVERSAL_WORDS) or (_has_any(s, IDENTITY_WORDS) and _has_any(s, ("真正", "名字", "主位", "才")))]
    reversal = _find_best(reversal_candidates, lambda s: 5 * sum(w in s for w in REVERSAL_WORDS) + 2 * sum(w in s for w in IDENTITY_WORDS)) if reversal_candidates else ""
    ending_pool = sentences[-3:]
    cta_candidates = [s for s in ending_pool if _has_any(s, CTA_WORDS) or "？" in s or "?" in s]
    cta = cta_candidates[-1] if cta_candidates else ending_pool[-1]

    hp, hs = _hook_pattern(hook)
    cp, cs = _conflict_pattern(conflict) if conflict else ("冲突偏弱", "补一段：【主角目标】遭遇【具体阻力】，失败会失去【明确代价】。")
    rp, rs = _reversal_pattern(reversal) if reversal else ("反转偏弱", "补一段：在冲突后揭开【隐藏事实/身份/证据】，重新解释前文。")
    ep, es = _cta_pattern(cta)

    kws = _keywords(text)[:4]
    focus = "、".join(w for w, _ in kws) if kws else "未提取到明显核心词"
    mode = " → ".join([hp.split(" → ")[0], cp.split(" → ")[0], rp.split(" → ")[0], ep.split(" → ")[0]])

    parts = [
        f"本文识别出的主打法：{mode}",
        f"本文核心词：{focus}",
        "",
        f"1. 钩子原型：{hp}",
        f"   来自原句：「{_clip(hook)}」",
        f"   可复用槽位：{hs}",
        "",
        f"2. 冲突原型：{cp}",
        f"   来自原句：「{_clip(conflict) if conflict else '本文未识别到足够强的冲突句'}」",
        f"   可复用槽位：{cs}",
        "",
        f"3. 反转原型：{rp}",
        f"   来自原句：「{_clip(reversal) if reversal else '本文未识别到明确反转句'}」",
        f"   可复用槽位：{rs}",
        "",
        f"4. 收尾原型：{ep}",
        f"   来自原句：「{_clip(cta)}」",
        f"   可复用槽位：{es}",
        "",
        "套用时只复用“信息顺序和冲突机制”，人物、身份、事件、证据和结果必须换成新内容。",
    ]
    return "\n".join(parts)


def _advice_item(location: str, original: str, how: str, why: str) -> str:
    return f"【{location}】\n原句：「{_clip(original)}」\n怎么改：{how}\n为什么：{why}"


def _advice(text: str, sentences: List[str], paragraphs: List[str]) -> str:
    if not sentences:
        return "1. 先补充正文，再进行针对性改写。"

    advice: List[str] = []
    opening = sentences[0]
    opening_score = _hook_score_sentence(opening, 0)
    trigger = next((w for w in HOOK_WORDS + CONFLICT_WORDS if w in opening), "反常结果")
    if opening_score < 65:
        advice.append(_advice_item("开头第1句", opening, f"把背景说明压缩，第一句末尾必须落到“{trigger}”对应的异常结果/冲突上；背景放到第2句以后。", f"当前首句钩子评分约 {opening_score}/100，信息差不足，容易在人物背景交代阶段掉人。"))
    else:
        advice.append(_advice_item("开头第1句", opening, "保留现有反差/悬念，不再继续往前加人物背景；如果要提速，只删解释词，不删结果词和转折词。", f"当前首句钩子已经较强（约 {opening_score}/100），主要风险不是不够猛，而是后续解释把首句优势稀释。"))

    conflict_candidates = [s for s in sentences if _conflict_score(s) > 0]
    if conflict_candidates:
        conflict = max(conflict_candidates, key=_conflict_score)
        how = "把这句拆成“对立动作一句 + 后果一句”，并让后果单独成段；不要把冲突、原因、解释挤在同一句。" if _visible_len(conflict) > 34 else "把这句单独成段，并在下一句立刻补“如果失败会失去什么/谁会受到什么后果”，把冲突从态度升级为代价。"
        advice.append(_advice_item("最强冲突句", conflict, how, "这句已经承担主要矛盾，单独强化它比再加一段泛情绪更有效。"))
    else:
        anchor = sentences[min(len(sentences) - 1, max(1, len(sentences)//2))]
        advice.append(_advice_item("正文中段", anchor, "紧接这句新增一个具体对立动作：谁阻止谁、做了什么、失败会失去什么。", "当前文本没有识别到足够强的冲突动作，中段容易只剩叙述。"))

    reversal_candidates = [s for s in sentences if _has_any(s, REVERSAL_WORDS) or (_has_any(s, IDENTITY_WORDS) and _has_any(s, ("真正", "名字", "主位", "才")))]
    if reversal_candidates:
        reversal = max(reversal_candidates, key=lambda s: sum(w in s for w in REVERSAL_WORDS) + sum(w in s for w in IDENTITY_WORDS))
        advice.append(_advice_item("反转句", reversal, "在它前面提前埋一个同类细节（身份线索/证据/称呼/动作），但不要提前解释；到这句再一次揭开。", "这样反转会从“突然告诉观众答案”变成“前面有伏笔、此处完成兑现”，可信度和二次留存更好。"))
    else:
        anchor = sentences[max(0, len(sentences) * 2 // 3 - 1)]
        advice.append(_advice_item("后半段转折位", anchor, "在这句后面补一个能重新解释前文的隐藏事实，优先用身份、证据、误会或真正目的。", "当前后半段缺少明确反转，剧情只有推进，没有第二个留存峰值。"))

    longest = max(sentences, key=_visible_len)
    if _visible_len(longest) >= 32:
        advice.append(_advice_item("最长句", longest, "按逗号/转折处拆成两句：第一句只放动作或事实，第二句只放后果或判断。", f"这句约 {_visible_len(longest)} 字，明显高于短视频口播舒适区，字幕和配音都容易拖。"))

    ending = sentences[-1]
    if _has_any(ending, CTA_WORDS) or "？" in ending or "?" in ending:
        advice.append(_advice_item("结尾最后一句", ending, "保留一个最关键的未解问题即可；如果已经有“下一集/继续看”，不要再叠加点赞、关注、评论等多个动作。", "剧情型 CTA 的核心是让观众想知道下一步，而不是同时执行多个平台动作。"))
    else:
        advice.append(_advice_item("结尾最后一句", ending, "把结尾改成“尚未解决的问题 + 下一步即将发生的动作”，必要时再接一次轻量“下一集”。", "当前最后一句把信息收得太完整，缺少自然的续看理由。"))

    if len(paragraphs) <= 2 and len(sentences) >= 8:
        anchor = sentences[len(sentences)//2]
        advice.append(_advice_item("中段分段位置", anchor, "从这句附近切开，形成“铺垫 / 冲突 / 反转”至少3个视觉段落。", "当前段落过少，剪辑时不容易直接按情节点卡镜头和字幕。"))

    kws = _keywords(text)
    if kws:
        top = kws[0][0]
        related = next((s for s in sentences if top in s), opening)
        advice.append(_advice_item("核心词所在句", related, f"标题或封面只抓“{top}”附近最强的一个冲突结果，不要把本文多个角色关系和背景同时塞进标题。", f"“{top}”是当前规则提取出的高频核心词之一，集中表达更利于观众一眼理解卖点。"))

    return "\n\n".join(f"{i+1}. {item}" for i, item in enumerate(advice[:8]))


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
        "G": _template(text, sentences),
        "H": _advice(text, sentences, paragraphs),
    }


def build_report(text: str, result: Dict[str, str]) -> str:
    sections = ["# 短剧文案拆解报告", "", "## 原文", "", text.strip() or "（空）", ""]
    for key, title in MODULE_TITLES:
        sections.extend([f"## {key}. {title}", "", result.get(key, ""), ""])
    sections.append("---\n说明：本报告由本地规则/启发式分析生成，用于辅助创作判断，不保证作品成为爆款。")
    return "\n".join(sections).strip() + "\n"
