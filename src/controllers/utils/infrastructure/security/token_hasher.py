import hashlib
import hmac
import secrets


class TokenHasher:
    def __init__(self, pepper: str) -> None:
        if not pepper:
            raise ValueError("LIBRARY_TOKEN_PEPPER must not be empty")
        self._pepper = pepper.encode("utf-8")

    def generate(self) -> tuple[str, str]:
        public_prefix = secrets.token_hex(6)
        secret = secrets.token_urlsafe(32)
        return public_prefix, f"rl_{public_prefix}_{secret}"

    def digest(self, token: str) -> str:
        return hmac.new(self._pepper, token.encode("utf-8"), hashlib.sha256).hexdigest()

    def matches(self, token: str, expected_hash: str) -> bool:
        return hmac.compare_digest(self.digest(token), expected_hash)

    @staticmethod
    def public_prefix(token: str) -> str | None:
        marker, separator, remainder = token.partition("_")
        if marker != "rl" or not separator:
            return None
        prefix, separator, secret = remainder.partition("_")
        if not separator or not prefix or not secret:
            return None
        return prefix
