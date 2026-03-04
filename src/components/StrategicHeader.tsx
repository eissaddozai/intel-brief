import type { BriefCycle, ThreatLevel, ThreatTrajectory } from '../types/brief'
import { TRAJECTORY_LABELS } from '../types/brief'

interface Props {
  strategicHeader: BriefCycle['strategicHeader']
  threatLevel: ThreatLevel
  threatTrajectory: ThreatTrajectory
}

const THREAT_CLASS: Record<ThreatLevel, string> = {
  CRITICAL: 'threat-level--critical',
  SEVERE:   'threat-level--severe',
  ELEVATED: 'threat-level--elevated',
  GUARDED:  'threat-level--guarded',
  LOW:      'threat-level--low',
}

const TRAJ_CLASS: Record<ThreatTrajectory, string> = {
  'escalating':    'trajectory-badge--escalating',
  'stable':        'trajectory-badge--stable',
  'de-escalating': 'trajectory-badge--de-escalating',
}

export function StrategicHeader({ strategicHeader, threatLevel, threatTrajectory }: Props) {
  return (
    <div className="strategic-header">
      <div className="strategic-header__content">
        <div className="strategic-header__label">STRATEGIC ASSESSMENT</div>
        <p className="strategic-header__judgment">{strategicHeader.headlineJudgment}</p>
      </div>
      <div className="strategic-header__meta">
        <span className={`threat-level ${THREAT_CLASS[threatLevel]}`}>
          {threatLevel}
        </span>
        <span className={`trajectory-badge ${TRAJ_CLASS[threatTrajectory]}`}>
          {TRAJECTORY_LABELS[threatTrajectory]}
        </span>
      </div>
    </div>
  )
}
