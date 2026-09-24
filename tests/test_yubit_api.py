import hashlib
import hmac
import unittest

from services.yubit_api import YubitAPI


class FakeYubitAPI(YubitAPI):
    def __init__(self, response):
        super().__init__()
        self.response = response
        self.request_args = None

    async def _request(self, method, path, params=None, body=None):
        self.request_args = (method, path, params, body)
        return self.response


class YubitSignatureTest(unittest.TestCase):
    def test_v2_signature_uses_documented_field_order(self):
        api = YubitAPI()
        api.api_key = "key"
        api.secret_key = "secret"
        api.recv_window = 5000
        source = (
            "GET/oapi/partner/affiliate/private/v1/validateUser"
            "1770086400123key5000uid=12345678"
        )
        expected = hmac.new(
            b"secret",
            source.encode(),
            hashlib.sha256,
        ).hexdigest()

        self.assertEqual(
            api._generate_signature(
                "GET",
                "/oapi/partner/affiliate/private/v1/validateUser",
                "1770086400123",
                "uid=12345678",
            ),
            expected,
        )


class YubitBalanceTest(unittest.IsolatedAsyncioTestCase):
    async def test_balance_response_accepts_string_success_code(self):
        api = FakeYubitAPI(
            {
                "code": "0",
                "result": {
                    "items": [
                        {
                            "uid": 12345678,
                            "totalBalance": "125.75",
                        }
                    ]
                },
            }
        )

        result = await api.validate_user("12345678")

        self.assertTrue(result["success"])
        self.assertEqual(result["balance"], 125.75)
        self.assertEqual(
            api.request_args[2],
            {"uid": "12345678"},
        )

    async def test_non_subordinate_is_rejected(self):
        api = FakeYubitAPI(
            {
                "code": 42000012,
                "msg": "not direct subordinate",
                "result": False,
            }
        )

        result = await api.validate_user("12345678")

        self.assertFalse(result["success"])

    async def test_global_commission_query_omits_uid(self):
        api = FakeYubitAPI(
            {
                "code": 0,
                "data": {"totalCommission": "12.5"},
            }
        )

        rows = await api.get_commission_report(
            None,
            1_790_000_000_000,
            1_790_000_100_000,
        )

        self.assertEqual(rows[0]["commissionAmount"], "12.5")
        self.assertNotIn("uid", api.request_args[2])


if __name__ == "__main__":
    unittest.main()
