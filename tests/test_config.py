"""Tests for config load/save and DC-id key coercion."""
import json

from tgproxy import config


def test_defaults_when_missing(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "APP_DIR", tmp_path)
    monkeypatch.setattr(config, "CONFIG_FILE", tmp_path / "config.json")
    cfg = config.load()
    assert cfg["port"] == 2080
    assert cfg["verbose"] is False


def test_roundtrip_and_merge(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "APP_DIR", tmp_path)
    monkeypatch.setattr(config, "CONFIG_FILE", tmp_path / "config.json")
    # Write a partial config: only port. Defaults must fill the rest.
    (tmp_path / "config.json").write_text(json.dumps({"port": 2090}))
    cfg = config.load()
    assert cfg["port"] == 2090
    assert "verbose" in cfg  # default merged in

    cfg["dc_ip"] = {"2": "149.154.167.220"}
    config.save(cfg)
    assert config.dc_ip_int_keys(config.load()) == {2: "149.154.167.220"}


def test_dc_ip_int_keys_skips_garbage():
    cfg = {"dc_ip": {"2": "1.2.3.4", "x": "5.6.7.8"}}
    assert config.dc_ip_int_keys(cfg) == {2: "1.2.3.4"}
