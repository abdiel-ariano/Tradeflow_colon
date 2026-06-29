import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import './styles.css';
import App from './App';

const mountEl = document.getElementById('root');

if (!mountEl) {
  console.error('[catalog] No se encontró #root');
} else {
  createRoot(mountEl).render(
    <StrictMode>
      <App />
    </StrictMode>,
  );
}
