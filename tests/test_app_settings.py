##############################################################################
#
# Name: test_app_settings.py
#
# Function:
#       Tests for the App's settings-related command line options
#
# Copyright notice and license:
#       See LICENSE.md
#
# Author:
#       Terry Moore
#
##############################################################################

import json
import pathlib

import pytest

from annotate_film_scans.app import App
from annotate_film_scans import settings as S

def write_json(path: pathlib.Path, data) -> pathlib.Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data))
    return path

AUTHOR = { "XMP:Creator": "A. Person", "XMP:Rights": "All rights reserved" }

@pytest.fixture
def env(tmp_path, monkeypatch):
    """ isolate from the real user settings directory """
    cfg = tmp_path / "cfg"
    monkeypatch.setenv(S.ENV_SETTINGS_DIR, str(cfg))
    out = tmp_path / "out"
    out.mkdir()
    img = tmp_path / "img.jpg"
    img.write_bytes(b"")
    return { "cfg": cfg, "out": out, "img": img, "tmp": tmp_path }

def annotate_argv(env, *extra) -> list[str]:
    return [ "-d", str(env["out"]), *extra, str(env["img"]) ]

class TestSettingsSelection:
    def test_builtin_by_default(self, env):
        app = App(annotate_argv(env))
        assert "fixed" in app.settings["lens"]

    def test_user_settings_merged(self, env):
        write_json(env["cfg"] / "settings.json", { "camera": { "Mine": { "IFD0:Make": "X" } } })
        app = App(annotate_argv(env, "--camera", "Mine"))
        assert app.args.camera == "Mine"
        assert "fixed" in app.settings["lens"]

    def test_no_builtin_settings(self, env):
        write_json(env["cfg"] / "settings.json", { "camera": { "Mine": {} } })
        app = App(annotate_argv(env, "--no-builtin-settings"))
        assert app.settings["lens"] == {}
        assert list(app.settings["camera"]) == ["Mine"]

    def test_builtin_settings_file(self, env):
        b = write_json(env["tmp"] / "b.json", { "film": { "Test Film": {} } })
        app = App(annotate_argv(env, "--builtin-settings", str(b), "--film", "Test Film"))
        assert list(app.settings["film"]) == ["Test Film"]

    def test_builtin_options_are_exclusive(self, env):
        b = write_json(env["tmp"] / "b.json", {})
        with pytest.raises(SystemExit):
            App(annotate_argv(env, "--builtin-settings", str(b), "--no-builtin-settings"))

    def test_no_user_settings(self, env):
        write_json(env["cfg"] / "settings.json", { "camera": { "Mine": {} } })
        app = App(annotate_argv(env, "--no-user-settings"))
        assert "Mine" not in app.settings["camera"]

    def test_settings_dir_option(self, env):
        other = env["tmp"] / "other"
        write_json(other / "s.json", { "camera": { "Other": {} } })
        app = App(annotate_argv(env, "--settings-dir", str(other), "--camera", "Other"))
        assert app.args.camera == "Other"

    def test_explicit_settings_dir_must_exist(self, env):
        with pytest.raises(App.Error, match="nonexistent"):
            App(annotate_argv(env, "--settings-dir", str(env["tmp"] / "nonexistent")))

    def test_unknown_choice_rejected(self, env):
        with pytest.raises(SystemExit):
            App(annotate_argv(env, "--camera", "Nope"))

    def test_settings_error_is_app_error(self, env):
        write_json(env["cfg"] / "settings.json", { "cameras": {} })
        with pytest.raises(App.Error, match="cameras"):
            App(annotate_argv(env))

class TestWarnings:
    def test_settings_problems_shown_without_verbose(self, env, capsys):
        write_json(env["cfg"] / "settings.json", { "camera": { "Mine": { "Make": "X" } } })
        App(annotate_argv(env))
        assert "Group:Tag" in capsys.readouterr().err

class TestDefaults:
    def test_defaults_from_settings(self, env):
        write_json(env["cfg"] / "settings.json", {
            "author": { "Me": AUTHOR },
            "defaults": { "author": "Me" } })
        app = App(annotate_argv(env))
        assert app.args.author == "Me"
        assert app.args.lens == "fixed"

    def test_no_default_author_or_camera(self, env):
        app = App(annotate_argv(env))
        assert app.args.author is None
        assert app.args.camera is None

    def test_command_line_overrides_default(self, env):
        write_json(env["cfg"] / "settings.json", {
            "author": { "Me": AUTHOR, "You": AUTHOR },
            "defaults": { "author": "Me" } })
        app = App(annotate_argv(env, "--author", "You"))
        assert app.args.author == "You"

class TestInitSettings:
    def test_init_without_input_files(self, env, capsys):
        app = App([ "--init-settings" ])
        assert app.run() == 0
        assert (env["cfg"] / "templates" / "camera.json").is_file()
        assert not (env["cfg"] / "settings.json").exists()
        assert str(env["cfg"]) in capsys.readouterr().out

    def test_init_from_file(self, env):
        src = write_json(env["tmp"] / "mine.json", { "camera": { "Mine": {} } })
        app = App([ "--init-settings", str(src) ])
        assert app.run() == 0
        assert json.loads((env["cfg"] / "settings.json").read_text()) == { "camera": { "Mine": {} } }

    def test_init_with_settings_dir(self, env):
        d = env["tmp"] / "elsewhere"
        app = App([ "--settings-dir", str(d), "--init-settings" ])
        assert app.run() == 0
        assert (d / "templates").is_dir()

    def test_init_refuses_overwrite(self, env):
        src = write_json(env["tmp"] / "mine.json", { "camera": {} })
        write_json(env["cfg"] / "settings.json", { "camera": { "Keep": {} } })
        app = App([ "--init-settings", str(src) ])
        with pytest.raises(App.Error, match="settings.json"):
            app.run()

class TestCheckSettings:
    def test_check_clean(self, env, capsys):
        write_json(env["cfg"] / "settings.json", { "camera": { "Mine": { "IFD0:Make": "X" } } })
        app = App([ "--check-settings" ])
        assert app.run() == 0
        out = capsys.readouterr().out
        assert "Mine" in out
        assert "settings.json" in out

    def test_check_reports_problems(self, env, capsys):
        write_json(env["cfg"] / "settings.json", { "camera": { "Mine": { "Make": "X" } } })
        app = App([ "--check-settings" ])
        assert app.run() == 1
        assert "Group:Tag" in capsys.readouterr().out
