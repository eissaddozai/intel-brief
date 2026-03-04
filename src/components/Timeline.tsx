import type { TimelineEvent } from '../types/brief'

interface Props {
  events: TimelineEvent[]
}

export function Timeline({ events }: Props) {
  return (
    <ul className="timeline">
      {events.map((ev, i) => (
        <li key={i} className={`timeline__event timeline__event--${ev.domain}`}>
          <div className="timeline__time">{ev.timestamp}</div>
          <div>
            <span className="timeline__actor">{ev.actor}</span>
            <span className="timeline__action">{ev.action}</span>
            {ev.citations.length > 0 && (
              <span className="body-para__source">
                ({ev.citations.map(c => c.source).join('; ')})
              </span>
            )}
          </div>
        </li>
      ))}
    </ul>
  )
}
