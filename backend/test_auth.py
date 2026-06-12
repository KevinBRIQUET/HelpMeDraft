import unittest
from unittest.mock import MagicMock, patch

from werkzeug.security import check_password_hash, generate_password_hash

from app import app


class AuthenticationTestCase(unittest.TestCase):
    # Configuration d'une application et d'un navigateur de test isolés.
    def setUp(self):
        app.config.update(
            TESTING=True,
            SECRET_KEY="test-secret-key",
            SESSION_COOKIE_SECURE=False,
        )
        self.client = app.test_client()

    @staticmethod
    def create_fake_connection(result):
        cursor = MagicMock()
        cursor.fetchone.return_value = result

        connection = MagicMock()
        connection.cursor.return_value = cursor

        return connection

    # Validation des identifiants
    def test_login_requires_email_and_password(self):
        response = self.client.post("/api/login", json={})

        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.get_json()["message"],
            "Email et mot de passe obligatoires",
        )

    @patch("app.get_db_connection")
    def test_login_rejects_wrong_password(self, mocked_connection):
        user = {
            "Id_utilisateur": 1,
            "nom": "Test",
            "prenom": "Kevin",
            "email": "test@helpmedraft.fr",
            "mot_de_passe_hash": generate_password_hash("Test1234!"),
            "role": 0,
        }
        mocked_connection.return_value = self.create_fake_connection(user)

        response = self.client.post(
            "/api/login",
            json={
                "email": "test@helpmedraft.fr",
                "password": "MauvaisMotDePasse",
            },
        )

        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.get_json()["message"], "Identifiants incorrects")

    @patch("app.get_db_connection")
    def test_login_creates_user_session(self, mocked_connection):
        user = {
            "Id_utilisateur": 1,
            "nom": "Test",
            "prenom": "Kevin",
            "email": "test@helpmedraft.fr",
            "mot_de_passe_hash": generate_password_hash("Test1234!"),
            "role": 0,
        }
        mocked_connection.return_value = self.create_fake_connection(user)

        response = self.client.post(
            "/api/login",
            json={
                "email": "test@helpmedraft.fr",
                "password": "Test1234!",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["user"]["id"], 1)

        with self.client.session_transaction() as session_data:
            self.assertEqual(session_data["user_id"], 1)

    # Création d'un compte
    def test_register_rejects_weak_password(self):
        response = self.client.post(
            "/api/register",
            json={
                "prenom": "Kevin",
                "nom": "Test",
                "email": "nouveau@helpmedraft.fr",
                "password": "faible",
                "passwordConfirmation": "faible",
                "consent": True,
            },
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("8 caractères", response.get_json()["message"])

    @patch("app.get_db_connection")
    def test_register_rejects_existing_email(self, mocked_connection):
        mocked_connection.return_value = self.create_fake_connection(
            {"Id_utilisateur": 1},
        )

        response = self.client.post(
            "/api/register",
            json={
                "prenom": "Kevin",
                "nom": "Test",
                "email": "test@helpmedraft.fr",
                "password": "Test1234!",
                "passwordConfirmation": "Test1234!",
                "consent": True,
            },
        )

        self.assertEqual(response.status_code, 409)
        self.assertEqual(
            response.get_json()["message"],
            "Cette adresse e-mail est déjà utilisée",
        )

    @patch("app.get_db_connection")
    def test_register_hashes_password_and_creates_session(
        self,
        mocked_connection,
    ):
        connection = self.create_fake_connection(None)
        connection.cursor.return_value.lastrowid = 7
        mocked_connection.return_value = connection

        response = self.client.post(
            "/api/register",
            json={
                "prenom": "Kevin",
                "nom": "Test",
                "email": "nouveau@helpmedraft.fr",
                "password": "Test1234!",
                "passwordConfirmation": "Test1234!",
                "consent": True,
            },
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.get_json()["user"]["id"], 7)
        connection.commit.assert_called_once()

        insert_parameters = connection.cursor.return_value.execute.call_args_list[1]
        stored_password = insert_parameters.args[1][3]

        self.assertNotEqual(stored_password, "Test1234!")
        self.assertTrue(check_password_hash(stored_password, "Test1234!"))

        with self.client.session_transaction() as session_data:
            self.assertEqual(session_data["user_id"], 7)

    # Protection et suppression de la session
    def test_me_requires_authentication(self):
        response = self.client.get("/api/me")

        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.get_json()["message"], "Authentification requise")

    def test_logout_clears_session(self):
        with self.client.session_transaction() as session_data:
            session_data["user_id"] = 1

        response = self.client.post("/api/logout")

        self.assertEqual(response.status_code, 200)

        with self.client.session_transaction() as session_data:
            self.assertNotIn("user_id", session_data)


if __name__ == "__main__":
    unittest.main()
