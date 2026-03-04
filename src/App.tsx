import type { BriefCycle } from './types/brief'
import cycleData from './data/cycle001.json'
import { useScrollGlow } from './hooks/useScrollGlow'
import { Masthead } from './components/Masthead'
import { StrategicHeader } from './components/StrategicHeader'
import { FlashPoints } from './components/FlashPoints'
import { ExecutiveAssessment } from './components/ExecutiveAssessment'
import { DomainSection } from './components/DomainSection'
import { WarningIndicators } from './components/WarningIndicators'
import { CollectionGaps } from './components/CollectionGaps'
import { Caveats } from './components/Caveats'
import { BriefFooter } from './components/BriefFooter'

// Cast JSON import to typed schema
const cycle = cycleData as unknown as BriefCycle

export function App() {
  useScrollGlow()

  const cycleRef = `CYCLE ${cycle.meta.cycleNum} · ${new Date(cycle.meta.timestamp)
    .toLocaleDateString('en-CA', { day: 'numeric', month: 'long', year: 'numeric', timeZone: 'UTC' })
    .toUpperCase()}`

  return (
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

      <BriefFooter footer={cycle.footer} meta={cycle.meta} />
    </div>
  )
}
