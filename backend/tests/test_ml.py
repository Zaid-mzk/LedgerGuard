from scripts.generate_synthetic_transactions import generate


def test_generator_reproducible_and_label_not_feature():
    a = generate(100, 42)
    b = generate(100, 42)
    assert a.equals(b)
    assert "synthetic_label" in a.columns
    assert len(a) == 100
