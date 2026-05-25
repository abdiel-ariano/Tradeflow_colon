import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import './index.css';
import { AdminSaasDashboard } from './routes/AdminSaasDashboard';

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <AdminSaasDashboard />
  </StrictMode>,
);
