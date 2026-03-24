# For A Quick View
# from HTML5 folder 
python3 -m http.server 8000


Then open http://localhost:8000 in your browser.


Notes, assumptions, and small design choices

I created a static HTML/JS representation of the alert dataset and implemented search + severity 
filter and a details modal.

Tailwind is included via the CDN build for quick prototyping (good for small UIs).

Bootstrap is used for layout and components (nav, buttons, modal). 

Font Awesome provides icons for severities.

I did not fully port the server-side correlation logic into the UI (that would be a larger client-side simulation). 
Instead, the UI shows the raw alerts with a placeholder fingerprint field and supports quick exploration.

The sample data file is stored under alerts.json so the UI works offline without calling the original Python server.
