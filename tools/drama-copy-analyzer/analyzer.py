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
BACKGROUND_WORDS = ("三年前", "从前", "以前", "当时", "一直", "原本", "曾经", "为了", "因为", "从小", "每天", "这些年", "之前", "平时", "工作", "生活")
NEG_WORDS = ("死", "哭", "恨", "骗", "背叛", "失去", "赶走", "拒绝", "崩溃", "威胁", "失败", "欠", "穷", "痛", "怕", "危险", "秘密", "离婚", "分手", "报复", "嘲笑", "看不起", "羞辱")
POS_WORDS = ("赢", "笑", "爱", "成功", "原谅", "重逢", "救", "真相", "希望", "幸福", "逆袭", "证明", "惊喜", "拿回")
URGENT_WORDS = ("立刻", "马上", "快", "赶紧", "只剩", "最后", "下一秒", "突然", "现在", "来不及", "必须", "倒计时", "冲", "跑")
CTA_WORDS = ("关注", "点赞", "评论", "收藏", "转发", "下一集", "主页", "继续看", "告诉我", "想知道", "点个", "下集")
HOOK_WORDS = ("没想到", "竟然", "千万", "如果", "你敢信", "谁能想到", "直到", "第一天", "刚", "只因", "真相", "秘密", "所有人", "谁也没想到", "万万没想到")
IDENTITY_WORDS = ("总裁", "老板", "董事长", "甲方", "负责人", "继承人", "千金", "少爷", "身份", "主位", "合同", "名字", "秘书", "股东", "董事")
PRESSURE_WORDS = ("威胁", "拒绝", "赶走", "嘲笑", "逼", "抢", "打", "骂", "背叛", "离婚", "分手", "看不起", "羞辱")
COMMON_SURNAMES = "赵钱孙李周吴郑王冯陈蒋沈韩杨朱秦许何吕张孔曹严华金魏陶姜谢邹潘葛范彭鲁韦马苗方俞任袁柳唐罗薛伍余姚孟顾尹江钟夏蔡田樊胡霍万卢莫房裘解丁邓洪包左石崔龚程陆翁荀于甄曲封储靳段富焦巴侯班秋仲宫宁仇甘厉祖武刘景詹龙叶司黎白怀蒲鄂赖卓谭劳姬申冉郦桑桂牛边燕浦尚温庄晏柴阎慕连习艾向古易慎廖曾关游权林"


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


def _clip(s: str, limit: int = 82) -> str:
    s = s.strip()
    return s if len(s) <= limit else s[: limit - 1] + "…"


def _hook_score_sentence(s: str, index: int = 0) -> int:
    score = 20 + (8 if index <= 1 else 0)
    score += 24 if _has_any(s, HOOK_WORDS) else 0
    score += 18 if (_has_any(s, CONFLICT_WORDS) or _has_any(s, NEG_WORDS)) else 0
    score += 12 if ("？" in s or "?" in s) else 0
    score += 5 if ("！" in s or "!" in s) else 0
    score += 8 if _visible_len(s) <= 24 else 0
    score -= 10 if _visible_len(s) > 55 else 0
    return max(0, min(100, score))


def _hook_analysis(sentences: List[str]) -> str:
    opening = sentences[:3]
    if not opening:
        return "评分：0/100\n点评：没有可分析文本。"
    joined = "".join(opening)
    score = max(_hook_score_sentence(s, i) for i, s in enumerate(opening))
    if len(opening) >= 2 and (_has_any(joined, HOOK_WORDS) or _has_any(joined, CONFLICT_WORDS)):
        score = min(100, score + 5)
    dimensions = [
        "有悬念" if (_has_any(joined, HOOK_WORDS) or "？" in joined or "?" in joined) else "悬念偏弱",
        "有冲突" if (_has_any(joined, CONFLICT_WORDS) or _has_any(joined, NEG_WORDS)) else "冲突偏弱",
        "有利益点" if re.search(r"省|赚|学会|方法|秘诀|免费|避坑|拿到|解决", joined) else "利益点不明显",
        "有情绪" if (_has_any(joined, NEG_WORDS) or _has_any(joined, POS_WORDS) or "！" in joined) else "情绪偏平",
    ]
    if sum(_visible_len(s) for s in opening) > 90:
        dimensions.append("前3句信息偏满")
    return "前1–3句：\n" + "\n".join(f"- {s}" for s in opening) + f"\n\n评分：{score}/100\n点评：" + "、".join(dimensions) + "。"


def _structure_scores(p: str, index: int, total: int) -> Dict[str, int]:
    ratio = index / max(1, total - 1)
    has_question = "？" in p or "?" in p
    hook_signal = _has_any(p, HOOK_WORDS) or has_question or _has_any(p, CONFLICT_WORDS) or _has_any(p, NEG_WORDS)

    hook = 0
    if hook_signal and ratio <= 0.35:
        hook = 2
        hook += 4 if _has_any(p, HOOK_WORDS) else 0
        hook += 2 if has_question else 0
        hook += 2 if (_has_any(p, CONFLICT_WORDS) or _has_any(p, NEG_WORDS)) else 0
        hook += 1 if _visible_len(p) <= 60 else 0

    setup = 1 if ratio <= 0.70 else 0
    setup += 4 if _has_any(p, BACKGROUND_WORDS) else 0
    setup += 2 if re.search(r"为了|因为|原本|曾经|一直|当时|三年前|之前|每天|平时|工作|生活", p) else 0
    setup += 2 if not (_has_any(p, CONFLICT_WORDS) or _has_any(p, REVERSAL_WORDS) or _has_any(p, CTA_WORDS) or _has_any(p, PRESSURE_WORDS)) else 0

    conflict = 0
    conflict += 5 if _has_any(p, PRESSURE_WORDS) else 0
    conflict += 3 if _has_any(p, CONFLICT_WORDS) else 0
    conflict += 3 if _has_any(p, NEG_WORDS) else 0
    conflict += 2 if re.search(r"不要|不许|必须|否则|失去|换掉|离开|当众|抢走|拿走", p) else 0

    reversal = 0
    reversal += 4 * sum(1 for w in REVERSAL_WORDS if w in p)
    reversal += 1 if ratio >= 0.25 else 0
    reversal += 5 * sum(1 for w in IDENTITY_WORDS if w in p)
    reversal += 2 if re.search(r"可.{0,16}(真正|却|竟|原来|才|其实)", p) else 0

    cta = 2 if ratio >= 0.65 else 0
    cta += 6 if _has_any(p, CTA_WORDS) else 0
    cta += 4 if (has_question and ratio >= 0.65) else 0

    return {"钩子": hook, "铺垫": setup, "冲突": conflict, "反转": reversal, "催行动作": cta}


def _structure_analysis(paragraphs: List[str], sentences: List[str]) -> str:
    if not paragraphs:
        return "弱/缺失：无文本。"
    thresholds = {"钩子": 5, "铺垫": 4, "冲突": 5, "反转": 6, "催行动作": 6}
    found = {k: False for k in thresholds}
    tagged = []
    total = len(paragraphs)

    for i, p in enumerate(paragraphs):
        scores = _structure_scores(p, i, total)
        eligible = [(tag, score) for tag, score in scores.items() if score >= thresholds[tag]]
        if not eligible:
            tagged.append(f"[弱/缺失] {p}")
            continue
        tag, best = max(eligible, key=lambda kv: kv[1])
        if tag == "钩子" and i > max(1, total // 3):
            eligible = [(t, s) for t, s in eligible if t != "钩子"]
            if not eligible:
                tagged.append(f"[弱/缺失] {p}")
                continue
            tag, best = max(eligible, key=lambda kv: kv[1])
        if tag == "催行动作" and i < max(1, total // 2):
            eligible = [(t, s) for t, s in eligible if t != "催行动作"]
            if not eligible:
                tagged.append(f"[弱/缺失] {p}")
                continue
            tag, best = max(eligible, key=lambda kv: kv[1])
        found[tag] = True
        confidence = "强" if best >= 10 else "中" if best >= 7 else "弱"
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
    score = 4 * sum(1 for w in PRESSURE_WORDS if w in s)
    score += 2 * sum(1 for w in CONFLICT_WORDS if w in s)
    score += 2 * sum(1 for w in NEG_WORDS if w in s)
    score += 2 if re.search(r"不要|不许|必须|否则|失去|换掉|离开|当众|拿走", s) else 0
    return score


def _conflicts(sentences: List[str]) -> str:
    items = []
    for s in sentences:
        hit = next((w for w in PRESSURE_WORDS if w in s), None)
        turn = next((w for w in CONFLICT_WORDS if w in s), None)
        if hit:
            reason = f"出现明确对立动作“{hit}”，角色目标受到直接阻力"
        elif turn:
            reason = f"包含转折/变化词“{turn}”，前后预期发生变化"
        elif _has_any(s, NEG_WORDS):
            reason = "包含损失、压力或关系破裂信息，形成剧情阻力"
        else:
            continue
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
    return f"节奏描述：{desc}。\n\n" + "\n".join(f"{i+1}. [{labels[i]}] {s}" for i, s in enumerate(sentences))


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
        for n in range(2, min(4, len(chunk)) + 1):
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
        return length_score + trigger + (5 if ("！" in s or "？" in s or "，" in s) else 0)
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


def _extract_names(text: str) -> List[str]:
    followers = r"(?=只是|没有|就|又|还|却|把|被|在|来|问|说|走|带|脸色|一直|为了|主动|才|是|会|要|正|当|，|。|！|？|：|“|”|$)"
    patterns = [
        rf"(?:前男友|前女友|男友|女友|丈夫|妻子|老板|总裁|秘书|同事|经理|医生|警察)([{COMMON_SURNAMES}][\u4e00-\u9fff]{{1,2}}?){followers}",
        rf"([{COMMON_SURNAMES}][\u4e00-\u9fff]{{1,2}}?){followers}",
    ]
    candidates: Counter[str] = Counter()
    for pattern in patterns:
        for match in re.finditer(pattern, text):
            name = match.group(1)
            if 2 <= len(name) <= 3:
                candidates[name] += max(1, text.count(name))
    ranked = sorted(candidates.items(), key=lambda kv: (-kv[1], text.find(kv[0])))
    result = []
    for name, _ in ranked:
        if name not in result:
            result.append(name)
        if len(result) == 4:
            break
    return result


def _reversal_score(s: str) -> int:
    score = 4 * sum(1 for w in REVERSAL_WORDS if w in s)
    score += 5 * sum(1 for w in IDENTITY_WORDS if w in s)
    score += 3 if re.search(r"证据|合同|名字|录音|照片|视频", s) else 0
    return score


def _template(text: str, sentences: List[str]) -> str:
    if not sentences:
        return "无文本。"
    opening_pool = sentences[: min(3, len(sentences))]
    hook = max(enumerate(opening_pool), key=lambda x: _hook_score_sentence(x[1], x[0]))[1]
    conflicts = [s for s in sentences if _conflict_score(s) > 0]
    conflict = max(conflicts, key=_conflict_score) if conflicts else ""
    reversals = [s for s in sentences if _reversal_score(s) >= 5]
    reversal = max(reversals, key=_reversal_score) if reversals else ""
    ending_pool = sentences[-3:]
    cta = next((s for s in ending_pool if "？" in s or "?" in s), None)
    if not cta:
        cta = next((s for s in reversed(ending_pool) if _has_any(s, CTA_WORDS)), ending_pool[-1])

    names = _extract_names(text)
    opening_text = "".join(opening_pool)
    opening_names = [n for n in names if n in opening_text]
    protagonist = min(opening_names, key=opening_text.find) if opening_names else (names[0] if names else "未识别到明确姓名")
    conflict_names = [n for n in names if n != protagonist and conflict and n in conflict]
    opponent = min(conflict_names, key=conflict.find) if conflict_names else next((n for n in names if n != protagonist), "未识别到明确姓名")
    action = next((w for w in PRESSURE_WORDS if conflict and w in conflict), next((w for w in CONFLICT_WORDS if conflict and w in conflict), "阻力事件"))
    reversal_key = next((w for w in IDENTITY_WORDS if reversal and w in reversal), next((w for w in REVERSAL_WORDS if reversal and w in reversal), "隐藏事实"))

    chain = [protagonist, f"遭遇“{action}”冲突" if conflict else "冲突偏弱", f"通过“{reversal_key}”完成反转" if reversal else "反转偏弱", "留下未解问题" if ("？" in cta or "?" in cta or _has_any(cta, CTA_WORDS)) else "收束结果"]
    return "\n".join([
        "本文已填槽结构：",
        f"- 主角：{protagonist}",
        f"- 对手/阻力方：{opponent}",
        f"- 开头钩子：{_clip(hook)}",
        f"- 核心冲突：{_clip(conflict) if conflict else '本文未识别到足够明确的冲突句'}",
        f"- 冲突动作：{action}",
        f"- 关键反转：{_clip(reversal) if reversal else '本文未识别到足够明确的反转句'}",
        f"- 反转证据/机制：{reversal_key}",
        f"- 收尾：{_clip(cta)}",
        "",
        "本文结构链：" + " → ".join(chain),
        "",
        "基于本文生成的复用提纲：",
        f"1. 先让“{protagonist}”处在被低估、被误判或信息不完整的位置，用本文钩子同类的反常事实迅速打破预期。",
        f"2. 让“{opponent}”或同等阻力角色做出明确的“{action}”动作；不要只写态度，要让主角面临实际后果。",
        f"3. 冲突升级后，再揭开类似“{reversal_key}”这样的证据/身份/事实，让前面的强弱关系重新解释。",
        f"4. 收尾沿用本文“{_clip(cta, 46)}”的机制：停在尚未解决的问题或下一步动作上，不把结果一次讲完。",
        "",
        "注意：这里提取的是本文的人物与事件机制。换题材时应替换人物、冲突事件和反转证据，不应直接照抄原文。",
    ])


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
        advice.append(_advice_item("开头第1句", opening, f"把背景说明压缩，第一句末尾落到“{trigger}”对应的异常结果/冲突上；背景放到第2句以后。", f"当前首句钩子评分约 {opening_score}/100，信息差不足，容易在背景交代阶段掉人。"))
    else:
        advice.append(_advice_item("开头第1句", opening, "保留现有反差/悬念，不再继续往前加背景；如果要提速，只删解释词，不删结果词和转折词。", f"当前首句钩子已经较强（约 {opening_score}/100），主要风险是后续解释稀释首句优势。"))

    conflicts = [s for s in sentences if _conflict_score(s) > 0]
    if conflicts:
        conflict = max(conflicts, key=_conflict_score)
        action = next((w for w in PRESSURE_WORDS if w in conflict), "对立动作")
        how = "把这句拆成“对立动作一句 + 后果一句”，让后果单独成段。" if _visible_len(conflict) > 34 else f"保留“{action}”这个动作，并紧接一句补出失败代价：主角会失去什么、谁会受影响。"
        advice.append(_advice_item("最强冲突句", conflict, how, "这句承担主要矛盾，强化具体动作与代价，比再加泛情绪更有效。"))
    else:
        anchor = sentences[min(len(sentences) - 1, max(1, len(sentences)//2))]
        advice.append(_advice_item("正文中段", anchor, "紧接这句新增一个具体对立动作：谁阻止谁、做了什么、失败会失去什么。", "当前文本没有识别到足够强的冲突动作，中段容易只剩叙述。"))

    reversals = [s for s in sentences if _reversal_score(s) >= 5]
    if reversals:
        reversal = max(reversals, key=_reversal_score)
        key = next((w for w in IDENTITY_WORDS if w in reversal), next((w for w in REVERSAL_WORDS if w in reversal), "反转证据"))
        advice.append(_advice_item("反转句", reversal, f"在它前面提前埋一个与“{key}”同类的细节，但不要解释；到这句再揭开答案。", "这样反转会从突然告知变成前有伏笔、此处兑现，可信度和二次留存更好。"))
    else:
        anchor = sentences[max(0, len(sentences) * 2 // 3 - 1)]
        advice.append(_advice_item("后半段转折位", anchor, "在这句后补一个能重新解释前文的隐藏事实，优先用身份、证据、误会或真正目的。", "当前后半段缺少明确反转，剧情只有推进，没有第二个留存峰值。"))

    longest = max(sentences, key=_visible_len)
    if _visible_len(longest) >= 32:
        advice.append(_advice_item("最长句", longest, "按逗号/转折处拆成两句：第一句只放动作或事实，第二句只放后果或判断。", f"这句约 {_visible_len(longest)} 字，明显偏长，字幕和口播都容易拖。"))

    ending = sentences[-1]
    if _has_any(ending, CTA_WORDS) or "？" in ending or "?" in ending:
        advice.append(_advice_item("结尾最后一句", ending, "只保留一个最关键的未解问题；如果已有“下一集/继续看”，不要再叠加点赞、关注、评论等多个动作。", "剧情型 CTA 的核心是让观众想知道下一步，而不是同时执行多个平台动作。"))
    else:
        advice.append(_advice_item("结尾最后一句", ending, "改成“尚未解决的问题 + 下一步即将发生的动作”，必要时再接一次轻量“下一集”。", "当前结尾收得太完整，缺少自然的续看理由。"))

    if len(paragraphs) <= 2 and len(sentences) >= 8:
        anchor = sentences[len(sentences)//2]
        advice.append(_advice_item("中段分段位置", anchor, "从这句附近切开，形成“铺垫 / 冲突 / 反转”至少3个视觉段落。", "当前段落过少，剪辑时不容易直接按情节点卡镜头和字幕。"))

    kws = _keywords(text)
    if kws:
        top = kws[0][0]
        related = next((s for s in sentences if top in s), opening)
        advice.append(_advice_item("核心词所在句", related, f"标题或封面只抓“{top}”附近最强的一个冲突结果，不要把多个关系和背景同时塞进标题。", f"“{top}”是当前文本的高频核心词之一，集中表达更利于观众一眼理解。"))
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
