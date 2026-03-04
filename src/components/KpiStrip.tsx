import type { KpiCell } from '../types/brief'

interface Props {
  kpis: KpiCell[]
}

export function KpiStrip({ kpis }: Props) {
  return (
    <div className="kpi-strip">
      {kpis.map((cell, i) => (
        <div key={i} className={`kpi-strip__cell kpi-strip__cell--${cell.domain}`}>
          <span className="kpi-strip__number">{cell.number}</span>
          <span className="kpi-strip__label">{cell.label}</span>
        </div>
      ))}
    </div>
  )
}
