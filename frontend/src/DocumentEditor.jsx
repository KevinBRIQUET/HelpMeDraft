import { useCallback, useEffect, useMemo, useState } from "react"

const AI_ACTIONS = {
  correct: {
    buttonLabel: "Corriger",
    historyType: "correction",
    loadingLabel: "Correction...",
    modalTitle: "Correction proposée",
    suggestionLabel: "Suggestion corrigée",
    appliedMessage: "Correction appliquée",
  },
  rephrase: {
    buttonLabel: "Reformuler",
    historyType: "reformuler",
    loadingLabel: "Reformulation...",
    modalTitle: "Reformulation proposée",
    suggestionLabel: "Version professionnelle",
    appliedMessage: "Reformulation appliquée",
  },
  complete: {
    buttonLabel: "Compléter",
    historyType: "completion",
    loadingLabel: "Rédaction...",
    modalTitle: "Suite proposée",
    suggestionLabel: "Texte complété",
    appliedMessage: "Suite appliquée",
  },
}

const HISTORY_LABELS = {
  correction: "Correction",
  reformuler: "Reformulation",
  completion: "Complétion",
}

function createDocumentSnapshot(title, content, folderId) {
  return JSON.stringify({
    title: title.trim(),
    content,
    folderId: folderId ? Number(folderId) : null,
  })
}

function DocumentEditor({
  documentId,
  onBack,
  onDeleted,
  onQuotaChanged,
  onSessionExpired,
}) {
  // Contenu du document et informations nécessaires à l'éditeur.
  const [title, setTitle] = useState("")
  const [content, setContent] = useState("")
  const [folderId, setFolderId] = useState("")
  const [folders, setFolders] = useState([])
  const [lastModified, setLastModified] = useState("")
  const [savedSnapshot, setSavedSnapshot] = useState(null)
  const [blockedAutoSaveSnapshot, setBlockedAutoSaveSnapshot] = useState(null)
  const [saveStatus, setSaveStatus] = useState("saved")
  const [isLoading, setIsLoading] = useState(true)
  const [isSaving, setIsSaving] = useState(false)
  const [isDeleting, setIsDeleting] = useState(false)
  const [activeAiAction, setActiveAiAction] = useState(null)
  const [isDeleteModalOpen, setIsDeleteModalOpen] = useState(false)
  const [aiSuggestion, setAiSuggestion] = useState(null)
  const [aiOriginalText, setAiOriginalText] = useState("")
  const [versions, setVersions] = useState([])
  const [interactions, setInteractions] = useState([])
  const [isHistoryOpen, setIsHistoryOpen] = useState(false)
  const [historyTab, setHistoryTab] = useState("versions")
  const [isHistoryLoading, setIsHistoryLoading] = useState(false)
  const [loadedHistoryTabs, setLoadedHistoryTabs] = useState({
    versions: false,
    interactions: false,
  })
  const [busyVersionId, setBusyVersionId] = useState(null)
  const [historyMessage, setHistoryMessage] = useState("")
  const [message, setMessage] = useState("")
  const [isSuccess, setIsSuccess] = useState(false)

  // Le compteur est recalculé uniquement quand le contenu change.
  const wordCount = useMemo(() => {
    const trimmedContent = content.trim()
    return trimmedContent ? trimmedContent.split(/\s+/).length : 0
  }, [content])

  const displayedSaveStatus = useMemo(() => {
    if (isSaving) {
      return "saving"
    }

    if (saveStatus === "error") {
      return "error"
    }

    if (
      savedSnapshot !== null &&
      createDocumentSnapshot(title, content, folderId) !== savedSnapshot
    ) {
      return "pending"
    }

    return "saved"
  }, [content, folderId, isSaving, saveStatus, savedSnapshot, title])

  function markDocumentChanged() {
    setSaveStatus("saved")
    setBlockedAutoSaveSnapshot(null)
  }

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
        setSavedSnapshot(
          createDocumentSnapshot(
            document.titre,
            document.contenu,
            document.dossier_id ?? "",
          ),
        )
      } catch {
        setMessage("Impossible de charger ce document.")
        setIsSuccess(false)
      } finally {
        setIsLoading(false)
      }
    }

    loadEditor()
  }, [documentId, onSessionExpired])

  // Les fenêtres peuvent être fermées avec Échap quand aucune action ne tourne.
  useEffect(() => {
    function closeModalWithEscape(event) {
      if (event.key === "Escape" && isDeleteModalOpen && !isDeleting) {
        setIsDeleteModalOpen(false)
      }

      if (event.key === "Escape" && aiSuggestion) {
        setAiSuggestion(null)
      }
    }

    document.addEventListener("keydown", closeModalWithEscape)
    return () => document.removeEventListener("keydown", closeModalWithEscape)
  }, [aiSuggestion, isDeleteModalOpen, isDeleting])

  const saveDocument = useCallback(async (showMessage = false, isAutomatic = false) => {
    if (!title.trim() || isSaving) {
      return
    }

    const currentSnapshot = createDocumentSnapshot(title, content, folderId)
    setIsSaving(true)
    setSaveStatus("saving")

    if (showMessage) {
      setMessage("")
      setIsSuccess(false)
    }

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
        setIsSuccess(false)
        setSaveStatus("error")

        if (isAutomatic) {
          setBlockedAutoSaveSnapshot(currentSnapshot)
        }
        return
      }

      setSavedSnapshot(currentSnapshot)
      setBlockedAutoSaveSnapshot(null)
      setSaveStatus("saved")
      setLastModified("à l'instant")

      if (showMessage) {
        setMessage(data.message)
        setIsSuccess(true)
      }

      if (data.version_created && loadedHistoryTabs.versions) {
        setVersions((currentVersions) => [
          data.version,
          ...currentVersions,
        ])
      }
    } catch {
      setMessage("Le serveur est inaccessible.")
      setIsSuccess(false)
      setSaveStatus("error")

      if (isAutomatic) {
        setBlockedAutoSaveSnapshot(currentSnapshot)
      }
    } finally {
      setIsSaving(false)
    }
  }, [
    content,
    documentId,
    folderId,
    isSaving,
    loadedHistoryTabs.versions,
    onSessionExpired,
    title,
  ])

  function handleSave(event) {
    event.preventDefault()
    saveDocument(true)
  }

  // Sauvegarde après une courte période sans nouvelle saisie.
  useEffect(() => {
    if (
      isLoading ||
      isSaving ||
      activeAiAction !== null ||
      savedSnapshot === null ||
      !title.trim()
    ) {
      return undefined
    }

    const currentSnapshot = createDocumentSnapshot(title, content, folderId)

    if (currentSnapshot === savedSnapshot) {
      return undefined
    }

    if (currentSnapshot === blockedAutoSaveSnapshot) {
      return undefined
    }

    const timer = window.setTimeout(() => {
      saveDocument(false, true)
    }, 2500)

    return () => window.clearTimeout(timer)
  }, [
    activeAiAction,
    blockedAutoSaveSnapshot,
    content,
    folderId,
    isLoading,
    isSaving,
    saveDocument,
    savedSnapshot,
    title,
  ])

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

  async function handleAiAction(action) {
    if (!content.trim()) {
      setMessage("Écrivez du texte avant d'utiliser l'assistant IA.")
      setIsSuccess(false)
      return
    }

    setActiveAiAction(action)
    setMessage("")
    setIsSuccess(false)
    setAiOriginalText(content)

    try {
      const response = await fetch(
        `http://localhost:5000/api/documents/${documentId}/ai/${action}`,
        {
          method: "POST",
          credentials: "include",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({ text: content }),
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

      setAiSuggestion({
        action,
        text: data.suggestion,
      })

      if (loadedHistoryTabs.interactions) {
        setInteractions((currentInteractions) => [
          {
            id: `new-${Date.now()}`,
            type_action: AI_ACTIONS[action].historyType,
            texte_entree: content,
            texte_sortie: data.suggestion,
            date: "À l'instant",
          },
          ...currentInteractions,
        ])
      }

      onQuotaChanged(data.quota_restant)
    } catch {
      setMessage("Le serveur ou l'assistant IA est inaccessible.")
    } finally {
      setActiveAiAction(null)
    }
  }

  async function loadHistoryTab(tab) {
    if (loadedHistoryTabs[tab]) {
      return
    }

    setIsHistoryLoading(true)
    setHistoryMessage("")

    try {
      const endpoint =
        tab === "versions"
          ? "versions"
          : "interactions"
      const response = await fetch(
        `http://localhost:5000/api/documents/${documentId}/${endpoint}`,
        {
          credentials: "include",
        },
      )
      const data = await response.json()

      if (response.status === 401) {
        onSessionExpired()
        return
      }

      if (!response.ok) {
        setHistoryMessage(data.message)
        return
      }

      if (tab === "versions") {
        setVersions(data.versions)
      } else {
        setInteractions(data.interactions)
      }

      setLoadedHistoryTabs((currentTabs) => ({
        ...currentTabs,
        [tab]: true,
      }))
    } catch {
      setHistoryMessage("Impossible de charger cet historique.")
    } finally {
      setIsHistoryLoading(false)
    }
  }

  async function toggleHistory() {
    const shouldOpen = !isHistoryOpen
    setIsHistoryOpen(shouldOpen)

    if (shouldOpen) {
      await loadHistoryTab(historyTab)
    }
  }

  async function changeHistoryTab(tab) {
    setHistoryTab(tab)
    setHistoryMessage("")
    await loadHistoryTab(tab)
  }

  async function restoreVersion(versionId) {
    setBusyVersionId(versionId)
    setHistoryMessage("")
    setMessage("")

    try {
      const response = await fetch(
        `http://localhost:5000/api/documents/${documentId}/versions/${versionId}/restore`,
        {
          method: "POST",
          credentials: "include",
        },
      )
      const data = await response.json()

      if (response.status === 401) {
        onSessionExpired()
        return
      }

      if (!response.ok) {
        setHistoryMessage(data.message)
        return
      }

      setTitle(data.document.titre)
      setContent(data.document.contenu)
      setSavedSnapshot(
        createDocumentSnapshot(
          data.document.titre,
          data.document.contenu,
          folderId,
        ),
      )
      setBlockedAutoSaveSnapshot(null)
      setSaveStatus("saved")
      setLastModified("à l'instant")
      setVersions((currentVersions) => [
        data.version,
        ...currentVersions,
      ])
      setMessage("Version restaurée avec succès")
      setIsSuccess(true)
    } catch {
      setHistoryMessage("Impossible de restaurer cette version.")
    } finally {
      setBusyVersionId(null)
    }
  }

  function applyAiSuggestion() {
    const actionConfig = AI_ACTIONS[aiSuggestion.action]
    setContent(aiSuggestion.text)
    markDocumentChanged()
    setAiSuggestion(null)
    setMessage(
      `${actionConfig.appliedMessage}. Enregistrez le document pour la conserver.`,
    )
    setIsSuccess(true)
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
          <span className={`autosave-status ${displayedSaveStatus}`}>
            {displayedSaveStatus === "pending" &&
              "Modifications non enregistrées"}
            {displayedSaveStatus === "saving" && "Enregistrement..."}
            {displayedSaveStatus === "error" && "Échec de l'enregistrement"}
            {displayedSaveStatus === "saved" && "Sauvegardé"}
          </span>
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
              onChange={(event) => {
                setTitle(event.target.value)
                markDocumentChanged()
              }}
              required
            />
          </div>

          <div className="editor-folder-field">
            <label htmlFor="editorFolder">Dossier</label>
            <select
              id="editorFolder"
              value={folderId}
              onChange={(event) => {
                setFolderId(event.target.value)
                markDocumentChanged()
              }}
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
              disabled={isSaving || activeAiAction !== null}
            >
              Supprimer
            </button>
            <button
              className="editor-save"
              type="submit"
              disabled={isSaving || activeAiAction !== null}
            >
              {isSaving ? "Enregistrement..." : "Enregistrer"}
            </button>
          </div>
        </div>

        <div className="editor-ai-tools">
          <div>
            <p>Assistant IA</p>
            <span>Améliorez votre texte avec le modèle local Ollama.</span>
          </div>
          <div className="editor-ai-buttons">
            {Object.entries(AI_ACTIONS).map(([action, actionConfig]) => (
              <button
                className="editor-ai"
                type="button"
                key={action}
                onClick={() => handleAiAction(action)}
                disabled={isSaving || activeAiAction !== null}
              >
                {activeAiAction === action
                  ? actionConfig.loadingLabel
                  : actionConfig.buttonLabel}
              </button>
            ))}
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
            onChange={(event) => {
              setContent(event.target.value)
              markDocumentChanged()
            }}
            placeholder="Commencez à rédiger votre document..."
          />
        </div>
      </form>

      <section className="ai-history">
        <button
          className="ai-history-toggle"
          type="button"
          onClick={toggleHistory}
          aria-expanded={isHistoryOpen}
          aria-controls="ai-history-content"
        >
          <div>
            <span>Historique du document</span>
            <small>Consultez les sauvegardes et les actions de l'assistant IA.</small>
          </div>
          <strong aria-hidden="true">{isHistoryOpen ? "−" : "+"}</strong>
        </button>

        {isHistoryOpen && (
          <div className="ai-history-content" id="ai-history-content">
            <div className="history-tabs" role="tablist">
              <button
                className={historyTab === "versions" ? "active" : ""}
                type="button"
                role="tab"
                aria-selected={historyTab === "versions"}
                onClick={() => changeHistoryTab("versions")}
              >
                Versions sauvegardées
              </button>
              <button
                className={historyTab === "interactions" ? "active" : ""}
                type="button"
                role="tab"
                aria-selected={historyTab === "interactions"}
                onClick={() => changeHistoryTab("interactions")}
              >
                Activité IA
              </button>
            </div>

            {isHistoryLoading ? (
              <p className="ai-history-state">Chargement de l'historique...</p>
            ) : historyMessage ? (
              <p className="ai-history-state error">{historyMessage}</p>
            ) : historyTab === "versions" && versions.length === 0 ? (
              <div className="ai-history-empty">
                <span aria-hidden="true">↺</span>
                <p>Aucune version sauvegardée pour ce document.</p>
              </div>
            ) : historyTab === "versions" ? (
              <div className="document-version-list">
                {versions.map((version, index) => (
                  <article className="document-version-item" key={version.id}>
                    <header>
                      <div>
                        <span>
                          {index === 0
                            ? "Dernière sauvegarde"
                            : `Version ${versions.length - index}`}
                        </span>
                        <time>{version.date}</time>
                      </div>
                      <button
                        type="button"
                        onClick={() => restoreVersion(version.id)}
                        disabled={busyVersionId !== null}
                      >
                        {busyVersionId === version.id
                          ? "Restauration..."
                          : "Restaurer"}
                      </button>
                    </header>
                    <h3>{version.titre}</h3>
                    <p>
                      {version.contenu ||
                        "Cette version ne contient encore aucun texte."}
                    </p>
                  </article>
                ))}
              </div>
            ) : interactions.length === 0 ? (
              <div className="ai-history-empty">
                <span aria-hidden="true">✦</span>
                <p>Aucune interaction IA pour ce document.</p>
              </div>
            ) : (
              <div className="ai-history-list">
                {interactions.map((interaction) => (
                  <article className="ai-history-item" key={interaction.id}>
                    <header>
                      <span>
                        {HISTORY_LABELS[interaction.type_action] ??
                          interaction.type_action}
                      </span>
                      <time>{interaction.date}</time>
                    </header>

                    <div className="ai-history-comparison">
                      <div>
                        <strong>Texte envoyé</strong>
                        <p>{interaction.texte_entree}</p>
                      </div>
                      <div>
                        <strong>Réponse de l'IA</strong>
                        <p>{interaction.texte_sortie}</p>
                      </div>
                    </div>
                  </article>
                ))}
              </div>
            )}
          </div>
        )}
      </section>

      {aiSuggestion && (
        <div
          className="modal-backdrop"
          onMouseDown={(event) => {
            if (event.target === event.currentTarget) {
              setAiSuggestion(null)
            }
          }}
        >
          <section
            className="ai-suggestion-modal"
            role="dialog"
            aria-modal="true"
            aria-labelledby="ai-suggestion-title"
            aria-describedby="ai-suggestion-description"
          >
            <div className="ai-suggestion-heading">
              <div>
                <p className="eyebrow">Assistant de rédaction</p>
                <h2 id="ai-suggestion-title">
                  {AI_ACTIONS[aiSuggestion.action].modalTitle}
                </h2>
              </div>
              <button
                type="button"
                onClick={() => setAiSuggestion(null)}
                aria-label="Fermer la suggestion"
              >
                ×
              </button>
            </div>

            <p id="ai-suggestion-description">
              Comparez les deux versions avant de remplacer le texte actuel.
            </p>

            <div className="ai-comparison">
              <article>
                <span>Texte actuel</span>
                <p>{aiOriginalText}</p>
              </article>
              <article className="ai-corrected-text">
                <span>{AI_ACTIONS[aiSuggestion.action].suggestionLabel}</span>
                <p>{aiSuggestion.text}</p>
              </article>
            </div>

            <div className="ai-suggestion-actions">
              <button type="button" onClick={() => setAiSuggestion(null)}>
                Conserver mon texte
              </button>
              <button
                className="apply"
                type="button"
                onClick={applyAiSuggestion}
                autoFocus
              >
                Appliquer la suggestion
              </button>
            </div>
          </section>
        </div>
      )}

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
