import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import './index.css';
import { AdminSaasDashboard } from './routes/AdminSaasDashboard';

const mountEl =
  document.getElementById('admin-saas-root') ?? document.getElementById('root');

if (!mountEl) {
  console.error('[admin-saas] No se encontró #admin-saas-root');
} else {
  createRoot(mountEl).render(
    <StrictMode>
      <AdminSaasDashboard />
    </StrictMode>,
  );
}
