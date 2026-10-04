from app.services.file_hash import calculate_file_hash


def test_calculate_file_hash(tmp_path):
    test_file = tmp_path / "test.txt"
    test_file.write_text("ManualMind test content", encoding="utf-8")

    file_hash = calculate_file_hash(str(test_file))

    assert isinstance(file_hash, str)
    assert len(file_hash) == 64