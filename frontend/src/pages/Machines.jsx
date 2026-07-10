import { useEffect, useState } from "react";
import { api, BASE_URL } from "../api";

const inputClass =
  "w-full bg-white/[0.02] border border-white/[0.08] rounded-control px-3.5 py-2.5 text-[13px] text-mist placeholder:text-ash focus:outline-none focus:border-mist transition-colors";
const cardShadow = { boxShadow: "rgb(35, 37, 42) 0px 0px 0px 1px inset" };

export default function Machines() {
  const [machines, setMachines] = useState([]);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  const [newMachineName, setNewMachineName] = useState("");
  const [newMachineLocation, setNewMachineLocation] = useState("");

  const [ptMachineId, setPtMachineId] = useState("");
  const [ptName, setPtName] = useState("");
  const [ptFile, setPtFile] = useState(null);

  async function load() {
    setLoading(true);
    setError("");
    try {
      setMachines(await api.getMachines());
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
  }, []);

  async function handleCreateMachine(e) {
    e.preventDefault();
    setError("");
    try {
      await api.createMachine(newMachineName, newMachineLocation);
      setNewMachineName("");
      setNewMachineLocation("");
      load();
    } catch (err) {
      setError(err.message);
    }
  }

  async function handleCreatePartType(e) {
    e.preventDefault();
    setError("");
    if (!ptFile) {
      setError("Choose a reference image");
      return;
    }
    try {
      const formData = new FormData();
      formData.append("name", ptName);
      formData.append("machineId", ptMachineId);
      formData.append("referenceImage", ptFile);
      await api.createPartType(formData);
      setPtName("");
      setPtFile(null);
      load();
    } catch (err) {
      setError(err.message);
    }
  }

  return (
    <div className="max-w-4xl mx-auto px-6 py-10">
      <h1 className="text-[24px] font-[510] text-paper tracking-[-0.012em] mb-8">Machines &amp; Part Types</h1>

      {error && <p className="text-[13px] text-coral-red mb-4">{error}</p>}

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-10">
        <form onSubmit={handleCreateMachine} className="bg-carbon rounded-card p-6" style={cardShadow}>
          <h2 className="text-[13px] font-[510] text-mist mb-4">Add a machine</h2>
          <input
            placeholder="Name (e.g. Lathe #1)"
            className={`${inputClass} mb-2.5`}
            value={newMachineName}
            onChange={(e) => setNewMachineName(e.target.value)}
            required
          />
          <input
            placeholder="Location (optional)"
            className={`${inputClass} mb-4`}
            value={newMachineLocation}
            onChange={(e) => setNewMachineLocation(e.target.value)}
          />
          <button className="bg-acid text-void rounded-control px-4 py-2 text-[13px] font-[510] tracking-[-0.011em] hover:brightness-95 transition-[filter]">
            Add machine
          </button>
        </form>

        <form onSubmit={handleCreatePartType} className="bg-carbon rounded-card p-6" style={cardShadow}>
          <h2 className="text-[13px] font-[510] text-mist mb-4">Add a part type</h2>
          <select
            className={`${inputClass} mb-2.5`}
            value={ptMachineId}
            onChange={(e) => setPtMachineId(e.target.value)}
            required
          >
            <option value="">Choose a machine...</option>
            {machines.map((m) => (
              <option key={m.id} value={m.id}>
                {m.name}
              </option>
            ))}
          </select>
          <input
            placeholder="Part name (e.g. M8 Tee Nut)"
            className={`${inputClass} mb-2.5`}
            value={ptName}
            onChange={(e) => setPtName(e.target.value)}
            required
          />
          <input
            type="file"
            accept="image/*"
            className="w-full text-[13px] text-fog mb-4 file:mr-3 file:bg-white/[0.05] file:text-mist file:border-0 file:rounded-control file:px-3 file:py-1.5 file:text-[12px]"
            onChange={(e) => setPtFile(e.target.files[0])}
            required
          />
          <button className="bg-acid text-void rounded-control px-4 py-2 text-[13px] font-[510] tracking-[-0.011em] hover:brightness-95 transition-[filter]">
            Add part type
          </button>
        </form>
      </div>

      {loading && <p className="text-[13px] text-fog">Loading...</p>}

      <div className="space-y-4">
        {machines.map((m) => (
          <div key={m.id} className="bg-carbon rounded-card p-6" style={cardShadow}>
            <h3 className="text-[14px] font-[510] text-mist">{m.name}</h3>
            {m.location && <p className="text-[12px] text-ash mt-0.5">{m.location}</p>}
            <div className="flex flex-wrap gap-2.5 mt-3.5">
              {(m.partTypes || []).map((pt) => (
                <div
                  key={pt.id}
                  className="flex items-center gap-2 bg-white/[0.02] border border-graphite rounded-control px-3 py-2"
                >
                  <img
                    src={`${BASE_URL}${pt.referenceImageUrl}`}
                    alt={pt.name}
                    className="w-9 h-9 object-cover rounded-badge bg-obsidian"
                  />
                  <span className="text-[13px] text-mist">{pt.name}</span>
                </div>
              ))}
              {(!m.partTypes || m.partTypes.length === 0) && (
                <p className="text-[12px] text-ash">No part types yet</p>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
