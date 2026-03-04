import type { DataTable as DataTableType } from '../types/brief'

interface Props {
  table: DataTableType
}

export function DataTable({ table }: Props) {
  return (
    <div className="data-table-wrap">
      <div className="data-table-caption">
        {table.caption}
        {table.unit && <span style={{ fontWeight: 400, marginLeft: 6 }}>({table.unit})</span>}
      </div>
      <table className="data-table">
        <thead>
          <tr>
            {table.headers.map((h, i) => (
              <th key={i}>{h}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {table.rows.map((row, ri) => (
            <tr key={ri} className={row.status ? `status--${row.status}` : ''}>
              <td className="label">{row.label}</td>
              {row.values.map((v, vi) => {
                const isFirst = vi === 0
                const isChange = vi === 1 && row.change
                const isStatus = vi === row.values.length - 1 && row.status
                return (
                  <td
                    key={vi}
                    className={[
                      isFirst ? 'val' : '',
                      isChange ? `change change--${row.change}` : '',
                      isStatus ? `status status--${row.status}` : '',
                    ].filter(Boolean).join(' ')}
                  >
                    {v}
                  </td>
                )
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
