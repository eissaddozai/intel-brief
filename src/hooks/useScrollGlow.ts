import { useEffect } from 'react'

/**
 * Adds `.masthead--scrolled` class to the element with id="masthead"
 * when the page has scrolled more than 40px, enabling the crimson drop shadow.
 */
export function useScrollGlow(): void {
  useEffect(() => {
    const el = document.getElementById('masthead')
    if (!el) return

    const handler = () => {
      el.classList.toggle('masthead--scrolled', window.scrollY > 40)
    }

    window.addEventListener('scroll', handler, { passive: true })
    return () => window.removeEventListener('scroll', handler)
  }, [])
}
