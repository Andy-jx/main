import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "app" / "configurator.py"

spec = importlib.util.spec_from_file_location("configurator", MODULE_PATH)
module = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(module)


def test_plugin_name_is_as_file():
    assert module.PLUGIN_NAME.endswith(".as")


def test_default_model_hint_present():
    assert "qwen" in module.DEFAULT_MODEL_HINT.lower()


def test_plugin_template_has_model_placeholder():
    text = (ROOT / "plugin" / module.PLUGIN_NAME).read_text(encoding="utf-8")
    assert "__DEFAULT_MODEL__" in text
    assert "127.0.0.1:11434" in text
    assert "/api/chat" in text
