import { createInMemoryStateAdapter } from './adapters/state/inMemoryStateAdapter.js';
import { createTestOrchestrationAdapter } from './adapters/orchestration/testOrchestrationAdapter.js';
import { createNoopNotificationAdapter } from './adapters/notification/noopNotificationAdapter.js';
import { createUser } from './entities/user.js';
import { parentCreatesTask } from './flows/parentCreatesTask.js';
import { bootResume } from './flows/bootResume.js';
import { reminderTrigger } from './flows/reminderTrigger.js';

export async function createApp() {
  const stateAdapter = createInMemoryStateAdapter();
  const orchestrationAdapter = createTestOrchestrationAdapter();
  const notificationAdapter = createNoopNotificationAdapter();
  return { stateAdapter, orchestrationAdapter, notificationAdapter };
}

export async function runDemo() {
  console.log('[FTM] starting demo');
  const app = await createApp();
  const parent = createUser({ role: 'parent', displayName: 'Alice' });
  await app.stateAdapter.saveUser(parent);
  const child = createUser({ role: 'child', displayName: 'Alex' });
  await app.stateAdapter.saveUser(child);
  console.log('[FTM] created users:', parent['ftm:displayName'], '+', child['ftm:displayName']);
  const dueAt = new Date(Date.now() + 5000).toISOString();
  const { taskDef, instances } = await parentCreatesTask({
    stateAdapter: app.stateAdapter,
    orchestrationAdapter: app.orchestrationAdapter,
    params: {
      title: 'Clean room',
      description: 'Vacuum and tidy',
      assignedTo: child['@id'],
      createdBy: parent['@id'],
      dueAt,
    },
  });
  console.log('[FTM] created task:', taskDef['ftm:title'], 'with', instances.length, 'instance(s)');
  const boot = await bootResume({ ...app, currentTime: new Date().toISOString() });
  console.log('[FTM] boot complete: toCreate=' + (boot.toCreate ?? 0) + ', skipped=' + boot.skipped);
  app.orchestrationAdapter.tick(new Date(Date.now() + 6000).toISOString());
  const fire = await reminderTrigger({
    ...app,
    instanceId: instances[0]['@id'],
    currentTime: new Date(Date.now() + 6000).toISOString(),
  });
  console.log('[FTM] reminder dispatched=' + fire.dispatched + ' reason=' + (fire.reason ?? 'first-and-only'));
  console.log('[FTM] demo complete; exit 0');
}

runDemo().catch(err => { console.error('[FTM]', err); process.exit(1); });
