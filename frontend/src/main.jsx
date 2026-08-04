import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter, Routes, Route } from 'react-router-dom'

// Fonts: Plus Jakarta Sans (readable primary) + JetBrains Mono (secondary), self-hosted.
import '@fontsource-variable/plus-jakarta-sans'
import '@fontsource-variable/jetbrains-mono'
import './index.css'

import Layout from './components/Layout.jsx'
import BookPage from './pages/BookPage.jsx'
import ScorePage from './pages/ScorePage.jsx'
import VendorPage from './pages/VendorPage.jsx'
import PackPage, { ContractPage } from './pages/PackPage.jsx'
import QueuePage from './pages/QueuePage.jsx'
import InventoryPage from './pages/InventoryPage.jsx'
import ProgramPage from './pages/ProgramPage.jsx'
import MethodologyPage from './pages/MethodologyPage.jsx'
import PerfectMethodologyPage from './pages/PerfectMethodologyPage.jsx'

// The book is the landing page, not the search box. A single-vendor scorecard answers "is this one
// safe?"; a programme with 146 vendors, a blocked queue and a monitoring schedule needs to open on
// what needs a person today.
createRoot(document.getElementById('root')).render(
  <StrictMode>
    <BrowserRouter>
      <Routes>
        <Route element={<Layout />}>
          <Route path="/" element={<BookPage />} />
          <Route path="/assess" element={<ScorePage />} />
          <Route path="/vendors/:ref" element={<VendorPage />} />
          <Route path="/vendors/:ref/pack" element={<PackPage />} />
          <Route path="/vendors/:ref/contract" element={<ContractPage />} />
          <Route path="/queue" element={<QueuePage />} />
          <Route path="/inventory" element={<InventoryPage />} />
          <Route path="/program" element={<ProgramPage />} />
          <Route path="/methodology" element={<MethodologyPage />} />
          <Route path="/perfect-methodology" element={<PerfectMethodologyPage />} />
        </Route>
      </Routes>
    </BrowserRouter>
  </StrictMode>,
)
