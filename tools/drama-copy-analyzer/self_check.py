from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import re
import sys
import threading

from analyzer import MODULE_TITLES
from ai_engine import ai_deep_analyze, ai_generate_rewrite, build_analysis_messages, extract_ai_modules
from coach import analyze, build_report
from local_ai import LocalAIConfig, base_url, stop_shared_manager
from rewriter import generate_rewrite


ROOT = Path(__file__).resolve().parent


class _FakeAIHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        return

    def _send(self, payload, status=200):
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path == "/health":
            self._send({"status": "ok"})
        elif self.path == "/v1/models":
            self._send({"object": "list", "data": [{"id": "fake-local-qwen"}]})
        else:
            self._send({"error": "not found"}, 404)

    def do_POST(self):
        if self.path != "/v1/chat/completions":
            self._send({"error": "not found"}, 404)
            return
        length = int(self.headers.get("Content-Length", "0"))
        payload = json.loads(self.rfile.read(length) or b"{}")
        if payload.get("response_format"):
            modules = {
                key: f"【本地AI深度批改】\n原句：「测试原句」\n弱点：测试。\n怎么改：测试改法。"
                for key, _ in MODULE_TITLES
            }
            content = json.dumps(modules, ensure_ascii=False)
        else:
            content = (
                "【完整改写稿｜本地AI版】\n测试改写第一句。\n测试改写第二句。"
                "\n\n【相对原文的关键改动】\n1. 钩子：测试。\n2. 冲突：测试。\n3. 反转：测试。"
            )
        self._send({"choices": [{"message": {"role": "assistant", "content": content}}]})


def _check_local_ai_contract(sample: str, rule_result: dict[str, str]) -> None:
    server = ThreadingHTTPServer(("127.0.0.1", 0), _FakeAIHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    port = server.server_address[1]
    cfg = LocalAIConfig(port=port, startup_timeout=5, request_timeout=10)
    try:
        assert base_url(cfg) == f"http://127.0.0.1:{port}"
        messages = build_analysis_messages(sample, rule_result)
        assert messages[0]["role"] == "system"
        assert "原文" in messages[1]["content"] and "A-H" in messages[1]["content"]

        parsed = extract_ai_modules(json.dumps({key: "测试" for key, _ in MODULE_TITLES}, ensure_ascii=False))
        assert set(parsed) == {key for key, _ in MODULE_TITLES}
        assert all("本地AI深度批改" in parsed[key] for key, _ in MODULE_TITLES)

        ai_result, status = ai_deep_analyze(sample, rule_result, cfg)
        assert set(ai_result) == {key for key, _ in MODULE_TITLES}
        assert all("本地AI深度批改" in ai_result[key] for key, _ in MODULE_TITLES)
        assert "fake-local-qwen" in status

        ai_rewrite, _ = ai_generate_rewrite(sample, rule_result, cfg)
        assert "【完整改写稿｜本地AI版】" in ai_rewrite
        assert "【相对原文的关键改动】" in ai_rewrite
    finally:
        stop_shared_manager()
        server.shutdown()
        server.server_close()


def run_checks(include_docs: bool = True, verbose: bool = True) -> None:
    if verbose and sys.stdout is not None and hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    sample = (ROOT / "sample_script.txt").read_text(encoding="utf-8")
    first = analyze(sample)

    assert set(first) == {key for key, _ in MODULE_TITLES}
    assert all(first[key].strip() for key, _ in MODULE_TITLES)

    for key, _ in MODULE_TITLES:
        assert "老师批改" in first[key], (key, first[key])

    plain_text = "小王今年二十五岁，在一家普通公司做行政。\n他每天八点半上班，主要负责整理资料。\n最近部门准备调整岗位。"
    plain_structure = analyze(plain_text)["B"]
    structure_lines = [line for line in plain_structure.splitlines() if line.startswith("[")]
    assert structure_lines, plain_structure
    first_line = structure_lines[0]
    assert first_line.startswith("[铺垫") or first_line.startswith("[弱/缺失"), first_line
    assert not first_line.startswith("[钩子"), "B 模块不能把第一段无条件标成钩子"

    g = first["G"]
    assert "本文已填槽结构" in g
    assert "林晚" in g and "周凯" in g, g
    assert "核心冲突：" in g and "嘲笑" in g, g
    assert "关键反转：" in g and ("甲方" in g or "负责人" in g or "合同" in g), g
    assert "【___】" not in g and "[___]" not in g

    h = first["H"]
    advice_count = len(re.findall(r"(?m)^\d+\. 【", h))
    quote_count = h.count("原句：「")
    assert 3 <= advice_count <= 8, (advice_count, h)
    assert quote_count == advice_count, (quote_count, advice_count, h)

    rewrite = generate_rewrite(sample, first)
    assert rewrite.strip()
    assert "【完整改写稿｜可直接试拍】" in rewrite
    assert "【相对原文的关键改动】" in rewrite
    assert rewrite.strip() != sample.strip()

    second_text = "我以为今天只是普通面试。没想到进门后，面试官竟然是三年前被我拒绝的人。可他没有报复，只把一份合伙人合同推到我面前。你会签吗？"
    second = analyze(second_text)
    assert first != second
    assert first["G"] != second["G"] and first["H"] != second["H"]
    second_rewrite = generate_rewrite(second_text, second)
    assert second_rewrite and second_rewrite != rewrite

    report = build_report(second_text, second, second_rewrite)
    for key, title in MODULE_TITLES:
        assert f"## {key}. {title}" in report
    assert "## 一键改写稿" in report
    assert "【相对原文的关键改动】" in report

    freq_text = "老板拿走合同。老板又把合同拿回来。公司的人都在等老板，公司最后还是签了合同。"
    freq_result = analyze(freq_text)["F"]
    assert "老板" in freq_result and "合同" in freq_result

    # 新增：用本机假 llama-server 验证 HTTP/JSON/双引擎合同，不访问公网。
    _check_local_ai_contract(sample, first)

    if include_docs:
        readme = (ROOT / "README_使用说明.md").read_text(encoding="utf-8")
        buyer_guide = (ROOT / "买家使用说明.txt").read_text(encoding="utf-8")
        build_script = (ROOT / "build_release.bat").read_text(encoding="utf-8")
        ai_build = (ROOT / "build_ai_release.bat").read_text(encoding="utf-8")
        gui_code = (ROOT / "gui.py").read_text(encoding="utf-8")
        local_ai_code = (ROOT / "local_ai.py").read_text(encoding="utf-8")
        for required in (
            "Windows", "build_ai_release.bat", "本地AI深度模式", "Qwen", "llama-server",
            "不上传", "无需安装 Python", "极速规则模式",
        ):
            assert required in readme, required
        for required in ("DramaCopyAnalyzer.exe", "本地AI", "不上传", "GGUF", "规则模式", "不保证爆款"):
            assert required in buyer_guide, required
        for required in ("Runtime", "Models", "DramaCopyAnalyzer_Windows.zip", "--self-check"):
            assert required in build_script, required
        assert "REQUIRE_AI" in ai_build and "DramaCopyAnalyzer_AI_Windows.zip" in ai_build
        assert "本地AI设置" in gui_code and "本地AI深度模式" in gui_code
        assert 'LOCAL_HOST = "127.0.0.1"' in local_ai_code
        assert "http://{LOCAL_HOST}" in local_ai_code

    if verbose and sys.stdout is not None:
        print("SELF_CHECK_OK")
        print("1) A-H 规则/老师批改：PASS")
        print("2) B/G/H 关键验收：PASS")
        print("3) 规则完整改写稿：PASS")
        print("4) 报告导出：PASS")
        print("5) 本地AI Prompt/JSON 解析：PASS")
        print("6) 127.0.0.1 假 llama-server 深度批改：PASS")
        print("7) 127.0.0.1 假 llama-server AI改写：PASS")
        if include_docs:
            print("8) README / 买家说明 / AI出包脚本：PASS")


def main() -> None:
    run_checks(include_docs=True, verbose=True)


if __name__ == "__main__":
    main()
