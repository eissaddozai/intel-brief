import type { AnalystNote as AnalystNoteType } from '../types/brief'

interface Props {
  note: AnalystNoteType
}

export function AnalystNote({ note }: Props) {
  return (
    <div className="analyst-note">
      <div className="analyst-note__gradient" />
      <div className="analyst-note__header">
        <span className="analyst-note__title">{note.title}</span>
        <span className="analyst-note__label">{note.cycleRef}</span>
      </div>
      <div className="analyst-note__body">
        <p className="analyst-note__text">{note.text}</p>
      </div>
    </div>
  )
}
