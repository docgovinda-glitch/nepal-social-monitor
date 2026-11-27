import os
import time
import unittest
from unittest import mock

os.environ.setdefault("APP_PASSWORD", "PIC@55")
os.environ.setdefault("APP_ENCRYPTION_KEY", "test-encryption-key-32bytes-long")


class MultiUserGreenApiTests(unittest.TestCase):
    def test_password_hashing_and_verification(self):
        import auth_store

        h1 = auth_store.hash_password("SecretPass123")
        h2 = auth_store.hash_password("SecretPass123")
        self.assertNotEqual(h1, h2)
        self.assertTrue(h1.startswith("scrypt$"))
        self.assertTrue(auth_store.verify_password("SecretPass123", h1))
        self.assertFalse(auth_store.verify_password("WrongPass", h1))
        self.assertFalse(auth_store.verify_password("", h1))

    def test_secret_encryption_roundtrip_and_tamper_detection(self):
        import auth_store

        ct = auth_store.encrypt_secret("my-green-api-token-999")
        self.assertTrue(ct.startswith("v1$"))
        self.assertNotIn("my-green-api-token-999", ct)
        self.assertEqual(auth_store.decrypt_secret(ct), "my-green-api-token-999")

        # Tamper with ciphertext
        parts = ct.split("$")
        tampered = "$".join([parts[0], parts[1], parts[2][:-2] + "AA", parts[3]])
        self.assertEqual(auth_store.decrypt_secret(tampered), "")
        self.assertEqual(auth_store.decrypt_secret(""), "")

    def test_session_token_roundtrip_expiry_and_tamper(self):
        import auth_store

        tok = auth_store.create_session_token(user_id=42, username="desk_editor", role="user", ttl_seconds=60)
        payload = auth_store.verify_session_token(tok)
        self.assertIsNotNone(payload)
        self.assertEqual(payload["uid"], 42)
        self.assertEqual(payload["u"], "desk_editor")
        self.assertEqual(payload["r"], "user")

        # Tampered signature fails
        self.assertIsNone(auth_store.verify_session_token(tok + "x"))

        # Expired token fails
        expired = auth_store.create_session_token(user_id=42, username="desk_editor", role="user", ttl_seconds=-5)
        self.assertIsNone(auth_store.verify_session_token(expired))

    def test_register_and_authenticate_approval_states(self):
        import auth_store

        # Validation checks
        ok_bad_user, _ = auth_store.register_user("a", "Short", "password123")
        self.assertFalse(ok_bad_user)
        ok_bad_pwd, _ = auth_store.register_user("validuser", "Valid", "123")
        self.assertFalse(ok_bad_pwd)

        # Pending user cannot log in
        pwd_hash = auth_store.hash_password("UserPass99")
        with mock.patch("auth_store.query_supabase", return_value=[{
            "id": 7,
            "username": "alice",
            "display_name": "Alice",
            "password_hash": pwd_hash,
            "role": "user",
            "status": "pending",
        }]):
            u, err = auth_store.authenticate_user("alice", "UserPass99")
            self.assertIsNone(u)
            self.assertIn("pending", err.lower())

        # Disabled user cannot log in
        with mock.patch("auth_store.query_supabase", return_value=[{
            "id": 7,
            "username": "alice",
            "display_name": "Alice",
            "password_hash": pwd_hash,
            "role": "user",
            "status": "disabled",
        }]):
            u, err = auth_store.authenticate_user("alice", "UserPass99")
            self.assertIsNone(u)
            self.assertIn("disabled", err.lower())

        # Approved user succeeds (and first-name match works when multiple candidates share first name)
        other_hash = auth_store.hash_password("OtherPass99")
        with mock.patch("auth_store.query_supabase", return_value=[
            {
                "id": 6,
                "username": "alice.rai",
                "display_name": "Alice Rai",
                "password_hash": other_hash,
                "role": "user",
                "status": "approved",
            },
            {
                "id": 7,
                "username": "alice.sharma",
                "display_name": "Alice Sharma",
                "password_hash": pwd_hash,
                "role": "user",
                "status": "approved",
            },
        ]):
            u, err = auth_store.authenticate_user("Alice", "UserPass99")
            self.assertIsNotNone(u)
            self.assertEqual(err, "")
            self.assertEqual(u["id"], 7)
            self.assertEqual(u["role"], "user")

    def test_per_user_greenapi_config_routing_and_group_membership(self):
        import whatsapp_greenapi as ga

        cfg_a = {
            "api_url": "https://7105.api.greenapi.com",
            "id_instance": "111111",
            "token_instance": "tok_aaa",
            "sending_enabled": True,
        }
        cfg_disabled = {
            "api_url": "https://7105.api.greenapi.com",
            "id_instance": "222222",
            "token_instance": "tok_bbb",
            "sending_enabled": False,
        }
        empty_cfg = {"api_url": "", "id_instance": "", "token_instance": "", "sending_enabled": False}

        self.assertTrue(ga.is_configured(config=cfg_a))
        self.assertTrue(ga.is_sending_active(session_approved=True, config=cfg_a))
        self.assertFalse(ga.is_sending_active(session_approved=True, config=cfg_disabled))
        self.assertFalse(ga.is_configured(config=empty_cfg))
        self.assertFalse(ga.is_sending_active(session_approved=True, config=empty_cfg))

        # Send routes to cfg_a's endpoint
        mock_resp = mock.MagicMock(status_code=200)
        mock_resp.json.return_value = {"idMessage": "MSG_USER_A_1"}
        with mock.patch("whatsapp_greenapi.requests.post", return_value=mock_resp) as m_post:
            res = ga.send_group_message(
                chat_id=ga.NEWS_SHARE_GROUPS[0]["id"],
                message="Hello from User A",
                session_approved=True,
                config=cfg_a,
            )
            self.assertTrue(res["ok"])
            self.assertEqual(res["id_message"], "MSG_USER_A_1")
            called_url = m_post.call_args[0][0]
            self.assertIn("/waInstance111111/sendMessage/tok_aaa", called_url)

        # verify_fixed_group_membership detects present & missing fixed groups
        mock_chats = mock.MagicMock(status_code=200)
        mock_chats.json.return_value = [
            {"id": ga.NEWS_SHARE_GROUPS[0]["id"], "name": ga.NEWS_SHARE_GROUPS[0]["name"]},
            {"id": ga.SOCIAL_MEDIA_GROUP["id"], "name": ga.SOCIAL_MEDIA_GROUP["name"]},
        ]
        with mock.patch("whatsapp_greenapi.requests.get", return_value=mock_chats):
            mem = ga.verify_fixed_group_membership(config=cfg_a)
            self.assertTrue(mem["ok"])
            self.assertEqual(len(mem["present"]), 2)
            self.assertEqual(len(mem["missing"]), 1)
            self.assertEqual(mem["missing"][0]["id"], ga.NEWS_SHARE_GROUPS[1]["id"])

    def test_record_whatsapp_sent_includes_user_attribution(self):
        import nepal_news_store as store

        captured = []
        with mock.patch("nepal_news_store.query_supabase", side_effect=lambda sql: captured.append(sql) or []):
            ok = store.record_whatsapp_sent(
                item_key="item_123",
                group_id="120363428884458826@g.us",
                group_name="India Related News in Nepali Media",
                id_message="WA_999",
                item_link="https://example.com/news",
                sent_by_user_id=7,
                sent_by_username="alice",
            )
            self.assertTrue(ok)
            self.assertEqual(len(captured), 1)
            self.assertIn("sent_by_user_id", captured[0])
            self.assertIn("sent_by_username", captured[0])
            self.assertIn("'alice'", captured[0])

    def test_change_own_password_verification(self):
        import auth_store

        old_hash = auth_store.hash_password("OldPass123")
        with mock.patch("auth_store.query_supabase", return_value=[{"password_hash": old_hash}]):
            ok_wrong, _ = auth_store.change_own_password(7, "WrongOld", "NewPass456")
            self.assertFalse(ok_wrong)
            ok_short, _ = auth_store.change_own_password(7, "OldPass123", "123")
            self.assertFalse(ok_short)
            ok_good, _ = auth_store.change_own_password(7, "OldPass123", "NewPass456")
            self.assertTrue(ok_good)


if __name__ == "__main__":
    unittest.main()
