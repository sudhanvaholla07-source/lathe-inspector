// Batches page: the production-run view the industry asked for.
//
// Top: open a new batch by label. List: every batch with its live totals
// (trays scanned, parts counted, per-variant breakdown), computed by the
// backend from member scans. Expanding a batch shows its individual tray
// scans with annotated overviews. Closing freezes the batch (backend
// rejects further scans into it).

import { useEffect, useState } from "react";
import { api, BASE_URL } from "../api";

const cardShadow = { boxShadow: "rgb(35, 37, 42) 0px 0px 0px 1px inset" };
const inputClass =
  "bg-white/[0.02] border border-graphite rounded-control px-3 py-2 text-[13px] text-mist focus:outline-none focus:border-smoke transition-colors";

export default function Batches() {
  const [batches, setBatches] = useState([]);
  const [newLabel, setNewLabel] = useState("");
  const [expanded, setExpanded] = useState(null);   // batch id
  const [detail, setDetail] = useState(null);       // full batch w/ scans
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  async function load() {
    setLoading(true);
    setError("");
    try {
      setBatches(await api.getBatches());
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
  }, []);

  async function handleCreate(e) {
    e.preventDefault();
    if (!newLabel.trim()) return;
    try {
      await api.createBatch(newLabel.trim());
      setNewLabel("");
      load();
    } catch (err) {
      setError(err.message);
    }
  }

  async function handleClose(id) {
    try {
      await api.closeBatch(id);
      load();
    } catch (err) {
      setError(err.message);
    }
  }

  async function toggleExpand(id) {
    if (expanded === id) {
      setExpanded(null);
      setDetail(null);
      return;
    }
    setExpanded(id);
    setDetail(null);
    try {
      setDetail(await api.getBatch(id));
    } catch (err) {
      setError(err.message);
    }
  }

  return (
    <div className="max-w-5xl mx-auto px-6 py-10">
      <div className="flex items-center justify-between mb-8">
        <h1 className="text-[24px] font-[510] text-paper tracking-[-0.012em]">Batches</h1>
        <form onSubmit={handleCreate} className="flex gap-2">
          <input
            className={inputClass}
            placeholder='New batch label, e.g. "Order 4521"'
            value={newLabel}
            onChange={(e) => setNewLabel(e.target.value)}
          />
          <button
            type="submit"
            className="text-[13px] border border-pulse-green/40 text-pulse-green rounded-control px-3 py-2 hover:bg-pulse-green/10 transition-colors"
          >
            Open batch
          </button>
        </form>
      </div>

      {error && <p className="text-[13px] text-coral-red mb-4">{error}</p>}
      {loading && <p className="text-[13px] text-fog">Loading...</p>}
      {!loading && batches.length === 0 && (
        <p className="text-[13px] text-fog">
          No batches yet. Open one above, then file scans into it with{" "}
          <code className="bg-white/[0.04] text-mist rounded-badge px-1.5 py-0.5 text-[12px]">
            pipeline/run_batch_scan.py --batch "label"
          </code>
        </p>
      )}

      <div className="space-y-3">
        {batches.map((b) => (
          <div key={b.id} className="bg-carbon rounded-card p-5" style={cardShadow}>
            <div className="flex items-center gap-3">
              <button onClick={() => toggleExpand(b.id)} className="text-left flex-1">
                <span className="text-[15px] text-paper font-[510]">{b.label}</span>
                <span
                  className={`ml-3 text-[11px] px-1.5 py-0.5 rounded-badge ${
                    b.status === "OPEN"
                      ? "bg-pulse-green/10 text-pulse-green"
                      : "bg-white/[0.06] text-fog"
                  }`}
                >
                  {b.status}
                </span>
              </button>
              <span className="text-[13px] text-mist">
                {b.trays} tray{b.trays === 1 ? "" : "s"} &middot; {b.parts} parts
              </span>
              {b.status === "OPEN" && (
                <button
                  onClick={() => handleClose(b.id)}
                  className="text-[12px] border border-graphite text-fog rounded-control px-2 py-1 hover:text-mist hover:bg-white/[0.04] transition-colors"
                >
                  Close
                </button>
              )}
            </div>

            {Object.keys(b.variants || {}).length > 0 && (
              <p className="text-[12px] text-ash mt-2">
                {Object.entries(b.variants)
                  .map(([v, n]) => `${v}: ${n}`)
                  .join("  ·  ")}
              </p>
            )}

            {expanded === b.id && (
              <div className="mt-4 border-t border-graphite pt-4">
                {!detail && <p className="text-[13px] text-fog">Loading scans...</p>}
                {detail && detail.inspections.length === 0 && (
                  <p className="text-[13px] text-fog">No scans in this batch yet.</p>
                )}
                {detail && (
                  <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
                    {detail.inspections.map((insp) => (
                      <div key={insp.id} className="bg-void rounded-card overflow-hidden" style={cardShadow}>
                        {(insp.diffImageUrl || insp.capturedImageUrl) && (
                          <img
                            src={`${BASE_URL}${insp.diffImageUrl || insp.capturedImageUrl}`}
                            alt="Scan"
                            className="w-full h-32 object-cover bg-obsidian"
                          />
                        )}
                        <div className="p-3">
                          <p className="text-[12px] text-mist">
                            {insp.tray?.total ?? "?"} parts
                            {insp.tray?.variants &&
                              " · " +
                                Object.entries(insp.tray.variants)
                                  .map(([v, n]) => `${n} ${v}`)
                                  .join(", ")}
                          </p>
                          <p className="text-[11px] text-ash mt-1">
                            {new Date(insp.timestamp).toLocaleString()}
                          </p>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
