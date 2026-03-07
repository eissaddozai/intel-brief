import { useParams, Link } from 'react-router-dom'
import { useScrollGlow } from '../hooks/useScrollGlow'
import { Masthead } from '../components/Masthead'
import { StrategicHeader } from '../components/StrategicHeader'
import { FlashPoints } from '../components/FlashPoints'
import { ExecutiveAssessment } from '../components/ExecutiveAssessment'
import { DomainSection } from '../components/DomainSection'
import { WarningIndicators } from '../components/WarningIndicators'
import { CollectionGaps } from '../components/CollectionGaps'
import { Caveats } from '../components/Caveats'
import { briefsById } from '../data'

export function BriefDetail() {
  const { cycleId } = useParams<{ cycleId: string }>()
  useScrollGlow()

  const cycle = cycleId ? briefsById[cycleId] : null

  if (!cycle) {
    return (
      <div className="brief-not-found">
        <h1>Brief Not Found</h1>
        <p>Cycle "{cycleId}" does not exist.</p>
        <Link to="/">← Back to List</Link>
      </div>
    )
  }

  const cycleRef = `CYCLE ${cycle.meta.cycleNum} · ${new Date(cycle.meta.timestamp)
    .toLocaleDateString('en-CA', { day: 'numeric', month: 'long', year: 'numeric', timeZone: 'UTC' })
    .toUpperCase()}`

  return (
    <div className="brief-detail-wrapper">
      <Link to="/" className="brief__back-link">← Back</Link>
      <div className="brief">
        <Masthead meta={cycle.meta} />

      <StrategicHeader
        strategicHeader={cycle.strategicHeader}
        threatLevel={cycle.meta.threatLevel}
        threatTrajectory={cycle.meta.threatTrajectory}
      />

      <FlashPoints flashPoints={cycle.flashPoints} />

      <ExecutiveAssessment
        executive={cycle.executive}
        cycleRef={cycleRef}
      />

      <div className="brief__inner">
        {cycle.domains.map(section => (
          <DomainSection key={section.id} section={section} />
        ))}
      </div>

      <WarningIndicators
        indicators={cycle.warningIndicators}
        cycleRef={cycleRef}
      />

      <CollectionGaps gaps={cycle.collectionGaps} />

      <Caveats caveats={cycle.caveats} />
      </div>
    </div>
  )
}
