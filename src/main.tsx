import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter, Routes, Route } from 'react-router-dom'
import './styles/tokens.css'
import './styles/base.css'
import './styles/animations.css'
import './styles/intel-brief.css'
import './styles/list.css'
import { BriefList } from './pages/BriefList'
import { BriefDetail } from './pages/BriefDetail'

const root = document.getElementById('root')
if (!root) throw new Error('Root element not found')

createRoot(root).render(
  <StrictMode>
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<BriefList />} />
        <Route path="/brief/:cycleId" element={<BriefDetail />} />
      </Routes>
    </BrowserRouter>
  </StrictMode>
)
