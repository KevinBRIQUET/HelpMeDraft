import { useEffect, useState } from "react"

function AdminView({ currentUserId, onSessionExpired }) {
  const [summary, setSummary] = useState(null)
  const [users, setUsers] = useState([])
  const [isLoading, setIsLoading] = useState(true)
  const [busyUserId, setBusyUserId] = useState(null)
  const [error, setError] = useState("")
  const [message, setMessage] = useState("")
  const [isMessageSuccess, setIsMessageSuccess] = useState(false)

  useEffect(() => {
    async function loadAdminData() {
      try {
        const [summaryResponse, usersResponse] = await Promise.all([
          fetch("http://localhost:5000/api/admin/summary", {
            credentials: "include",
          }),
          fetch("http://localhost:5000/api/admin/users", {
            credentials: "include",
          }),
        ])

        if (
          [401, 403].includes(summaryResponse.status) ||
          [401, 403].includes(usersResponse.status)
        ) {
          onSessionExpired()
          return
        }

        if (!summaryResponse.ok || !usersResponse.ok) {
          throw new Error()
        }

        const summaryData = await summaryResponse.json()
        const usersData = await usersResponse.json()

        setSummary(summaryData.summary)
        setUsers(usersData.users)
      } catch {
        setError("Impossible de charger le back-office.")
      } finally {
        setIsLoading(false)
      }
    }

    loadAdminData()
  }, [onSessionExpired])

  function updateUserField(userId, field, value) {
    setUsers((currentUsers) =>
      currentUsers.map((account) =>
        account.id === userId
          ? { ...account, [field]: value }
          : account,
      ),
    )
    setMessage("")
    setIsMessageSuccess(false)
  }

  async function saveUser(account) {
    const quota = Number(account.quota_restant)

    if (!Number.isInteger(quota) || quota < 0 || quota > 1000) {
      setMessage("Le quota doit être un nombre entier entre 0 et 1000.")
      setIsMessageSuccess(false)
      return
    }

    setBusyUserId(account.id)
    setMessage("")
    setIsMessageSuccess(false)

    try {
      const response = await fetch(
        `http://localhost:5000/api/admin/users/${account.id}`,
        {
          method: "PATCH",
          credentials: "include",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({
            role: Number(account.role),
            quota,
            active: Number(account.actif),
          }),
        },
      )
      const data = await response.json()

      if ([401, 403].includes(response.status)) {
        onSessionExpired()
        return
      }

      if (!response.ok) {
        setMessage(data.message)
        setIsMessageSuccess(false)
        return
      }

      setUsers((currentUsers) =>
        currentUsers.map((currentAccount) =>
          currentAccount.id === account.id
            ? {
                ...currentAccount,
                role: data.user.role,
                quota_restant: data.user.quota_restant,
                actif: data.user.actif,
              }
            : currentAccount,
        ),
      )
      setSummary((currentSummary) => ({
        ...currentSummary,
        nombre_administrateurs: users.filter((user) =>
          user.id === account.id ? data.user.role : user.role,
        ).length,
      }))
      setMessage(`Le compte de ${account.prenom} a été mis à jour.`)
      setIsMessageSuccess(true)
    } catch {
      setMessage("Le serveur est inaccessible.")
      setIsMessageSuccess(false)
    } finally {
      setBusyUserId(null)
    }
  }

  if (isLoading) {
    return <p className="admin-loading">Chargement du back-office...</p>
  }

  return (
    <div className="admin-view">
      <header className="section-heading admin-heading">
        <div>
          <p className="eyebrow">Back-office</p>
          <h1>Administration</h1>
          <p>Consultez les comptes et l’activité globale de HelpMeDraft.</p>
        </div>
      </header>

      {error && (
        <p className="dashboard-error" role="status">
          {error}
        </p>
      )}

      {message && (
        <p
          className={`admin-message ${
            isMessageSuccess ? "success" : "error"
          }`}
          role="status"
        >
          {message}
        </p>
      )}

      {!error && summary && (
        <>
          <section className="admin-stats" aria-label="Statistiques globales">
            <article>
              <span>Utilisateurs</span>
              <strong>{summary.nombre_utilisateurs}</strong>
              <small>
                {summary.nombre_utilisateurs_actifs} actif(s),{" "}
                {summary.nombre_utilisateurs_inactifs} inactif(s)
              </small>
            </article>
            <article>
              <span>Documents</span>
              <strong>{summary.nombre_documents}</strong>
              <small>{summary.nombre_dossiers} dossier(s)</small>
            </article>
            <article>
              <span>Actions IA</span>
              <strong>{summary.nombre_interactions}</strong>
              <small>interactions enregistrées</small>
            </article>
          </section>

          <section className="admin-users-section">
            <div className="admin-users-heading">
              <div>
                <p className="eyebrow">Gestion des comptes</p>
                <h2>Utilisateurs inscrits</h2>
              </div>
              <span>{users.length} compte(s)</span>
            </div>

            <div className="admin-table-wrapper">
              <table className="admin-users-table">
                <thead>
                  <tr>
                    <th>Utilisateur</th>
                    <th>Statut</th>
                    <th>Rôle</th>
                    <th>Inscription</th>
                    <th>Documents</th>
                    <th>Dossiers</th>
                    <th>Quota IA</th>
                    <th>Action</th>
                  </tr>
                </thead>
                <tbody>
                  {users.map((account) => (
                    <tr key={account.id}>
                      <td>
                        <strong>
                          {account.prenom} {account.nom}
                        </strong>
                        <span>{account.email}</span>
                      </td>
                      <td>
                        <select
                          className={`admin-status-select ${
                            account.actif ? "active" : "inactive"
                          }`}
                          value={Number(account.actif)}
                          disabled={account.id === currentUserId}
                          onChange={(event) =>
                            updateUserField(
                              account.id,
                              "actif",
                              Number(event.target.value),
                            )
                          }
                          aria-label={`Statut de ${account.prenom} ${account.nom}`}
                        >
                          <option value={1}>Actif</option>
                          <option value={0}>Inactif</option>
                        </select>
                      </td>
                      <td>
                        <select
                          className="admin-role-select"
                          value={Number(account.role)}
                          disabled={account.id === currentUserId}
                          onChange={(event) =>
                            updateUserField(
                              account.id,
                              "role",
                              Number(event.target.value),
                            )
                          }
                          aria-label={`Rôle de ${account.prenom} ${account.nom}`}
                        >
                          <option value={0}>Utilisateur</option>
                          <option value={1}>Administrateur</option>
                        </select>
                      </td>
                      <td>{account.date_inscription || "Non renseignée"}</td>
                      <td>{account.nombre_documents}</td>
                      <td>{account.nombre_dossiers}</td>
                      <td>
                        <input
                          className="admin-quota-input"
                          type="number"
                          min="0"
                          max="1000"
                          value={account.quota_restant}
                          onChange={(event) =>
                            updateUserField(
                              account.id,
                              "quota_restant",
                              event.target.value,
                            )
                          }
                          aria-label={`Quota IA de ${account.prenom} ${account.nom}`}
                        />
                      </td>
                      <td>
                        <button
                          className="admin-save-user"
                          type="button"
                          onClick={() => saveUser(account)}
                          disabled={busyUserId === account.id}
                        >
                          {busyUserId === account.id
                            ? "Enregistrement..."
                            : "Enregistrer"}
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>
        </>
      )}
    </div>
  )
}

export default AdminView
