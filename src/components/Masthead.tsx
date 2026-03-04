import type { BriefCycle } from '../types/brief'

interface Props {
  meta: BriefCycle['meta']
}

const TLP_CLASS: Record<string, string> = {
  RED: 'masthead__tlp--red',
  AMBER: 'masthead__tlp--amber',
  GREEN: 'masthead__tlp--green',
  CLEAR: 'masthead__tlp--clear',
}

function formatTimestamp(iso: string): string {
  const d = new Date(iso)
  return d.toUTCString().replace('GMT', 'UTC').toUpperCase()
}

export function Masthead({ meta }: Props) {
  const cycleDate = new Date(meta.timestamp)
  const dateStr = cycleDate.toLocaleDateString('en-CA', {
    day: '2-digit',
    month: 'long',
    year: 'numeric',
    timeZone: 'UTC',
  }).toUpperCase()

  const timeStr = cycleDate.toLocaleTimeString('en-CA', {
    hour: '2-digit',
    minute: '2-digit',
    timeZone: 'UTC',
    hour12: false,
  }) + ' UTC'

  return (
    <header className="masthead" id="masthead">
      {/* Classification bar */}
      <div className="masthead__class-bar">
        <span className="masthead__class-label">{meta.classification}</span>
        <span className="masthead__class-unit">{meta.analystUnit}</span>
      </div>

      {/* Hero */}
      <div className="masthead__hero">
        <div className="masthead__title-block">
          <h1 className="masthead__title">
            <span className="masthead__title-main">INTEL</span>
            <span className="masthead__title-year"> BRIEF</span>
          </h1>
          <p className="masthead__subtitle">{meta.subtitle}</p>
        </div>
        <div className="masthead__cycle-block">
          <span className="masthead__cycle-label">CYCLE</span>
          <span className="masthead__cycle-num">{meta.cycleNum.padStart(3, '0')}</span>
          <span className="masthead__cycle-date">{dateStr}</span>
          <span className="masthead__cycle-meta">{timeStr} · {meta.region}</span>
        </div>
      </div>

      {/* Crimson rule */}
      <hr className="masthead__crimson-rule" />

      {/* Status strip */}
      <div className="masthead__strip">
        {meta.stripCells.map((cell, i) => (
          <div key={i} className="masthead__strip-cell">
            <span className="masthead__strip-top">{cell.top}</span>
            <span className="masthead__strip-bot">{cell.bot}</span>
          </div>
        ))}
      </div>

      {/* Distribution / context bar */}
      <div className="masthead__ctx">
        <p className="masthead__ctx-note">{meta.contextNote}</p>
        <span className={`masthead__tlp ${TLP_CLASS[meta.tlp] ?? ''}`}>
          TLP:{meta.tlp}
        </span>
      </div>
    </header>
  )
}
