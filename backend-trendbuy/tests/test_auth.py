from services.auth import generate_token, generate_unsubscribe_token, verify_unsubscribe_token


def test_generate_token_is_random_and_long():
    a = generate_token()
    b = generate_token()
    assert a != b
    assert len(a) >= 32


def test_unsubscribe_token_round_trip():
    token = generate_unsubscribe_token(42)
    assert verify_unsubscribe_token(token) == 42


def test_unsubscribe_token_tampered_signature_rejected():
    token = generate_unsubscribe_token(42)
    user_id_part, _, signature = token.partition(".")
    tampered = f"{user_id_part}.{signature[:-1]}0"
    assert verify_unsubscribe_token(tampered) is None


def test_unsubscribe_token_tampered_user_id_rejected():
    token = generate_unsubscribe_token(42)
    _, _, signature = token.partition(".")
    tampered = f"43.{signature}"
    assert verify_unsubscribe_token(tampered) is None


def test_unsubscribe_token_malformed_rejected():
    assert verify_unsubscribe_token("not-a-valid-token") is None
    assert verify_unsubscribe_token("") is None
