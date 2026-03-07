import type { BriefCycle } from '../types/brief'
import { DissenterNote } from './DissenterNote'

interface Props {
  caveats: BriefCycle['caveats']
}

export function Caveats({ caveats }: Props) {
  return (
    <section className="caveats">
      <div className="caveats__gradient" />
      <div className="caveats__header">
        <span className="caveats__title">CAVEATS &amp; ANALYTICAL CONFIDENCE</span>
        <span className="caveats__cycle">{caveats.cycleRef}</span>
      </div>
      <ul className="caveats__items">
        {caveats.items.map((item, i) => (
          <li key={i} className="caveats__item">
            <span className="caveats__item-label">{item.label}</span>
            {item.text}
          </li>
        ))}
      </ul>
      <div className="caveats__confidence">
        <div className="caveats__confidence-label">OVERALL CONFIDENCE ASSESSMENT</div>
        <p className="caveats__confidence-text">{caveats.confidenceAssessment}</p>
      </div>
      {caveats.dissenterNotes.length > 0 && (
        <div className="caveats__dissenters">
          <div className="caveats__dissenter-wrap">
            {caveats.dissenterNotes.map((note, i) => (
              <DissenterNote key={i} note={note} />
            ))}
          </div>
        </div>
      )}
    </section>
  )
}
