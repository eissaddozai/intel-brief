import type { CollectionGap } from '../types/brief'
import { DOMAIN_LABELS } from '../types/brief'

interface Props {
  gaps: CollectionGap[]
}

const SEV_CLASS: Record<string, string> = {
  critical:    'gap-item__severity--critical',
  significant: 'gap-item__severity--significant',
  minor:       'gap-item__severity--minor',
}

export function CollectionGaps({ gaps }: Props) {
  return (
    <section className="collection-gaps">
      <div className="collection-gaps__gradient" />
      <div className="collection-gaps__header">
        <span className="collection-gaps__title">COLLECTION GAP REGISTER</span>
      </div>
      <ul className="collection-gaps__items">
        {gaps.map(gap => (
          <li key={gap.id} className="gap-item">
            <span className={`gap-item__severity ${SEV_CLASS[gap.severity] ?? ''}`}>
              {gap.severity.toUpperCase()}
            </span>
            <span className={`gap-item__domain gap-item__domain--${gap.domain}`}>
              {DOMAIN_LABELS[gap.domain]}
            </span>
            <div className="gap-item__content">
              <div className="gap-item__gap">{gap.gap}</div>
              <div className="gap-item__significance">{gap.significance}</div>
            </div>
          </li>
        ))}
      </ul>
    </section>
  )
}
