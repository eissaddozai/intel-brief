import type { KeyJudgment } from '../types/brief'
import { CONFIDENCE_PHRASES, DOMAIN_LABELS } from '../types/brief'

interface Props {
  judgment: KeyJudgment
  /** When true, renders inside a domain section (uses domain CSS context).
   *  When false, renders in the executive summary list. */
  variant?: 'domain' | 'exec'
}

const CONF_CLASS: Record<string, string> = {
  high:     'badge badge--green',
  moderate: 'badge badge--blue',
  low:      'badge badge--amber',
}

export function KeyJudgmentBox({ judgment, variant = 'domain' }: Props) {
  const { phrase } = CONFIDENCE_PHRASES[judgment.language] ?? { phrase: '' }

  if (variant === 'exec') {
    return (
      <li className="exec__kj-item">
        <span className={`exec__kj-domain exec__kj-domain--${judgment.domain}`}>
          {DOMAIN_LABELS[judgment.domain]}
        </span>
        <span className="exec__kj-text">
          <em>{phrase}</em> {judgment.text.replace(/^(We assess with high confidence( that)?|We judge it highly likely( that)?|Available evidence suggests( that)?|Reporting indicates,? though corroboration is limited,?( that)?|We judge it unlikely,? though we cannot exclude,?( that)?|We assess with high confidence this will not)\s*/i, '')}
          {judgment.citations.length > 0 && (
            <span className="body-para__source">
              ({judgment.citations.map(c => c.source).join('; ')})
            </span>
          )}
        </span>
        <span className={CONF_CLASS[judgment.confidence] ?? 'badge badge--blue'}>
          {judgment.confidence.toUpperCase()}
        </span>
      </li>
    )
  }

  return (
    <div className="kj">
      <div className="kj__label-row">
        <span className="kj__label">KEY JUDGMENT</span>
        <div className="kj__meta">
          <span className="kj__domain-ref">
            {judgment.domain.toUpperCase()} · {DOMAIN_LABELS[judgment.domain]}
          </span>
          <span className="kj__probability">{judgment.probabilityRange}</span>
          <span className={CONF_CLASS[judgment.confidence] ?? 'badge badge--blue'}>
            {judgment.confidence.toUpperCase()}
          </span>
        </div>
      </div>
      <p className="kj__text">{judgment.text}</p>
      {judgment.basis && (
        <p className="kj__basis">{judgment.basis}</p>
      )}
    </div>
  )
}
