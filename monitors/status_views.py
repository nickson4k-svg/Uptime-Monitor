"""
Public status page HTML view — rendered Django template.
Served at /status/<slug>/.
No authentication required.
"""

from django.shortcuts import get_object_or_404, render
from django.views import View

from monitors.models import Monitor


class PublicStatusPageView(View):
    """
    Renders the public status page HTML shell.
    The page fetches live data via /api/v1/public/status/<slug>/ (JS fetch).

    Access control:
    - get_object_or_404 with is_public=True → returns 404 for non-public monitors.
    - Owner identity is NOT exposed in the template context.
    """

    template_name = "status/public_status.html"

    def get(self, request, slug: str):
        monitor = get_object_or_404(Monitor, public_slug=slug, is_public=True)

        context = {
            "monitor_name": monitor.name,
            "monitor_slug": slug,
            # Pass only the public slug — JS will fetch the rest
            "api_url": f"/api/v1/public/status/{slug}/",
        }
        return render(request, self.template_name, context)
