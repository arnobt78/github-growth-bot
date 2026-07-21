from app.token_crypto import decrypt_token, encrypt_token


def test_encrypt_decrypt_round_trip():
    plaintext = "gho_realGitHubOAuthTokenValue"
    ciphertext = encrypt_token(plaintext)
    assert ciphertext != plaintext
    assert decrypt_token(ciphertext) == plaintext
