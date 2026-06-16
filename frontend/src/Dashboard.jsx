import { useCallback, useEffect, useState } from "react"
import "./Dashboard.css"
import AdminView from "./AdminView"
import DocumentEditor from "./DocumentEditor"
import DocumentsView from "./DocumentsView"
import FoldersView from "./FoldersView"

function Dashboard({ user, isLoggingOut, onLogout, onSessionExpired }) {
  // Données privées chargées depuis Flask pour l'utilisateur connecté.
  const [summary, setSummary] = useState(null)
  const [error, setError] = useState("")
  const [activeView, setActiveView] = useState("overview")
  const [activeDocumentId, setActiveDocumentId] = useState(null)
  const [selectedFolderId, setSelectedFolderId] = useState(null)
  const [recentDocuments, setRecentDocuments] = useState([])

  const loadSidebarRecents = useCallback(async () => {
    try {
      const response = await fetch(
        "http://localhost:5000/api/sidebar-recents",
        {
          credentials: "include",
        },
      )

      if ([401, 403].includes(response.status)) {
        onSessionExpired()
        return
      }

      if (!response.ok) {
        return
      }

      const data = await response.json()
      setRecentDocuments(data.documents)
    } catch {
      // Les raccourcis sont secondaires et ne bloquent pas le tableau de bord.
    }
  }, [onSessionExpired])

  useEffect(() => {
    async function loadSummary() {
      try {
        const response = await fetch(
          "http://localhost:5000/api/dashboard-summary",
          {
            credentials: "include",
          },
        )

        if ([401, 403].includes(response.status)) {
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
    const recentsTimer = window.setTimeout(loadSidebarRecents, 0)

    return () => window.clearTimeout(recentsTimer)
  }, [loadSidebarRecents, onSessionExpired])

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
    loadSidebarRecents()
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
    loadSidebarRecents()
  }

  function handleDocumentCreated() {
    setSummary((currentSummary) => {
      if (!currentSummary) {
        return currentSummary
      }

      return {
        ...currentSummary,
        nombre_documents: currentSummary.nombre_documents + 1,
      }
    })
    loadSidebarRecents()
  }

  function handleDocumentDeleted() {
    setSummary((currentSummary) => {
      if (!currentSummary) {
        return currentSummary
      }

      return {
        ...currentSummary,
        nombre_documents: Math.max(currentSummary.nombre_documents - 1, 0),
      }
    })
    loadSidebarRecents()
    showDocuments()
  }

  function handleQuotaChanged(remainingQuota) {
    setSummary((currentSummary) => {
      if (!currentSummary) {
        return currentSummary
      }

      return {
        ...currentSummary,
        quota_restant: remainingQuota,
      }
    })
  }

  function openDocument(documentId) {
    setActiveDocumentId(documentId)
    setActiveView("editor")
  }

  function showDocuments() {
    setActiveDocumentId(null)
    setActiveView("documents")
  }

  function showAllDocuments() {
    setSelectedFolderId(null)
    showDocuments()
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
          <button
            className={
              activeView === "documents" || activeView === "editor"
                ? "active"
                : ""
            }
            type="button"
            onClick={showAllDocuments}
          >
            <span aria-hidden="true">▤</span>
            Mes documents
          </button>
          <button
            className={activeView === "folders" ? "active" : ""}
            type="button"
            onClick={() => setActiveView("folders")}
          >
            <span aria-hidden="true">□</span>
            Mes dossiers
          </button>
          {Boolean(user.role) && (
            <button
              className={activeView === "admin" ? "active" : ""}
              type="button"
              onClick={() => setActiveView("admin")}
            >
              <span aria-hidden="true">⚙</span>
              Administration
            </button>
          )}
        </nav>

        <div className="sidebar-recents">
          <section>
            <h2>Documents récents</h2>
            {recentDocuments.length === 0 ? (
              <p>Aucun document</p>
            ) : (
              <div className="sidebar-shortcuts">
                {recentDocuments.map((document) => (
                  <button
                    type="button"
                    key={document.id}
                    onClick={() => openDocument(document.id)}
                    title={document.titre}
                  >
                    <span aria-hidden="true">▤</span>
                    <span>
                      <strong>{document.titre}</strong>
                      <small>{document.dossier_nom || "Sans dossier"}</small>
                    </span>
                  </button>
                ))}
              </div>
            )}
          </section>

        </div>

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
        ) : activeView === "admin" && user.role ? (
          <AdminView
            currentUserId={user.id}
            onSessionExpired={onSessionExpired}
          />
        ) : activeView === "folders" ? (
          <FoldersView
            onFolderCreated={handleFolderCreated}
            onFolderDeleted={handleFolderDeleted}
            onFolderUpdated={loadSidebarRecents}
            onSessionExpired={onSessionExpired}
          />
        ) : activeView === "editor" && activeDocumentId ? (
          <DocumentEditor
            documentId={activeDocumentId}
            onBack={showDocuments}
            onDeleted={handleDocumentDeleted}
            onDocumentUpdated={loadSidebarRecents}
            onQuotaChanged={handleQuotaChanged}
            onSessionExpired={onSessionExpired}
          />
        ) : (
          <DocumentsView
            filterFolderId={selectedFolderId}
            onDocumentCreated={handleDocumentCreated}
            onFilterFolderChange={setSelectedFolderId}
            onOpenDocument={openDocument}
            onSessionExpired={onSessionExpired}
          />
        )}
      </section>
    </main>
  )
}

export default Dashboard
