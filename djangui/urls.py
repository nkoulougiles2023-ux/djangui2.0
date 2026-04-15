from django.contrib import admin
from django.http import HttpResponse
from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView


LANDING_HTML = """<!doctype html>
<html lang="fr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>DJANGUI 2.0 — Preview</title>
<style>
  *{box-sizing:border-box;margin:0;padding:0}
  body{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;background:linear-gradient(135deg,#0f172a 0%,#1e293b 100%);color:#e2e8f0;min-height:100vh;display:flex;align-items:center;justify-content:center;padding:24px}
  .wrap{max-width:720px;width:100%;background:#0b1220;border:1px solid #1f2937;border-radius:20px;padding:40px;box-shadow:0 20px 60px rgba(0,0,0,.4)}
  .badge{display:inline-block;background:#1e3a8a;color:#93c5fd;padding:4px 12px;border-radius:999px;font-size:12px;font-weight:600;letter-spacing:.5px;text-transform:uppercase}
  h1{font-size:38px;margin:16px 0 8px;background:linear-gradient(90deg,#60a5fa,#c084fc);-webkit-background-clip:text;background-clip:text;color:transparent}
  .tag{color:#94a3b8;font-size:16px;margin-bottom:28px}
  .flag{font-size:20px}
  .grid{display:grid;grid-template-columns:1fr 1fr;gap:12px;margin:24px 0}
  @media (max-width:520px){.grid{grid-template-columns:1fr}}
  a.card{display:block;background:#111827;border:1px solid #1f2937;border-radius:12px;padding:18px;text-decoration:none;color:#e2e8f0;transition:all .2s}
  a.card:hover{border-color:#3b82f6;transform:translateY(-2px);background:#151d2d}
  a.card h3{font-size:15px;margin-bottom:4px;color:#f1f5f9}
  a.card p{font-size:13px;color:#94a3b8}
  .features{margin-top:28px;padding-top:24px;border-top:1px solid #1f2937}
  .features h2{font-size:14px;text-transform:uppercase;letter-spacing:1px;color:#64748b;margin-bottom:12px}
  .features ul{list-style:none;display:flex;flex-wrap:wrap;gap:8px}
  .features li{background:#111827;border:1px solid #1f2937;padding:6px 12px;border-radius:8px;font-size:13px;color:#cbd5e1}
  .foot{margin-top:28px;font-size:12px;color:#64748b;text-align:center}
  code{background:#111827;padding:2px 6px;border-radius:4px;font-size:12px;color:#fbbf24}
</style>
</head>
<body>
  <div class="wrap">
    <span class="badge">Preview build</span>
    <h1>DJANGUI 2.0 <span class="flag">🇨🇲</span></h1>
    <p class="tag">Tontine, prêt instantané &amp; investissement — Cameroun</p>

    <div class="grid">
      <a class="card" href="/api/docs/">
        <h3>📘 API Docs</h3>
        <p>Swagger UI — explore tous les endpoints</p>
      </a>
      <a class="card" href="/admin/login/">
        <h3>🔐 Admin</h3>
        <p>Console d'administration Django</p>
      </a>
      <a class="card" href="/api/schema/">
        <h3>📄 OpenAPI Schema</h3>
        <p>Schéma JSON pour les clients</p>
      </a>
      <a class="card" href="/api/v1/honor-board/">
        <h3>🏆 Honor Board</h3>
        <p>Endpoint public (auth requise)</p>
      </a>
    </div>

    <div class="features">
      <h2>Modules livrés</h2>
      <ul>
        <li>Comptes &amp; KYC</li>
        <li>Wallet &amp; transactions</li>
        <li>Prêts instantanés</li>
        <li>Garants &amp; cautions</li>
        <li>Tontines</li>
        <li>Investissements</li>
        <li>Tchékélé (récompenses)</li>
        <li>Notifications</li>
      </ul>
    </div>

    <p class="foot">Backend API · Django 5 + DRF · Base <code>/api/v1/</code></p>
  </div>
</body>
</html>"""


def landing(_request):
    return HttpResponse(LANDING_HTML, content_type="text/html; charset=utf-8")


api_v1 = [
    path("auth/", include("apps.accounts.urls_auth")),
    path("users/", include("apps.accounts.urls_users")),
    path("wallet/", include("apps.transactions.urls")),
    path("loans/", include("apps.loans.urls")),
    path("guarantees/", include("apps.loans.urls_guarantees")),
    path("tontines/", include("apps.tontines.urls")),
    path("investments/", include("apps.investments.urls")),
    path("tchekele/", include("apps.rewards.urls_tchekele")),
    path("honor-board/", include("apps.rewards.urls_honor")),
    path("notifications/", include("apps.notifications.urls")),
    path("admin/", include("apps.admin_dashboard.urls")),
    path("webhooks/", include("apps.transactions.urls_webhooks")),
]

urlpatterns = [
    path("", landing, name="landing"),
    path("admin/", admin.site.urls),
    path("api/v1/", include(api_v1)),
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path("api/docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="docs"),
]
