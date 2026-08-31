from pathlib import Path
import re
import sys

from analyzer import MODULE_TITLES
from coach import analyze, build_report
from rewriter import generate_rewrite


ROOT = Path(__file__).resolve().parent


def run_checks(include_docs: bool = True, verbose: bool = True) -> None:
    if verbose and sys.stdout is not None and hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    sample = (ROOT / "sample_script.txt").read_text(encoding="utf-8")
    first = analyze(sample)

    assert set(first) == {key for key, _ in MODULE_TITLES}
    assert all(first[key].strip() for key, _ in MODULE_TITLES)

    # 加强版：A-H 都要有老师批改感，不能只是统计表。
    for key, _ in MODULE_TITLES:
        assert "老师批改" in first[key], (key, first[key])

    # B：禁止无条件把首段当钩子。
    plain_text = "小王今年二十五岁，在一家普通公司做行政。\n他每天八点半上班，主要负责整理资料。\n最近部门准备调整岗位。"
    plain_structure = analyze(plain_text)["B"]
    structure_lines = [line for line in plain_structure.splitlines() if line.startswith("[")]
    assert structure_lines, plain_structure
    first_line = structure_lines[0]
    assert first_line.startswith("[铺垫") or first_line.startswith("[弱/缺失"), first_line
    assert not first_line.startswith("[钩子"), "B 模块不能把第一段无条件标成钩子"

    # G：必须根据样例抽到具体人物、冲突和反转，不允许退回固定空槽。
    g = first["G"]
    assert "本文已填槽结构" in g
    assert "林晚" in g, g
    assert "周凯" in g, g
    assert "核心冲突：" in g and "嘲笑" in g, g
    assert "关键反转：" in g and ("甲方" in g or "负责人" in g or "合同" in g), g
    assert "【___】" not in g and "[___]" not in g, "G 不能退回固定空白模板"

    # H：至少 3 条，且每条都必须引用具体原句。
    h = first["H"]
    advice_count = len(re.findall(r"(?m)^\d+\. 【", h))
    quote_count = h.count("原句：「")
    assert 3 <= advice_count <= 8, (advice_count, h)
    assert quote_count == advice_count, (quote_count, advice_count, h)

    # 一键改写稿：必须非空、包含完整改写稿和关键改动，而且不能与原文完全相同。
    rewrite = generate_rewrite(sample, first)
    assert rewrite.strip(), "一键改写稿不能为空"
    assert "【完整改写稿｜可直接试拍】" in rewrite, rewrite
    assert "【相对原文的关键改动】" in rewrite, rewrite
    assert "钩子：" in rewrite and ("冲突：" in rewrite or "反转：" in rewrite), rewrite
    assert rewrite.strip() != sample.strip(), "改写稿不能只是原文原样返回"

    second_text = "我以为今天只是普通面试。没想到进门后，面试官竟然是三年前被我拒绝的人。可他没有报复，只把一份合伙人合同推到我面前。你会签吗？"
    second = analyze(second_text)
    assert first != second
    assert first["A"] != second["A"] or first["E"] != second["E"]
    assert first["G"] != second["G"]
    assert first["H"] != second["H"]
    second_rewrite = generate_rewrite(second_text, second)
    assert second_rewrite and second_rewrite != rewrite

    # 导出报告必须自动可带上一键改写稿。
    report = build_report(second_text, second, second_rewrite)
    for key, title in MODULE_TITLES:
        assert f"## {key}. {title}" in report
    assert "## 一键改写稿" in report
    assert "【完整改写稿｜可直接试拍】" in report
    assert "【相对原文的关键改动】" in report

    freq_text = "老板拿走合同。老板又把合同拿回来。公司的人都在等老板，公司最后还是签了合同。"
    freq_result = analyze(freq_text)["F"]
    assert "老板" in freq_result
    assert "合同" in freq_result

    if include_docs:
        readme = (ROOT / "README_使用说明.md").read_text(encoding="utf-8")
        buyer_guide = (ROOT / "买家使用说明.txt").read_text(encoding="utf-8")
        build_script = (ROOT / "build_release.bat").read_text(encoding="utf-8")
        gui_code = (ROOT / "gui.py").read_text(encoding="utf-8")
        for required in ("Windows", "run.bat", "build_release.bat", "不保证", "完全本地", "无需安装 Python", "生成改写稿", "一键改写稿"):
            assert required in readme
        for required in ("双击", "DramaCopyAnalyzer.exe", "本地", "不上传", "不保证爆款", "生成改写稿", "改写稿"):
            assert required in buyer_guide
        for required in ("release\\DramaCopyAnalyzer_Windows", "DramaCopyAnalyzer_Windows.zip", "--self-check"):
            assert required in build_script
        assert "生成改写稿" in gui_code and "generate_rewrite_action" in gui_code

    if verbose and sys.stdout is not None:
        print("SELF_CHECK_OK")
        print("1) 示例 A-H 八模块：PASS")
        print("2) A-H 老师批改口吻：PASS")
        print("3) B 纯背景首段不强制标钩子：PASS")
        print("4) G 抽取本文人物/冲突/反转：PASS")
        print("5) H 每条引用原句：PASS")
        print("6) 一键改写稿非空且包含关键改动：PASS")
        print("7) 新文案分析与改写稿会变化：PASS")
        print("8) MD/TXT 报告包含 A-H + 改写稿：PASS")
        print("9) 高频词重复提取：PASS")
        if include_docs:
            print("10) README / 买家说明 / GUI / 一键出包脚本：PASS")


def main() -> None:
    run_checks(include_docs=True, verbose=True)


if __name__ == "__main__":
    main()
