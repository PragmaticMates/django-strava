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
│       ├── data.js            # DS data module (mock data + derived stats)
│       ├── charts.js          # DSCharts module (SVG/canvas chart renderers)
│       ├── classic-data.js    # Dashboard wiring (records tabs, trends, calendar)
│       └── image-slot.js      # <image-slot> web component
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

## Replacing Mock Data with Real Data

The templates currently use the bundled `data.js` / `classic-data.js` JavaScript modules
which generate deterministic mock data on the client side. To connect real Strava data:

1. Remove `<script src="{% static 'js/data.js' %}">` from `dashboard.html`
2. Remove `<script src="{% static 'js/classic-data.js' %}">` from `dashboard.html`
3. Pass your data from the Django view as JSON and initialise the charts manually,
   or use the same `window.DS` / `window.DSCharts` API that `classic-data.js` already calls.

---

## Image Slots

The `<image-slot>` elements in the templates are drag-and-drop placeholders used
during the design phase. In production, replace them with standard `<img>` tags
loading images from your models:

```html
<!-- Replace this: -->
<image-slot id="aoty-photo" class="aoty-photo" ...></image-slot>

<!-- With this: -->
<img src="{{ activity.photo.url }}" class="aoty-photo" alt="Activity photo">
```

You can remove `image-slot.js` from the static folder once all slots are replaced.

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
