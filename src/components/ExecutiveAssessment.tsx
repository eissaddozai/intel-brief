import type { BriefCycle } from '../types/brief'
import { KpiStrip } from './KpiStrip'
import { KeyJudgmentBox } from './KeyJudgmentBox'

interface Props {
  executive: BriefCycle['executive']
  cycleRef: string
}

export function ExecutiveAssessment({ executive, cycleRef }: Props) {
  return (
    <section className="exec">
      <div className="exec__gradient" />
      <div className="exec__header">
        <span className="exec__header-title">EXECUTIVE ASSESSMENT</span>
        <span className="exec__header-meta">{cycleRef}</span>
      </div>

      {/* BLUF */}
      <div className="exec__bluf">
        <div className="exec__bluf-label">BOTTOM LINE UP FRONT</div>
        <p className="exec__bluf-text">{executive.bluf}</p>
      </div>

      {/* KPI strip */}
      <KpiStrip kpis={executive.kpis} />

      {/* Key Judgments */}
      <ol className="exec__kj-list">
        {executive.keyJudgments.map(judgment => (
          <KeyJudgmentBox key={judgment.id} judgment={judgment} variant="exec" />
        ))}
      </ol>
    </section>
  )
}
