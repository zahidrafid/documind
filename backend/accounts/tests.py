from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient

User = get_user_model()
PASSWORD = "a-long-test-pass-42"


class AuthApiTests(TestCase):
    def setUp(self):
        self.client = APIClient()

    def login(self, username):
        response = self.client.post(
            "/api/auth/login/", {"username": username, "password": PASSWORD}, format="json"
        )
        return response.data["token"]

    def test_register_returns_token_and_hashes_password(self):
        response = self.client.post(
            "/api/auth/register/",
            {"username": "carol", "email": "carol@example.com", "password": PASSWORD},
            format="json",
        )

        self.assertEqual(response.status_code, 201)
        user = User.objects.get(username="carol")
        self.assertTrue(Token.objects.filter(user=user, key=response.data["token"]).exists())
        self.assertNotEqual(user.password, PASSWORD)
        self.assertTrue(user.check_password(PASSWORD))

    def test_weak_password_is_rejected(self):
        response = self.client.post(
            "/api/auth/register/", {"username": "carol", "password": "password"}, format="json"
        )
        self.assertEqual(response.status_code, 400)
        self.assertFalse(User.objects.filter(username="carol").exists())

    def test_login_returns_a_working_token(self):
        User.objects.create_user("dave", password=PASSWORD)
        token = self.login("dave")

        self.client.credentials(HTTP_AUTHORIZATION=f"Token {token}")
        response = self.client.get("/api/auth/me/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["username"], "dave")

    def test_logout_invalidates_the_token(self):
        User.objects.create_user("dave", password=PASSWORD)
        token = self.login("dave")
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {token}")

        self.assertEqual(self.client.post("/api/auth/logout/").status_code, 204)
        self.assertEqual(self.client.get("/api/auth/me/").status_code, 401)

    def test_me_requires_authentication(self):
        self.assertEqual(self.client.get("/api/auth/me/").status_code, 401)


@override_settings(DEMO_USERNAME="demo")
class DemoAccountTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.demo = User.objects.create_user("demo", password=PASSWORD)

    def test_demo_login_returns_a_token_marked_as_demo(self):
        response = self.client.post("/api/auth/demo/")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data["user"]["is_demo"])

    def test_demo_logout_keeps_the_shared_token(self):
        token = self.client.post("/api/auth/demo/").data["token"]
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {token}")
        self.client.post("/api/auth/logout/")
        self.assertTrue(Token.objects.filter(key=token).exists())

    def test_demo_cannot_upload_or_delete(self):
        self.client.force_authenticate(self.demo)
        self.assertEqual(self.client.post("/api/documents/", {}, format="multipart").status_code, 403)
        self.assertEqual(self.client.get("/api/documents/").status_code, 200)

    @override_settings(DEMO_USERNAME="")
    def test_demo_login_disabled_without_setting(self):
        self.assertEqual(self.client.post("/api/auth/demo/").status_code, 404)

    @override_settings(ALLOW_REGISTRATION=False)
    def test_registration_can_be_closed(self):
        response = self.client.post(
            "/api/auth/register/", {"username": "erin", "password": PASSWORD}, format="json"
        )
        self.assertEqual(response.status_code, 403)
