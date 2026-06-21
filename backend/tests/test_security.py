import unittest

from app.security import redact_sensitive, validate_outbound_url


class RedactionTests(unittest.TestCase):
    def test_redacts_nested_credentials_without_mutating_input(self):
        source = {
            "headers": {"Authorization": "Bearer secret", "Content-Type": "application/json"},
            "body": {"api_key": "abc", "items": [{"token": "xyz"}]},
        }
        safe = redact_sensitive(source)
        self.assertEqual(safe["headers"]["Authorization"], "[REDACTED]")
        self.assertEqual(safe["body"]["api_key"], "[REDACTED]")
        self.assertEqual(safe["body"]["items"][0]["token"], "[REDACTED]")
        self.assertEqual(source["headers"]["Authorization"], "Bearer secret")


class OutboundUrlTests(unittest.IsolatedAsyncioTestCase):
    async def test_rejects_non_http_urls(self):
        with self.assertRaises(ValueError):
            await validate_outbound_url("file:///etc/passwd")

    async def test_rejects_loopback(self):
        with self.assertRaises(ValueError):
            await validate_outbound_url("http://127.0.0.1/private")

    async def test_allows_private_when_explicit(self):
        await validate_outbound_url("http://127.0.0.1/private", allow_private=True)

    async def test_allows_docker_proxy_benchmark_address(self):
        await validate_outbound_url("http://198.18.0.61/resource")


if __name__ == "__main__":
    unittest.main()
