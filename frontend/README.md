# FraudGraph AI frontend

The frontend runs in mock mode by default so CASE-1024 can be demonstrated end to end without the backend.

```bash
npm install
npm run dev
```

Set `NEXT_PUBLIC_USE_MOCK_API=false` and `NEXT_PUBLIC_API_BASE_URL` to use the documented backend API adapter.

Demo path: `/investigate` → `CASE-1024` → request verification → add customer denial → approve → resolved case memory.
