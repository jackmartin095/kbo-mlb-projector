import React, { useMemo, useState, useCallback, useEffect } from 'react';
import './ZOStickinessChart.css';

const AXIS_MIN = 15;
const AXIS_MAX = 55;
const AXIS_TICKS = [15, 25, 35, 45, 55];

function pct(value) {
  const clamped = Math.max(AXIS_MIN, Math.min(AXIS_MAX, value));
  return ((clamped - AXIS_MIN) / (AXIS_MAX - AXIS_MIN)) * 100;
}

function yearRange(years) {
  const vals = Object.values(years).map((y) => y.zo);
  return { min: Math.min(...vals), max: Math.max(...vals) };
}

function stickinessTier(p) {
  if (p === null || p === undefined) return 'na';
  if (p >= 80) return 'good';
  if (p >= 40) return 'warn';
  return 'crit';
}

function fmt(n, digits = 1) {
  return n.toFixed(digits);
}

function fmtSigned(n, digits = 1) {
  const v = n.toFixed(digits);
  return n > 0 ? `+${v}` : v;
}

function useSummary(data) {
  return useMemo(() => {
    const withStick = data.filter((p) => p.stickiness_pct !== null);
    const sorted = [...withStick].sort((a, b) => b.stickiness_pct - a.stickiness_pct);
    const q = Math.max(1, Math.round(sorted.length * 0.25));
    const stickiest = sorted.slice(0, q);
    const volatile = sorted.slice(-q);
    const avgRange = (arr) =>
      arr.reduce((sum, p) => {
        const { min, max } = yearRange(p.years);
        return sum + (max - min);
      }, 0) / arr.length;
    const stds = data.filter((p) => p.std !== null).map((p) => p.std);
    const avgStd = stds.reduce((a, b) => a + b, 0) / stds.length;
    return {
      stickiestRange: avgRange(stickiest),
      volatileRange: avgRange(volatile),
      avgStd,
    };
  }, [data]);
}

const SORT_OPTIONS = [
  { key: 'dev', label: 'Deviation' },
  { key: 'stickiness', label: 'Stickiness' },
  { key: 'mean', label: 'Established Z-O' },
];

function sortRows(rows, sortKey) {
  return [...rows].sort((a, b) => {
    if (sortKey === 'dev') return Math.abs(b.dev_2026) - Math.abs(a.dev_2026);
    if (sortKey === 'stickiness') {
      const av = a.stickiness_pct === null ? -1 : a.stickiness_pct;
      const bv = b.stickiness_pct === null ? -1 : b.stickiness_pct;
      return bv - av;
    }
    if (sortKey === 'mean') return b.mean_zo - a.mean_zo;
    return 0;
  });
}

function Tooltip({ tooltip }) {
  if (!tooltip) return null;
  return (
    <div
      className="zo-tooltip"
      style={{ left: tooltip.x, top: tooltip.y }}
      role="tooltip"
    >
      {tooltip.lines.map((line, i) => (
        <div key={i} className={i === 0 ? 'zo-tooltip-title' : 'zo-tooltip-line'}>
          {line}
        </div>
      ))}
    </div>
  );
}

function Dot({ className, left, size, onEnter, onLeave, label }) {
  return (
    <span
      className={className}
      style={{ left: `${left}%`, width: size, height: size }}
      tabIndex={0}
      role="img"
      aria-label={label}
      onMouseEnter={onEnter}
      onMouseLeave={onLeave}
      onFocus={onEnter}
      onBlur={onLeave}
    />
  );
}

function StickinessGauge({ value }) {
  const tier = stickinessTier(value);
  if (tier === 'na') {
    return (
      <div className="zo-gauge zo-gauge-na" role="img" aria-label="Stickiness: not enough seasons">
        <span className="zo-gauge-label">N/A</span>
      </div>
    );
  }
  return (
    <div
      className="zo-gauge"
      role="img"
      aria-label={`Stickiness ${value} percent`}
    >
      <div className="zo-gauge-track">
        <div className={`zo-gauge-fill zo-gauge-${tier}`} style={{ width: `${value}%` }} />
      </div>
      <span className="zo-gauge-value">{value}</span>
    </div>
  );
}

function Row({ player, onTooltip, onClearTooltip }) {
  const { min, max } = yearRange(player.years);
  const yearEntries = Object.entries(player.years).sort((a, b) => Number(a[0]) - Number(b[0]));
  const zoAboveMean = player.zo_2026 >= player.mean_zo;

  const showTooltip = useCallback(
    (e, lines) => {
      const rect = e.currentTarget.getBoundingClientRect();
      onTooltip({
        x: rect.left + rect.width / 2,
        y: rect.top,
        lines,
      });
    },
    [onTooltip]
  );

  return (
    <div className="zo-row">
      <div className="zo-row-label">
        <span className="zo-row-name">{player.name}</span>
        <span className="zo-row-team">{player.team}</span>
      </div>

      <div className="zo-row-track">
        {AXIS_TICKS.map((t) => (
          <span key={t} className="zo-gridline" style={{ left: `${pct(t)}%` }} />
        ))}

        <span
          className="zo-range-line"
          style={{ left: `${pct(min)}%`, width: `${pct(max) - pct(min)}%` }}
        />

        {yearEntries.map(([year, y]) => (
          <Dot
            key={year}
            className="zo-dot zo-dot-year"
            left={pct(y.zo)}
            size={6}
            label={`${year}: Z-O ${y.zo}, ${y.pa} PA`}
            onEnter={(e) =>
              showTooltip(e, [`${year}`, `Z-O: ${fmt(y.zo)}`, `${y.pa} PA`])
            }
            onLeave={onClearTooltip}
          />
        ))}

        <Dot
          className="zo-dot zo-dot-mean"
          left={pct(player.mean_zo)}
          size={11}
          label={`Established level: ${fmt(player.mean_zo)} over ${player.n_years} seasons`}
          onEnter={(e) =>
            showTooltip(e, [
              'Established level',
              `${fmt(player.mean_zo)} (${player.n_years} season${player.n_years > 1 ? 's' : ''})`,
            ])
          }
          onLeave={onClearTooltip}
        />

        <Dot
          className={`zo-dot zo-dot-2026 ${zoAboveMean ? 'zo-dot-above' : 'zo-dot-below'}`}
          left={pct(player.zo_2026)}
          size={9}
          label={`2026: ${player.zo_2026}, deviation ${fmtSigned(player.dev_2026)}`}
          onEnter={(e) =>
            showTooltip(e, [
              '2026',
              `Z-O: ${fmt(player.zo_2026)}`,
              `Deviation: ${fmtSigned(player.dev_2026)}`,
            ])
          }
          onLeave={onClearTooltip}
        />
      </div>

      <div className="zo-row-dev">
        <span className={zoAboveMean ? 'zo-dev-above' : 'zo-dev-below'}>
          {fmtSigned(player.dev_2026)}
        </span>
      </div>

      <StickinessGauge value={player.stickiness_pct} />
    </div>
  );
}

function TableView({ rows }) {
  return (
    <div className="zo-table-wrap">
      <table className="zo-table">
        <thead>
          <tr>
            <th>Player</th>
            <th>Team</th>
            <th>Seasons</th>
            <th>Established Z-O</th>
            <th>2026 Z-O</th>
            <th>Deviation</th>
            <th>Stickiness</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((p) => (
            <tr key={p.name}>
              <td>{p.name}</td>
              <td>{p.team}</td>
              <td>{p.n_years}</td>
              <td>{fmt(p.mean_zo)}</td>
              <td>{fmt(p.zo_2026)}</td>
              <td className={p.dev_2026 >= 0 ? 'zo-dev-above' : 'zo-dev-below'}>
                {fmtSigned(p.dev_2026)}
              </td>
              <td>{p.stickiness_pct === null ? 'N/A' : p.stickiness_pct}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export default function ZOStickinessChart({ data }) {
  const [query, setQuery] = useState('');
  const [sortKey, setSortKey] = useState('dev');
  const [tableView, setTableView] = useState(false);
  const [tooltip, setTooltip] = useState(null);

  const summary = useSummary(data);

  const rows = useMemo(() => {
    const q = query.trim().toLowerCase();
    const matched = q
      ? data.filter(
          (p) => p.name.toLowerCase().includes(q) || p.team.toLowerCase().includes(q)
        )
      : data;
    const sorted = sortRows(matched, sortKey);
    return q ? sorted : sorted.slice(0, 20);
  }, [data, query, sortKey]);

  const clearTooltip = useCallback(() => setTooltip(null), []);

  // A hovered dot can be unmounted by filtering/sorting/view changes without
  // firing mouseleave/blur, which would otherwise leave a stale tooltip on screen.
  useEffect(() => {
    setTooltip(null);
  }, [query, sortKey, tableView]);

  return (
    <div className="zo-chart">
      <div className="zo-summary">
        <div className="zo-callout">
          <span className="zo-callout-label">Stickiest quartile</span>
          <span className="zo-callout-value">
            avg year-to-year range of {fmt(summary.stickiestRange)} pts
          </span>
        </div>
        <div className="zo-callout">
          <span className="zo-callout-label">Most volatile quartile</span>
          <span className="zo-callout-value">
            avg range of {fmt(summary.volatileRange)} pts
          </span>
        </div>
        <div className="zo-callout">
          <span className="zo-callout-label">Pool average std</span>
          <span className="zo-callout-value">{fmt(summary.avgStd, 2)} pts</span>
        </div>
      </div>

      <div className="zo-controls">
        <input
          type="text"
          className="zo-search"
          placeholder="Search player or team..."
          value={query}
          onChange={(e) => setQuery(e.target.value)}
        />
        <div className="zo-sort">
          {SORT_OPTIONS.map((opt) => (
            <button
              key={opt.key}
              className={`zo-sort-btn ${sortKey === opt.key ? 'active' : ''}`}
              onClick={() => setSortKey(opt.key)}
              type="button"
            >
              {opt.label}
            </button>
          ))}
        </div>
        <button
          type="button"
          className="zo-table-toggle"
          onClick={() => setTableView((v) => !v)}
        >
          {tableView ? 'Chart view' : 'Table view'}
        </button>
      </div>

      {!tableView && (
        <>
          <div className="zo-legend">
            <span className="zo-legend-item">
              <span className="zo-dot zo-dot-year zo-legend-dot" /> Prior season
            </span>
            <span className="zo-legend-item">
              <span className="zo-dot zo-dot-mean zo-legend-dot" /> Established level
            </span>
            <span className="zo-legend-item">
              <span className="zo-dot zo-dot-2026 zo-dot-above zo-legend-dot" /> 2026 above
              established
            </span>
            <span className="zo-legend-item">
              <span className="zo-dot zo-dot-2026 zo-dot-below zo-legend-dot" /> 2026 below
              established
            </span>
          </div>

          <div className="zo-axis-header">
            <div className="zo-row-label" />
            <div className="zo-row-track">
              {AXIS_TICKS.map((t) => (
                <span key={t} className="zo-axis-tick" style={{ left: `${pct(t)}%` }}>
                  {t}
                </span>
              ))}
            </div>
            <div className="zo-row-dev" />
            <div className="zo-gauge-header">Stickiness</div>
          </div>

          <div className="zo-rows">
            {rows.length === 0 && <div className="zo-empty">No players match.</div>}
            {rows.map((p) => (
              <Row key={p.name} player={p} onTooltip={setTooltip} onClearTooltip={clearTooltip} />
            ))}
          </div>
        </>
      )}

      {tableView && <TableView rows={rows} />}

      <Tooltip tooltip={tooltip} />

      <div className="zo-footer">
        Data: FanGraphs plate-discipline splits (Statcast-ABS), 2021-2026 | @jack_mariners
      </div>
    </div>
  );
}
