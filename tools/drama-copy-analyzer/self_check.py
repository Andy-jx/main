from pathlib import Path
import sys

from analyzer import MODULE_TITLES, analyze, build_report


ROOT = Path(__file__).resolve().parent


def run_checks(include_docs: bool = True, verbose: bool = True) -> None:
    if verbose and sys.stdout is not None and hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    sample = (ROOT / "sample_script.txt").read_text(encoding="utf-8")
    first = analyze(sample)

    assert set(first) == {key for key, _ in MODULE_TITLES}
    assert all(first[key].strip() for key, _ in MODULE_TITLES)
    assert "来自原句" in first["G"]
    assert "原句：「" in first["H"]

    second_text = "我以为今天只是普通面试。没想到进门后，面试官竟然是三年前被我拒绝的人。可他没有报复，只把一份合伙人合同推到我面前。你会签吗？"
    second = analyze(second_text)
    assert first != second
    assert first["A"] != second["A"] or first["E"] != second["E"]
    assert first["G"] != second["G"]
    assert first["H"] != second["H"]

    plain_text = "小王今年二十五岁，在一家普通公司做行政。\n他每天八点半上班，主要负责整理资料。\n最近部门准备调整岗位。"
    plain_structure = analyze(plain_text)["B"]
    assert not plain_structure.lstrip().startswith("[钩子"), "B 模块不能把第一段无条件标成钩子"

    report = build_report(second_text, second)
    for key, title in MODULE_TITLES:
        assert f"## {key}. {title}" in report

    freq_text = "老板拿走合同。老板又把合同拿回来。公司的人都在等老板，公司最后还是签了合同。"
    freq_result = analyze(freq_text)["F"]
    assert "老板" in freq_result
    assert "合同" in freq_result

    if include_docs:
        readme = (ROOT / "README_使用说明.md").read_text(encoding="utf-8")
        buyer_guide = (ROOT / "买家使用说明.txt").read_text(encoding="utf-8")
        for required in ("Windows", "run.bat", "build_release.bat", "不保证", "完全本地", "无需安装 Python"):
            assert required in readme
        for required in ("双击", "DramaCopyAnalyzer.exe", "本地", "不上传", "不保证爆款"):
            assert required in buyer_guide

    if verbose and sys.stdout is not None:
        print("SELF_CHECK_OK")
        print("1) 示例八模块：PASS")
        print("2) 新文案结果变化：PASS")
        print("3) B 非固定首段钩子：PASS")
        print("4) G 根据本文生成：PASS")
        print("5) H 引用原句给建议：PASS")
        print("6) MD/TXT 报告八模块：PASS")
        print("7) 高频词重复提取：PASS")
        if include_docs:
            print("8) README / 买家说明：PASS")


def main() -> None:
    run_checks(include_docs=True, verbose=True)


if __name__ == "__main__":
    main()
