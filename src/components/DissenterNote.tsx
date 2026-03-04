import type { DissenterNote as DissenterNoteType } from '../types/brief'
import { DOMAIN_LABELS } from '../types/brief'

interface Props {
  note: DissenterNoteType
}

export function DissenterNote({ note }: Props) {
  return (
    <div className="dissenter-note">
      <div className="dissenter-note__gradient" />
      <div className="dissenter-note__header">
        <span className="dissenter-note__title">DISSENTING VIEW — {DOMAIN_LABELS[note.domain]}</span>
        <span className="dissenter-note__attribution">{note.analystId}</span>
      </div>
      <div className="dissenter-note__body">
        <p className="dissenter-note__text">{note.text}</p>
      </div>
    </div>
  )
}
