import { useState } from "react"

function App() {
  const [email, setEmail] = useState("")
  const [password, setPassword] = useState("")
  const [message, setMessage] = useState("")

  async function handleSubmit(event) {
    event.preventDefault()
    setMessage("Connexion en cours...")

    try {
      const response = await fetch("http://127.0.0.1:5000/api/login", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ email, password }),
      })

      const data = await response.json()
      setMessage(data.message)
    } catch {
      setMessage("Le serveur est inaccessible")
    }
  }

  return (
    <main>
      <h1>Connexion</h1>

      <form onSubmit={handleSubmit}>
        <label htmlFor="email">Adresse e-mail</label>
        <input
          id="email"
          type="email"
          value={email}
          onChange={(event) => setEmail(event.target.value)}
          required
        />

        <label htmlFor="password">Mot de passe</label>
        <input
          id="password"
          type="password"
          value={password}
          onChange={(event) => setPassword(event.target.value)}
          required
        />

        <button type="submit">Se connecter</button>
      </form>

      {message && <p>{message}</p>}
    </main>
  )
}

export default App