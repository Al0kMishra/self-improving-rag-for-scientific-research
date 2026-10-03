export default function RunSelector({ runs, value, onChange, includeLive = true }) {
  const known = runs.some((run) => run.experiment_run === value);
  const options = value && !known ? [{ experiment_run: value }, ...runs] : runs;
  return (
    <div className="filters">
      <label className="body-sm muted" htmlFor="run-select">
        Scope
      </label>
      <select id="run-select" className="select" value={value ?? ""} onChange={(e) => onChange(e.target.value || null)}>
        {includeLive && <option value="">Live usage</option>}
        {options.map((run) => (
          <option key={run.experiment_run} value={run.experiment_run}>
            {run.experiment_run}
          </option>
        ))}
      </select>
    </div>
  );
}
