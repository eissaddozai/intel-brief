import type { BriefCycle } from '../types/brief'
import canadaFlagGoc from '../assets/canada-flag-goc.svg'

interface Props {
  footer: BriefCycle['footer']
  meta: BriefCycle['meta']
}

export function BriefFooter({ footer, meta }: Props) {
  return (
    <footer className="brief-footer">
      <div className="brief-footer__main">
        <span className="brief-footer__id">{footer.id}</span>
        <span className="brief-footer__class">{footer.classification}</span>
        <span className="brief-footer__page">{meta.classification} // {meta.tlp}</span>
      </div>
      <p className="brief-footer__sources">Sources: {footer.sources}</p>
      <p className="brief-footer__handling">{footer.handling}</p>
      <div className="brief-footer__flag">
        <img src={canadaFlagGoc} alt="Government of Canada" />
      </div>
    </footer>
  )
}
