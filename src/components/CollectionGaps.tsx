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

const CATEGORY_LABEL: Record<string, string> = {
  'source-outage':       'SOURCE OUTAGE',
  'terrain-denial':      'TERRAIN DENIAL',
  'signal-obscuration':  'SIGNAL OBSCURATION',
  'attribution-gap':     'ATTRIBUTION GAP',
  'diplomatic-opacity':  'DIPLOMATIC OPACITY',
  'kurdish-turkish-gap': 'KURDISH/TURKISH GAP',
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
            <div className="gap-item__meta">
              <span className={`gap-item__severity ${SEV_CLASS[gap.severity] ?? ''}`}>
                {gap.severity.toUpperCase()}
              </span>
              <span className={`gap-item__domain gap-item__domain--${gap.domain}`}>
                {DOMAIN_LABELS[gap.domain]}
              </span>
              {gap.category && (
                <span className="gap-item__category">
                  {CATEGORY_LABEL[gap.category] ?? gap.category.toUpperCase()}
                </span>
              )}
            </div>
            <div className="gap-item__content">
              <div className="gap-item__gap">{gap.gap}</div>
              <div className="gap-item__significance">{gap.significance}</div>
              {gap.keyJudgmentAtRisk && (
                <div className="gap-item__kj-risk">
                  KJ AT RISK: <span className="gap-item__kj-risk-id">{gap.keyJudgmentAtRisk}</span>
                </div>
              )}
              {gap.gapClosingSource && (
                <div className="gap-item__closing">
                  GAP-CLOSING SOURCE: {gap.gapClosingSource}
                </div>
              )}
            </div>
          </li>
        ))}
      </ul>
    </section>
  )
}
