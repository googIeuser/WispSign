import plistlib

import pytest
from appgen import PNG_1X1, make_app

from wispsign.errors import WispError
from wispsign.signing.plist_edit import AppInfo, apply_overrides, read_info


def test_read_info(tmp_path):
    app = make_app(tmp_path, bundle_id="com.example.demo")
    assert read_info(app) == AppInfo("Test", "com.example.demo", "1.0", PNG_1X1)


def test_read_info_prefers_display_name_and_no_icon(tmp_path):
    app = make_app(tmp_path)
    plist = app / "Info.plist"
    data = plistlib.loads(plist.read_bytes())
    data["CFBundleDisplayName"] = "Shown"
    del data["CFBundleIcons"]
    plist.write_bytes(plistlib.dumps(data))
    info = read_info(app)
    assert info.name == "Shown"
    assert info.icon_png is None


def test_read_info_picks_largest_icon(tmp_path):
    app = make_app(tmp_path)
    (app / "AppIcon60x60@3x.png").write_bytes(PNG_1X1 + b"padding")
    assert read_info(app).icon_png == PNG_1X1 + b"padding"


def test_read_info_missing_plist(tmp_path):
    app = tmp_path / "X.app"
    app.mkdir()
    with pytest.raises(WispError) as err:
        read_info(app)
    assert err.value.code == "error.ipa_invalid"
    assert str(tmp_path) not in str(err.value)


def test_overrides_rename_and_rebundle(tmp_path):
    app = make_app(tmp_path, bundle_id="com.example.demo")
    apply_overrides(app, name="Demo Copy", bundle_id="com.example.copy", icon_png=None)
    info = read_info(app)
    assert (info.name, info.bundle_id) == ("Demo Copy", "com.example.copy")
    ext = plistlib.loads((app / "PlugIns/Ext.appex/Info.plist").read_bytes())
    assert ext["CFBundleIdentifier"] == "com.example.copy.Ext"


def test_overrides_none_keeps_bundle(tmp_path):
    app = make_app(tmp_path, bundle_id="com.example.demo")
    apply_overrides(app, name=None, bundle_id=None, icon_png=None)
    info = read_info(app)
    assert (info.name, info.bundle_id) == ("Test", "com.example.demo")
    ext = plistlib.loads((app / "PlugIns/Ext.appex/Info.plist").read_bytes())
    assert ext["CFBundleIdentifier"] == "com.example.demo.Ext"


def test_unrelated_appex_prefix_untouched(tmp_path):
    app = make_app(tmp_path, bundle_id="com.a.app")
    other = app / "PlugIns/Other.appex"
    other.mkdir()
    (other / "Info.plist").write_bytes(
        plistlib.dumps({"CFBundleIdentifier": "com.a.app2.X"})
    )
    apply_overrides(app, name=None, bundle_id="com.b.app", icon_png=None)
    data = plistlib.loads((other / "Info.plist").read_bytes())
    assert data["CFBundleIdentifier"] == "com.a.app2.X"


NEW_ICON = PNG_1X1 + b"new"
WISP_FILES = (
    "WispIcon60x60@2x.png",
    "WispIcon60x60@3x.png",
    "WispIcon76x76@2x~ipad.png",
)


def _info(app):
    return plistlib.loads((app / "Info.plist").read_bytes())


def _assert_points_at_new_icons(app):
    info = _info(app)
    for name in WISP_FILES:
        assert (app / name).read_bytes() == NEW_ICON
    primary = info["CFBundleIcons"]["CFBundlePrimaryIcon"]
    assert primary["CFBundleIconFiles"] == ["WispIcon60x60"]
    ipad = info["CFBundleIcons~ipad"]["CFBundlePrimaryIcon"]
    assert ipad["CFBundleIconFiles"] == ["WispIcon60x60", "WispIcon76x76"]
    assert info["CFBundleIconFiles"] == ["WispIcon60x60", "WispIcon76x76"]
    for holder in (info, primary, ipad):
        assert "CFBundleIconName" not in holder
    assert read_info(app).icon_png == NEW_ICON


def test_overrides_icon_on_legacy_icon_files(tmp_path):
    app = make_app(tmp_path)
    apply_overrides(app, name=None, bundle_id=None, icon_png=NEW_ICON)
    assert (app / "AppIcon60x60@2x.png").read_bytes() == NEW_ICON
    _assert_points_at_new_icons(app)


def test_overrides_icon_on_asset_catalog_app(tmp_path):

    app = make_app(tmp_path)
    (app / "AppIcon60x60@2x.png").unlink()
    (app / "Assets.car").write_bytes(b"car")
    info = _info(app)
    info["CFBundleIconName"] = "AppIcon"
    info["CFBundleIcons"] = {
        "CFBundlePrimaryIcon": {"CFBundleIconName": "AppIcon"},
        "CFBundleAlternateIcons": {"Dark": {"CFBundleIconName": "Dark"}},
    }
    info["CFBundleIcons~ipad"] = {
        "CFBundlePrimaryIcon": {"CFBundleIconName": "AppIcon"}
    }
    (app / "Info.plist").write_bytes(plistlib.dumps(info))
    apply_overrides(app, name=None, bundle_id=None, icon_png=NEW_ICON)
    _assert_points_at_new_icons(app)
    alternate = _info(app)["CFBundleIcons"]["CFBundleAlternateIcons"]
    assert alternate == {"Dark": {"CFBundleIconName": "Dark"}}
    assert (app / "Assets.car").read_bytes() == b"car"


def test_overrides_icon_without_any_icon_keys(tmp_path):
    app = make_app(tmp_path)
    info = _info(app)
    del info["CFBundleIcons"]
    (app / "Info.plist").write_bytes(plistlib.dumps(info))
    apply_overrides(app, name=None, bundle_id=None, icon_png=NEW_ICON)
    _assert_points_at_new_icons(app)


def test_overrides_icon_that_cannot_be_written_is_an_error(tmp_path):
    app = make_app(tmp_path)
    (app / "WispIcon60x60@2x.png").mkdir()
    with pytest.raises(WispError) as err:
        apply_overrides(app, name=None, bundle_id=None, icon_png=NEW_ICON)
    assert err.value.code == "error.icon_invalid"
    assert str(tmp_path) not in str(err.value)


def test_overrides_preserve_binary_plist_format(tmp_path):
    app = make_app(tmp_path)
    plist = app / "Info.plist"
    plist.write_bytes(
        plistlib.dumps(plistlib.loads(plist.read_bytes()), fmt=plistlib.FMT_BINARY)
    )
    apply_overrides(app, name="N", bundle_id=None, icon_png=None)
    assert plist.read_bytes().startswith(b"bplist")


def _write_plist(path, raw: bytes):
    path.write_bytes(raw)


@pytest.mark.parametrize(
    "raw", [b"<plist><dict><key>", b"\x00garbage", plistlib.dumps([1, 2])]
)
def test_hostile_info_plist_is_ipa_invalid(tmp_path, raw):
    app = make_app(tmp_path)
    _write_plist(app / "Info.plist", raw)
    for call in (
        lambda: read_info(app),
        lambda: apply_overrides(app, name="N", bundle_id=None, icon_png=None),
    ):
        with pytest.raises(WispError) as err:
            call()
        assert err.value.code == "error.ipa_invalid"
        assert str(tmp_path) not in str(err.value)


@pytest.mark.parametrize("raw", [b"<plist><dict><key>", plistlib.dumps([1, 2])])
def test_hostile_appex_plist_is_ipa_invalid(tmp_path, raw):
    app = make_app(tmp_path, bundle_id="com.a.app")
    _write_plist(app / "PlugIns/Ext.appex/Info.plist", raw)
    with pytest.raises(WispError) as err:
        apply_overrides(app, name=None, bundle_id="com.b.app", icon_png=None)
    assert err.value.code == "error.ipa_invalid"
