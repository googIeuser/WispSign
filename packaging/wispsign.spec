
from pathlib import Path

from PyInstaller.utils.hooks import collect_all

ROOT = Path(SPECPATH).parent

datas = [
    (str(ROOT / "ui" / "dist"), "ui"),
    (str(ROOT / "vendor" / "zsign" / "zsign.exe"), "zsign"),
    (str(ROOT / "LICENSE"), "."),
    (str(ROOT / "third_party" / "zsign" / "LICENSE"), "third_party/zsign"),

    (str(ROOT / "build" / "notices" / "THIRD_PARTY_NOTICES.txt"), "."),
]
binaries = []
hiddenimports = ["clr_loader", "pythonnet"]

for package in ("pymobiledevice3", "webview"):
    pkg_datas, pkg_binaries, pkg_hidden = collect_all(package)
    datas += pkg_datas
    binaries += pkg_binaries
    hiddenimports += pkg_hidden

a = Analysis(
    [str(ROOT / "src" / "wispsign" / "__main__.py")],
    pathex=[str(ROOT / "src")],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    noarchive=False,
)


a.datas = [entry for entry in a.datas if Path(entry[0]).name != "direct_url.json"]
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="WispSign",
    console=False,
    icon=str(ROOT / "packaging" / "assets" / "wispsign.ico"),
)
coll = COLLECT(exe, a.binaries, a.datas, name="WispSign")
