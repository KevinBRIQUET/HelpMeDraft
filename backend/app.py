import os
import re
from datetime import timedelta
from functools import wraps

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


@app.post("/api/logout")
def logout():
    session.clear()
    return jsonify({"message": "Déconnexion réussie"}), 200


if __name__ == "__main__":
    app.run(debug=True)
