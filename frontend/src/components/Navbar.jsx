import { Link, useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";

export default function Navbar() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();

  if (!user) return null;

  return (
    <nav className="border-b border-graphite bg-void px-6 py-3 flex items-center justify-between">
      <div className="flex items-center gap-6">
        <span className="text-[15px] font-[510] text-paper tracking-[-0.011em]">
          Lathe Inspector
        </span>
        <Link
          to="/"
          className="text-[13px] text-mist hover:text-paper transition-colors px-3 py-2 rounded-control"
        >
          Inspections
        </Link>
        <Link
          to="/machines"
          className="text-[13px] text-mist hover:text-paper transition-colors px-3 py-2 rounded-control"
        >
          Machines
        </Link>
        <Link
          to="/batches"
          className="text-[13px] text-mist hover:text-paper transition-colors px-3 py-2 rounded-control"
        >
          Batches
        </Link>
        <Link
          to="/stats"
          className="text-[13px] text-mist hover:text-paper transition-colors px-3 py-2 rounded-control"
        >
          Stats
        </Link>
      </div>
      <div className="flex items-center gap-4 text-[13px]">
        <span className="text-fog">
          {user.name} <span className="text-ash">({user.role})</span>
        </span>
        <button
          onClick={() => {
            logout();
            navigate("/login");
          }}
          className="text-fog hover:text-paper transition-colors"
        >
          Log out
        </button>
      </div>
    </nav>
  );
}
