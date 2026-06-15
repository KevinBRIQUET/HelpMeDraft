import unittest
from unittest.mock import MagicMock, patch

from werkzeug.security import check_password_hash, generate_password_hash

from app import (
    OllamaUnavailableError,
    app,
    call_ollama,
    clean_ollama_answer,
)


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

    def test_ollama_answer_hides_model_thinking(self):
        raw_answer = (
            "<think>Analyse interne qui ne doit pas être affichée.</think>\n\n"
            "OK"
        )

        self.assertEqual(clean_ollama_answer(raw_answer), "OK")

    def test_ollama_answer_handles_missing_opening_think_tag(self):
        raw_answer = (
            "Analyse interne sans balise ouvrante.\n"
            "</think>\n\n"
            "OK"
        )

        self.assertEqual(clean_ollama_answer(raw_answer), "OK")

    @patch("app.urlopen")
    def test_ollama_rejects_truncated_response(self, mocked_urlopen):
        mocked_response = MagicMock()
        mocked_response.read.return_value = (
            b'{"done_reason": "length", '
            b'"message": {"content": "Incomplete answer"}}'
        )
        mocked_urlopen.return_value.__enter__.return_value = mocked_response

        with self.assertRaises(OllamaUnavailableError):
            call_ollama([{"role": "user", "content": "Corrige ce texte"}])

    @patch("app.call_ollama", return_value="OK")
    def test_ollama_connection_returns_model_response(self, mocked_ollama):
        with self.client.session_transaction() as session_data:
            session_data["user_id"] = 7

        response = self.client.get("/api/test-ollama")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["response"], "OK")
        mocked_ollama.assert_called_once()

    @patch(
        "app.call_ollama",
        side_effect=OllamaUnavailableError,
    )
    def test_ollama_connection_handles_unavailable_service(
        self,
        mocked_ollama,
    ):
        with self.client.session_transaction() as session_data:
            session_data["user_id"] = 7

        response = self.client.get("/api/test-ollama")

        self.assertEqual(response.status_code, 503)
        self.assertIn("Ollama est inaccessible", response.get_json()["message"])
        mocked_ollama.assert_called_once()

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

    @patch("app.get_db_connection")
    def test_dashboard_summary_returns_user_statistics(
        self,
        mocked_connection,
    ):
        summary = {
            "quota_restant": 20,
            "date_inscription": "15/06/2026",
            "nombre_dossiers": 2,
            "nombre_documents": 5,
        }
        mocked_connection.return_value = self.create_fake_connection(summary)

        with self.client.session_transaction() as session_data:
            session_data["user_id"] = 1

        response = self.client.get("/api/dashboard-summary")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["summary"], summary)

    @patch("app.get_db_connection")
    def test_folders_are_limited_to_connected_user(self, mocked_connection):
        cursor = MagicMock()
        cursor.fetchall.return_value = [
            {
                "id": 3,
                "nom": "Travail",
                "date_creation": "15/06/2026",
                "nombre_documents": 2,
            },
        ]
        connection = MagicMock()
        connection.cursor.return_value = cursor
        mocked_connection.return_value = connection

        with self.client.session_transaction() as session_data:
            session_data["user_id"] = 7

        response = self.client.get("/api/folders")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["folders"][0]["nom"], "Travail")
        self.assertEqual(cursor.execute.call_args.args[1], (7,))

    @patch("app.get_db_connection")
    def test_create_folder_assigns_connected_user(self, mocked_connection):
        cursor = MagicMock()
        cursor.lastrowid = 4
        connection = MagicMock()
        connection.cursor.return_value = cursor
        mocked_connection.return_value = connection

        with self.client.session_transaction() as session_data:
            session_data["user_id"] = 7

        response = self.client.post("/api/folders", json={"name": "Personnel"})

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.get_json()["folder"]["id"], 4)
        self.assertEqual(cursor.execute.call_args.args[1], ("Personnel", 7))
        connection.commit.assert_called_once()

    def test_create_folder_rejects_long_name(self):
        with self.client.session_transaction() as session_data:
            session_data["user_id"] = 7

        response = self.client.post(
            "/api/folders",
            json={"name": "Dossier avec un nom beaucoup trop long"},
        )

        self.assertEqual(response.status_code, 400)

    @patch("app.get_db_connection")
    def test_update_folder_checks_owner(self, mocked_connection):
        cursor = MagicMock()
        cursor.rowcount = 1
        connection = MagicMock()
        connection.cursor.return_value = cursor
        mocked_connection.return_value = connection

        with self.client.session_transaction() as session_data:
            session_data["user_id"] = 7

        response = self.client.patch(
            "/api/folders/4",
            json={"name": "Archives"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(cursor.execute.call_args.args[1], ("Archives", 4, 7))
        connection.commit.assert_called_once()

    @patch("app.get_db_connection")
    def test_delete_folder_rejects_folder_with_documents(
        self,
        mocked_connection,
    ):
        mocked_connection.return_value = self.create_fake_connection(
            {"nombre_documents": 2},
        )

        with self.client.session_transaction() as session_data:
            session_data["user_id"] = 7

        response = self.client.delete("/api/folders/4")

        self.assertEqual(response.status_code, 409)
        self.assertEqual(
            response.get_json()["message"],
            "Ce dossier contient encore des documents",
        )

    @patch("app.get_db_connection")
    def test_delete_empty_folder_checks_owner(self, mocked_connection):
        cursor = MagicMock()
        cursor.fetchone.return_value = {"nombre_documents": 0}
        cursor.rowcount = 1
        connection = MagicMock()
        connection.cursor.return_value = cursor
        mocked_connection.return_value = connection

        with self.client.session_transaction() as session_data:
            session_data["user_id"] = 7

        response = self.client.delete("/api/folders/4")

        self.assertEqual(response.status_code, 200)
        delete_parameters = cursor.execute.call_args_list[1].args[1]
        self.assertEqual(delete_parameters, (4, 7))
        connection.commit.assert_called_once()

    @patch("app.get_db_connection")
    def test_documents_are_limited_to_connected_user(self, mocked_connection):
        cursor = MagicMock()
        cursor.fetchall.return_value = [
            {
                "id": 9,
                "titre": "Compte rendu",
                "extrait": "Contenu du document",
                "derniere_modification": "15/06/2026 à 14:30",
                "dossier_id": 4,
                "dossier_nom": "Travail",
            },
        ]
        connection = MagicMock()
        connection.cursor.return_value = cursor
        mocked_connection.return_value = connection

        with self.client.session_transaction() as session_data:
            session_data["user_id"] = 7

        response = self.client.get("/api/documents")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.get_json()["documents"][0]["titre"],
            "Compte rendu",
        )
        self.assertEqual(cursor.execute.call_args.args[1], (7,))

    @patch("app.get_db_connection")
    def test_create_document_assigns_connected_user(self, mocked_connection):
        cursor = MagicMock()
        cursor.lastrowid = 9
        connection = MagicMock()
        connection.cursor.return_value = cursor
        mocked_connection.return_value = connection

        with self.client.session_transaction() as session_data:
            session_data["user_id"] = 7

        response = self.client.post(
            "/api/documents",
            json={
                "title": "Compte rendu",
                "content": "",
                "folderId": None,
            },
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.get_json()["document"]["id"], 9)
        self.assertEqual(
            cursor.execute.call_args.args[1],
            ("Compte rendu", "", None, 7),
        )
        connection.commit.assert_called_once()

    @patch("app.get_db_connection")
    def test_create_document_rejects_another_user_folder(
        self,
        mocked_connection,
    ):
        mocked_connection.return_value = self.create_fake_connection(None)

        with self.client.session_transaction() as session_data:
            session_data["user_id"] = 7

        response = self.client.post(
            "/api/documents",
            json={
                "title": "Document privé",
                "content": "",
                "folderId": 99,
            },
        )

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.get_json()["message"], "Dossier introuvable")

    @patch("app.get_db_connection")
    def test_get_document_checks_owner(self, mocked_connection):
        document = {
            "id": 9,
            "titre": "Compte rendu",
            "contenu": "Texte complet",
            "dossier_id": 4,
            "derniere_modification": "15/06/2026 à 14:30",
        }
        mocked_connection.return_value = self.create_fake_connection(document)

        with self.client.session_transaction() as session_data:
            session_data["user_id"] = 7

        response = self.client.get("/api/documents/9")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["document"]["contenu"], "Texte complet")
        self.assertEqual(
            mocked_connection.return_value.cursor.return_value.execute
            .call_args.args[1],
            (9, 7),
        )

    @patch("app.get_db_connection")
    def test_update_document_checks_owner(self, mocked_connection):
        cursor = MagicMock()
        cursor.fetchone.return_value = {"Id_document": 9}
        connection = MagicMock()
        connection.cursor.return_value = cursor
        mocked_connection.return_value = connection

        with self.client.session_transaction() as session_data:
            session_data["user_id"] = 7

        response = self.client.patch(
            "/api/documents/9",
            json={
                "title": "Nouveau titre",
                "content": "Nouveau contenu",
                "folderId": None,
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            cursor.execute.call_args_list[1].args[1],
            ("Nouveau titre", "Nouveau contenu", None, 9, 7),
        )
        connection.commit.assert_called_once()

    @patch("app.get_db_connection")
    def test_update_document_rejects_another_user_folder(
        self,
        mocked_connection,
    ):
        cursor = MagicMock()
        cursor.fetchone.side_effect = [{"Id_document": 9}, None]
        connection = MagicMock()
        connection.cursor.return_value = cursor
        mocked_connection.return_value = connection

        with self.client.session_transaction() as session_data:
            session_data["user_id"] = 7

        response = self.client.patch(
            "/api/documents/9",
            json={
                "title": "Document privé",
                "content": "Contenu",
                "folderId": 99,
            },
        )

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.get_json()["message"], "Dossier introuvable")

    def test_correct_document_requires_text(self):
        with self.client.session_transaction() as session_data:
            session_data["user_id"] = 7

        response = self.client.post(
            "/api/documents/9/ai/correct",
            json={"text": ""},
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.get_json()["message"],
            "Le texte à traiter est obligatoire",
        )

    @patch("app.call_ollama")
    @patch("app.get_db_connection")
    def test_correct_document_rejects_exhausted_quota(
        self,
        mocked_connection,
        mocked_ollama,
    ):
        mocked_connection.return_value = self.create_fake_connection({
            "Id_document": 9,
            "quota_restant": 0,
        })

        with self.client.session_transaction() as session_data:
            session_data["user_id"] = 7

        response = self.client.post(
            "/api/documents/9/ai/correct",
            json={"text": "Je suis aller à la réunion."},
        )

        self.assertEqual(response.status_code, 429)
        self.assertIn("quota", response.get_json()["message"])
        mocked_ollama.assert_not_called()

    @patch(
        "app.call_ollama",
        return_value="Je suis allé à la réunion.",
    )
    @patch("app.get_db_connection")
    def test_correct_document_saves_interaction_and_decrements_quota(
        self,
        mocked_connection,
        mocked_ollama,
    ):
        read_connection = self.create_fake_connection({
            "Id_document": 9,
            "quota_restant": 20,
        })

        write_cursor = MagicMock()
        write_cursor.rowcount = 1
        write_connection = MagicMock()
        write_connection.cursor.return_value = write_cursor
        mocked_connection.side_effect = [read_connection, write_connection]

        with self.client.session_transaction() as session_data:
            session_data["user_id"] = 7

        response = self.client.post(
            "/api/documents/9/ai/correct",
            json={"text": "Je suis aller à la réunion."},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.get_json()["suggestion"],
            "Je suis allé à la réunion.",
        )
        self.assertEqual(response.get_json()["quota_restant"], 19)
        self.assertEqual(
            write_cursor.execute.call_args_list[1].args[1],
            (
                "correction",
                "Je suis aller à la réunion.",
                "Je suis allé à la réunion.",
                7,
                9,
            ),
        )
        write_connection.commit.assert_called_once()
        mocked_ollama.assert_called_once()

    def test_ai_rejects_unknown_action(self):
        with self.client.session_transaction() as session_data:
            session_data["user_id"] = 7

        response = self.client.post(
            "/api/documents/9/ai/inconnue",
            json={"text": "Texte"},
        )

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.get_json()["message"], "Action IA inconnue")

    @patch(
        "app.call_ollama",
        return_value="Nous vous confirmons la tenue de la réunion.",
    )
    @patch("app.get_db_connection")
    def test_rephrase_document_records_short_database_type(
        self,
        mocked_connection,
        mocked_ollama,
    ):
        read_connection = self.create_fake_connection({
            "Id_document": 9,
            "quota_restant": 8,
        })
        write_cursor = MagicMock()
        write_cursor.rowcount = 1
        write_connection = MagicMock()
        write_connection.cursor.return_value = write_cursor
        mocked_connection.side_effect = [read_connection, write_connection]

        with self.client.session_transaction() as session_data:
            session_data["user_id"] = 7

        response = self.client.post(
            "/api/documents/9/ai/rephrase",
            json={"text": "La réunion est bien prévue."},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            write_cursor.execute.call_args_list[1].args[1][0],
            "reformuler",
        )
        mocked_ollama.assert_called_once()

    @patch("app.get_db_connection")
    def test_delete_document_checks_owner(self, mocked_connection):
        cursor = MagicMock()
        cursor.fetchone.return_value = {
            "Id_document": 9,
            "titre": "Document à supprimer",
        }
        connection = MagicMock()
        connection.cursor.return_value = cursor
        mocked_connection.return_value = connection

        with self.client.session_transaction() as session_data:
            session_data["user_id"] = 7

        response = self.client.delete("/api/documents/9")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["message"], "Document supprimé")
        self.assertEqual(
            cursor.execute.call_args_list[0].args[1],
            (9, 7),
        )
        self.assertEqual(
            cursor.execute.call_args_list[2].args[1],
            (9, 7),
        )
        connection.commit.assert_called_once()

    @patch("app.get_db_connection")
    def test_delete_document_rejects_unknown_document(
        self,
        mocked_connection,
    ):
        mocked_connection.return_value = self.create_fake_connection(None)

        with self.client.session_transaction() as session_data:
            session_data["user_id"] = 7

        response = self.client.delete("/api/documents/99")

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.get_json()["message"], "Document introuvable")
        mocked_connection.return_value.commit.assert_not_called()

    def test_logout_clears_session(self):
        with self.client.session_transaction() as session_data:
            session_data["user_id"] = 1

        response = self.client.post("/api/logout")

        self.assertEqual(response.status_code, 200)

        with self.client.session_transaction() as session_data:
            self.assertNotIn("user_id", session_data)


if __name__ == "__main__":
    unittest.main()
