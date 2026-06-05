import React, { useEffect, useState } from 'react';
import { html } from 'htm/react';
import { resolveIdentity } from './identity.js';
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
  const [identity, setId] = useState(() => resolveIdentity());
  const [route, setRoute] = useState(() => parseRoute(typeof window !== 'undefined' ? window.location.hash : ''));
  const [alertPayload, setAlertPayload] = useState(null);

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

  if (!identity) {
    return html`<div className="identity-prompt"><p>No identity configured. Append ?as=parent:<id> or ?as=child:<id> to the URL.</p></div>`;
  }

  return html`
    <div className="app">
      ${html`<${PlatformDisclosure} />`}
      <header><h1>Family Task Manager</h1><p>${identity.role}: ${identity.userId.split(':').pop()}</p></header>
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
    // role-agnostic deep link
    return identity.role === 'parent' ? html`<${TaskDetailParent} ftm=${ftm} instanceId=${route.params.id} />` : html`<${TaskDetailChild} ftm=${ftm} identity=${identity} instanceId=${route.params.id} />`;
  }
  if (route.view === 'not-found') return html`<p>Page not found.</p>`;
  return html`<p>Unauthorized for role ${identity.role}.</p>`;
}
