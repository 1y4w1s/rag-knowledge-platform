/**
 * Eval-Ops M2 · 跨库搜索延迟基线（I2）
 *
 * 流程：登录（或 TOKEN）→ GET /search/documents?mode=filename → mode=content
 * 数据前提见同目录 README「I2 跨库搜」节
 *
 * 认证二选一：
 *   A) IDENTIFIER + PASSWORD（默认 demo_admin）
 *   B) TOKEN + WORKSPACE（跳过登录；适合评测库主人 JWT）
 */

import http from 'k6/http';
import { check, sleep } from 'k6';
import { Trend } from 'k6/metrics';

const BASE_URL = __ENV.BASE_URL || 'http://localhost:8000';
const IDENTIFIER = __ENV.IDENTIFIER || 'demo_admin';
const PASSWORD = __ENV.PASSWORD || 'password123';
const WORKSPACE = __ENV.WORKSPACE || '';
const TOKEN = __ENV.TOKEN || '';
const Q_FILENAME = __ENV.Q_FILENAME || 'acme';
const Q_CONTENT = __ENV.Q_CONTENT || '产品';
const SEARCH_LIMIT = Number(__ENV.SEARCH_LIMIT || 20);
const RUN_CONTENT = (__ENV.RUN_CONTENT || '1') !== '0';

const filenameDuration = new Trend('search_filename_duration', true);
const contentDuration = new Trend('search_content_duration', true);
const loginDuration = new Trend('login_duration', true);

export const options = {
  scenarios: {
    search_paths: {
      executor: 'constant-vus',
      vus: Number(__ENV.VUS || 5),
      duration: __ENV.DURATION || '20s',
    },
  },
  thresholds: {
    http_req_failed: ['rate<0.01'],
    search_filename_duration: ['p(95)<300'],
    search_content_duration: RUN_CONTENT ? ['p(95)<800'] : [],
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
  if (TOKEN) {
    if (!WORKSPACE) {
      console.error('TOKEN set but WORKSPACE missing (use personal or org UUID)');
      return null;
    }
    return { token: TOKEN, orgId: WORKSPACE };
  }

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
    orgId: String(res.json('user.org_id') || WORKSPACE || 'personal'),
  };
}

function searchDocuments(token, workspace, mode, q) {
  const url =
    `${BASE_URL}/api/v1/search/documents` +
    `?workspace=${encodeURIComponent(workspace)}` +
    `&mode=${encodeURIComponent(mode)}` +
    `&q=${encodeURIComponent(q)}` +
    `&limit=${SEARCH_LIMIT}&offset=0`;
  return http.get(url, {
    ...jsonHeaders(token),
    tags: { name: `GET /search/documents?mode=${mode}` },
  });
}

export default function () {
  const session = login();
  if (!session) {
    sleep(1);
    return;
  }

  const workspace = WORKSPACE || session.orgId || 'personal';
  const fnRes = searchDocuments(session.token, workspace, 'filename', Q_FILENAME);
  filenameDuration.add(fnRes.timings.duration);
  check(fnRes, {
    'filename status 200': (r) => r.status === 200,
    'filename has total': (r) => typeof r.json('total') === 'number',
    'filename mode ok': (r) => r.json('mode') === 'filename',
  });

  if (RUN_CONTENT) {
    const cRes = searchDocuments(session.token, workspace, 'content', Q_CONTENT);
    contentDuration.add(cRes.timings.duration);
    check(cRes, {
      'content status 200': (r) => r.status === 200,
      'content has total': (r) => typeof r.json('total') === 'number',
      'content mode ok': (r) => r.json('mode') === 'content',
    });
  }

  sleep(0.3);
}

export function handleSummary(data) {
  const line = (metric, label) => {
    if (!metric || !metric.values) {
      return `${label}: (no samples)`;
    }
    const v = metric.values;
    const p50 = v.med ?? v['p(50)'];
    return `${label}: p50=${p50?.toFixed(1)}ms p95=${v['p(95)']?.toFixed(1)}ms avg=${v.avg?.toFixed(1)}ms`;
  };

  const failed = data.metrics.http_req_failed;
  console.log('\n--- Eval-Ops M2 search (I2) summary ---');
  console.log(
    `VUs=${__ENV.VUS || 5} duration=${__ENV.DURATION || '20s'} limit=${SEARCH_LIMIT} ` +
      `q_fn=${Q_FILENAME} q_content=${Q_CONTENT} run_content=${RUN_CONTENT ? '1' : '0'} ` +
      `auth=${TOKEN ? 'TOKEN' : 'login'}`,
  );
  console.log(line(data.metrics.search_filename_duration, 'GET /search/documents filename'));
  if (RUN_CONTENT) {
    console.log(line(data.metrics.search_content_duration, 'GET /search/documents content'));
  } else {
    console.log('GET /search/documents content: SKIPPED (RUN_CONTENT=0)');
  }
  if (failed && failed.values) {
    console.log(`http_req_failed: ${(failed.values.rate * 100).toFixed(2)}%`);
  }
  console.log('----------------------------------------\n');
  return {};
}
