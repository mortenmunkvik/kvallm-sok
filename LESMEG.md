# KVALLM-søk

Søkeside for alle episodene av KVALLM, publisert på https://søk.kvallm.no (også https://sok.kvallm.no).

- `tags.txt` – temaer og stikkord per episode (én linje per episode: `nummer|temakoder|stikkord`). Rediger her for bedre treff.
- `template.html` – selve siden (utseende og søkemotor).
- `build.py` – henter feeden fra Acast og bygger `dist/index.html`.
- `.github/workflows/oppdater.yml` – kjører `build.py` hver morgen i GitHub.
- `netlify.toml` – forteller Netlify at siden ligger i `dist/`.

## Slik oppdateres siden

Automatisk: GitHub kjører `build.py` hver dag kl. 06:00 (UTC). Har det kommet nye episoder, lagres en ny `dist/index.html`, og Netlify publiserer søk.kvallm.no på nytt.

Nye episoder får temaer gjettet ut fra tittelen. For bedre treff kan du legge dem inn i `tags.txt` (rediger filen direkte på GitHub). Siden bygges da på nytt med en gang.

Manuelt: på GitHub, gå til «Actions» → «Oppdater episoder» → «Run workflow».

Temakodene står øverst i `build.py` (THEMES).
