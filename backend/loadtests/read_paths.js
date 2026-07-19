/**
 * Eval-Ops M2 · 读路径性能基线（k6）
 *
 * 流程：登录 → GET /knowledge-bases（分页）→ GET /dashboard/stats
 * 数据前提：L 档 6000+ 库 · 默认 limit=24（与前端分页 v1 一致）
 *
 * 用法见同目录 README.md
 */

import http from 'k6/http';
import { check, sleep } from 'k6';
import { Trend } from 'k6/metrics';

const BASE_URL = __ENV.BASE_URL || 'http://localhost:8000';
const IDENTIFIER = __ENV.IDENTIFIER || 'demo_admin';
const PASSWORD = __ENV.PASSWORD || 'password123';
const WORKSPACE = __ENV.WORKSPACE || '';
const KB_LIMIT = Number(__ENV.KB_LIMIT || 24);
const KB_OFFSET = Number(__ENV.KB_OFFSET || 0);

const kbListDuration = new Trend('kb_list_duration', true);
const dashboardStatsDuration = new Trend('dashboard_stats_duration', true);
const loginDuration = new Trend('login_duration', true);

export const options = {
  scenarios: {
    read_paths: {
      executor: 'constant-vus',
      vus: Number(__ENV.VUS || 10),
      duration: __ENV.DURATION || '30s',
    },
  },
  thresholds: {
    http_req_failed: ['rate<0.01'],
    kb_list_duration: ['p(95)<500'],
  },
};

function jsonHeaders(token) {
  return {
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${token}`,
    },
  };
}

function login() {
  const res = http.post(
    `${BASE_URL}/api/v1/auth/login`,
    JSON.stringify({ identifier: IDENTIFIER, password: PASSWORD }),
    { headers: { 'Content-Type': 'application/json' }, tags: { name: 'POST /auth/login' } },
  );
  loginDuration.add(res.timings.duration);
  check(res, {
    'login status 200': (r) => r.status === 200,
    'login has token': (r) => Boolean(r.json('access_token')),
  });
  if (res.status !== 200) {
    return null;
  }
  return {
    token: res.json('access_token'),
    orgId: String(res.json('user.org_id') || WORKSPACE),
  };
}

export default function () {
  const session = login();
  if (!session) {
    sleep(1);
    return;
  }

  const workspace = WORKSPACE || session.orgId;
  const auth = jsonHeaders(session.token);

  const kbRes = http.get(
    `${BASE_URL}/api/v1/knowledge-bases?workspace=${workspace}&limit=${KB_LIMIT}&offset=${KB_OFFSET}`,
    { ...auth, tags: { name: 'GET /knowledge-bases' } },
  );
  kbListDuration.add(kbRes.timings.duration);
  check(kbRes, {
    'kb list status 200': (r) => r.status === 200,
    'kb list paginated': (r) => r.json('limit') === KB_LIMIT,
    'kb list has total': (r) => (r.json('total') || 0) >= 6000,
  });

  const statsRes = http.get(
    `${BASE_URL}/api/v1/dashboard/stats?workspace=${workspace}`,
    { ...auth, tags: { name: 'GET /dashboard/stats' } },
  );
  dashboardStatsDuration.add(statsRes.timings.duration);
  check(statsRes, {
    'dashboard stats status 200': (r) => r.status === 200,
    'dashboard kb count': (r) => (r.json('knowledge_base_count') || 0) >= 6000,
  });

  sleep(0.3);
}

export function handleSummary(data) {
  const kb = data.metrics.kb_list_duration;
  const dash = data.metrics.dashboard_stats_duration;
  const failed = data.metrics.http_req_failed;

  const line = (metric, label) => {
    if (!metric || !metric.values) {
      return `${label}: (no samples)`;
    }
    const v = metric.values;
    const p50 = v.med ?? v['p(50)'];
    return `${label}: p50=${p50?.toFixed(1)}ms p95=${v['p(95)']?.toFixed(1)}ms avg=${v.avg?.toFixed(1)}ms`;
  };

  console.log('\n--- Eval-Ops M2 summary ---');
  console.log(`VUs=${__ENV.VUS || 10} duration=${__ENV.DURATION || '30s'} limit=${KB_LIMIT}`);
  console.log(line(kb, 'GET /knowledge-bases'));
  console.log(line(dash, 'GET /dashboard/stats'));
  if (failed && failed.values) {
    console.log(`http_req_failed: ${(failed.values.rate * 100).toFixed(2)}%`);
  }
  console.log('---------------------------\n');

  return {};
}
