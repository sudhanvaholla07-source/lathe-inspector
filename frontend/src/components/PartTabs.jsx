// Part-type tabs: the top-level "which production line am I looking at"
// switcher, shared by the Inspections and Stats pages.
//
// Why tabs instead of the old dropdown: each part type is effectively its
// own inspection station (different part, different model, different
// numbers), so switching between them is primary navigation, not a filter
// tweak. The selection is kept in localStorage so moving between pages
// stays on the same part -- pick Commutator on Inspections, Stats opens
// scoped to Commutator too.
//
// Tabs are generated from the registered part types, so a third part shows
// up here with zero UI changes.

const STORAGE_KEY = "partTypeTab";

export function getStoredPartTab() {
  return localStorage.getItem(STORAGE_KEY) || "";
}

export default function PartTabs({ partTypes, value, onChange }) {
  function select(id) {
    localStorage.setItem(STORAGE_KEY, id);
    onChange(id);
  }

  const tabClass = (active) =>
    `px-4 py-2 text-[13px] rounded-control transition-colors ${
      active
        ? "bg-white/[0.08] text-paper"
        : "text-fog hover:text-mist hover:bg-white/[0.03]"
    }`;

  return (
    <div className="flex gap-1 mb-6 border-b border-graphite pb-3">
      <button className={tabClass(value === "")} onClick={() => select("")}>
        All parts
      </button>
      {partTypes.map((pt) => (
        <button key={pt.id} className={tabClass(value === pt.id)} onClick={() => select(pt.id)}>
          {pt.name}
        </button>
      ))}
    </div>
  );
}
