import os

import mysql.connector
from dotenv import load_dotenv
from flask import Flask, jsonify, request, session
from werkzeug.security import check_password_hash
from flask_cors import CORS

load_dotenv()
app = Flask(__name__)
app.config["SECRET_KEY"] = os.getenv("SECRET_KEY")

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
def get_current_user():
    user_id = session.get("user_id")

    if user_id is None:
        return jsonify({"message": "Aucun utilisateur connecte"}), 401

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
