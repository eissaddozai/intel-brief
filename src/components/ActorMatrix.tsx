import type { ActorMatrixRow } from '../types/brief'

interface Props {
  rows: ActorMatrixRow[]
}

const CONF_CLASS: Record<string, string> = {
  high:     'conf-text--high',
  moderate: 'conf-text--moderate',
  low:      'conf-text--low',
}

export function ActorMatrix({ rows }: Props) {
  return (
    <div className="actor-matrix">
      <div className="actor-matrix__caption">ACTOR MATRIX — CURRENT CYCLE</div>
      <table>
        <thead>
          <tr>
            <th>ACTOR</th>
            <th>POSTURE</th>
            <th>CHANGE</th>
            <th>ASSESSMENT</th>
            <th>CONF.</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row, i) => (
            <tr key={i}>
              <td className="actor-name">{row.actor}</td>
              <td>{row.posture}</td>
              <td className={`actor-change actor-change--${row.changeSincePrevCycle}`}>
                {row.changeSincePrevCycle === 'up' ? '↑' : row.changeSincePrevCycle === 'down' ? '↓' : '→'}
              </td>
              <td>{row.assessment}</td>
              <td>
                <span className={`conf-text ${CONF_CLASS[row.confidence] ?? ''}`}>
                  {row.confidence.toUpperCase()}
                </span>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
