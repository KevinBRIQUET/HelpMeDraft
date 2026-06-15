import { useEffect, useMemo, useState } from "react"

function DocumentEditor({
  documentId,
  onBack,
  onDeleted,
  onSessionExpired,
}) {
  // Contenu du document et informations nécessaires à l'éditeur.
  const [title, setTitle] = useState("")
  const [content, setContent] = useState("")
  const [folderId, setFolderId] = useState("")
  const [folders, setFolders] = useState([])
  const [lastModified, setLastModified] = useState("")
  const [isLoading, setIsLoading] = useState(true)
  const [isSaving, setIsSaving] = useState(false)
  const [isDeleting, setIsDeleting] = useState(false)
  const [isDeleteModalOpen, setIsDeleteModalOpen] = useState(false)
  const [message, setMessage] = useState("")
  const [isSuccess, setIsSuccess] = useState(false)

  // Le compteur est recalculé uniquement quand le contenu change.
  const wordCount = useMemo(() => {
    const trimmedContent = content.trim()
    return trimmedContent ? trimmedContent.split(/\s+/).length : 0
  }, [content])

  useEffect(() => {
    async function loadEditor() {
      try {
        const [documentResponse, foldersResponse] = await Promise.all([
          fetch(`http://localhost:5000/api/documents/${documentId}`, {
            credentials: "include",
          }),
          fetch("http://localhost:5000/api/folders", {
            credentials: "include",
          }),
        ])

        if (documentResponse.status === 401 || foldersResponse.status === 401) {
          onSessionExpired()
          return
        }

        if (!documentResponse.ok || !foldersResponse.ok) {
          throw new Error()
        }

        const documentData = await documentResponse.json()
        const foldersData = await foldersResponse.json()
        const document = documentData.document

        setTitle(document.titre)
        setContent(document.contenu)
        setFolderId(document.dossier_id ?? "")
        setLastModified(document.derniere_modification)
        setFolders(foldersData.folders)
      } catch {
        setMessage("Impossible de charger ce document.")
        setIsSuccess(false)
      } finally {
        setIsLoading(false)
      }
    }

    loadEditor()
  }, [documentId, onSessionExpired])

  // La fenêtre peut être fermée avec Échap, sauf pendant la suppression.
  useEffect(() => {
    function closeModalWithEscape(event) {
      if (event.key === "Escape" && isDeleteModalOpen && !isDeleting) {
        setIsDeleteModalOpen(false)
      }
    }

    document.addEventListener("keydown", closeModalWithEscape)
    return () => document.removeEventListener("keydown", closeModalWithEscape)
  }, [isDeleteModalOpen, isDeleting])

  async function handleSave(event) {
    event.preventDefault()
    setIsSaving(true)
    setMessage("")
    setIsSuccess(false)

    try {
      const response = await fetch(
        `http://localhost:5000/api/documents/${documentId}`,
        {
          method: "PATCH",
          credentials: "include",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({
            title,
            content,
            folderId: folderId ? Number(folderId) : null,
          }),
        },
      )
      const data = await response.json()

      if (response.status === 401) {
        onSessionExpired()
        return
      }

      if (!response.ok) {
        setMessage(data.message)
        return
      }

      setMessage("Document enregistré")
      setIsSuccess(true)
      setLastModified("à l'instant")
    } catch {
      setMessage("Le serveur est inaccessible.")
    } finally {
      setIsSaving(false)
    }
  }

  async function handleDelete() {
    setIsDeleting(true)
    setMessage("")
    setIsSuccess(false)

    try {
      const response = await fetch(
        `http://localhost:5000/api/documents/${documentId}`,
        {
          method: "DELETE",
          credentials: "include",
        },
      )
      const data = await response.json()

      if (response.status === 401) {
        onSessionExpired()
        return
      }

      if (!response.ok) {
        setMessage(data.message)
        setIsDeleteModalOpen(false)
        return
      }

      setIsDeleteModalOpen(false)
      onDeleted()
    } catch {
      setMessage("Le serveur est inaccessible.")
      setIsDeleteModalOpen(false)
    } finally {
      setIsDeleting(false)
    }
  }

  if (isLoading) {
    return <p className="editor-loading">Chargement de l'éditeur...</p>
  }

  return (
    <div className="document-editor">
      <header className="editor-header">
        <button className="editor-back" type="button" onClick={onBack}>
          <span aria-hidden="true">←</span>
          Mes documents
        </button>

        <div className="editor-status">
          <span>{wordCount} mot{wordCount !== 1 ? "s" : ""}</span>
          {lastModified && <span>Modifié {lastModified}</span>}
        </div>
      </header>

      <form className="editor-workspace" onSubmit={handleSave}>
        <div className="editor-toolbar">
          <div className="editor-title-field">
            <label htmlFor="editorTitle">Titre du document</label>
            <input
              id="editorTitle"
              type="text"
              maxLength="255"
              value={title}
              onChange={(event) => setTitle(event.target.value)}
              required
            />
          </div>

          <div className="editor-folder-field">
            <label htmlFor="editorFolder">Dossier</label>
            <select
              id="editorFolder"
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

          <div className="editor-actions">
            <button
              className="editor-delete"
              type="button"
              onClick={() => setIsDeleteModalOpen(true)}
              disabled={isSaving}
            >
              Supprimer
            </button>
            <button className="editor-save" type="submit" disabled={isSaving}>
              {isSaving ? "Enregistrement..." : "Enregistrer"}
            </button>
          </div>
        </div>

        {message && (
          <p
            className={`editor-message ${isSuccess ? "success" : "error"}`}
            role="status"
          >
            {message}
          </p>
        )}

        <div className="editor-paper">
          <label htmlFor="editorContent">Contenu du document</label>
          <textarea
            id="editorContent"
            value={content}
            onChange={(event) => setContent(event.target.value)}
            placeholder="Commencez à rédiger votre document..."
          />
        </div>
      </form>

      {isDeleteModalOpen && (
        <div
          className="modal-backdrop"
          onMouseDown={(event) => {
            if (event.target === event.currentTarget && !isDeleting) {
              setIsDeleteModalOpen(false)
            }
          }}
        >
          <section
            className="confirm-modal"
            role="dialog"
            aria-modal="true"
            aria-labelledby="delete-document-title"
            aria-describedby="delete-document-description"
          >
            <span className="confirm-modal-icon" aria-hidden="true">
              !
            </span>
            <p className="eyebrow">Suppression définitive</p>
            <h2 id="delete-document-title">Supprimer ce document ?</h2>
            <p id="delete-document-description">
              Le document <strong>« {title} »</strong> et son historique seront
              supprimés définitivement. Cette action est irréversible.
            </p>

            <div className="confirm-modal-actions">
              <button
                type="button"
                onClick={() => setIsDeleteModalOpen(false)}
                disabled={isDeleting}
                autoFocus
              >
                Annuler
              </button>
              <button
                className="danger"
                type="button"
                onClick={handleDelete}
                disabled={isDeleting}
              >
                {isDeleting ? "Suppression..." : "Supprimer définitivement"}
              </button>
            </div>
          </section>
        </div>
      )}
    </div>
  )
}

export default DocumentEditor
