from wispsign.storage import JsonStore


def test_jsonstore_roundtrip_and_default(tmp_path):
    s = JsonStore(tmp_path / "x.json", default=[])
    assert s.load() == []
    s.save([{"a": 1}])
    assert s.load() == [{"a": 1}]
    assert not (tmp_path / "x.json.tmp").exists()


def test_jsonstore_corrupt_file_returns_default(tmp_path):
    p = tmp_path / "x.json"
    p.write_text("{oops")
    assert JsonStore(p, default={}).load() == {}


def test_corrupt_file_is_renamed_aside(tmp_path):
    p = tmp_path / "x.json"
    p.write_text("{oops")
    JsonStore(p, default={}).load()
    assert not p.exists()
    backups = list(tmp_path.glob("x.json.corrupt-*"))
    assert len(backups) == 1 and backups[0].read_text() == "{oops"


def test_invalid_utf8_counts_as_corrupt(tmp_path):
    p = tmp_path / "x.json"
    p.write_bytes(b'{"n": "\xff\xfe"}')
    assert JsonStore(p, default={}).load() == {}
    assert len(list(tmp_path.glob("x.json.corrupt-*"))) == 1


def test_default_is_not_shared_between_loads(tmp_path):
    s = JsonStore(tmp_path / "x.json", default=[])
    s.load().append(1)
    assert s.load() == []


def test_save_creates_parent_and_keeps_unicode(tmp_path):
    s = JsonStore(tmp_path / "sub" / "x.json", default={})
    s.save({"n": "çay"})
    assert s.load() == {"n": "çay"}


def test_concurrent_saves_keep_valid_json(tmp_path):
    import json
    import threading

    path = tmp_path / "x.json"
    store = JsonStore(path, default=[])
    errors = []

    def work(i):
        try:
            for _ in range(20):
                store.save({"i": i, "pad": "x" * 5000})
        except Exception as exc:  # noqa: BLE001
            errors.append(exc)

    threads = [threading.Thread(target=work, args=(i,)) for i in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert errors == []
    assert json.loads(path.read_text())["pad"] == "x" * 5000
    assert list(tmp_path.glob("*.tmp")) == []
