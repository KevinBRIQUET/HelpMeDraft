import { useEffect, useState } from "react"
import "./Dashboard.css"
import FoldersView from "./FoldersView"

function Dashboard({ user, isLoggingOut, onLogout, onSessionExpired }) {
  // Données privées chargées depuis Flask pour l'utilisateur connecté.
  const [summary, setSummary] = useState(null)
  const [error, setError] = useState("")
  const [activeView, setActiveView] = useState("overview")

  useEffect(() => {
    async function loadSummary() {
      try {
        const response = await fetch(
          "http://localhost:5000/api/dashboard-summary",
          {
            credentials: "include",
          },
        )

        if (response.status === 401) {
          onSessionExpired()
          return
        }

        if (!response.ok) {
          throw new Error()
        }

        const data = await response.json()
        setSummary(data.summary)
      } catch {
        setError("Impossible de charger les informations de votre espace.")
      }
    }

    loadSummary()
  }, [onSessionExpired])

  function handleFolderCreated() {
    setSummary((currentSummary) => {
      if (!currentSummary) {
        return currentSummary
      }

      return {
        ...currentSummary,
        nombre_dossiers: currentSummary.nombre_dossiers + 1,
      }
    })
  }

  function handleFolderDeleted() {
    setSummary((currentSummary) => {
      if (!currentSummary) {
        return currentSummary
      }

      return {
        ...currentSummary,
        nombre_dossiers: Math.max(currentSummary.nombre_dossiers - 1, 0),
      }
    })
  }

  return (
    <main className="dashboard-page">
      <aside className="dashboard-sidebar">
        <div className="dashboard-brand">
          <span className="brand-mark" aria-hidden="true">
            H
          </span>
          <span>HelpMeDraft</span>
        </div>

        <nav className="dashboard-nav" aria-label="Navigation principale">
          <button
            className={activeView === "overview" ? "active" : ""}
            type="button"
            onClick={() => setActiveView("overview")}
          >
            <span aria-hidden="true">⌂</span>
            Vue d’ensemble
          </button>
          <button type="button" disabled>
            <span aria-hidden="true">▤</span>
            Mes documents
            <small>Bientôt</small>
          </button>
          <button
            className={activeView === "folders" ? "active" : ""}
            type="button"
            onClick={() => setActiveView("folders")}
          >
            <span aria-hidden="true">□</span>
            Mes dossiers
          </button>
        </nav>

        <div className="sidebar-user">
          <div className="sidebar-avatar" aria-hidden="true">
            {user.prenom.charAt(0)}
          </div>
          <div>
            <strong>
              {user.prenom} {user.nom}
            </strong>
            <span>{user.email}</span>
          </div>
        </div>
      </aside>

      <section className="dashboard-content">
        <div className="dashboard-top-actions">
          <button
            className="dashboard-logout"
            type="button"
            onClick={onLogout}
            disabled={isLoggingOut}
          >
            {isLoggingOut ? "Déconnexion..." : "Se déconnecter"}
          </button>
        </div>

        {error && (
          <p className="dashboard-error" role="status">
            {error}
          </p>
        )}

        {activeView === "overview" ? (
          <>
            <header className="dashboard-header">
              <div>
                <p className="eyebrow">Espace personnel</p>
                <h1>Bonjour {user.prenom}</h1>
                <p>Retrouvez ici un aperçu de votre activité HelpMeDraft.</p>
              </div>
            </header>

            <section className="stats-grid" aria-label="Résumé du compte">
          <article className="stat-card quota-card">
            <span className="stat-icon" aria-hidden="true">✦</span>
            <div>
              <p>Requêtes IA restantes</p>
              <strong>{summary ? summary.quota_restant : "..."}</strong>
              <span>sur votre quota actuel</span>
            </div>
          </article>

          <article className="stat-card">
            <span className="stat-icon document-icon" aria-hidden="true">▤</span>
            <div>
              <p>Documents</p>
              <strong>{summary ? summary.nombre_documents : "..."}</strong>
              <span>enregistrés dans votre espace</span>
            </div>
          </article>

          <article className="stat-card">
            <span className="stat-icon folder-icon" aria-hidden="true">□</span>
            <div>
              <p>Dossiers</p>
              <strong>{summary ? summary.nombre_dossiers : "..."}</strong>
              <span>pour organiser vos écrits</span>
            </div>
          </article>
            </section>

            <section className="dashboard-grid">
          <article className="welcome-card">
            <div>
              <p className="eyebrow">Commencer à rédiger</p>
              <h2>Votre prochain document commence ici.</h2>
              <p>
                L’éditeur intelligent permettra bientôt de rédiger, corriger et
                reformuler vos contenus professionnels.
              </p>
            </div>
            <button type="button" disabled>
              Nouvel éditeur bientôt disponible
            </button>
          </article>

          <article className="account-card">
            <p className="eyebrow">Votre compte</p>
            <h2>Informations personnelles</h2>
            <dl>
              <div>
                <dt>Nom</dt>
                <dd>
                  {user.prenom} {user.nom}
                </dd>
              </div>
              <div>
                <dt>Adresse e-mail</dt>
                <dd>{user.email}</dd>
              </div>
              <div>
                <dt>Membre depuis</dt>
                <dd>{summary ? summary.date_inscription : "..."}</dd>
              </div>
              <div>
                <dt>Type de compte</dt>
                <dd>{user.role ? "Administrateur" : "Utilisateur standard"}</dd>
              </div>
            </dl>
          </article>
            </section>
          </>
        ) : (
          <FoldersView
            onFolderCreated={handleFolderCreated}
            onFolderDeleted={handleFolderDeleted}
            onSessionExpired={onSessionExpired}
          />
        )}
      </section>
    </main>
  )
}

export default Dashboard
