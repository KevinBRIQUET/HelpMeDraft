import json
import os
import re
from datetime import timedelta
from functools import wraps
from urllib.error import URLError
from urllib.request import Request, urlopen

import mysql.connector
from dotenv import load_dotenv
from flask import Flask, jsonify, request, session
from flask_cors import CORS
from werkzeug.security import check_password_hash, generate_password_hash

load_dotenv()
app = Flask(__name__)

# Sécurité de la session utilisateur
app.config.update(
    SECRET_KEY=os.getenv("SECRET_KEY"),
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_SECURE=os.getenv("APP_ENV") == "production",
    PERMANENT_SESSION_LIFETIME=timedelta(hours=8),
)

# Communication avec le frontend React pendant le développement.
CORS(
    app,
    resources={r"/api/*": {"origins": "http://localhost:5173"}},
    supports_credentials=True,
)


# Connexion à la base de données
def get_db_connection():
    return mysql.connector.connect(
        host=os.getenv("DB_HOST"),
        port=int(os.getenv("DB_PORT")),
        database=os.getenv("DB_NAME"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
    )


# Communication avec le modèle local Ollama
class OllamaUnavailableError(Exception):
    """Indique que le service Ollama ne peut pas fournir de réponse."""


def clean_ollama_answer(answer):
    # Certaines versions de modèles renvoient encore leur réflexion dans
    # le contenu. HelpMeDraft ne conserve que la réponse destinée à l'utilisateur.
    cleaned_answer = re.sub(
        r"<think>.*?</think>",
        "",
        answer,
        flags=re.DOTALL | re.IGNORECASE,
    )

    # Qwen peut parfois omettre la balise ouvrante mais conserver </think>.
    if re.search(r"</think>", cleaned_answer, flags=re.IGNORECASE):
        cleaned_answer = re.split(
            r"</think>",
            cleaned_answer,
            flags=re.IGNORECASE,
        )[-1]

    return cleaned_answer.strip()


def call_ollama(messages):
    ollama_url = os.getenv("OLLAMA_URL", "http://localhost:11434").rstrip("/")
    model = os.getenv("OLLAMA_MODEL", "qwen3:4b-instruct")
    input_length = sum(
        len(message.get("content", ""))
        for message in messages
    )
    max_generated_tokens = min(4096, max(128, input_length // 3 + 64))

    payload = json.dumps(
        {
            "model": model,
            "messages": messages,
            "stream": False,
            "think": False,
            "keep_alive": "10m",
            "options": {
                "temperature": 0.2,
                "num_ctx": 8192,
                "num_predict": max_generated_tokens,
            },
        },
        ensure_ascii=False,
    ).encode("utf-8")

    ollama_request = Request(
        f"{ollama_url}/api/chat",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        timeout = int(os.getenv("OLLAMA_TIMEOUT", "300"))
        with urlopen(ollama_request, timeout=timeout) as response:
            response_data = json.loads(response.read().decode("utf-8"))
    except (URLError, TimeoutError, json.JSONDecodeError) as error:
        raise OllamaUnavailableError from error

    # Une réponse arrêtée par la limite est incomplète et ne doit jamais être
    # proposée à l'utilisateur comme une correction valide.
    if response_data.get("done_reason") == "length":
        raise OllamaUnavailableError

    answer = clean_ollama_answer(
        response_data.get("message", {}).get("content", ""),
    )

    if not answer:
        raise OllamaUnavailableError

    return answer


# Actions IA autorisées et prompts associés
AI_ACTIONS = {
    "correct": {
        "database_type": "correction",
        "success_message": "Correction générée",
        "prompt": (
            "Tu es le correcteur de HelpMeDraft. Corrige uniquement "
            "l'orthographe, la grammaire, la conjugaison et la ponctuation "
            "du texte. Conserve son sens et son ton. Retourne uniquement "
            "le texte corrigé, sans explication."
        ),
    },
    "rephrase": {
        "database_type": "reformuler",
        "success_message": "Reformulation générée",
        "prompt": (
            "Tu es l'assistant de rédaction de HelpMeDraft. Reformule le "
            "texte dans un style professionnel, clair et naturel. Conserve "
            "toutes les informations et le sens d'origine. Retourne "
            "uniquement le texte reformulé, sans explication."
        ),
    },
    "complete": {
        "database_type": "completion",
        "success_message": "Suite générée",
        "prompt": (
            "Tu es l'assistant de rédaction de HelpMeDraft. Continue le "
            "texte de façon cohérente et professionnelle avec un court "
            "paragraphe. Retourne le texte original inchangé suivi de ta "
            "continuation, sans titre ni explication."
        ),
    },
}


# Protection des routes réservées aux utilisateurs connectés
def login_required(route):
    @wraps(route)
    def protected_route(*args, **kwargs):
        if session.get("user_id") is None:
            return jsonify({"message": "Authentification requise"}), 401

        return route(*args, **kwargs)

    return protected_route


# Routes de diagnostic
@app.get("/api/test")
def test():
    return {"message": "Le backend fonctionne"}


@app.get("/api/test-db")
def test_db():
    connection = get_db_connection()
    cursor = connection.cursor()

    cursor.execute("SELECT DATABASE()")
    database_name = cursor.fetchone()[0]

    cursor.close()
    connection.close()

    return {
        "message": "Connexion MySQL réussie",
        "database": database_name
    }


@app.get("/api/test-ollama")
@login_required
def test_ollama():
    try:
        answer = call_ollama([
            {
                "role": "system",
                "content": (
                    "Tu testes la connexion technique de HelpMeDraft. "
                    "Réponds uniquement par OK."
                ),
            },
            {
                "role": "user",
                "content": "Le service fonctionne-t-il ?",
            },
        ])
    except OllamaUnavailableError:
        return jsonify({
            "message": "Ollama est inaccessible ou le modèle est indisponible",
        }), 503

    return jsonify({
        "message": "Connexion Ollama réussie",
        "model": os.getenv("OLLAMA_MODEL", "qwen3:4b-instruct"),
        "response": answer,
    }), 200


# Authentification
@app.post("/api/register")
def register():
    data = request.get_json(silent=True) or {}

    first_name = data.get("prenom", "").strip()
    last_name = data.get("nom", "").strip()
    email = data.get("email", "").strip().lower()
    password = data.get("password", "")
    password_confirmation = data.get("passwordConfirmation", "")
    consent = data.get("consent") is True

    if not all([first_name, last_name, email, password, password_confirmation]):
        return jsonify({"message": "Tous les champs sont obligatoires"}), 400

    if not consent:
        return jsonify({
            "message": "Vous devez accepter les conditions d'utilisation",
        }), 400

    if len(first_name) > 50 or len(last_name) > 50 or len(email) > 50:
        return jsonify({"message": "Un ou plusieurs champs sont trop longs"}), 400

    if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):
        return jsonify({"message": "Adresse e-mail invalide"}), 400

    if password != password_confirmation:
        return jsonify({"message": "Les mots de passe ne correspondent pas"}), 400

    password_is_valid = (
        len(password) >= 8
        and any(character.islower() for character in password)
        and any(character.isupper() for character in password)
        and any(character.isdigit() for character in password)
    )

    if not password_is_valid:
        return jsonify({
            "message": (
                "Le mot de passe doit contenir au moins 8 caractères, "
                "une majuscule, une minuscule et un chiffre"
            ),
        }), 400

    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)

    cursor.execute(
        "SELECT Id_utilisateur FROM utilisateur WHERE email = %s",
        (email,),
    )

    if cursor.fetchone() is not None:
        cursor.close()
        connection.close()
        return jsonify({"message": "Cette adresse e-mail est déjà utilisée"}), 409

    cursor.execute(
        """
        INSERT INTO utilisateur
            (nom, prenom, email, mot_de_passe_hash, role,
             date_inscription, quota_restant)
        VALUES (%s, %s, %s, %s, 0, NOW(), 20)
        """,
        (
            last_name,
            first_name,
            email,
            generate_password_hash(password),
        ),
    )
    connection.commit()
    user_id = cursor.lastrowid

    cursor.close()
    connection.close()

    session.clear()
    session.permanent = True
    session["user_id"] = user_id

    return jsonify({
        "message": "Compte créé avec succès",
        "user": {
            "id": user_id,
            "nom": last_name,
            "prenom": first_name,
            "email": email,
            "role": 0,
        },
    }), 201


@app.post("/api/login")
def login():
    data = request.get_json(silent=True) or {}

    email = data.get("email", "").strip().lower()
    password = data.get("password", "")

    if not email or not password:
        return jsonify({"message": "Email et mot de passe obligatoires"}), 400

    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)

    cursor.execute(
        """
        SELECT Id_utilisateur, nom, prenom, email, mot_de_passe_hash, role
        FROM utilisateur
        WHERE email = %s
        """,
        (email,),
    )

    user = cursor.fetchone()

    cursor.close()
    connection.close()

    if user is None or not check_password_hash(
        user["mot_de_passe_hash"], password
    ):
        return jsonify({"message": "Identifiants incorrects"}), 401

    session.clear()
    session.permanent = True
    session["user_id"] = user["Id_utilisateur"]

    return jsonify({
        "message": "Connexion réussie",
        "user": {
            "id": user["Id_utilisateur"],
            "nom": user["nom"],
            "prenom": user["prenom"],
            "email": user["email"],
            "role": user["role"],
        },
    }), 200


# Lecture de la session active
@app.get("/api/me")
@login_required
def get_current_user():
    user_id = session.get("user_id")

    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)

    cursor.execute(
        """
        SELECT Id_utilisateur, nom, prenom, email, role
        FROM utilisateur
        WHERE Id_utilisateur = %s
        """,
        (user_id,),
    )

    user = cursor.fetchone()

    cursor.close()
    connection.close()

    if user is None:
        session.clear()
        return jsonify({"message": "Utilisateur introuvable"}), 401

    return jsonify({
        "user": {
            "id": user["Id_utilisateur"],
            "nom": user["nom"],
            "prenom": user["prenom"],
            "email": user["email"],
            "role": user["role"],
        },
    }), 200


# Résumé de l'espace personnel
@app.get("/api/dashboard-summary")
@login_required
def get_dashboard_summary():
    user_id = session.get("user_id")

    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)

    cursor.execute(
        """
        SELECT
            u.quota_restant,
            DATE_FORMAT(u.date_inscription, '%d/%m/%Y') AS date_inscription,
            (
                SELECT COUNT(*)
                FROM dossier d
                WHERE d.Id_utilisateur = u.Id_utilisateur
            ) AS nombre_dossiers,
            (
                SELECT COUNT(*)
                FROM document doc
                WHERE doc.Id_utilisateur = u.Id_utilisateur
            ) AS nombre_documents
        FROM utilisateur u
        WHERE u.Id_utilisateur = %s
        """,
        (user_id,),
    )

    summary = cursor.fetchone()

    cursor.close()
    connection.close()

    if summary is None:
        session.clear()
        return jsonify({"message": "Utilisateur introuvable"}), 401

    return jsonify({"summary": summary}), 200


# Gestion des dossiers
@app.get("/api/folders")
@login_required
def get_folders():
    user_id = session.get("user_id")

    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)

    cursor.execute(
        """
        SELECT
            d.Id_dossier AS id,
            d.nom,
            DATE_FORMAT(d.date_creation, '%d/%m/%Y') AS date_creation,
            COUNT(doc.Id_document) AS nombre_documents
        FROM dossier d
        LEFT JOIN document doc ON doc.Id_dossier = d.Id_dossier
        WHERE d.Id_utilisateur = %s
        GROUP BY d.Id_dossier, d.nom, d.date_creation
        ORDER BY d.date_creation DESC, d.Id_dossier DESC
        """,
        (user_id,),
    )

    folders = cursor.fetchall()

    cursor.close()
    connection.close()

    return jsonify({"folders": folders}), 200


@app.post("/api/folders")
@login_required
def create_folder():
    user_id = session.get("user_id")
    data = request.get_json(silent=True) or {}
    folder_name = data.get("name", "").strip()

    if not folder_name:
        return jsonify({"message": "Le nom du dossier est obligatoire"}), 400

    if len(folder_name) > 20:
        return jsonify({
            "message": "Le nom du dossier ne doit pas dépasser 20 caractères",
        }), 400

    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)

    cursor.execute(
        """
        INSERT INTO dossier (nom, date_creation, Id_utilisateur)
        VALUES (%s, NOW(), %s)
        """,
        (folder_name, user_id),
    )
    connection.commit()
    folder_id = cursor.lastrowid

    cursor.close()
    connection.close()

    return jsonify({
        "message": "Dossier créé avec succès",
        "folder": {
            "id": folder_id,
            "nom": folder_name,
            "nombre_documents": 0,
        },
    }), 201


@app.patch("/api/folders/<int:folder_id>")
@login_required
def update_folder(folder_id):
    user_id = session.get("user_id")
    data = request.get_json(silent=True) or {}
    folder_name = data.get("name", "").strip()

    if not folder_name:
        return jsonify({"message": "Le nom du dossier est obligatoire"}), 400

    if len(folder_name) > 20:
        return jsonify({
            "message": "Le nom du dossier ne doit pas dépasser 20 caractères",
        }), 400

    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)

    cursor.execute(
        """
        UPDATE dossier
        SET nom = %s
        WHERE Id_dossier = %s AND Id_utilisateur = %s
        """,
        (folder_name, folder_id, user_id),
    )

    if cursor.rowcount == 0:
        cursor.close()
        connection.close()
        return jsonify({"message": "Dossier introuvable"}), 404

    connection.commit()
    cursor.close()
    connection.close()

    return jsonify({
        "message": "Dossier renommé avec succès",
        "folder": {
            "id": folder_id,
            "nom": folder_name,
        },
    }), 200


@app.delete("/api/folders/<int:folder_id>")
@login_required
def delete_folder(folder_id):
    user_id = session.get("user_id")

    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)

    cursor.execute(
        """
        SELECT COUNT(*) AS nombre_documents
        FROM document
        WHERE Id_dossier = %s AND Id_utilisateur = %s
        """,
        (folder_id, user_id),
    )
    document_count = cursor.fetchone()["nombre_documents"]

    if document_count > 0:
        cursor.close()
        connection.close()
        return jsonify({
            "message": "Ce dossier contient encore des documents",
        }), 409

    cursor.execute(
        """
        DELETE FROM dossier
        WHERE Id_dossier = %s AND Id_utilisateur = %s
        """,
        (folder_id, user_id),
    )

    if cursor.rowcount == 0:
        cursor.close()
        connection.close()
        return jsonify({"message": "Dossier introuvable"}), 404

    connection.commit()
    cursor.close()
    connection.close()

    return jsonify({"message": "Dossier supprimé avec succès"}), 200


# Gestion des documents
@app.get("/api/documents")
@login_required
def get_documents():
    user_id = session.get("user_id")

    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)

    cursor.execute(
        """
        SELECT
            doc.Id_document AS id,
            doc.titre,
            LEFT(doc.contenu, 180) AS extrait,
            DATE_FORMAT(doc.derniere_modification, '%d/%m/%Y à %H:%i')
                AS derniere_modification,
            d.Id_dossier AS dossier_id,
            d.nom AS dossier_nom
        FROM document doc
        LEFT JOIN dossier d ON d.Id_dossier = doc.Id_dossier
        WHERE doc.Id_utilisateur = %s
        ORDER BY doc.derniere_modification DESC, doc.Id_document DESC
        """,
        (user_id,),
    )

    documents = cursor.fetchall()

    cursor.close()
    connection.close()

    return jsonify({"documents": documents}), 200


@app.post("/api/documents")
@login_required
def create_document():
    user_id = session.get("user_id")
    data = request.get_json(silent=True) or {}

    title = data.get("title", "").strip()
    content = data.get("content", "")
    folder_id = data.get("folderId")

    if not title:
        return jsonify({"message": "Le titre du document est obligatoire"}), 400

    if len(title) > 255:
        return jsonify({
            "message": "Le titre ne doit pas dépasser 255 caractères",
        }), 400

    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)

    if folder_id is not None:
        cursor.execute(
            """
            SELECT Id_dossier
            FROM dossier
            WHERE Id_dossier = %s AND Id_utilisateur = %s
            """,
            (folder_id, user_id),
        )

        if cursor.fetchone() is None:
            cursor.close()
            connection.close()
            return jsonify({"message": "Dossier introuvable"}), 404

    cursor.execute(
        """
        INSERT INTO document
            (titre, contenu, date_creation, derniere_modification,
             Id_dossier, Id_utilisateur)
        VALUES (%s, %s, NOW(), NOW(), %s, %s)
        """,
        (title, content, folder_id, user_id),
    )
    document_id = cursor.lastrowid

    cursor.execute(
        """
        INSERT INTO version_document
            (titre, contenu, date_version, Id_document, Id_utilisateur)
        VALUES (%s, %s, NOW(), %s, %s)
        """,
        (title, content, document_id, user_id),
    )

    connection.commit()
    cursor.close()
    connection.close()

    return jsonify({
        "message": "Document créé avec succès",
        "document": {
            "id": document_id,
            "titre": title,
            "extrait": content[:180],
            "dossier_id": folder_id,
        },
    }), 201


@app.get("/api/documents/<int:document_id>")
@login_required
def get_document(document_id):
    user_id = session.get("user_id")

    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)

    cursor.execute(
        """
        SELECT
            doc.Id_document AS id,
            doc.titre,
            doc.contenu,
            doc.Id_dossier AS dossier_id,
            DATE_FORMAT(doc.derniere_modification, '%d/%m/%Y à %H:%i')
                AS derniere_modification
        FROM document doc
        WHERE doc.Id_document = %s AND doc.Id_utilisateur = %s
        """,
        (document_id, user_id),
    )

    document = cursor.fetchone()

    cursor.close()
    connection.close()

    if document is None:
        return jsonify({"message": "Document introuvable"}), 404

    return jsonify({"document": document}), 200


@app.patch("/api/documents/<int:document_id>")
@login_required
def update_document(document_id):
    user_id = session.get("user_id")
    data = request.get_json(silent=True) or {}

    title = data.get("title", "").strip()
    content = data.get("content", "")
    folder_id = data.get("folderId")

    if not title:
        return jsonify({"message": "Le titre du document est obligatoire"}), 400

    if len(title) > 255:
        return jsonify({
            "message": "Le titre ne doit pas dépasser 255 caractères",
        }), 400

    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)

    # Charge la version courante pour vérifier le propriétaire et détecter
    # si l'utilisateur a réellement modifié le document.
    cursor.execute(
        """
        SELECT Id_document, titre, contenu, Id_dossier
        FROM document
        WHERE Id_document = %s AND Id_utilisateur = %s
        """,
        (document_id, user_id),
    )
    current_document = cursor.fetchone()

    if current_document is None:
        cursor.close()
        connection.close()
        return jsonify({"message": "Document introuvable"}), 404

    if folder_id is not None:
        cursor.execute(
            """
            SELECT Id_dossier
            FROM dossier
            WHERE Id_dossier = %s AND Id_utilisateur = %s
            """,
            (folder_id, user_id),
        )

        if cursor.fetchone() is None:
            cursor.close()
            connection.close()
            return jsonify({"message": "Dossier introuvable"}), 404

    has_changed = (
        current_document["titre"] != title
        or current_document["contenu"] != content
        or current_document["Id_dossier"] != folder_id
    )
    created_version = None

    if has_changed:
        cursor.execute(
            """
            UPDATE document
            SET titre = %s,
                contenu = %s,
                Id_dossier = %s,
                derniere_modification = NOW()
            WHERE Id_document = %s AND Id_utilisateur = %s
            """,
            (title, content, folder_id, document_id, user_id),
        )
        cursor.execute(
            """
            INSERT INTO version_document
                (titre, contenu, date_version, Id_document, Id_utilisateur)
            VALUES (%s, %s, NOW(), %s, %s)
            """,
            (title, content, document_id, user_id),
        )
        created_version = {
            "id": cursor.lastrowid,
            "titre": title,
            "contenu": content,
            "date": "À l'instant",
        }
        connection.commit()

    cursor.close()
    connection.close()

    return jsonify({
        "message": (
            "Document enregistré"
            if has_changed
            else "Aucune modification à enregistrer"
        ),
        "version_created": has_changed,
        "version": created_version,
        "document": {
            "id": document_id,
            "titre": title,
            "contenu": content,
            "dossier_id": folder_id,
        },
    }), 200


@app.get("/api/documents/<int:document_id>/versions")
@login_required
def get_document_versions(document_id):
    user_id = session.get("user_id")

    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)
    cursor.execute(
        """
        SELECT Id_document
        FROM document
        WHERE Id_document = %s AND Id_utilisateur = %s
        """,
        (document_id, user_id),
    )

    if cursor.fetchone() is None:
        cursor.close()
        connection.close()
        return jsonify({"message": "Document introuvable"}), 404

    cursor.execute(
        """
        SELECT
            Id_version AS id,
            titre,
            contenu,
            DATE_FORMAT(date_version, '%d/%m/%Y à %H:%i') AS date
        FROM version_document
        WHERE Id_document = %s AND Id_utilisateur = %s
        ORDER BY date_version DESC, Id_version DESC
        """,
        (document_id, user_id),
    )
    versions = cursor.fetchall()

    cursor.close()
    connection.close()

    return jsonify({"versions": versions}), 200


@app.post(
    "/api/documents/<int:document_id>/versions/<int:version_id>/restore",
)
@login_required
def restore_document_version(document_id, version_id):
    user_id = session.get("user_id")

    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)
    cursor.execute(
        """
        SELECT version.titre, version.contenu
        FROM version_document version
        JOIN document doc ON doc.Id_document = version.Id_document
        WHERE version.Id_version = %s
          AND version.Id_document = %s
          AND version.Id_utilisateur = %s
          AND doc.Id_utilisateur = %s
        """,
        (version_id, document_id, user_id, user_id),
    )
    version = cursor.fetchone()

    if version is None:
        cursor.close()
        connection.close()
        return jsonify({"message": "Version introuvable"}), 404

    cursor.execute(
        """
        UPDATE document
        SET titre = %s,
            contenu = %s,
            derniere_modification = NOW()
        WHERE Id_document = %s AND Id_utilisateur = %s
        """,
        (version["titre"], version["contenu"], document_id, user_id),
    )
    cursor.execute(
        """
        INSERT INTO version_document
            (titre, contenu, date_version, Id_document, Id_utilisateur)
        VALUES (%s, %s, NOW(), %s, %s)
        """,
        (
            version["titre"],
            version["contenu"],
            document_id,
            user_id,
        ),
    )
    restored_version_id = cursor.lastrowid

    connection.commit()
    cursor.close()
    connection.close()

    return jsonify({
        "message": "Version restaurée",
        "document": {
            "titre": version["titre"],
            "contenu": version["contenu"],
        },
        "version": {
            "id": restored_version_id,
            "titre": version["titre"],
            "contenu": version["contenu"],
            "date": "À l'instant",
        },
    }), 200


@app.get("/api/documents/<int:document_id>/interactions")
@login_required
def get_document_interactions(document_id):
    user_id = session.get("user_id")

    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)

    # Le document doit appartenir à l'utilisateur connecté.
    cursor.execute(
        """
        SELECT Id_document
        FROM document
        WHERE Id_document = %s AND Id_utilisateur = %s
        """,
        (document_id, user_id),
    )

    if cursor.fetchone() is None:
        cursor.close()
        connection.close()
        return jsonify({"message": "Document introuvable"}), 404

    cursor.execute(
        """
        SELECT
            Id_interaction AS id,
            type_action,
            texte_entree,
            texte_sortie,
            DATE_FORMAT(date_, '%d/%m/%Y à %H:%i') AS date
        FROM interaction
        WHERE Id_document = %s AND Id_utilisateur = %s
        ORDER BY date_ DESC, Id_interaction DESC
        """,
        (document_id, user_id),
    )
    interactions = cursor.fetchall()

    cursor.close()
    connection.close()

    return jsonify({"interactions": interactions}), 200


@app.post("/api/documents/<int:document_id>/ai/<action>")
@login_required
def generate_ai_suggestion(document_id, action):
    user_id = session.get("user_id")
    data = request.get_json(silent=True) or {}
    text = data.get("text", "")
    action_config = AI_ACTIONS.get(action)

    if action_config is None:
        return jsonify({"message": "Action IA inconnue"}), 404

    if not isinstance(text, str) or not text.strip():
        return jsonify({"message": "Le texte à traiter est obligatoire"}), 400

    if len(text) > 12000:
        return jsonify({
            "message": "Le texte ne doit pas dépasser 12 000 caractères",
        }), 400

    # Vérifie le propriétaire du document et le quota avant d'appeler l'IA.
    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)
    cursor.execute(
        """
        SELECT doc.Id_document, u.quota_restant
        FROM document doc
        JOIN utilisateur u ON u.Id_utilisateur = doc.Id_utilisateur
        WHERE doc.Id_document = %s AND doc.Id_utilisateur = %s
        """,
        (document_id, user_id),
    )
    document_access = cursor.fetchone()
    cursor.close()
    connection.close()

    if document_access is None:
        return jsonify({"message": "Document introuvable"}), 404

    if (document_access["quota_restant"] or 0) <= 0:
        return jsonify({"message": "Votre quota de requêtes IA est épuisé"}), 429

    try:
        suggestion = call_ollama([
            {
                "role": "system",
                "content": action_config["prompt"],
            },
            {
                "role": "user",
                "content": text,
            },
        ])
    except OllamaUnavailableError:
        return jsonify({
            "message": "L'assistant IA est temporairement indisponible",
        }), 503

    # Le quota et l'historique sont modifiés ensemble après une réponse réussie.
    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)
    cursor.execute(
        """
        UPDATE utilisateur
        SET quota_restant = quota_restant - 1
        WHERE Id_utilisateur = %s AND quota_restant > 0
        """,
        (user_id,),
    )

    if cursor.rowcount == 0:
        connection.rollback()
        cursor.close()
        connection.close()
        return jsonify({"message": "Votre quota de requêtes IA est épuisé"}), 429

    cursor.execute(
        """
        INSERT INTO interaction
            (type_action, texte_entree, texte_sortie, date_,
             Id_utilisateur, Id_document)
        VALUES (%s, %s, %s, NOW(), %s, %s)
        """,
        (
            action_config["database_type"],
            text,
            suggestion,
            user_id,
            document_id,
        ),
    )
    connection.commit()
    cursor.close()
    connection.close()

    return jsonify({
        "message": action_config["success_message"],
        "suggestion": suggestion,
        "quota_restant": document_access["quota_restant"] - 1,
    }), 200


@app.delete("/api/documents/<int:document_id>")
@login_required
def delete_document(document_id):
    user_id = session.get("user_id")

    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)

    # L'identifiant de l'utilisateur fait partie de la recherche :
    # un utilisateur ne peut donc pas supprimer le document d'un autre.
    cursor.execute(
        """
        SELECT Id_document, titre
        FROM document
        WHERE Id_document = %s AND Id_utilisateur = %s
        """,
        (document_id, user_id),
    )
    document = cursor.fetchone()

    if document is None:
        cursor.close()
        connection.close()
        return jsonify({"message": "Document introuvable"}), 404

    # Les interactions dépendent du document par une clé étrangère.
    cursor.execute(
        "DELETE FROM interaction WHERE Id_document = %s",
        (document_id,),
    )
    cursor.execute(
        """
        DELETE FROM document
        WHERE Id_document = %s AND Id_utilisateur = %s
        """,
        (document_id, user_id),
    )

    connection.commit()
    cursor.close()
    connection.close()

    return jsonify({
        "message": "Document supprimé",
        "document": {
            "id": document_id,
            "titre": document["titre"],
        },
    }), 200


@app.post("/api/logout")
def logout():
    session.clear()
    return jsonify({"message": "Déconnexion réussie"}), 200


if __name__ == "__main__":
    app.run(debug=True)
