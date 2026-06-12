import os
import mysql.connector
from dotenv import load_dotenv

from flask import Flask

load_dotenv()
app = Flask(__name__)
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

if __name__ == "__main__":
    app.run(debug=True)