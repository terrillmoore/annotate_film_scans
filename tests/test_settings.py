##############################################################################
#
# Name: test_settings.py
#
# Function:
#       Tests for annotate_film_scans.settings
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

from annotate_film_scans import settings as S

def write_json(path: pathlib.Path, data) -> pathlib.Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data))
    return path

CAMERA_A = { "IFD0:Make": "Canon", "IFD0:Model": "F-1" }
CAMERA_B = { "IFD0:Make": "Minolta", "IFD0:Model": "Autocord" }
AUTHOR = { "XMP:Creator": "A. Person", "XMP:Rights": "All rights reserved" }

#### user_settings_dir ####

class TestUserSettingsDir:
    def test_env_override_wins(self, tmp_path):
        env = { "ANNOTATE_FILM_SCANS_CONFIG": str(tmp_path / "x"), "XDG_CONFIG_HOME": "/xdg" }
        assert S.user_settings_dir(env, "posix", pathlib.Path("/home/u")) == tmp_path / "x"

    def test_posix_default(self):
        assert S.user_settings_dir({}, "posix", pathlib.Path("/home/u")) == \
            pathlib.Path("/home/u/.config/annotate-film-scans")

    def test_posix_xdg(self):
        env = { "XDG_CONFIG_HOME": "/xdg" }
        assert S.user_settings_dir(env, "posix", pathlib.Path("/home/u")) == \
            pathlib.Path("/xdg/annotate-film-scans")

    def test_posix_relative_xdg_ignored(self):
        # the XDG spec says relative paths are invalid and must be ignored
        env = { "XDG_CONFIG_HOME": "rel" }
        assert S.user_settings_dir(env, "posix", pathlib.Path("/home/u")) == \
            pathlib.Path("/home/u/.config/annotate-film-scans")

    def test_windows_appdata(self):
        env = { "APPDATA": "C:/Users/u/AppData/Roaming", "XDG_CONFIG_HOME": "/xdg" }
        assert S.user_settings_dir(env, "nt", pathlib.Path("C:/Users/u")) == \
            pathlib.Path("C:/Users/u/AppData/Roaming/annotate-film-scans")

    def test_windows_no_appdata(self):
        assert S.user_settings_dir({}, "nt", pathlib.Path("C:/Users/u")) == \
            pathlib.Path("C:/Users/u/AppData/Roaming/annotate-film-scans")

#### loading and merging ####

class TestLoad:
    def test_bad_json_names_file(self, tmp_path):
        p = tmp_path / "bad.json"
        p.write_text("{ not json")
        with pytest.raises(S.SettingsError, match="bad.json"):
            S.load_settings(builtin=p, user_dir=None)

    def test_top_level_must_be_object(self, tmp_path):
        p = write_json(tmp_path / "a.json", [1, 2])
        with pytest.raises(S.SettingsError, match="a.json"):
            S.load_settings(builtin=p, user_dir=None)

    def test_unknown_category_is_error(self, tmp_path):
        p = write_json(tmp_path / "a.json", { "cameras": { "X": CAMERA_A } })
        with pytest.raises(S.SettingsError, match="cameras"):
            S.load_settings(builtin=p, user_dir=None)

    def test_entry_must_be_object(self, tmp_path):
        p = write_json(tmp_path / "a.json", { "camera": { "X": "F-1" } })
        with pytest.raises(S.SettingsError, match="X"):
            S.load_settings(builtin=p, user_dir=None)

    def test_underscore_keys_ignored(self, tmp_path):
        p = write_json(tmp_path / "a.json", {
            "_comment": "file comment",
            "camera": { "_comment": "category comment",
                        "X": { "_comment": "entry comment", **CAMERA_A } },
            })
        s = S.load_settings(builtin=p, user_dir=None)
        assert list(s["camera"]) == ["X"]
        assert s["camera"]["X"] == CAMERA_A

    def test_all_categories_present_when_empty(self):
        s = S.load_settings(builtin=None, user_dir=None)
        for c in S.CATEGORIES:
            assert s[c] == {}
        assert s.defaults == {}

    def test_missing_user_dir_is_ok(self, tmp_path):
        s = S.load_settings(builtin=None, user_dir=tmp_path / "nonexistent")
        assert s["camera"] == {}

    def test_user_replaces_builtin_entry_wholesale(self, tmp_path):
        b = write_json(tmp_path / "builtin.json", { "camera": { "X": CAMERA_A, "Y": CAMERA_B } })
        write_json(tmp_path / "user" / "settings.json", { "camera": { "X": { "IFD0:Make": "Other" } } })
        s = S.load_settings(builtin=b, user_dir=tmp_path / "user")
        assert s["camera"]["X"] == { "IFD0:Make": "Other" }
        assert s["camera"]["Y"] == CAMERA_B

    def test_null_removes_entry(self, tmp_path):
        b = write_json(tmp_path / "builtin.json", { "camera": { "X": CAMERA_A, "Y": CAMERA_B } })
        write_json(tmp_path / "user" / "settings.json", { "camera": { "X": None } })
        s = S.load_settings(builtin=b, user_dir=tmp_path / "user")
        assert list(s["camera"]) == ["Y"]

    def test_user_files_load_in_sorted_order(self, tmp_path):
        u = tmp_path / "user"
        write_json(u / "b.json", { "camera": { "X": CAMERA_B } })
        write_json(u / "a.json", { "camera": { "X": CAMERA_A } })
        s = S.load_settings(builtin=None, user_dir=u)
        assert s["camera"]["X"] == CAMERA_B
        assert s.origin("camera", "X") == u / "b.json"

    def test_templates_subdir_not_loaded(self, tmp_path):
        u = tmp_path / "user"
        write_json(u / "templates" / "camera.json", { "camera": { "Example": CAMERA_A } })
        s = S.load_settings(builtin=None, user_dir=u)
        assert s["camera"] == {}

    def test_origin_tracks_builtin(self, tmp_path):
        b = write_json(tmp_path / "builtin.json", { "camera": { "X": CAMERA_A } })
        s = S.load_settings(builtin=b, user_dir=None)
        assert s.origin("camera", "X") == b

    def test_entry_order_builtin_then_user(self, tmp_path):
        b = write_json(tmp_path / "builtin.json", { "film": { "A": {}, "B": {} } })
        write_json(tmp_path / "user" / "s.json", { "film": { "C": {}, "A": {} } })
        s = S.load_settings(builtin=b, user_dir=tmp_path / "user")
        assert list(s["film"]) == ["A", "B", "C"]

#### defaults ####

class TestDefaults:
    def test_defaults_merge_per_key(self, tmp_path):
        b = write_json(tmp_path / "builtin.json", {
            "lens": { "fixed": {} },
            "defaults": { "lens": "fixed" } })
        write_json(tmp_path / "user" / "s.json", {
            "author": { "Me": AUTHOR },
            "defaults": { "author": "Me" } })
        s = S.load_settings(builtin=b, user_dir=tmp_path / "user")
        assert s.defaults == { "lens": "fixed", "author": "Me" }

    def test_null_removes_default(self, tmp_path):
        b = write_json(tmp_path / "builtin.json", {
            "lens": { "fixed": {} }, "defaults": { "lens": "fixed" } })
        write_json(tmp_path / "user" / "s.json", { "defaults": { "lens": None } })
        s = S.load_settings(builtin=b, user_dir=tmp_path / "user")
        assert s.defaults == {}

    def test_default_must_name_existing_entry(self, tmp_path):
        b = write_json(tmp_path / "builtin.json", { "defaults": { "camera": "Nope" } })
        with pytest.raises(S.SettingsError, match="Nope"):
            S.load_settings(builtin=b, user_dir=None)

    def test_default_for_unknown_category(self, tmp_path):
        b = write_json(tmp_path / "builtin.json", { "defaults": { "cameras": "X" } })
        with pytest.raises(S.SettingsError, match="cameras"):
            S.load_settings(builtin=b, user_dir=None)

    def test_removed_entry_invalidates_default(self, tmp_path):
        b = write_json(tmp_path / "builtin.json", {
            "lens": { "fixed": {} }, "defaults": { "lens": "fixed" } })
        write_json(tmp_path / "user" / "s.json", { "lens": { "fixed": None } })
        with pytest.raises(S.SettingsError, match="fixed"):
            S.load_settings(builtin=b, user_dir=tmp_path / "user")

#### check ####

class TestCheck:
    def test_clean_settings(self, tmp_path):
        b = write_json(tmp_path / "builtin.json", {
            "camera": { "X": CAMERA_A }, "author": { "Me": AUTHOR } })
        s = S.load_settings(builtin=b, user_dir=None)
        assert s.check() == []

    def test_malformed_tag_name(self, tmp_path):
        b = write_json(tmp_path / "builtin.json", { "camera": { "X": { "Make": "Canon" } } })
        s = S.load_settings(builtin=b, user_dir=None)
        problems = s.check()
        assert len(problems) == 1 and "Make" in problems[0] and "X" in problems[0]

    def test_unknown_group(self, tmp_path):
        b = write_json(tmp_path / "builtin.json", { "camera": { "X": { "XMP-Bogus:Make": "Canon" } } })
        s = S.load_settings(builtin=b, user_dir=None)
        problems = s.check()
        assert len(problems) == 1 and "XMP-Bogus" in problems[0]

    def test_author_needs_creator_and_rights(self, tmp_path):
        b = write_json(tmp_path / "builtin.json", { "author": { "Me": { "XMP:Creator": "Me" } } })
        s = S.load_settings(builtin=b, user_dir=None)
        problems = s.check()
        assert len(problems) == 1 and "XMP:Rights" in problems[0]

#### init ####

class TestInit:
    def make_templates(self, tmp_path) -> pathlib.Path:
        t = tmp_path / "pkg_templates"
        write_json(t / "camera.json", { "camera": {} })
        write_json(t / "lens.json", { "lens": {} })
        return t

    def test_creates_dir_and_templates(self, tmp_path):
        t = self.make_templates(tmp_path)
        d = tmp_path / "cfg"
        created = S.init_settings(d, source=None, templates_dir=t)
        assert sorted(p.name for p in (d / "templates").iterdir()) == ["camera.json", "lens.json"]
        assert set(created) == { d / "templates" / "camera.json", d / "templates" / "lens.json" }
        assert not (d / "settings.json").exists()

    def test_copies_source(self, tmp_path):
        t = self.make_templates(tmp_path)
        src = write_json(tmp_path / "mine.json", { "camera": { "X": CAMERA_A } })
        d = tmp_path / "cfg"
        S.init_settings(d, source=src, templates_dir=t)
        assert json.loads((d / "settings.json").read_text()) == { "camera": { "X": CAMERA_A } }

    def test_invalid_source_rejected_before_writing(self, tmp_path):
        t = self.make_templates(tmp_path)
        src = write_json(tmp_path / "mine.json", { "cameras": {} })
        d = tmp_path / "cfg"
        with pytest.raises(S.SettingsError, match="cameras"):
            S.init_settings(d, source=src, templates_dir=t)
        assert not d.exists()

    def test_refuses_to_overwrite_anything(self, tmp_path):
        t = self.make_templates(tmp_path)
        src = write_json(tmp_path / "mine.json", { "camera": {} })
        d = tmp_path / "cfg"
        write_json(d / "settings.json", { "camera": { "Keep": CAMERA_A } })
        with pytest.raises(S.SettingsError, match="settings.json"):
            S.init_settings(d, source=src, templates_dir=t)
        assert json.loads((d / "settings.json").read_text()) == { "camera": { "Keep": CAMERA_A } }
        assert not (d / "templates").exists()

    def test_no_templates_is_error(self, tmp_path):
        with pytest.raises(S.SettingsError, match="templates"):
            S.init_settings(tmp_path / "cfg", source=None, templates_dir=tmp_path / "none")

    def test_existing_template_is_error(self, tmp_path):
        t = self.make_templates(tmp_path)
        d = tmp_path / "cfg"
        write_json(d / "templates" / "lens.json", { "lens": { "Edited": {} } })
        with pytest.raises(S.SettingsError, match="lens.json"):
            S.init_settings(d, source=None, templates_dir=t)
        assert not (d / "templates" / "camera.json").exists()

#### the packaged files ####

class TestPackaged:
    def test_builtin_settings_load_and_check(self):
        s = S.load_settings(builtin=S.builtin_settings_path(), user_dir=None)
        assert s.check() == []

    def test_templates_load_and_check(self, tmp_path):
        # every template must be valid as-is when copied up into the
        # settings directory
        templates = sorted(S.templates_path().glob("*.json"))
        assert len(templates) == len(S.CATEGORIES)
        for t in templates:
            u = tmp_path / t.stem
            write_json(u / t.name, json.loads(t.read_text()))
            s = S.load_settings(builtin=None, user_dir=u)
            assert s.check() == [], t.name
