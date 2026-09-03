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


def test_plugin_template_has_model_placeholder_and_local_api():
    text = (ROOT / "plugin" / module.PLUGIN_NAME).read_text(encoding="utf-8")
    assert "__DEFAULT_MODEL__" in text
    assert "127.0.0.1:11434" in text
    assert "/api/chat" in text


def test_plugin_has_context_and_duplicate_cache():
    text = (ROOT / "plugin" / module.PLUGIN_NAME).read_text(encoding="utf-8")
    assert "MAX_HISTORY" in text
    assert "MAX_CACHE" in text
    assert "LookupCache" in text
    assert "PushCache" in text


def test_plugin_destination_is_inside_potplayer_tree(tmp_path):
    exe = tmp_path / "PotPlayerMini64.exe"
    exe.write_bytes(b"")
    dest = module.plugin_destination(exe)
    assert dest.name == module.PLUGIN_NAME
    assert dest.parent.parts[-3:] == ("Extension", "Subtitle", "Translate")


def test_backup_existing_file_preserves_original(tmp_path):
    target = tmp_path / "sample.as"
    target.write_text("old", encoding="utf-8")
    backup = module.backup_existing_file(target)
    assert backup is not None
    assert target.read_text(encoding="utf-8") == "old"
    assert backup.read_text(encoding="utf-8") == "old"
    assert ".backup-" in backup.name
