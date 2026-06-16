import { useEffect, useState } from "react"

function DocumentsView({
  filterFolderId,
  onDocumentCreated,
  onFilterFolderChange,
  onOpenDocument,
  onSessionExpired,
}) {
  // Données nécessaires à la liste et au formulaire de création.
  const [documents, setDocuments] = useState([])
  const [folders, setFolders] = useState([])
  const [title, setTitle] = useState("")
  const [folderId, setFolderId] = useState("")
  const [isLoading, setIsLoading] = useState(true)
  const [isCreating, setIsCreating] = useState(false)
  const [message, setMessage] = useState("")

  useEffect(() => {
    async function loadDocumentsAndFolders() {
      try {
        const [documentsResponse, foldersResponse] = await Promise.all([
          fetch("http://localhost:5000/api/documents", {
            credentials: "include",
          }),
          fetch("http://localhost:5000/api/folders", {
            credentials: "include",
          }),
        ])

        if (
          [401, 403].includes(documentsResponse.status) ||
          [401, 403].includes(foldersResponse.status)
        ) {
          onSessionExpired()
          return
        }

        if (!documentsResponse.ok || !foldersResponse.ok) {
          throw new Error()
        }

        const documentsData = await documentsResponse.json()
        const foldersData = await foldersResponse.json()

        setDocuments(documentsData.documents)
        setFolders(foldersData.folders)
      } catch {
        setMessage("Impossible de charger vos documents.")
      } finally {
        setIsLoading(false)
      }
    }

    loadDocumentsAndFolders()
  }, [onSessionExpired])

  async function handleCreateDocument(event) {
    event.preventDefault()
    setIsCreating(true)
    setMessage("")

    const selectedFolderId = folderId ? Number(folderId) : null

    try {
      const response = await fetch("http://localhost:5000/api/documents", {
        method: "POST",
        credentials: "include",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          title,
          content: "",
          folderId: selectedFolderId,
        }),
      })
      const data = await response.json()

      if ([401, 403].includes(response.status)) {
        onSessionExpired()
        return
      }

      if (!response.ok) {
        setMessage(data.message)
        return
      }

      const selectedFolder = folders.find(
        (folder) => folder.id === selectedFolderId,
      )

      setDocuments((currentDocuments) => [
        {
          ...data.document,
          dossier_nom: selectedFolder?.nom ?? null,
          derniere_modification: "À l’instant",
        },
        ...currentDocuments,
      ])
      setTitle("")
      setFolderId("")
      setMessage("Document créé avec succès")
      onDocumentCreated()
    } catch {
      setMessage("Le serveur est inaccessible.")
    } finally {
      setIsCreating(false)
    }
  }

  const displayedDocuments = filterFolderId
    ? documents.filter(
        (document) => document.dossier_id === Number(filterFolderId),
      )
    : documents

  return (
    <div className="documents-view">
      <header className="section-heading">
        <div>
          <p className="eyebrow">Bibliothèque</p>
          <h1>Mes documents</h1>
          <p>Créez vos écrits et retrouvez-les dans votre espace personnel.</p>
        </div>
      </header>

      <section className="document-create-card">
        <div>
          <p className="eyebrow">Nouveau document</p>
          <h2>Préparez votre prochain brouillon</h2>
          <p>
            Donnez-lui un titre et rangez-le éventuellement dans un dossier.
          </p>
        </div>

        <form onSubmit={handleCreateDocument}>
          <div className="document-form-field">
            <label htmlFor="documentTitle">Titre du document</label>
            <input
              id="documentTitle"
              type="text"
              maxLength="255"
              placeholder="Ex. Compte rendu de réunion"
              value={title}
              onChange={(event) => setTitle(event.target.value)}
              required
            />
          </div>

          <div className="document-form-field">
            <label htmlFor="documentFolder">Dossier</label>
            <select
              id="documentFolder"
              value={folderId}
              onChange={(event) => setFolderId(event.target.value)}
            >
              <option value="">Aucun dossier</option>
              {folders.map((folder) => (
                <option value={folder.id} key={folder.id}>
                  {folder.nom}
                </option>
              ))}
            </select>
          </div>

          <button type="submit" disabled={isCreating}>
            {isCreating ? "Création..." : "Créer le document"}
            {!isCreating && <span aria-hidden="true">→</span>}
          </button>
        </form>
      </section>

      {message && (
        <p
          className={
            message === "Document créé avec succès"
              ? "documents-message success"
              : "documents-message error"
          }
          role="status"
        >
          {message}
        </p>
      )}

      <section className="documents-list-section">
        <div className="documents-list-heading">
          <div>
            <h2>Vos documents</h2>
            {!isLoading && (
              <span>
                {displayedDocuments.length} affiché
                {displayedDocuments.length !== 1 ? "s" : ""}
              </span>
            )}
          </div>

          <label className="documents-filter">
            <span>Filtrer par dossier</span>
            <select
              value={filterFolderId ?? ""}
              onChange={(event) =>
                onFilterFolderChange(
                  event.target.value ? Number(event.target.value) : null,
                )
              }
            >
              <option value="">Tous les dossiers</option>
              {folders.map((folder) => (
                <option value={folder.id} key={folder.id}>
                  {folder.nom}
                </option>
              ))}
            </select>
          </label>
        </div>

        {isLoading ? (
          <p className="documents-loading">Chargement des documents...</p>
        ) : displayedDocuments.length === 0 ? (
          <div className="empty-documents">
            <span aria-hidden="true">▤</span>
            <h3>
              {filterFolderId
                ? "Aucun document dans ce dossier"
                : "Aucun document pour le moment"}
            </h3>
            <p>
              {filterFolderId
                ? "Choisissez un autre dossier ou créez un nouveau document."
                : "Créez votre premier brouillon avec le formulaire ci-dessus."}
            </p>
          </div>
        ) : (
          <div className="documents-grid">
            {displayedDocuments.map((document) => (
              <article
                className="document-card"
                key={document.id}
                role="button"
                tabIndex="0"
                aria-label={`Ouvrir le document ${document.titre}`}
                onClick={() => onOpenDocument(document.id)}
                onKeyDown={(event) => {
                  if (event.key === "Enter" || event.key === " ") {
                    event.preventDefault()
                    onOpenDocument(document.id)
                  }
                }}
              >
                <div className="document-card-top">
                  <span className="document-card-icon" aria-hidden="true">
                    ▤
                  </span>
                  {document.dossier_nom && (
                    <span className="document-folder-badge">
                      {document.dossier_nom}
                    </span>
                  )}
                </div>

                <h3>{document.titre}</h3>
                <p>
                  {document.extrait ||
                    "Ce document est vide. Il est prêt à être rédigé."}
                </p>

                <footer>
                  <span>Modifié {document.derniere_modification}</span>
                  <strong>Ouvrir →</strong>
                </footer>
              </article>
            ))}
          </div>
        )}
      </section>
    </div>
  )
}

export default DocumentsView
