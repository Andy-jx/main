from pathlib import Path
import sys

from analyzer import MODULE_TITLES, analyze, build_report


ROOT = Path(__file__).resolve().parent


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    sample = (ROOT / "sample_script.txt").read_text(encoding="utf-8")
    first = analyze(sample)

    assert set(first) == {key for key, _ in MODULE_TITLES}
    assert all(first[key].strip() for key, _ in MODULE_TITLES)

    second_text = "我以为今天只是普通面试。没想到进门后，面试官竟然是三年前被我拒绝的人。可他没有报复，只把一份合伙人合同推到我面前。你会签吗？"
    second = analyze(second_text)
    assert first != second
    assert first["A"] != second["A"] or first["E"] != second["E"]

    report = build_report(second_text, second)
    for key, title in MODULE_TITLES:
        assert f"## {key}. {title}" in report

    readme = (ROOT / "README_使用说明.md").read_text(encoding="utf-8")
    for required in ("Windows", "run.bat", "不保证", "完全本地"):
        assert required in readme

    print("SELF_CHECK_OK")
    print("1) 示例八模块：PASS")
    print("2) 新文案结果变化：PASS")
    print("3) MD/TXT 报告八模块：PASS")
    print("4) README Windows 运行说明：PASS")


if __name__ == "__main__":
    main()
