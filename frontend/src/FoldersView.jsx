import { useEffect, useState } from "react"

function FoldersView({
  onFolderCreated,
  onFolderDeleted,
  onFolderUpdated,
  onSessionExpired,
}) {
  // État local de la page dossiers.
  const [folders, setFolders] = useState([])
  const [folderName, setFolderName] = useState("")
  const [isLoading, setIsLoading] = useState(true)
  const [isCreating, setIsCreating] = useState(false)
  const [message, setMessage] = useState("")
  const [editingFolderId, setEditingFolderId] = useState(null)
  const [editedFolderName, setEditedFolderName] = useState("")
  const [busyFolderId, setBusyFolderId] = useState(null)
  const [folderToDelete, setFolderToDelete] = useState(null)

  useEffect(() => {
    async function loadFolders() {
      try {
        const response = await fetch("http://localhost:5000/api/folders", {
          credentials: "include",
        })

        if ([401, 403].includes(response.status)) {
          onSessionExpired()
          return
        }

        if (!response.ok) {
          throw new Error()
        }

        const data = await response.json()
        setFolders(data.folders)
      } catch {
        setMessage("Impossible de charger vos dossiers.")
      } finally {
        setIsLoading(false)
      }
    }

    loadFolders()
  }, [onSessionExpired])

  // Ferme la fenêtre de confirmation avec la touche Échap.
  useEffect(() => {
    function closeModalWithEscape(event) {
      if (
        event.key === "Escape" &&
        folderToDelete &&
        busyFolderId !== folderToDelete.id
      ) {
        setFolderToDelete(null)
      }
    }

    document.addEventListener("keydown", closeModalWithEscape)
    return () => document.removeEventListener("keydown", closeModalWithEscape)
  }, [busyFolderId, folderToDelete])

  async function handleCreateFolder(event) {
    event.preventDefault()
    setIsCreating(true)
    setMessage("")

    try {
      const response = await fetch("http://localhost:5000/api/folders", {
        method: "POST",
        credentials: "include",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ name: folderName }),
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

      setFolders((currentFolders) => [
        {
          ...data.folder,
          date_creation: "Aujourd’hui",
        },
        ...currentFolders,
      ])
      setFolderName("")
      setMessage("Dossier créé avec succès")
      onFolderCreated()
    } catch {
      setMessage("Le serveur est inaccessible.")
    } finally {
      setIsCreating(false)
    }
  }

  function startEditing(folder) {
    setEditingFolderId(folder.id)
    setEditedFolderName(folder.nom)
    setMessage("")
  }

  function cancelEditing() {
    setEditingFolderId(null)
    setEditedFolderName("")
  }

  async function handleRenameFolder(event, folderId) {
    event.preventDefault()
    setBusyFolderId(folderId)
    setMessage("")

    try {
      const response = await fetch(
        `http://localhost:5000/api/folders/${folderId}`,
        {
          method: "PATCH",
          credentials: "include",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({ name: editedFolderName }),
        },
      )
      const data = await response.json()

      if ([401, 403].includes(response.status)) {
        onSessionExpired()
        return
      }

      if (!response.ok) {
        setMessage(data.message)
        return
      }

      setFolders((currentFolders) =>
        currentFolders.map((folder) =>
          folder.id === folderId
            ? { ...folder, nom: data.folder.nom }
            : folder,
        ),
      )
      cancelEditing()
      setMessage("Dossier renommé avec succès")
      onFolderUpdated()
    } catch {
      setMessage("Le serveur est inaccessible.")
    } finally {
      setBusyFolderId(null)
    }
  }

  async function handleDeleteFolder() {
    if (!folderToDelete) {
      return
    }

    const folder = folderToDelete
    setBusyFolderId(folder.id)
    setMessage("")

    try {
      const response = await fetch(
        `http://localhost:5000/api/folders/${folder.id}`,
        {
          method: "DELETE",
          credentials: "include",
        },
      )
      const data = await response.json()

      if ([401, 403].includes(response.status)) {
        onSessionExpired()
        return
      }

      if (!response.ok) {
        setMessage(data.message)
        setFolderToDelete(null)
        return
      }

      setFolders((currentFolders) =>
        currentFolders.filter((currentFolder) => currentFolder.id !== folder.id),
      )
      onFolderDeleted()
      setMessage("Dossier supprimé avec succès")
      setFolderToDelete(null)
    } catch {
      setMessage("Le serveur est inaccessible.")
      setFolderToDelete(null)
    } finally {
      setBusyFolderId(null)
    }
  }

  const isSuccessMessage = message.endsWith("avec succès")

  return (
    <div className="folders-view">
      <header className="section-heading">
        <div>
          <p className="eyebrow">Organisation</p>
          <h1>Mes dossiers</h1>
          <p>Regroupez vos futurs documents par projet ou par catégorie.</p>
        </div>
      </header>

      <section className="folder-create-card">
        <div>
          <h2>Créer un dossier</h2>
          <p>Choisissez un nom court et facilement identifiable.</p>
        </div>

        <form onSubmit={handleCreateFolder}>
          <label htmlFor="folderName">Nom du dossier</label>
          <div>
            <input
              id="folderName"
              type="text"
              maxLength="20"
              placeholder="Ex. Rapports 2026"
              value={folderName}
              onChange={(event) => setFolderName(event.target.value)}
              required
            />
            <button type="submit" disabled={isCreating}>
              {isCreating ? "Création..." : "Créer"}
            </button>
          </div>
          <span>{folderName.length}/20 caractères</span>
        </form>
      </section>

      {message && (
        <p
          className={
            isSuccessMessage
              ? "folders-message success"
              : "folders-message error"
          }
          role="status"
        >
          {message}
        </p>
      )}

      <section className="folders-list-section">
        <div className="folders-list-heading">
          <h2>Vos dossiers</h2>
          {!isLoading && <span>{folders.length} au total</span>}
        </div>

        {isLoading ? (
          <p className="folders-loading">Chargement des dossiers...</p>
        ) : folders.length === 0 ? (
          <div className="empty-folders">
            <span aria-hidden="true">□</span>
            <h3>Aucun dossier pour le moment</h3>
            <p>Créez votre premier dossier avec le formulaire ci-dessus.</p>
          </div>
        ) : (
          <div className="folders-grid">
            {folders.map((folder) => (
              <article className="folder-card" key={folder.id}>
                <span className="folder-card-icon" aria-hidden="true">
                  □
                </span>
                <div className="folder-card-content">
                  {editingFolderId === folder.id ? (
                    <form
                      className="folder-edit-form"
                      onSubmit={(event) =>
                        handleRenameFolder(event, folder.id)
                      }
                    >
                      <label className="sr-only" htmlFor={`folder-${folder.id}`}>
                        Nouveau nom du dossier
                      </label>
                      <input
                        id={`folder-${folder.id}`}
                        type="text"
                        maxLength="20"
                        value={editedFolderName}
                        onChange={(event) =>
                          setEditedFolderName(event.target.value)
                        }
                        autoFocus
                        required
                      />
                      <div>
                        <button
                          type="submit"
                          disabled={busyFolderId === folder.id}
                        >
                          Enregistrer
                        </button>
                        <button type="button" onClick={cancelEditing}>
                          Annuler
                        </button>
                      </div>
                    </form>
                  ) : (
                    <>
                      <div className="folder-card-heading">
                        <h3>{folder.nom}</h3>
                        <div className="folder-actions">
                          <button
                            type="button"
                            onClick={() => startEditing(folder)}
                            disabled={busyFolderId === folder.id}
                          >
                            Renommer
                          </button>
                          <button
                            className="delete"
                            type="button"
                            onClick={() => setFolderToDelete(folder)}
                            disabled={busyFolderId === folder.id}
                          >
                            Supprimer
                          </button>
                        </div>
                      </div>
                      <p>
                        {folder.nombre_documents} document
                        {folder.nombre_documents !== 1 ? "s" : ""}
                      </p>
                      <span>Créé le {folder.date_creation}</span>
                    </>
                  )}
                </div>
              </article>
            ))}
          </div>
        )}
      </section>

      {folderToDelete && (
        <div
          className="modal-backdrop"
          onMouseDown={(event) => {
            if (
              event.target === event.currentTarget &&
              busyFolderId !== folderToDelete.id
            ) {
              setFolderToDelete(null)
            }
          }}
        >
          <section
            className="confirm-modal"
            role="dialog"
            aria-modal="true"
            aria-labelledby="delete-folder-title"
            aria-describedby="delete-folder-description"
          >
            <span className="confirm-modal-icon" aria-hidden="true">
              !
            </span>
            <p className="eyebrow">Suppression définitive</p>
            <h2 id="delete-folder-title">Supprimer ce dossier ?</h2>
            <p id="delete-folder-description">
              Le dossier <strong>« {folderToDelete.nom} »</strong> sera supprimé
              définitivement. Cette action est irréversible.
            </p>

            <div className="confirm-modal-actions">
              <button
                type="button"
                onClick={() => setFolderToDelete(null)}
                disabled={busyFolderId === folderToDelete.id}
                autoFocus
              >
                Annuler
              </button>
              <button
                className="danger"
                type="button"
                onClick={handleDeleteFolder}
                disabled={busyFolderId === folderToDelete.id}
              >
                {busyFolderId === folderToDelete.id
                  ? "Suppression..."
                  : "Supprimer définitivement"}
              </button>
            </div>
          </section>
        </div>
      )}
    </div>
  )
}

export default FoldersView
