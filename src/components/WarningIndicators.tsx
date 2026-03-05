import type { WarningIndicator, BriefCycle } from '../types/brief'
import { DOMAIN_LABELS } from '../types/brief'

interface Props {
  indicators: WarningIndicator[]
  cycleRef: string
}

const STATUS_CLASS: Record<string, string> = {
  triggered: 'wi-status--triggered',
  elevated:  'wi-status--elevated',
  watching:  'wi-status--watching',
  cleared:   'wi-status--cleared',
}

const CHANGE_CLASS: Record<string, string> = {
  new:       'wi-change--new',
  elevated:  'wi-change--elevated',
  unchanged: 'wi-change--unchanged',
  cleared:   'wi-change--cleared',
}

const CHANGE_LABEL: Record<string, string> = {
  new:       '⚡ NEW',
  elevated:  '↑ ELEVATED',
  unchanged: '→ UNCHANGED',
  cleared:   '✓ CLEARED',
}

export function WarningIndicators({ indicators, cycleRef }: Props) {
  return (
    <section className="warning-indicators">
      <div className="warning-indicators__gradient" />
      <div className="warning-indicators__header">
        <span className="warning-indicators__title">WARNING INDICATORS</span>
        <span className="warning-indicators__cycle">{cycleRef}</span>
      </div>
      <div className="warning-indicators__table">
        <table className="wi-table">
          <thead>
            <tr>
              <th>INDICATOR</th>
              <th>DOMAIN</th>
              <th>STATUS</th>
              <th>CHANGE</th>
              <th>DETAIL</th>
            </tr>
          </thead>
          <tbody>
            {indicators.map(wi => (
              <tr key={wi.id}>
                <td className="wi-table__indicator">{wi.indicator}</td>
                <td className="wi-table__domain">{DOMAIN_LABELS[wi.domain]}</td>
                <td>
                  <span className={`wi-status ${STATUS_CLASS[wi.status] ?? ''}`}>
                    {wi.status.toUpperCase()}
                  </span>
                </td>
                <td>
                  <span className={`wi-change ${CHANGE_CLASS[wi.change] ?? ''}`}>
                    {CHANGE_LABEL[wi.change] ?? wi.change}
                  </span>
                </td>
                <td>{wi.detail}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  )
}
