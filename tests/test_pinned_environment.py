from btcusdt_quant import governance


def test_pinned_list_hashes_to_pinned_fingerprint() -> None:
    text = governance.PINNED_ENVIRONMENT_FILE.read_text(encoding="utf-8")
    assert governance.sha256_text(text) == governance.PINNED_ENVIRONMENT_FINGERPRINT
