import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App.tsx'
import { installSessionTokenFetch } from './lib/sessionToken'

installSessionTokenFetch()

if (new URLSearchParams(window.location.search).get('mode') === 'island' || window.location.pathname.includes('/island')) {
  document.documentElement.classList.add('island-mode')
}

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
