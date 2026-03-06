import { useState, useEffect } from 'react'
import type { BriefCycle } from './types/brief'
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

export function App() {
  const [cycle, setCycle] = useState<BriefCycle | null>(null)
  const [error, setError] = useState<string | null>(null)

  useScrollGlow()

  useEffect(() => {
    fetch(`${import.meta.env.BASE_URL}data/latest.json`)
      .then(r => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`)
        return r.json()
      })
      .then(data => {
        if (!data || typeof data !== 'object' || !data.meta || !data.domains) {
          throw new Error('Cycle JSON missing required fields (meta, domains)')
        }
        setCycle(data as BriefCycle)
      })
      .catch(err => setError(String(err)))
  }, [])

  if (error) {
    return (
      <div className="brief" style={{ padding: '40px 20px', color: 'var(--conf-red)', fontFamily: 'var(--font-data)' }}>
        LOAD ERROR: {error}
        <div style={{ marginTop: '12px', color: 'var(--text-dim)', fontSize: 'var(--size-aq)' }}>
          Ensure src/data/latest.json exists. Run: python pipeline/main.py run --demo --auto-approve
        </div>
      </div>
    )
  }

  if (!cycle) {
    return (
      <div className="brief" style={{ padding: '40px 20px', color: 'var(--text-dim)', fontFamily: 'var(--font-data)' }}>
        LOADING CYCLE DATA…
      </div>
    )
  }

  const _ts = new Date(cycle.meta.timestamp)
  const _dateStr = isNaN(_ts.getTime())
    ? cycle.meta.timestamp
    : _ts.toLocaleDateString('en-CA', { day: 'numeric', month: 'long', year: 'numeric', timeZone: 'UTC' }).toUpperCase()
  const cycleRef = `CYCLE ${cycle.meta.cycleNum} · ${_dateStr}`

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
