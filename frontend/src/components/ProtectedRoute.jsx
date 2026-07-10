import { Navigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";

// Wraps a page and refuses to render it (redirecting to /login instead)
// if nobody's logged in. `role` is optional -- pass e.g. role="MANAGER"
// to also block operators from a manager-only page.
export default function ProtectedRoute({ children, role }) {
  const { user } = useAuth();

  if (!user) return <Navigate to="/login" replace />;
  if (role && user.role !== role) return <Navigate to="/" replace />;

  return children;
}
