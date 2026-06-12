from flask import Flask

app = Flask(__name__)


@app.get("/api/test")
def test():
    return {"message": "Le backend fonctionne"}


if __name__ == "__main__":
    app.run(debug=True)