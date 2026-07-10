import { useEffect, useState } from "react";
import { api } from "../api";
import PartTabs, { getStoredPartTab } from "../components/PartTabs";

const cardShadow = { boxShadow: "rgb(35, 37, 42) 0px 0px 0px 1px inset" };

function MetricCard({ label, value, tint }) {
  return (
    <div className="bg-carbon rounded-card p-6" style={cardShadow}>
      <p className="text-[12px] text-fog mb-2">{label}</p>
      <p className={`text-[32px] font-[510] tracking-[-0.011em] ${tint || "text-paper"}`}>{value}</p>
    </div>
  );
}

const RESULT_STYLES = {
  PASS: "bg-pulse-green/10 text-pulse-green",
  FAIL: "bg-coral-red/10 text-coral-red",
  REJECTED: "bg-iris-violet/10 text-iris-violet",
};

export default function Stats() {
  const [stats, setStats] = useState(null);
  const [history, setHistory] = useState([]);
  const [partTypes, setPartTypes] = useState([]);
  const [partTypeFilter, setPartTypeFilter] = useState(getStoredPartTab);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  // "Reset counters" doesn't delete anything -- it stores a timestamp and the
  // stats endpoint only counts inspections after it. Kept in localStorage so
  // the counting window survives page reloads. History below stays all-time.
  const [since, setSince] = useState(() => localStorage.getItem("statsSince") || "");

  async function load() {
    setLoading(true);
    setError("");
    try {
      const filters = {};
      if (partTypeFilter) filters.partTypeId = partTypeFilter;
      const statsFilters = { ...filters };
      if (since) statsFilters.since = since;
      const [statsData, partTypeData, inspectionData] = await Promise.all([
        api.getStats(statsFilters),
        api.getPartTypes(),
        api.getInspections(filters),
      ]);
      setStats(statsData);
      setPartTypes(partTypeData);
      setHistory(inspectionData.slice(0, 20));
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [partTypeFilter, since]);

  function resetCounters() {
    const now = new Date().toISOString();
    localStorage.setItem("statsSince", now);
    setSince(now); // triggers reload via the effect above
  }

  function showAllTime() {
    localStorage.removeItem("statsSince");
    setSince("");
  }

  return (
    <div className="max-w-4xl mx-auto px-6 py-10">
      <div className="flex items-center justify-between mb-8">
        <h1 className="text-[24px] font-[510] text-paper tracking-[-0.012em]">Production stats</h1>
        <div className="flex gap-2">
          <button
            onClick={load}
            disabled={loading}
            className="text-[13px] border border-graphite text-mist rounded-control px-3 py-2 hover:bg-white/[0.04] transition-colors disabled:opacity-50"
          >
            {loading ? "Refreshing..." : "Refresh"}
          </button>
          <button
            onClick={resetCounters}
            disabled={loading}
            className="text-[13px] border border-coral-red/40 text-coral-red rounded-control px-3 py-2 hover:bg-coral-red/10 transition-colors disabled:opacity-50"
          >
            Reset counters
          </button>
        </div>
      </div>

      <PartTabs partTypes={partTypes} value={partTypeFilter} onChange={setPartTypeFilter} />

      {since && (
        <p className="text-[12px] text-ash mb-4">
          Counting since {new Date(since).toLocaleString()}.{" "}
          <button onClick={showAllTime} className="text-mist underline hover:text-paper transition-colors">
            Show all-time
          </button>
        </p>
      )}

      {error && <p className="text-[13px] text-coral-red mb-4">{error}</p>}
      {loading && <p className="text-[13px] text-fog">Loading...</p>}

      {!loading && stats && (
        <>
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 mb-4">
            <MetricCard label="Produced" value={stats.produced} />
            <MetricCard label="Pass" value={stats.pass} tint="text-pulse-green" />
            <MetricCard label="Fail" value={stats.fail} tint="text-coral-red" />
            <MetricCard label="Rejected" value={stats.rejected} tint="text-iris-violet" />
          </div>

          <div className="bg-carbon rounded-card p-6" style={cardShadow}>
            <p className="text-[12px] text-fog mb-2">Pass rate</p>
            <p className="text-[24px] font-[510] text-paper tracking-[-0.012em]">
              {stats.passRate === null ? "—" : `${Math.round(stats.passRate * 100)}%`}
            </p>
            <p className="text-[12px] text-ash mt-2">
              Of {stats.produced} produced units (rejected captures aren't counted as production).
            </p>
          </div>

          {/* History: the same inspections the Inspections page shows, but
              condensed into rows -- one line per run, tray counts inline.
              For photos and confirm buttons, click through to Inspections. */}
          <div className="bg-carbon rounded-card p-6 mt-4" style={cardShadow}>
            <p className="text-[12px] text-fog mb-4">Recent runs</p>
            {history.length === 0 && <p className="text-[13px] text-fog">No inspections yet.</p>}
            <div className="divide-y divide-graphite">
              {history.map((insp) => (
                <div key={insp.id} className="flex items-center gap-3 py-2.5">
                  <span
                    className={`text-[12px] px-1.5 py-0.5 rounded-badge shrink-0 ${RESULT_STYLES[insp.result]}`}
                  >
                    {insp.result}
                  </span>
                  <span className="text-[13px] text-mist shrink-0">
                    {insp.tray ? `Tray ${insp.tray.rows}×${insp.tray.cols}` : "Single part"}
                  </span>
                  {insp.tray && (
                    <span className="text-[12px] text-ash truncate">
                      {insp.tray.total} parts &middot; {insp.tray.pass} pass &middot; {insp.tray.fail} fail
                      &middot; {insp.tray.empty} empty
                    </span>
                  )}
                  <span className="text-[12px] text-ash ml-auto shrink-0">
                    {new Date(insp.timestamp).toLocaleString()}
                  </span>
                </div>
              ))}
            </div>
          </div>
        </>
      )}
    </div>
  );
}
