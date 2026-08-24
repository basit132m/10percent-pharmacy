from pharmacy_desktop.core.security import hash_password, password_problem, verify_password


def test_password_verifies_and_salts_differ():
    first = hash_password("secret123", iterations=1000)
    second = hash_password("secret123", iterations=1000)
    assert first != second
    assert verify_password("secret123", first)
    assert not verify_password("Secret123", first)


def test_garbage_hash_is_rejected_not_crashed():
    assert not verify_password("x", "not-a-hash")
    assert not verify_password("x", "")


def test_short_passwords_are_refused():
    assert password_problem("abc")
    assert password_problem("abcd") is None
