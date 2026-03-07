import { useState, useMemo } from 'react'
import { Link } from 'react-router-dom'
import { allBriefs } from '../data'

const THREAT_COLORS: Record<string, string> = {
  CRITICAL: 'var(--color-crimson)',
  SEVERE: '#E85830',
  ELEVATED: 'var(--color-gold)',
  GUARDED: 'var(--d3-bright)',
  LOW: 'var(--d5-bright)',
}

const THREAT_LEVELS = ['ALL', 'CRITICAL', 'SEVERE', 'ELEVATED', 'GUARDED', 'LOW']
const PAGE_SIZE = 10

function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString('en-CA', {
    year: 'numeric',
    month: 'long',
    day: 'numeric',
    timeZone: 'UTC',
  })
}

export function BriefList() {
  const [search, setSearch] = useState('')
  const [threatFilter, setThreatFilter] = useState('ALL')
  const [page, setPage] = useState(1)

  const filteredBriefs = useMemo(() => {
    return allBriefs.filter(({ data }) => {
      // Threat level filter
      if (threatFilter !== 'ALL' && data.meta.threatLevel !== threatFilter) {
        return false
      }
      // Search filter
      if (search) {
        const searchLower = search.toLowerCase()
        const matchesBluf = data.executive.bluf.toLowerCase().includes(searchLower)
        const matchesId = data.meta.cycleId.toLowerCase().includes(searchLower)
        const matchesDate = formatDate(data.meta.timestamp).toLowerCase().includes(searchLower)
        return matchesBluf || matchesId || matchesDate
      }
      return true
    })
  }, [search, threatFilter])

  const totalPages = Math.ceil(filteredBriefs.length / PAGE_SIZE)
  const paginatedBriefs = filteredBriefs.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE)

  return (
    <div className="brief-list">
      {/* Masthead Header - matches detail page */}
      <header className="masthead">
        <div className="masthead__class-bar">
          <span className="masthead__class-label">PROTECTED B</span>
          <span className="masthead__class-unit">CSE Conflict Assessment Unit</span>
        </div>
        <div className="masthead__hero">
          <div className="masthead__title-block">
            <h1 className="masthead__title">
              <span className="masthead__title-main">INTEL</span>
              <span className="masthead__title-year"> BRIEF</span>
            </h1>
            <p className="masthead__subtitle">Iran War File — Daily Assessment</p>
          </div>
          <div className="masthead__cycle-block">
            <span className="masthead__cycle-label">ARCHIVE</span>
            <span className="masthead__cycle-num">{allBriefs.length.toString().padStart(3, '0')}</span>
            <span className="masthead__cycle-date">BRIEFS AVAILABLE</span>
            <span className="masthead__cycle-meta">All cycles · Iran · Gulf Region</span>
          </div>
        </div>
        <hr className="masthead__crimson-rule" />
      </header>

      {/* Search & Filter Bar */}
      <div className="list-toolbar">
        <div className="list-search">
          <input
            type="text"
            placeholder="Search briefs..."
            value={search}
            onChange={(e) => { setSearch(e.target.value); setPage(1) }}
            className="list-search__input"
          />
        </div>
        <div className="list-filters">
          {THREAT_LEVELS.map(level => (
            <button
              key={level}
              className={`list-filter ${threatFilter === level ? 'list-filter--active' : ''}`}
              onClick={() => { setThreatFilter(level); setPage(1) }}
              style={level !== 'ALL' ? { '--filter-color': THREAT_COLORS[level] } as React.CSSProperties : undefined}
            >
              {level}
            </button>
          ))}
        </div>
      </div>

      {/* Results count */}
      <div className="list-results">
        {filteredBriefs.length} brief{filteredBriefs.length !== 1 ? 's' : ''} found
      </div>

      {/* Feed */}
      <div className="list-feed">
        {paginatedBriefs.map(({ id, data }) => (
          <Link to={`/brief/${id}`} key={id} className="brief-card">
            <div className="brief-card__header">
              <span
                className="brief-card__threat"
                style={{ backgroundColor: THREAT_COLORS[data.meta.threatLevel] }}
              >
                {data.meta.threatLevel}
              </span>
              <span className="brief-card__trajectory">
                {data.meta.threatTrajectory === 'escalating' ? '↑ Escalating' :
                 data.meta.threatTrajectory === 'de-escalating' ? '↓ De-escalating' : '→ Stable'}
              </span>
              <span className="brief-card__date">{formatDate(data.meta.timestamp)}</span>
              <span className="brief-card__id">{data.meta.cycleId}</span>
            </div>

            <p className="brief-card__bluf">
              {data.executive.bluf.slice(0, 280)}...
            </p>

            <div className="brief-card__stats">
              {data.meta.stripCells?.slice(0, 4).map((cell, i) => (
                <div key={i} className="brief-card__stat">
                  <span className="brief-card__stat-value">{cell.top}</span>
                  <span className="brief-card__stat-label">{cell.bot}</span>
                </div>
              ))}
            </div>
          </Link>
        ))}

        {filteredBriefs.length === 0 && (
          <div className="list-empty">
            No briefs match your search criteria.
          </div>
        )}
      </div>

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="list-pagination">
          <button
            className="list-pagination__btn"
            onClick={() => setPage(p => Math.max(1, p - 1))}
            disabled={page === 1}
          >
            ← Previous
          </button>
          <span className="list-pagination__info">
            Page {page} of {totalPages}
          </span>
          <button
            className="list-pagination__btn"
            onClick={() => setPage(p => Math.min(totalPages, p + 1))}
            disabled={page === totalPages}
          >
            Next →
          </button>
        </div>
      )}
    </div>
  )
}
