from __future__ import annotations

import unittest

from scripts.real_provider_acceptance import (
    classify_provider,
    require_real_response,
    sanitize_error,
)


class RealProviderAcceptanceHelperTests(unittest.TestCase):
    def test_classify_provider_rejects_mock_and_fallback(self) -> None:
        self.assertEqual(classify_provider({"provider": "xiaomi_mimo", "fallback_used": False}), "real")
        self.assertEqual(classify_provider({"provider": "mock", "fallback_used": False}), "mock")
        self.assertEqual(classify_provider({"provider": "fallback", "fallback_used": True}), "fallback")

    def test_require_real_response_rejects_mock_even_when_http_succeeds(self) -> None:
        with self.assertRaisesRegex(RuntimeError, "tutor"):
            require_real_response({"provider": "mock", "fallback_used": False}, "tutor")

    def test_sanitize_error_removes_bearer_tokens(self) -> None:
        self.assertNotIn("secret-value", sanitize_error("Bearer secret-value provider failed"))
