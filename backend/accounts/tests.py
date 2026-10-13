from rest_framework.test import APITestCase

from .models import User


class AuthTests(APITestCase):
    def setUp(self):
        self.editor = User.objects.create_user(
            email="editor@example.com", password="pass12345!", full_name="Ed Itor", role=User.Role.EDITOR
        )
        self.writer = User.objects.create_user(
            email="writer@example.com", password="pass12345!", full_name="Wri Ter", role=User.Role.WRITER
        )

    def login(self, email, password):
        return self.client.post("/api/auth/login/", {"email": email, "password": password}, format="json")

    def test_login_returns_tokens_and_profile(self):
        response = self.login("editor@example.com", "pass12345!")
        self.assertEqual(response.status_code, 200)
        self.assertIn("access", response.data)
        self.assertEqual(response.data["user"]["role"], "EDITOR")

    def test_login_email_is_case_insensitive(self):
        response = self.login("Editor@Example.com", "pass12345!")
        self.assertEqual(response.status_code, 200)

    def test_wrong_password_is_rejected(self):
        response = self.login("editor@example.com", "wrong")
        self.assertEqual(response.status_code, 401)

    def test_me_requires_login(self):
        response = self.client.get("/api/auth/me/")
        self.assertEqual(response.status_code, 401)

    def test_writer_cannot_call_editor_only_endpoint(self):
        token = self.login("writer@example.com", "pass12345!").data["access"]
        self.client.credentials(HTTP_AUTHORIZATION="Bearer " + token)
        response = self.client.get("/api/auth/writers/")
        self.assertEqual(response.status_code, 403)

    def test_editor_can_list_writers(self):
        token = self.login("editor@example.com", "pass12345!").data["access"]
        self.client.credentials(HTTP_AUTHORIZATION="Bearer " + token)
        response = self.client.get("/api/auth/writers/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 1)
