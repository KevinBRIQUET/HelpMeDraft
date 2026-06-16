# HelpMeDraft

HelpMeDraft est une application web de rédaction assistée par IA pour documents professionnels. Elle couvre le parcours utilisateur complet : authentification, dossiers, documents, autosauvegarde, historique, suggestions IA et back-office administrateur.

## Fonctionnalités principales

- Inscription, connexion, déconnexion et récupération de mot de passe.
- Sessions Flask sécurisées avec cookie `HttpOnly`.
- Rôles `utilisateur` et `administrateur`.
- Activation et désactivation des comptes.
- Gestion des dossiers et documents.
- Éditeur visuel avec gras, italique, souligné et titres.
- Autosauvegarde et historique des versions.
- Correction, reformulation et complétion via Ollama.
- Historique des interactions IA.
- Quota IA modifiable par l'administrateur.
- Back-office avec statistiques et gestion des comptes.
- Tests backend automatisés et vérification du frontend.

## Architecture

```text
React + Vite  ->  API Flask  ->  MySQL
                    |
                    +-> Ollama
```

- `frontend/` : interface React.
- `backend/` : API Flask, logique métier et sécurité.
- `database/` : schéma SQL et migrations.
- `docs/` : documents de révision et livrables PDF.

## Prérequis

- WAMP avec MySQL et phpMyAdmin.
- Python 3.11 ou plus.
- Node.js et npm.
- Ollama installé localement.
- Git.

## Installation backend

Depuis la racine du projet :

```powershell
cd backend
python -m venv venv
.\venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

Copier le fichier d'exemple :

```powershell
Copy-Item .env.example .env
```

Puis adapter les valeurs dans `backend/.env`, notamment :

- `SECRET_KEY`
- `DB_NAME`
- `DB_USER`
- `DB_PASSWORD`
- `OLLAMA_MODEL`

## Base de données

Créer la base `helpmedraft` dans phpMyAdmin.

Pour une nouvelle installation, importer :

```text
database/schema.sql
```

Pour une base déjà existante, importer les migrations dans l'ordre :

```text
database/migrations/001_create_document_versions.sql
database/migrations/002_add_user_active_status.sql
database/migrations/003_expand_password_hash_length.sql
```

Pour passer un compte en administrateur :

```sql
UPDATE utilisateur
SET role = 1
WHERE email = 'ton-adresse@email.fr';
```

## Lancement backend

```powershell
cd backend
.\venv\Scripts\Activate.ps1
python app.py
```

L'API démarre sur :

```text
http://localhost:5000
```

Routes de test utiles :

```text
http://localhost:5000/api/test
http://localhost:5000/api/test-db
http://localhost:5000/api/test-ollama
```

## Installation frontend

Dans un autre terminal :

```powershell
cd frontend
npm install
npm run dev
```

L'application démarre sur :

```text
http://localhost:5173
```

## Ollama

Installer ou lancer le modèle configuré dans `.env`.

Exemple :

```powershell
ollama run qwen3:4b-instruct
```

Si tu utilises un autre modèle déjà installé, adapte `OLLAMA_MODEL` dans `backend/.env`.

## Tests et qualité

Backend :

```powershell
cd backend
.\venv\Scripts\Activate.ps1
python -m unittest
```

Frontend :

```powershell
cd frontend
npm run lint
npm run build
```

État actuel :

- 52 tests backend automatisés.
- ESLint valide.
- Build React valide.

## Sécurité

Mesures déjà présentes :

- Mots de passe hachés avec Werkzeug.
- Sessions avec cookie `HttpOnly`.
- Configuration sensible dans `.env`.
- Requêtes SQL préparées.
- Contrôle de propriété des dossiers et documents.
- Contrôle des rôles côté backend.
- Blocage immédiat des comptes inactifs.
- Récupération de mot de passe par jeton signé et expirant.

Améliorations prévues :

- Ajouter un jeton CSRF explicite.
- Ajouter une limitation de fréquence sur connexion et mot de passe oublié.
- Réaliser un audit de sécurité formel.
- Renforcer la configuration de production avec HTTPS, CSP et sauvegardes.

## RGPD

L'application utilise Ollama localement, ce qui évite l'envoi des documents à un service IA externe. Le back-office permet de désactiver un compte sans supprimer immédiatement ses données.

Points à formaliser pour une version production :

- Information utilisateur et consentement IA.
- Durées de conservation.
- Procédure de droit à l'effacement.
- Registre des traitements.

## Livrables utiles

- `docs/Guide_revision_authentification_HelpMeDraft.pdf`
- `docs/Questions_reponses_jury_HelpMeDraft_CDA.pdf`
- `database/schema.sql`
- `database/migrations/`

## Démarche DevOps prévue

Le projet est versionné avec Git et GitHub. La prochaine amélioration pertinente est une GitHub Action qui lance automatiquement :

- les tests Flask ;
- ESLint ;
- le build React.

Cela permettrait de vérifier automatiquement le projet à chaque `push`.
