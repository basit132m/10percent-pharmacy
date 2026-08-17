import { NavLink, Outlet } from 'react-router-dom';

import { useAuth } from '../auth/AuthContext';

const NAV_ITEMS = [
  { to: '/', label: 'Dashboard', end: true },
  { to: '/offers', label: 'Bonus Offers', end: false },
  { to: '/stores', label: 'Store Owners', end: false },
  { to: '/notifications', label: 'Notification Log', end: false },
];

export function Layout() {
  const { user, signOut } = useAuth();

  return (
    <div className="shell">
      <aside className="sidebar">
        <div className="brand">
          <span className="brand__mark">10%</span>
          <span className="brand__text">
            Discount Pharmacy
            <small>Kahror Pakka</small>
          </span>
        </div>
        <nav>
          {NAV_ITEMS.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.end}
              className={({ isActive }) => (isActive ? 'nav-link nav-link--active' : 'nav-link')}
            >
              {item.label}
            </NavLink>
          ))}
        </nav>
        <div className="sidebar__footer">
          <span className="sidebar__user" title={user?.email ?? ''}>
            {user?.email}
          </span>
          <button type="button" className="button button--ghost" onClick={() => void signOut()}>
            Log out
          </button>
        </div>
      </aside>
      <main className="content">
        <Outlet />
      </main>
    </div>
  );
}
