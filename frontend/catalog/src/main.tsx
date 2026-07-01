import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { RouterProvider } from '@tanstack/react-router';
import './styles.css';
import { router } from './router';

const mountEl = document.getElementById('root');

if (!mountEl) {
  console.error('[catalog] No se encontró #root');
} else {
  createRoot(mountEl).render(
    <StrictMode>
      <RouterProvider router={router} />
    </StrictMode>,
  );
}
