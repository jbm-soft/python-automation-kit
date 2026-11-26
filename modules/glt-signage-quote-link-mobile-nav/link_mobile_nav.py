# -*- coding: utf-8 -*-
from pathlib import Path

root = Path(r"D:/GLT-signage-quote/public/legacy")
files = [
    "online_sseugi.html",
    "online_sseugi02.html",
    "online_sseugi03.html",
    "work-order.html",
    "admin.html",
    "index.html",
]
css = "mobile-form.css"
js = "mobile-nav.js"

for name in files:
    path = root / name
    text = path.read_text(encoding="utf-8")
    changed = False

    if css not in text:
        if "admin-legacy.css" in text:
            text = text.replace(
                'href="admin-legacy.css">',
                'href="admin-legacy.css">\n  <link rel="stylesheet" href="mobile-form.css">',
                1,
            )
        elif "</head>" in text:
            text = text.replace("</head>", '  <link rel="stylesheet" href="mobile-form.css">\n</head>', 1)
        changed = True

    if js not in text:
        if "</body>" in text:
            text = text.replace("</body>", f'  <script src="{js}"></script>\n</body>', 1)
            changed = True

    if changed:
        path.write_text(text, encoding="utf-8")
        print(name, "updated")
    else:
        print(name, "ok")
