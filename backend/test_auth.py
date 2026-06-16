import unittest
from unittest.mock import MagicMock, patch

from werkzeug.security import check_password_hash, generate_password_hash

from app import (
    OllamaUnavailableError,
    app,
    call_ollama,
    clean_ollama_answer,
    create_password_reset_token,
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
        self.active_account_patcher = patch(
            "app.account_is_active",
            return_value=True,
        )
        self.mocked_active_account = self.active_account_patcher.start()

    def tearDown(self):
        self.active_account_patcher.stop()

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

    @patch("app.send_password_reset_email", return_value=False)
    @patch("app.get_db_connection")
    def test_forgot_password_returns_development_link(
        self,
        mocked_connection,
        mocked_email,
    ):
        password_hash = generate_password_hash("Ancien123")
        mocked_connection.return_value = self.create_fake_connection({
            "Id_utilisateur": 7,
            "email": "test@helpmedraft.fr",
            "mot_de_passe_hash": password_hash,
        })

        response = self.client.post(
            "/api/forgot-password",
            json={"email": "test@helpmedraft.fr"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn(
            "development_reset_url",
            response.get_json(),
        )
        self.assertIn(
            "/reset-password?token=",
            response.get_json()["development_reset_url"],
        )
        mocked_email.assert_called_once()

    @patch("app.send_password_reset_email")
    @patch("app.get_db_connection")
    def test_forgot_password_hides_unknown_email(
        self,
        mocked_connection,
        mocked_email,
    ):
        mocked_connection.return_value = self.create_fake_connection(None)

        response = self.client.post(
            "/api/forgot-password",
            json={"email": "inconnu@helpmedraft.fr"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertNotIn("development_reset_url", response.get_json())
        mocked_email.assert_not_called()

    @patch("app.get_db_connection")
    def test_reset_password_updates_hash(self, mocked_connection):
        old_hash = generate_password_hash("Ancien123")
        token = create_password_reset_token(7, old_hash)
        cursor = MagicMock()
        cursor.fetchone.return_value = {
            "Id_utilisateur": 7,
            "mot_de_passe_hash": old_hash,
        }
        connection = MagicMock()
        connection.cursor.return_value = cursor
        mocked_connection.return_value = connection

        response = self.client.post(
            "/api/reset-password",
            json={
                "token": token,
                "password": "Nouveau123",
                "passwordConfirmation": "Nouveau123",
            },
        )

        self.assertEqual(response.status_code, 200)
        new_hash, user_id = cursor.execute.call_args_list[1].args[1]
        self.assertEqual(user_id, 7)
        self.assertTrue(check_password_hash(new_hash, "Nouveau123"))
        connection.commit.assert_called_once()

    @patch("app.get_db_connection")
    def test_reset_password_rejects_already_used_token(
        self,
        mocked_connection,
    ):
        old_hash = generate_password_hash("Ancien123")
        token = create_password_reset_token(7, old_hash)
        mocked_connection.return_value = self.create_fake_connection({
            "Id_utilisateur": 7,
            "mot_de_passe_hash": generate_password_hash("Autre123"),
        })

        response = self.client.post(
            "/api/reset-password",
            json={
                "token": token,
                "password": "Nouveau123",
                "passwordConfirmation": "Nouveau123",
            },
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("déjà été utilisé", response.get_json()["message"])
        mocked_connection.return_value.commit.assert_not_called()

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
            "actif": 1,
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
            "actif": 1,
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

    @patch("app.get_db_connection")
    def test_login_rejects_inactive_account(self, mocked_connection):
        user = {
            "Id_utilisateur": 1,
            "nom": "Test",
            "prenom": "Kevin",
            "email": "test@helpmedraft.fr",
            "mot_de_passe_hash": generate_password_hash("Test1234!"),
            "role": 0,
            "actif": 0,
        }
        mocked_connection.return_value = self.create_fake_connection(user)

        response = self.client.post(
            "/api/login",
            json={
                "email": "test@helpmedraft.fr",
                "password": "Test1234!",
            },
        )

        self.assertEqual(response.status_code, 403)
        self.assertEqual(
            response.get_json()["message"],
            "Ce compte a été désactivé",
        )

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
    def test_admin_summary_rejects_standard_user(self, mocked_connection):
        mocked_connection.return_value = self.create_fake_connection({
            "role": 0,
        })

        with self.client.session_transaction() as session_data:
            session_data["user_id"] = 7

        response = self.client.get("/api/admin/summary")

        self.assertEqual(response.status_code, 403)
        self.assertEqual(
            response.get_json()["message"],
            "Accès administrateur requis",
        )

    @patch("app.get_db_connection")
    def test_admin_summary_returns_global_statistics(
        self,
        mocked_connection,
    ):
        admin_connection = self.create_fake_connection({"role": 1})
        summary_connection = self.create_fake_connection({
            "nombre_utilisateurs": 4,
            "nombre_administrateurs": 1,
            "nombre_documents": 12,
            "nombre_dossiers": 6,
            "nombre_interactions": 8,
        })
        mocked_connection.side_effect = [
            admin_connection,
            summary_connection,
        ]

        with self.client.session_transaction() as session_data:
            session_data["user_id"] = 1

        response = self.client.get("/api/admin/summary")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.get_json()["summary"]["nombre_utilisateurs"],
            4,
        )

    @patch("app.get_db_connection")
    def test_admin_users_returns_registered_accounts(
        self,
        mocked_connection,
    ):
        admin_connection = self.create_fake_connection({"role": 1})
        users_cursor = MagicMock()
        users_cursor.fetchall.return_value = [
            {
                "id": 1,
                "nom": "Admin",
                "prenom": "Kevin",
                "email": "admin@helpmedraft.fr",
                "role": 1,
                "actif": 1,
                "quota_restant": 20,
                "date_inscription": "15/06/2026",
                "nombre_dossiers": 2,
                "nombre_documents": 5,
            },
        ]
        users_connection = MagicMock()
        users_connection.cursor.return_value = users_cursor
        mocked_connection.side_effect = [
            admin_connection,
            users_connection,
        ]

        with self.client.session_transaction() as session_data:
            session_data["user_id"] = 1

        response = self.client.get("/api/admin/users")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.get_json()["users"]), 1)
        self.assertEqual(
            response.get_json()["users"][0]["email"],
            "admin@helpmedraft.fr",
        )

    @patch("app.get_db_connection")
    def test_admin_can_update_user_role_and_quota(self, mocked_connection):
        admin_connection = self.create_fake_connection({"role": 1})
        update_cursor = MagicMock()
        update_cursor.fetchone.return_value = {"Id_utilisateur": 7}
        update_connection = MagicMock()
        update_connection.cursor.return_value = update_cursor
        mocked_connection.side_effect = [
            admin_connection,
            update_connection,
        ]

        with self.client.session_transaction() as session_data:
            session_data["user_id"] = 1

        response = self.client.patch(
            "/api/admin/users/7",
            json={"role": 1, "quota": 50, "active": 1},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            update_cursor.execute.call_args_list[1].args[1],
            (1, 50, 1, 7),
        )
        update_connection.commit.assert_called_once()

    @patch("app.get_db_connection")
    def test_admin_cannot_remove_own_role(self, mocked_connection):
        mocked_connection.return_value = self.create_fake_connection({
            "role": 1,
        })

        with self.client.session_transaction() as session_data:
            session_data["user_id"] = 1

        response = self.client.patch(
            "/api/admin/users/1",
            json={"role": 0, "quota": 20, "active": 1},
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("rôle administrateur", response.get_json()["message"])

    @patch("app.get_db_connection")
    def test_admin_update_rejects_invalid_quota(self, mocked_connection):
        mocked_connection.return_value = self.create_fake_connection({
            "role": 1,
        })

        with self.client.session_transaction() as session_data:
            session_data["user_id"] = 1

        response = self.client.patch(
            "/api/admin/users/7",
            json={"role": 0, "quota": 1001, "active": 1},
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("entre 0 et 1000", response.get_json()["message"])

    @patch("app.get_db_connection")
    def test_admin_cannot_deactivate_own_account(self, mocked_connection):
        mocked_connection.return_value = self.create_fake_connection({
            "role": 1,
            "actif": 1,
        })

        with self.client.session_transaction() as session_data:
            session_data["user_id"] = 1

        response = self.client.patch(
            "/api/admin/users/1",
            json={"role": 1, "quota": 20, "active": 0},
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("désactiver", response.get_json()["message"])

    def test_inactive_session_is_rejected(self):
        self.mocked_active_account.return_value = False

        with self.client.session_transaction() as session_data:
            session_data["user_id"] = 7

        response = self.client.get("/api/dashboard-summary")

        self.assertEqual(response.status_code, 403)
        self.assertEqual(
            response.get_json()["message"],
            "Ce compte a été désactivé",
        )

    @patch("app.get_db_connection")
    def test_sidebar_recents_are_limited_to_connected_user(
        self,
        mocked_connection,
    ):
        cursor = MagicMock()
        cursor.fetchall.return_value = [
            {
                "id": 9,
                "titre": "Compte rendu",
                "dossier_id": 4,
                "dossier_nom": "Travail",
            },
        ]
        connection = MagicMock()
        connection.cursor.return_value = cursor
        mocked_connection.return_value = connection

        with self.client.session_transaction() as session_data:
            session_data["user_id"] = 7

        response = self.client.get("/api/sidebar-recents")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["documents"][0]["id"], 9)
        self.assertNotIn("folders", response.get_json())
        self.assertEqual(cursor.execute.call_args.args[1], (7,))

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
            cursor.execute.call_args_list[0].args[1],
            ("Compte rendu", "", None, 7),
        )
        self.assertEqual(
            cursor.execute.call_args_list[1].args[1],
            ("Compte rendu", "", 9, 7),
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
        cursor.lastrowid = 15
        cursor.fetchone.return_value = {
            "Id_document": 9,
            "titre": "Ancien titre",
            "contenu": "Ancien contenu",
            "Id_dossier": None,
        }
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
        self.assertEqual(
            cursor.execute.call_args_list[2].args[1],
            ("Nouveau titre", "Nouveau contenu", 9, 7),
        )
        connection.commit.assert_called_once()

    @patch("app.get_db_connection")
    def test_update_document_skips_identical_version(self, mocked_connection):
        cursor = MagicMock()
        cursor.fetchone.return_value = {
            "Id_document": 9,
            "titre": "Même titre",
            "contenu": "Même contenu",
            "Id_dossier": None,
        }
        connection = MagicMock()
        connection.cursor.return_value = cursor
        mocked_connection.return_value = connection

        with self.client.session_transaction() as session_data:
            session_data["user_id"] = 7

        response = self.client.patch(
            "/api/documents/9",
            json={
                "title": "Même titre",
                "content": "Même contenu",
                "folderId": None,
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.get_json()["version_created"])
        self.assertEqual(cursor.execute.call_count, 1)
        connection.commit.assert_not_called()

    @patch("app.get_db_connection")
    def test_update_document_rejects_another_user_folder(
        self,
        mocked_connection,
    ):
        cursor = MagicMock()
        cursor.fetchone.side_effect = [
            {
                "Id_document": 9,
                "titre": "Document privé",
                "contenu": "Contenu",
                "Id_dossier": None,
            },
            None,
        ]
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

    @patch("app.get_db_connection")
    def test_document_versions_are_limited_to_owner(
        self,
        mocked_connection,
    ):
        cursor = MagicMock()
        cursor.fetchone.return_value = {"Id_document": 9}
        cursor.fetchall.return_value = [
            {
                "id": 14,
                "titre": "Compte rendu",
                "contenu": "Version enregistrée",
                "date": "15/06/2026 à 17:00",
            },
        ]
        connection = MagicMock()
        connection.cursor.return_value = cursor
        mocked_connection.return_value = connection

        with self.client.session_transaction() as session_data:
            session_data["user_id"] = 7

        response = self.client.get("/api/documents/9/versions")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["versions"][0]["id"], 14)
        self.assertEqual(
            cursor.execute.call_args_list[1].args[1],
            (9, 7),
        )

    @patch("app.get_db_connection")
    def test_restore_document_version_creates_new_snapshot(
        self,
        mocked_connection,
    ):
        cursor = MagicMock()
        cursor.fetchone.return_value = {
            "titre": "Ancien titre",
            "contenu": "Ancien contenu",
        }
        cursor.lastrowid = 15
        connection = MagicMock()
        connection.cursor.return_value = cursor
        mocked_connection.return_value = connection

        with self.client.session_transaction() as session_data:
            session_data["user_id"] = 7

        response = self.client.post(
            "/api/documents/9/versions/12/restore",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["document"]["titre"], "Ancien titre")
        self.assertEqual(
            cursor.execute.call_args_list[1].args[1],
            ("Ancien titre", "Ancien contenu", 9, 7),
        )
        self.assertEqual(
            cursor.execute.call_args_list[2].args[1],
            ("Ancien titre", "Ancien contenu", 9, 7),
        )
        connection.commit.assert_called_once()

    @patch("app.get_db_connection")
    def test_document_interactions_are_limited_to_owner(
        self,
        mocked_connection,
    ):
        cursor = MagicMock()
        cursor.fetchone.return_value = {"Id_document": 9}
        cursor.fetchall.return_value = [
            {
                "id": 12,
                "type_action": "correction",
                "texte_entree": "Salu sa va",
                "texte_sortie": "Salut, ça va ?",
                "date": "15/06/2026 à 16:30",
            },
        ]
        connection = MagicMock()
        connection.cursor.return_value = cursor
        mocked_connection.return_value = connection

        with self.client.session_transaction() as session_data:
            session_data["user_id"] = 7

        response = self.client.get("/api/documents/9/interactions")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.get_json()["interactions"]), 1)
        self.assertEqual(
            response.get_json()["interactions"][0]["type_action"],
            "correction",
        )
        self.assertEqual(
            cursor.execute.call_args_list[0].args[1],
            (9, 7),
        )
        self.assertEqual(
            cursor.execute.call_args_list[1].args[1],
            (9, 7),
        )

    @patch("app.get_db_connection")
    def test_document_interactions_reject_unknown_document(
        self,
        mocked_connection,
    ):
        mocked_connection.return_value = self.create_fake_connection(None)

        with self.client.session_transaction() as session_data:
            session_data["user_id"] = 7

        response = self.client.get("/api/documents/99/interactions")

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.get_json()["message"], "Document introuvable")

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
