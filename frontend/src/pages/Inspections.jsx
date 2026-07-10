import { useEffect, useState } from "react";
import { api, BASE_URL } from "../api";
import { useAuth } from "../context/AuthContext";
import PartTabs, { getStoredPartTab } from "../components/PartTabs";

const RESULT_STYLES = {
  PASS: "bg-pulse-green/10 text-pulse-green",
  FAIL: "bg-coral-red/10 text-coral-red",
  REJECTED: "bg-iris-violet/10 text-iris-violet",
};

const selectClass =
  "bg-white/[0.02] border border-graphite rounded-control px-3 py-2 text-[13px] text-mist focus:outline-none focus:border-smoke transition-colors";

export default function Inspections() {
  const { user } = useAuth();
  const [inspections, setInspections] = useState([]);
  const [partTypes, setPartTypes] = useState([]);
  const [resultFilter, setResultFilter] = useState("");
  const [partTypeFilter, setPartTypeFilter] = useState(getStoredPartTab);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  async function load() {
    setLoading(true);
    setError("");
    try {
      const filters = {};
      if (resultFilter) filters.result = resultFilter;
      if (partTypeFilter) filters.partTypeId = partTypeFilter;
      const [inspectionData, partTypeData] = await Promise.all([
        api.getInspections(filters),
        api.getPartTypes(),
      ]);
      setInspections(inspectionData);
      setPartTypes(partTypeData);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [resultFilter, partTypeFilter]);

  async function handleConfirm(id, confirmedResult) {
    try {
      await api.confirmInspection(id, confirmedResult);
      load();
    } catch (err) {
      setError(err.message);
    }
  }

  return (
    <div className="max-w-5xl mx-auto px-6 py-10">
      <div className="flex items-center justify-between mb-8">
        <h1 className="text-[24px] font-[510] text-paper tracking-[-0.012em]">Inspections</h1>
        <select className={selectClass} value={resultFilter} onChange={(e) => setResultFilter(e.target.value)}>
          <option value="">All results</option>
          <option value="PASS">Pass</option>
          <option value="FAIL">Fail</option>
          <option value="REJECTED">Rejected</option>
        </select>
      </div>

      <PartTabs partTypes={partTypes} value={partTypeFilter} onChange={setPartTypeFilter} />

      {error && <p className="text-[13px] text-coral-red mb-4">{error}</p>}
      {loading && <p className="text-[13px] text-fog">Loading...</p>}

      {!loading && inspections.length === 0 && (
        <p className="text-[13px] text-fog">
          No inspections yet. Run{" "}
          <code className="bg-white/[0.04] text-mist rounded-badge px-1.5 py-0.5 text-[12px]">
            pipeline/run_pipeline.py
          </code>{" "}
          against a photo to create one.
        </p>
      )}

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
        {inspections.map((insp) => (
          <div
            key={insp.id}
            className="bg-carbon rounded-card overflow-hidden"
            style={{ boxShadow: "rgb(35, 37, 42) 0px 0px 0px 1px inset" }}
          >
            {/* Tray inspections: show the annotated overview (color-coded
                slots + counts banner) instead of the raw capture -- that's
                the image a reviewer actually needs. */}
            {(insp.capturedImageUrl || insp.diffImageUrl) && (
              <img
                src={`${BASE_URL}${insp.tray && insp.diffImageUrl ? insp.diffImageUrl : insp.capturedImageUrl}`}
                alt="Captured"
                className="w-full h-40 object-cover bg-obsidian"
              />
            )}
            <div className="p-4">
              <div className="flex items-center justify-between mb-2.5">
                <span
                  className={`text-[12px] font-normal px-1.5 py-0.5 rounded-badge ${RESULT_STYLES[insp.result]}`}
                >
                  {insp.result}
                </span>
                <span className="text-[12px] text-ash">{new Date(insp.timestamp).toLocaleString()}</span>
              </div>
              <p className="text-[14px] text-mist">{insp.partType?.name || "Unknown part"}</p>
              <p className="text-[12px] text-ash mt-1">
                score {insp.score.toFixed(2)} &middot; {insp.method}
              </p>
              {insp.tray && (
                <p className="text-[12px] mt-1.5">
                  <span className="text-fog">Tray {insp.tray.rows}&times;{insp.tray.cols}: </span>
                  <span className="text-mist">{insp.tray.total} parts</span>
                  <span className="text-pulse-green"> &middot; {insp.tray.pass} pass</span>
                  <span className="text-coral-red"> &middot; {insp.tray.fail} fail</span>
                  <span className="text-fog"> &middot; {insp.tray.empty} empty</span>
                </p>
              )}

              {insp.confirmedResult ? (
                <p className="text-[12px] text-fog mt-2.5">
                  Confirmed: <span className="text-mist">{insp.confirmedResult}</span>
                </p>
              ) : insp.result === "REJECTED" ? null : user?.role === "MANAGER" ? (
                <div className="flex gap-2 mt-3">
                  <button
                    onClick={() => handleConfirm(insp.id, "PASS")}
                    className="text-[12px] border border-pulse-green/40 text-pulse-green rounded-control px-2 py-1 hover:bg-pulse-green/10 transition-colors"
                  >
                    Confirm PASS
                  </button>
                  <button
                    onClick={() => handleConfirm(insp.id, "FAIL")}
                    className="text-[12px] border border-coral-red/40 text-coral-red rounded-control px-2 py-1 hover:bg-coral-red/10 transition-colors"
                  >
                    Confirm FAIL
                  </button>
                </div>
              ) : null}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
