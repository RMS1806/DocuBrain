import http from 'k6/http';

export const options = { vus: 1, iterations: 1 };

export default function () {
  const email = `debug-${Date.now()}@test.com`;

  const reg = http.post('http://localhost/auth/register',
    JSON.stringify({ email, password: 'LoadTest1234!', full_name: 'Test' }),
    { headers: { 'Content-Type': 'application/json' } }
  );
  console.log(`register → ${reg.status} body: ${reg.body.substring(0, 120)}`);

  const login = http.post('http://localhost/auth/login',
    `username=${encodeURIComponent(email)}&password=${encodeURIComponent('LoadTest1234!')}`,
    { headers: { 'Content-Type': 'application/x-www-form-urlencoded' } }
  );
  console.log(`login    → ${login.status} body: ${login.body.substring(0, 120)}`);

  if (login.json('access_token')) {
    const token = login.json('access_token');
    const docs = http.get('http://localhost/documents/',
      { headers: { 'Authorization': `Bearer ${token}` } }
    );
    console.log(`documents → ${docs.status}`);

    const analytics = http.get('http://localhost/analytics/dashboard',
      { headers: { 'Authorization': `Bearer ${token}` } }
    );
    console.log(`analytics → ${analytics.status} body: ${analytics.body.substring(0, 120)}`);
  }
}
