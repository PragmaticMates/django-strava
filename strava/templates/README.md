# django-strava — Frontend Package

Static HTML/CSS/JS templates ready to drop into a Django project.

---

## File Structure

```
django_package/
├── static/
│   ├── css/
│   │   ├── classic.css        # Shared base styles (nav, cards, layout)
│   │   ├── activities.css     # Activities page styles
│   │   ├── gear.css           # Gear page styles
│   │   └── gallery.css        # Gallery page styles
│   └── js/
│       ├── charts.js          # DSCharts module (SVG/canvas chart renderers)
│       └── classic-data.js    # Dashboard wiring (records tabs, trends, calendar)
├── templates/
│   ├── dashboard.html
│   ├── activities.html
│   ├── gear.html
│   └── gallery.html
├── sample_views.py
├── sample_urls.py
└── README.md
```

---

## Setup

### 1. Copy files into your project

```
your_project/
├── static/          ← copy contents of static/ here
└── templates/       ← copy contents of templates/ here
```

### 2. Django settings

```python
# settings.py
STATICFILES_DIRS = [BASE_DIR / 'static']

TEMPLATES = [{
    ...
    'DIRS': [BASE_DIR / 'templates'],
    ...
}]
```

### 3. Wire up URLs

See `sample_urls.py`. The templates use these named URL patterns:

| URL name      | Page            |
|---------------|-----------------|
| `dashboard`   | Dashboard        |
| `activities`  | Activities       |
| `gear`        | Gear             |
| `gallery`     | Gallery          |

### 4. Views

Each view must pass `active_page` in the context to highlight the correct nav item.
See `sample_views.py`.

---

## Dashboard Data

`classic-data.js` wires up the dashboard's records list, calendar dots and trends
chart. It reads real server data from the JSON `<script>` blocks rendered by
`_dash_data.html` (`dashboard-records`, `dashboard-trends`, `dashboard-calendar`)
and falls back to a small deterministic demo series only when those are absent.
To feed it real data, populate those JSON blocks from your Django view; no
JavaScript changes are needed.

---

## Density

The `<html>` element carries a `data-density` attribute (`comfortable` or `compact`)
that scales padding/gaps throughout the UI. To make it user-controllable:

```python
# In your view:
density = request.COOKIES.get('density', 'comfortable')
return render(request, 'dashboard.html', {'density': density, ...})
```

```html
<!-- In your template: -->
<html lang="en" data-density="{{ density }}">
```

---

## Fonts

Fonts are loaded from Google Fonts CDN. For self-hosted or offline use,
download the families and update the `@font-face` rules in `classic.css`:
- **Barlow** (body text)
- **Barlow Condensed** (numbers, headings)
- **Inter** (UI labels)
- **DM Sans** (optional)
