import { useCallback, useEffect, useState } from "react"
import "./App.css"
import Dashboard from "./Dashboard"

function App() {
  // Données du formulaire et état de l'interface
  const [resetToken] = useState(
    () => new URLSearchParams(window.location.search).get("token") ?? "",
  )
  const [authMode, setAuthMode] = useState(
    () =>
      window.location.pathname === "/reset-password" && resetToken
        ? "reset"
        : "login",
  )
  const [firstName, setFirstName] = useState("")
  const [lastName, setLastName] = useState("")
  const [email, setEmail] = useState("")
  const [password, setPassword] = useState("")
  const [passwordConfirmation, setPasswordConfirmation] = useState("")
  const [consent, setConsent] = useState(false)
  const [message, setMessage] = useState("")
  const [isLoading, setIsLoading] = useState(false)
  const [isSuccess, setIsSuccess] = useState(false)
  const [showPassword, setShowPassword] = useState(false)
  const [user, setUser] = useState(null)
  const [developmentResetUrl, setDevelopmentResetUrl] = useState("")

  const handleSessionExpired = useCallback(() => {
    setUser(null)
  }, [])

  // Vérifie si une session existe déjà lors du chargement de la page.
  useEffect(() => {
    async function checkSession() {
      if (resetToken) {
        return
      }

      try {
        const response = await fetch("http://localhost:5000/api/me", {
          credentials: "include",
        })

        if (!response.ok) {
          return
        }

        const data = await response.json()
        setUser(data.user)
      } catch {
        // Flask peut simplement ne pas être lancé au chargement de la page.
      }
    }

    checkSession()
  }, [resetToken])

  // Bascule entre connexion et inscription en réinitialisant le formulaire.
  function changeAuthMode(mode) {
    setAuthMode(mode)
    setFirstName("")
    setLastName("")
    setEmail("")
    setPassword("")
    setPasswordConfirmation("")
    setConsent(false)
    setMessage("")
    setIsSuccess(false)
    setShowPassword(false)
    setDevelopmentResetUrl("")

    if (mode !== "reset") {
      window.history.replaceState({}, "", "/")
    }
  }

  // Envoie les données au bon endpoint selon le formulaire affiché.
  async function handleSubmit(event) {
    event.preventDefault()
    const isRegistering = authMode === "register"
    const isForgottenPassword = authMode === "forgot"
    const isResettingPassword = authMode === "reset"

    setMessage(
      isRegistering
        ? "Création du compte..."
        : isForgottenPassword
          ? "Création du lien..."
          : isResettingPassword
            ? "Modification du mot de passe..."
            : "Connexion en cours...",
    )
    setIsLoading(true)
    setIsSuccess(false)
    setDevelopmentResetUrl("")

    try {
      const endpoint = isRegistering
        ? "/api/register"
        : isForgottenPassword
          ? "/api/forgot-password"
          : isResettingPassword
            ? "/api/reset-password"
            : "/api/login"
      const body = isRegistering
        ? {
            prenom: firstName,
            nom: lastName,
            email,
            password,
            passwordConfirmation,
            consent,
          }
        : isForgottenPassword
          ? { email }
          : isResettingPassword
            ? { token: resetToken, password, passwordConfirmation }
            : { email, password }

      const response = await fetch(`http://localhost:5000${endpoint}`, {
        method: "POST",
        credentials: "include",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify(body),
      })

      const data = await response.json()
      setMessage(data.message)
      setIsSuccess(response.ok)

      if (response.ok && data.development_reset_url) {
        setDevelopmentResetUrl(data.development_reset_url)
      }

      if (response.ok && (authMode === "login" || isRegistering)) {
        setUser(data.user)
        setPassword("")
        setMessage("")
      }

      if (response.ok && isResettingPassword) {
        setAuthMode("login")
        setPassword("")
        setPasswordConfirmation("")
        window.history.replaceState({}, "", "/")
      }
    } catch {
      setMessage("Le serveur est inaccessible")
      setIsSuccess(false)
    } finally {
      setIsLoading(false)
    }
  }

  // Supprime la session côté Flask puis réaffiche le formulaire.
  async function handleLogout() {
    setIsLoading(true)

    try {
      const response = await fetch("http://localhost:5000/api/logout", {
        method: "POST",
        credentials: "include",
      })

      if (!response.ok) {
        throw new Error()
      }

      setUser(null)
      setAuthMode("login")
      setFirstName("")
      setLastName("")
      setEmail("")
      setPassword("")
      setPasswordConfirmation("")
      setConsent(false)
      setMessage("")
      setIsSuccess(false)
    } catch {
      setMessage("Impossible de se déconnecter")
      setIsSuccess(false)
    } finally {
      setIsLoading(false)
    }
  }

  if (user) {
    return (
      <Dashboard
        user={user}
        isLoggingOut={isLoading}
        onLogout={handleLogout}
        onSessionExpired={handleSessionExpired}
      />
    )
  }

  const isForgottenPassword = authMode === "forgot"
  const isResettingPassword = authMode === "reset"
  const displaysEmail = !isResettingPassword
  const displaysPassword = !isForgottenPassword
  const displaysPasswordConfirmation =
    authMode === "register" || isResettingPassword

  return (
    <main className="login-page">
      <section className="brand-panel" aria-label="Présentation de HelpMeDraft">
        <div className="brand">
          <span className="brand-mark" aria-hidden="true">
            H
          </span>
          <span>HelpMeDraft</span>
        </div>

        <div className="brand-content">
          <p className="eyebrow">Votre assistant de rédaction</p>
          <h1>Des écrits professionnels, plus clairs et plus rapides.</h1>
          <p className="brand-description">
            Rédigez, améliorez et organisez vos documents dans un espace
            personnel sécurisé.
          </p>

          <ul className="benefits">
            <li>Reformulation professionnelle assistée par IA</li>
            <li>Documents enregistrés dans votre espace</li>
            <li>Données et historique protégés</li>
          </ul>
        </div>

        <p className="brand-footer">LexiCorp · HelpMeDraft</p>
      </section>

      <section className="form-panel">
        <div className="mobile-brand" aria-label="HelpMeDraft">
          <span className="brand-mark" aria-hidden="true">
            H
          </span>
          <span>HelpMeDraft</span>
        </div>

        <div className="login-card">
          <>
            {(isForgottenPassword || isResettingPassword) && (
              <button
                className="auth-back-button"
                type="button"
                onClick={() => changeAuthMode("login")}
              >
                ← Retour à la connexion
              </button>
            )}

            {!isForgottenPassword && !isResettingPassword && (
              <div className="auth-tabs" aria-label="Choix du formulaire">
                <button
                  type="button"
                  className={authMode === "login" ? "active" : ""}
                  onClick={() => changeAuthMode("login")}
                  aria-pressed={authMode === "login"}
                >
                  Connexion
                </button>
                <button
                  type="button"
                  className={authMode === "register" ? "active" : ""}
                  onClick={() => changeAuthMode("register")}
                  aria-pressed={authMode === "register"}
                >
                  Créer un compte
                </button>
              </div>
            )}

              <div className="form-heading">
                <p className="eyebrow">Espace personnel</p>
                <h2>
                  {authMode === "login"
                    ? "Bon retour parmi nous"
                    : authMode === "register"
                      ? "Créez votre espace"
                      : isForgottenPassword
                        ? "Mot de passe oublié"
                        : "Choisissez un nouveau mot de passe"}
                </h2>
                <p>
                  {authMode === "login"
                    ? "Connectez-vous pour retrouver vos documents."
                    : authMode === "register"
                      ? "Commencez à rédiger et organiser vos documents."
                      : isForgottenPassword
                        ? "Saisissez votre adresse pour recevoir un lien temporaire."
                        : "Ce lien est valable pendant 30 minutes et une seule fois."}
                </p>
              </div>

              <form
                className={authMode === "register" ? "register-form" : ""}
                onSubmit={handleSubmit}
              >
                {authMode === "register" && (
                  <div className="name-fields">
                    <div className="field">
                      <label htmlFor="firstName">Prénom</label>
                      <div className="input-wrapper no-icon">
                        <input
                          id="firstName"
                          name="firstName"
                          type="text"
                          autoComplete="given-name"
                          placeholder="Votre prénom"
                          maxLength="50"
                          value={firstName}
                          onChange={(event) => setFirstName(event.target.value)}
                          required
                        />
                      </div>
                    </div>

                    <div className="field">
                      <label htmlFor="lastName">Nom</label>
                      <div className="input-wrapper no-icon">
                        <input
                          id="lastName"
                          name="lastName"
                          type="text"
                          autoComplete="family-name"
                          placeholder="Votre nom"
                          maxLength="50"
                          value={lastName}
                          onChange={(event) => setLastName(event.target.value)}
                          required
                        />
                      </div>
                    </div>
                  </div>
                )}

                {displaysEmail && (
                  <div className="field">
                    <label htmlFor="email">Adresse e-mail</label>
                    <div className="input-wrapper">
                      <span className="input-icon" aria-hidden="true">@</span>
                      <input
                        id="email"
                        name="email"
                        type="email"
                        autoComplete="email"
                        placeholder="vous@exemple.fr"
                        value={email}
                        onChange={(event) => setEmail(event.target.value)}
                        required
                      />
                    </div>
                  </div>
                )}

                {displaysPassword && (
                  <div className="field">
                    <label htmlFor="password">
                      {isResettingPassword
                        ? "Nouveau mot de passe"
                        : "Mot de passe"}
                    </label>
                    <div className="input-wrapper">
                      <span className="input-icon lock-icon" aria-hidden="true" />
                      <input
                        id="password"
                        name="password"
                        type={showPassword ? "text" : "password"}
                        autoComplete={
                          authMode === "login"
                            ? "current-password"
                            : "new-password"
                        }
                        placeholder="Votre mot de passe"
                        minLength={authMode === "login" ? undefined : 8}
                        value={password}
                        onChange={(event) => setPassword(event.target.value)}
                        required
                      />
                      <button
                        className="password-toggle"
                        type="button"
                        onClick={() => setShowPassword(!showPassword)}
                        aria-label={
                          showPassword
                            ? "Masquer le mot de passe"
                            : "Afficher le mot de passe"
                        }
                      >
                        {showPassword ? "Masquer" : "Afficher"}
                      </button>
                    </div>
                    {authMode !== "login" && (
                      <p className="field-hint">
                        8 caractères minimum, avec majuscule, minuscule et chiffre.
                      </p>
                    )}
                  </div>
                )}

                {displaysPasswordConfirmation && (
                  <>
                    <div className="field">
                      <label htmlFor="passwordConfirmation">
                        Confirmer le mot de passe
                      </label>
                      <div className="input-wrapper">
                        <span
                          className="input-icon lock-icon"
                          aria-hidden="true"
                        />
                        <input
                          id="passwordConfirmation"
                          name="passwordConfirmation"
                          type={showPassword ? "text" : "password"}
                          autoComplete="new-password"
                          placeholder="Saisissez-le à nouveau"
                          minLength="8"
                          value={passwordConfirmation}
                          onChange={(event) =>
                            setPasswordConfirmation(event.target.value)
                          }
                          required
                        />
                      </div>
                    </div>

                    {authMode === "register" && (
                      <label className="consent-field">
                        <input
                          type="checkbox"
                          checked={consent}
                          onChange={(event) => setConsent(event.target.checked)}
                          required
                        />
                        <span>
                          J’accepte les conditions d’utilisation et le traitement
                          de mes données pour créer mon compte.
                        </span>
                      </label>
                    )}
                  </>
                )}

                {authMode === "login" && (
                  <button
                    className="forgot-password-button"
                    type="button"
                    onClick={() => changeAuthMode("forgot")}
                  >
                    Mot de passe oublié ?
                  </button>
                )}

                <button
                  className="submit-button"
                  type="submit"
                  disabled={isLoading}
                >
                  {isLoading
                    ? authMode === "register"
                      ? "Création..."
                      : isForgottenPassword
                        ? "Création du lien..."
                        : isResettingPassword
                          ? "Modification..."
                          : "Connexion..."
                    : authMode === "register"
                      ? "Créer mon compte"
                      : isForgottenPassword
                        ? "Générer le lien"
                        : isResettingPassword
                          ? "Modifier mon mot de passe"
                          : "Se connecter"}
                  {!isLoading && <span aria-hidden="true">→</span>}
                </button>
              </form>

              {message && (
                <p
                  className={`form-message ${
                    isLoading ? "loading" : isSuccess ? "success" : "error"
                  }`}
                  role="status"
                  aria-live="polite"
                >
                  {message}
                </p>
              )}

              {developmentResetUrl && (
                <a
                  className="development-reset-link"
                  href={developmentResetUrl}
                >
                  Ouvrir le lien de réinitialisation
                </a>
              )}

              <p className="privacy-note">
                Connexion sécurisée · Vos identifiants restent confidentiels
              </p>
          </>
        </div>
      </section>
    </main>
  )
}

export default App
