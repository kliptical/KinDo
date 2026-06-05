import React, { useEffect, useState } from 'react';
import { html } from 'htm/react';
import { resolveIdentity, setIdentity, clearIdentity } from './identity.js';
import { parseRoute, subscribeRoute } from './router.js';
import TaskCreator from './components/TaskCreator.js';
import ParentDashboard from './components/ParentDashboard.js';
import TaskDetailParent from './components/TaskDetailParent.js';
import MyTasks from './components/MyTasks.js';
import TaskDetailChild from './components/TaskDetailChild.js';
import AlertModal from './components/AlertModal.js';
import PlatformDisclosure from './components/PlatformDisclosure.js';
import UserManager from './components/UserManager.js';

export default function App({ ftm }) {
  // ftm: the createBrowserApp() result with { stateAdapter, orchestrationAdapter, notificationAdapter }
  const [identity, setIdentityState] = useState(() => resolveIdentity());
  const [route, setRoute] = useState(() => parseRoute(typeof window !== 'undefined' ? window.location.hash : ''));
  const [alertPayload, setAlertPayload] = useState(null);
  const [users, setUsers] = useState([]);

  // Load users for the identity switcher and to resolve unknown role
  async function refreshUsers() {
    const all = await ftm.stateAdapter.listUsers();
    setUsers(all);
  }
  useEffect(() => { refreshUsers(); }, []);

  // Refresh user list when a new user is saved elsewhere in the app
  useEffect(() => {
    if (typeof window === 'undefined') return;
    const handler = () => refreshUsers();
    // Re-poll on hashchange (cheap; covers add-via-UserManager case)
    window.addEventListener('hashchange', handler);
    return () => window.removeEventListener('hashchange', handler);
  }, []);

  // If identity has no role yet (URL bootstrap with bare @id), look it up
  useEffect(() => {
    if (!identity || identity.role) return;
    let cancelled = false;
    (async () => {
      const u = await ftm.stateAdapter.getUser(identity.userId);
      if (cancelled) return;
      if (u) {
        setIdentityState({ userId: identity.userId, role: u['ftm:role'] });
      }
    })();
    return () => { cancelled = true; };
  }, [identity, ftm]);

  useEffect(() => {
    const unsub = subscribeRoute(setRoute);
    return () => unsub && unsub();
  }, []);

  useEffect(() => {
    if (typeof window === 'undefined') return;
    const handler = (e) => setAlertPayload(e.detail);
    window.addEventListener('ftm:alert', handler);
    return () => window.removeEventListener('ftm:alert', handler);
  }, []);

  function switchIdentityTo(userIdValue) {
    if (!userIdValue) return;
    const user = users.find(u => u['@id'] === userIdValue);
    if (!user) return;
    const newId = { userId: user['@id'], role: user['ftm:role'] };
    setIdentity(newId);
    // Navigate back to the role's home and reload so all views re-fetch
    window.location.hash = '#/';
    window.location.reload();
  }

  function logOut() {
    clearIdentity();
    window.location.hash = '#/';
    window.location.reload();
  }

  if (!identity) {
    return html`
      <div className="identity-prompt">
        <h2>No identity configured</h2>
        <p>Open the app with <code>?as=parent:demo</code> in the URL to bootstrap a parent identity, or pick a saved user below.</p>
        ${users.length > 0 ? html`
          <ul className="user-list">
            ${users.map(u => html`
              <li key=${u['@id']}>
                <span className="user-name">${u['ftm:displayName']}</span>
                <span className="badge">${u['ftm:role']}</span>
                <button type="button" onClick=${() => switchIdentityTo(u['@id'])}>Log in as this user</button>
              </li>
            `)}
          </ul>
        ` : null}
      </div>
    `;
  }

  // Whether the current identity matches a saved user (so we can show
  // the displayName instead of the raw @id).
  const currentUser = users.find(u => u['@id'] === identity.userId);
  const currentLabel = currentUser
    ? `${currentUser['ftm:displayName']} (${currentUser['ftm:role']})`
    : `${identity.role ?? 'unknown'}: ${identity.userId.split(':').pop()}`;

  return html`
    <div className="app">
      <${PlatformDisclosure} />
      <header>
        <h1>Family Task Manager</h1>
        <div className="identity-switcher">
          <label>Logged in as
            <select value=${currentUser ? identity.userId : ''} onChange=${e => switchIdentityTo(e.target.value)}>
              ${!currentUser ? html`<option value="">${currentLabel}</option>` : null}
              ${users.map(u => html`
                <option key=${u['@id']} value=${u['@id']}>
                  ${u['ftm:displayName']} (${u['ftm:role']})
                </option>
              `)}
            </select>
          </label>
          <button type="button" onClick=${logOut} className="log-out">Log out</button>
        </div>
      </header>
      <main>${renderRoute({ route, identity, ftm })}</main>
      ${alertPayload ? html`<${AlertModal} payload=${alertPayload} onDismiss=${() => setAlertPayload(null)} />` : null}
    </div>
  `;
}

function renderRoute({ route, identity, ftm }) {
  if (!route) return html`<p>Loading...</p>`;
  if (route.view === 'home') {
    return identity.role === 'parent' ? html`<${ParentDashboard} ftm=${ftm} identity=${identity} />` : html`<${MyTasks} ftm=${ftm} identity=${identity} />`;
  }
  if (route.view === 'parent-dashboard' && identity.role === 'parent') return html`<${ParentDashboard} ftm=${ftm} identity=${identity} />`;
  if (route.view === 'parent-create' && identity.role === 'parent') return html`<${TaskCreator} ftm=${ftm} identity=${identity} onCreated=${() => { window.location.hash = '#/parent/dashboard'; }} />`;
  if (route.view === 'parent-users' && identity.role === 'parent') return html`<${UserManager} ftm=${ftm} />`;
  if (route.view === 'parent-instance' && identity.role === 'parent') return html`<${TaskDetailParent} ftm=${ftm} instanceId=${route.params.id} />`;
  if (route.view === 'child-tasks' && identity.role === 'child') return html`<${MyTasks} ftm=${ftm} identity=${identity} />`;
  if (route.view === 'child-instance' && identity.role === 'child') return html`<${TaskDetailChild} ftm=${ftm} identity=${identity} instanceId=${route.params.id} />`;
  if (route.view === 'instance') {
    return identity.role === 'parent' ? html`<${TaskDetailParent} ftm=${ftm} instanceId=${route.params.id} />` : html`<${TaskDetailChild} ftm=${ftm} identity=${identity} instanceId=${route.params.id} />`;
  }
  if (route.view === 'not-found') return html`<p>Page not found.</p>`;
  return html`<p>Unauthorized for role ${identity.role}.</p>`;
}
