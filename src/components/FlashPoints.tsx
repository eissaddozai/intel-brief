import type { FlashPoint } from '../types/brief'

interface Props {
  flashPoints: FlashPoint[]
}

const CONF_CLASS: Record<string, string> = {
  high:     'badge badge--red',
  moderate: 'badge badge--amber',
  low:      'badge badge--blue',
}

function formatFlashTime(iso: string): string {
  const d = new Date(iso)
  return d.toLocaleTimeString('en-CA', {
    hour: '2-digit',
    minute: '2-digit',
    timeZone: 'UTC',
    hour12: false,
  }) + 'Z'
}

export function FlashPoints({ flashPoints }: Props) {
  if (flashPoints.length === 0) return null

  const now = new Date().toLocaleTimeString('en-CA', {
    hour: '2-digit', minute: '2-digit', timeZone: 'UTC', hour12: false,
  }) + ' UTC'

  return (
    <section className="flash-points">
      <div className="flash-points__header">
        <span className="flash-points__label">FLASH POINTS</span>
        <span className="flash-points__timestamp">UPDATED {now}</span>
      </div>
      {flashPoints.map(fp => (
        <div key={fp.id} className="flash-points__item">
          <span className="flash-points__item-time">{formatFlashTime(fp.timestamp)}</span>
          <div className="flash-points__item-content">
            <div className="flash-points__item-headline">{fp.headline}</div>
            <div className="flash-points__item-detail">{fp.detail}</div>
          </div>
          <span className={CONF_CLASS[fp.confidence] ?? 'badge badge--blue'}>
            {fp.confidence.toUpperCase()}
          </span>
        </div>
      ))}
    </section>
  )
}
