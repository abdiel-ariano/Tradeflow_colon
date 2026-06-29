import { Route as rootRoute } from './routes/__root';
import { Route as catalogRoute } from './routes/catalog';
import { createRoute, redirect } from '@tanstack/react-router';

const indexRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/',
  beforeLoad: () => {
    throw redirect({ to: '/catalog' });
  },
});

export const routeTree = rootRoute.addChildren([indexRoute, catalogRoute]);
