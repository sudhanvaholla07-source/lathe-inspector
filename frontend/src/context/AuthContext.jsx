import { createContext, useContext, useState } from "react";
import { api } from "../api";

// React Context solves one specific problem: "who is logged in" needs
// to be readable from many components (navbar, protected routes,
// the confirm-button that's manager-only) that aren't directly related
// to each other in the component tree. Without Context you'd have to
// pass `user` down as a prop through every layer in between ("prop
// drilling"). Context lets any component just call useAuth() and read
// it directly, no matter how deep it is.
const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  // Lazy initializer: reads localStorage once on first render, so a
  // page refresh doesn't log the user out.
  const [user, setUser] = useState(() => {
    const stored = localStorage.getItem("user");
    return stored ? JSON.parse(stored) : null;
  });

  async function login(email, password) {
    const data = await api.login(email, password);
    localStorage.setItem("token", data.token);
    localStorage.setItem("user", JSON.stringify(data.user));
    setUser(data.user);
  }

  function logout() {
    localStorage.removeItem("token");
    localStorage.removeItem("user");
    setUser(null);
  }

  return (
    <AuthContext.Provider value={{ user, login, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

// Small custom hook wrapping useContext -- lets components write
// `const { user } = useAuth()` instead of importing AuthContext and
// calling useContext(AuthContext) everywhere.
export function useAuth() {
  return useContext(AuthContext);
}
