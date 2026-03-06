import type { DomainSection as DomainSectionType } from '../types/brief'
import { BADGE_CLASS } from '../types/brief'
import { KeyJudgmentBox } from './KeyJudgmentBox'
import { BodyContent } from './BodyContent'
import { DataTable } from './DataTable'
import { Timeline } from './Timeline'
import { ActorMatrix } from './ActorMatrix'
import { AnalystNote } from './AnalystNote'
import { DissenterNote } from './DissenterNote'

interface Props {
  section: DomainSectionType
}

export function DomainSection({ section }: Props) {
  return (
    <section className={`domain domain--${section.id}`}>

      {/* 1. Gradient */}
      <div className="domain__gradient" />

      {/* 2. Header bar */}
      <div className="domain__header">
        <div className="domain__num">{section.num}</div>
        <div className="domain__title-cell">
          <h2 className="domain__title">{section.title}</h2>
          <div className="domain__aq-badge-inline">
            <span className={BADGE_CLASS[section.confidence] ?? 'badge badge--blue'}>
              {section.confidence.toUpperCase()} CONFIDENCE
            </span>
          </div>
        </div>
      </div>

      {/* 3. Assessment Question bar */}
      <div className="domain__aq">
        <p className="domain__aq-text">{section.assessmentQuestion}</p>
        <span className="domain__aq-conf">
          {section.id.toUpperCase()} · {section.num}
        </span>
      </div>

      {/* 4. Key Judgment box */}
      <KeyJudgmentBox judgment={section.keyJudgment} variant="domain" />

      {/* 5. Body wrap */}
      <div className="body-wrap">
        <BodyContent paragraphs={section.bodyParagraphs} />

        {/* Optional: Data Tables */}
        {section.tables?.map((table, i) => (
          <DataTable key={i} table={table} />
        ))}

        {/* Optional: Timeline */}
        {section.timeline && section.timeline.length > 0 && (
          <Timeline events={section.timeline} />
        )}

        {/* Optional: Actor Matrix */}
        {section.actorMatrix && section.actorMatrix.length > 0 && (
          <ActorMatrix rows={section.actorMatrix} />
        )}
      </div>

      {/* 6. Optional: Analyst Note */}
      {section.analystNote && (
        <AnalystNote note={section.analystNote} />
      )}

      {/* 7. Optional: Dissenter Note */}
      {section.dissenterNote && (
        <DissenterNote note={section.dissenterNote} />
      )}

      {/* 8. Section end — double rule */}
      <div className="section-end">
        <div className="section-end--thick" />
        <div className="section-end--thin" />
      </div>

    </section>
  )
}
