/**
 * Chat + Upload Load Test (k6)
 *
 * Per VU: register unique user -> create KB -> upload doc -> chat -> cleanup
 * Measures P50/P95 for each step.
 */

import http from 'k6/http';
import { check, sleep } from 'k6';
import { Trend } from 'k6/metrics';

const BASE_URL = __ENV.BASE_URL || 'http://localhost:8000';
const PASSWORD = 'password123';

const createKb = new Trend('create_kb_duration', true);
const uploadDoc = new Trend('upload_duration', true);
const chatReq = new Trend('chat_duration', true);
const loginReq = new Trend('login_duration', true);

export const options = {
  scenarios: {
    chat_upload: {
      executor: 'constant-vus',
      vus: Number(__ENV.VUS || 5),
      duration: __ENV.DURATION || '30s',
    },
  },
  thresholds: {
    http_req_failed: ['rate<0.05'],
  },
};

function login(username) {
  const res = http.post(
    `${BASE_URL}/api/v1/auth/login`,
    JSON.stringify({ identifier: username, password: PASSWORD }),
    { headers: { 'Content-Type': 'application/json' }, tags: { name: 'login' } },
  );
  loginReq.add(res.timings.duration);
  check(res, { 'login 200': (r) => r.status === 200 });
  return res.status === 200 ? { token: res.json('access_token') } : null;
}

function registerAndLogin(vu, iter) {
  const tag = `${vu}_${iter}`;
  const email = `k6lt_${tag}@test.example.com`;
  const username = `k6lt_${tag}`;

  http.post(
    `${BASE_URL}/api/v1/auth/register`,
    JSON.stringify({ email, username, password: PASSWORD, account_type: 'personal' }),
    { headers: { 'Content-Type': 'application/json' }, tags: { name: 'register' } },
  );
  return login(username);
}

export default function () {
  const session = registerAndLogin(__VU, Date.now());
  if (!session) {
    sleep(1);
    return;
  }

  const token = session.token;
  const authJson = { headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` } };

  // Create KB
  const kb = http.post(
    `${BASE_URL}/api/v1/knowledge-bases?workspace=personal`,
    JSON.stringify({ name: `k6lt-${__VU}-${Date.now()}` }),
    { ...authJson, tags: { name: 'create_kb' } },
  );
  createKb.add(kb.timings.duration);
  check(kb, { 'kb created': (r) => r.status === 201 });
  if (kb.status !== 201) { sleep(1); return; }
  const kbId = kb.json('id');

  // Upload
  const upload = http.post(
    `${BASE_URL}/api/v1/knowledge-bases/${kbId}/documents`,
    { files: http.file('handbook.md', '# Handbook\n\nAnnual leave: 10 days.', 'text/markdown') },
    { headers: { Authorization: `Bearer ${token}` }, tags: { name: 'upload' } },
  );
  uploadDoc.add(upload.timings.duration);
  check(upload, { 'upload 201': (r) => r.status === 201 });

  sleep(1);

  // Chat
  const chat = http.post(
    `${BASE_URL}/api/v1/knowledge-bases/${kbId}/chat`,
    JSON.stringify({ message: '年假几天？', mode: 'fast' }),
    { ...authJson, tags: { name: 'chat' } },
  );
  chatReq.add(chat.timings.duration);
  check(chat, { 'chat 200': (r) => r.status === 200 });

  // Cleanup
  http.del(`${BASE_URL}/api/v1/knowledge-bases/${kbId}?workspace=personal`, null, {
    headers: { Authorization: `Bearer ${token}` },
    tags: { name: 'cleanup' },
  });

  sleep(0.3);
}

export function handleSummary(data) {
  const line = (m, label) => {
    if (!m?.values) return `${label}: (no data)`;
    const v = m.values;
    return `${label}: p50=${(v.med ?? v['p(50)'])?.toFixed(1)}ms p95=${v['p(95)']?.toFixed(1)}ms avg=${v.avg?.toFixed(1)}ms`;
  };

  console.log('\n--- Chat+Upload Load Test ---');
  console.log(`VUs=${__ENV.VUS || 5} duration=${__ENV.DURATION || '30s'}`);
  console.log(line(data.metrics.login_duration, 'login'));
  console.log(line(data.metrics.create_kb_duration, 'create_kb'));
  console.log(line(data.metrics.upload_duration, 'upload'));
  console.log(line(data.metrics.chat_duration, 'chat'));
  if (data.metrics.http_req_failed?.values) {
    console.log(`errors: ${(data.metrics.http_req_failed.values.rate * 100).toFixed(1)}%`);
  }
  console.log('-------------------------------\n');
  return {};
}
