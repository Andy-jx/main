from __future__ import annotations

import json
import re
from typing import Dict, Tuple

from analyzer import MODULE_TITLES
from local_ai import LocalAIConfig, get_shared_manager


SYSTEM_COACH = """你是短剧剪辑导演和口播文案老师。你的任务不是写论文，而是像老师拿红笔批稿。
要求：
1. 必须紧扣用户原文，不虚构原文没有的人物、身份、证据和关键剧情。
2. 每个模块尽量点名具体原句，说明“好在哪 / 弱在哪 / 怎么改一句更好”。
3. 面向短剧口播、分镜、字幕节奏；句子短，动作明确，少空话。
4. 重点看前3秒钩子、冲突可拍性、情绪峰值、信息差、反转证据、收尾续看。
5. 输出简体中文。"""

SYSTEM_REWRITE = """你是短剧编导，负责把用户原稿改成可直接试拍的口播稿。
要求：
1. 保留原剧情事实、人物关系和核心结局，不凭空添加重大身份/证据。
2. 开头3秒先给异常、冲突或信息差；不能把最终谜底全部提前泄光。
3. 冲突句要能直接拍成动作；长句拆短，减少解释腔。
4. 反转要有前因/证据，尽量单独成段。
5. 结尾留一个剧情问题或未解决动作，不堆“点赞关注评论”。
6. 输出一篇完整稿，不要只给建议。"""


def _rule_digest(rule_result: Dict[str, str]) -> str:
    blocks = []
    for key in ("A", "B", "C", "G", "H"):
        text = (rule_result.get(key) or "").strip()
        if len(text) > 1800:
            text = text[:1800] + "…"
        blocks.append(f"[{key}]\n{text}")
    return "\n\n".join(blocks)


def build_analysis_messages(source: str, rule_result: Dict[str, str]) -> list[dict[str, str]]:
    schema = (
        "只返回一个 JSON 对象，键必须严格为 A、B、C、D、E、F、G、H，值都是字符串。"
        "不要 Markdown 代码围栏。每个值开头写【本地AI深度批改】，并至少包含一处对原句的引用或明确说明。"
    )
    user = f"""请对下面短剧/口播文案做 A-H 深度批改。

A 开头钩子
B 结构标注
C 冲突点
D 情绪起伏
E 句段节奏
F 高频词/金句用途
G 本文结构模板
H 逐句改写建议

{schema}

【原文】
{source.strip()}

【规则引擎预分析｜仅作线索，不要机械照抄】
{_rule_digest(rule_result)}
"""
    return [{"role": "system", "content": SYSTEM_COACH}, {"role": "user", "content": user}]


def build_rewrite_messages(source: str, rule_result: Dict[str, str]) -> list[dict[str, str]]:
    user = f"""基于原文和规则预分析，生成一篇完整改写稿。

必须按这个格式输出：
【完整改写稿｜本地AI版】
<完整口播稿>

【相对原文的关键改动】
1. 钩子：...
2. 冲突：...
3. 反转：...
4. 节奏/收尾：...

关键改动必须说明相对原文改了什么，不要写泛泛而谈的技巧。

【原文】
{source.strip()}

【规则预分析】
{_rule_digest(rule_result)}
"""
    return [{"role": "system", "content": SYSTEM_REWRITE}, {"role": "user", "content": user}]


def extract_ai_modules(text: str) -> Dict[str, str]:
    cleaned = text.strip()
    cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.I)
    cleaned = re.sub(r"\s*```$", "", cleaned)
    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError:
        start = cleaned.find("{")
        end = cleaned.rfind("}")
        if start < 0 or end <= start:
            raise ValueError("AI 返回不是有效 JSON")
        data = json.loads(cleaned[start : end + 1])

    out: Dict[str, str] = {}
    for key, _ in MODULE_TITLES:
        value = data.get(key)
        if isinstance(value, (dict, list)):
            value = json.dumps(value, ensure_ascii=False, indent=2)
        value = str(value or "").strip()
        if not value:
            raise ValueError(f"AI 返回缺少模块 {key}")
        if "本地AI深度批改" not in value:
            value = "【本地AI深度批改】\n" + value
        out[key] = value
    return out


def ai_deep_analyze(
    source: str,
    rule_result: Dict[str, str],
    cfg: LocalAIConfig | None = None,
) -> Tuple[Dict[str, str], str]:
    manager = get_shared_manager(cfg)
    raw = manager.chat(
        build_analysis_messages(source, rule_result),
        max_tokens=3200,
        temperature=0.35,
        json_mode=True,
    )
    return extract_ai_modules(raw), manager.status_text()


def ai_generate_rewrite(
    source: str,
    rule_result: Dict[str, str],
    cfg: LocalAIConfig | None = None,
) -> Tuple[str, str]:
    manager = get_shared_manager(cfg)
    text = manager.chat(
        build_rewrite_messages(source, rule_result),
        max_tokens=3200,
        temperature=0.55,
        json_mode=False,
    )
    if "【完整改写稿｜本地AI版】" not in text:
        text = "【完整改写稿｜本地AI版】\n" + text
    if "【相对原文的关键改动】" not in text:
        text += (
            "\n\n【相对原文的关键改动】\n"
            "1. 已由本地模型按钩子、冲突、反转和口播节奏重新组织，请人工复核剧情事实。"
        )
    return text.strip(), manager.status_text()
