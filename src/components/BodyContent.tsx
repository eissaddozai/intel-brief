import type { BodyParagraph } from '../types/brief'

interface Props {
  paragraphs: BodyParagraph[]
}

function formatCitationTimestamp(ts: string): string {
  try {
    const d = new Date(ts)
    if (isNaN(d.getTime())) return ''
    return ' ' + d.toLocaleString('en-CA', {
      month: 'short', day: 'numeric', hour: '2-digit',
      minute: '2-digit', timeZone: 'UTC', hour12: false,
    }) + ' UTC'
  } catch {
    return ''
  }
}

const STATUS_PREFIX: Record<string, string> = {
  confirmed: '',
  reported:  'reported: ',
  claimed:   'claimed: ',
  disputed:  'disputed: ',
}

export function BodyContent({ paragraphs }: Props) {
  return (
    <>
      {paragraphs.map((para, i) => (
        <div key={i}>
          {para.subLabel && (
            <div className={`sub-label${para.subLabelVariant ? ` sub-label--${para.subLabelVariant}` : ''}`}>
              {para.subLabel}
            </div>
          )}
          <div className="body-para">
            {para.timestamp && (
              <span className="body-para__timestamp">{para.timestamp}</span>
            )}
            {para.text}
            {para.citations.length > 0 && (
              <span className="body-para__source">
                ({para.citations
                  .map(c => {
                    const prefix = STATUS_PREFIX[c.verificationStatus] ?? ''
                    const ts = c.timestamp ? formatCitationTimestamp(c.timestamp) : ''
                    return prefix + c.source + ts
                  })
                  .join('; ')})
              </span>
            )}
          </div>
        </div>
      ))}
    </>
  )
}
