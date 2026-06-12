import os

import mysql.connector
from dotenv import load_dotenv
from flask import Flask, jsonify, request
from werkzeug.security import check_password_hash
from flask_cors import CORS

load_dotenv()
app = Flask(__name__)
CORS(app, resources={r"/api/*": {"origins": "http://localhost:5173"}})
def get_db_connection():
    return mysql.connector.connect(
        host=os.getenv("DB_HOST"),
        port=int(os.getenv("DB_PORT")),
        database=os.getenv("DB_NAME"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
    )


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

if __name__ == "__main__":
    app.run(debug=True)