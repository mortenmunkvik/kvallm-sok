#!/usr/bin/env python3
"""Bygger KVALLM-søkesiden.

Bruk:  python3 build.py            (henter feeden fra Acast)
       python3 build.py feed.xml   (bruker en lokal kopi)

Leser tags.txt (temaer og søkeord per episode) og template.html, og skriver
  dist/index.html     – den ferdige siden (dra dist-mappen inn i Netlify)
  forhandsvisning/artifact.html – samme side uten <html>-skall (for forhåndsvisning)
Nye episoder som mangler i tags.txt får temaer automatisk fra RULES nedenfor,
og listes opp slik at du kan legge dem inn i tags.txt for bedre treff.
"""
import html, json, os, re, sys, urllib.request, xml.etree.ElementTree as ET
from email.utils import parsedate_to_datetime

HERE = os.path.dirname(os.path.abspath(__file__))
FEED_URL = "https://feeds.acast.com/public/shows/66863ea94cb273e461b0ce6f"
NS = {"itunes": "http://www.itunes.com/dtds/podcast-1.0.dtd"}

THEMES = {
    "HJ": "Hjerte og kar", "LU": "Lunger og allergi", "INF": "Infeksjoner og antibiotika",
    "VAK": "Vaksiner", "END": "Diabetes og hormoner", "LEV": "Levevaner og overvekt",
    "PSY": "Psykisk helse og søvn", "RUS": "Rus og avhengighet", "NEV": "Nevrologi og hodepine",
    "MSK": "Muskel og skjelett", "HUD": "Hud", "ONH": "Øre, nese, hals og øye",
    "GAS": "Mage, tarm og lever", "URO": "Nyre, urinveier og mannshelse",
    "KV": "Kvinnehelse og prevensjon", "GR": "Graviditet og amming", "BA": "Barn og unge",
    "ELD": "Eldre og demens", "KRE": "Kreft og screening", "LAB": "Blodprøver og diagnostikk",
    "LM": "Legemidler", "BR": "Blå resept og refusjon", "TRY": "Sykmelding, NAV og attester",
    "JUS": "Juss, etikk og meldeplikt", "TAK": "Takster og økonomi",
    "PRA": "Fastlegepraksis og helsepolitikk", "UTD": "Utdanning og veiledning",
    "AKU": "Akuttmedisin og legevakt", "SMI": "Smittevern og pandemi", "DIV": "Jubileer og annet",
}

# Ordstammer som gir tema for nye, utaggede episoder (sjekkes mot tittel og beskrivelse).
RULES = {
    "HJ": "hjerte blodtrykk hypertensjon kolesterol statin flimmer hjertesvikt ldl hdl kar",
    "LU": "kols astma lunge inhal spirometri allergi hoste",
    "INF": "antibiotika infeksjon virus bakteri strep uvi sopp",
    "VAK": "vaksine vaksinasjon",
    "END": "diabetes insulin glp-1 sglt stoffskifte tyre hormon testosteron",
    "LEV": "overvekt fedme vekt trening kosthold bmi",
    "PSY": "depresjon angst psyk søvn melatonin adhd",
    "RUS": "alkohol rus røyk snus nikotin",
    "NEV": "hodepine migrene epilepsi nevro demens svimmel",
    "MSK": "rygg kne skulder hofte artrose smerte osteoporose",
    "HUD": "hud eksem psoriasis utslett vorter",
    "ONH": "øre nese hals øye hørsel",
    "GAS": "mage tarm lever ibs dyspepsi gastro",
    "URO": "nyre urin prostata blære",
    "KV": "prevensjon spiral p-pille overgangsalder klimakter gyn",
    "GR": "gravid svangerskap amming",
    "BA": "barn ungdom spedbarn",
    "ELD": "eldre demens",
    "KRE": "kreft screening",
    "LAB": "prøve analyse laboratori",
    "LM": "legemiddel medisin bivirkning",
    "BR": "blå resept refusjon",
    "TRY": "sykmeld sykemeld nav attest førerkort",
    "JUS": "meldeplikt taushetsplikt juss lov tilsyn",
    "TAK": "takst egenandel frikort",
    "PRA": "fastlege legekontor helsepolitikk",
    "AKU": "legevakt akutt",
}

SERIES = [
    (r"\bGKV\b|Gjør Kloke Valg", "Gjør kloke valg"),
    (r"Dette sier blodet", "Dette sier blodet"),
    (r"Din siste attest", "Din siste attest"),
    (r"Medisinguiden", "Medisinguiden"),
    (r"\bSTFD\b|Sånn tenker fastlegen din", "Sånn tenker fastlegen din"),
    (r"\bLIVE\b|^\d+ Live\b", "Live-opptak"),
]

def key_of(title):
    t = title.strip()
    if re.match(r"^162\s*,5", t): return "162,5"
    return re.split(r"\s+", t)[0].rstrip(".")

def load_tags():
    tags = {}
    for line in open(os.path.join(HERE, "tags.txt"), encoding="utf-8"):
        line = line.strip()
        if not line or line.startswith("#"): continue
        k, codes, kw = (line.split("|") + ["", ""])[:3]
        bad = [c for c in codes.split() if c not in THEMES]
        if bad: sys.exit(f"Ukjent temakode {bad} på linje: {line}")
        tags[k] = (codes.split(), kw.strip())
    return tags

def clean_desc(raw):
    raw = re.sub(r"<hr>.*$", "", raw or "", flags=re.S)
    links = re.findall(r'href=["\']([^"\']+)', raw)
    txt = html.unescape(re.sub(r"<[^>]+>", " ", raw))
    links += re.findall(r"https?://[^\s<\"')]+", txt)
    txt = re.sub(r"https?://\S+", "", txt)
    txt = re.sub(r"Podcastene er ingen lærebok.*$", "", txt, flags=re.S)
    txt = re.sub(r"Bakgrunn: er ingen lærebok.*$", "", txt, flags=re.S)
    txt = re.sub(r"^\s*\d+[.,]?\d*\s.*? by KVALLM\s*$", "", txt)  # «519 Tittel by KVALLM»
    txt = re.sub(r"\s+", " ", txt).strip()
    seen, out = set(), []
    for l in links:
        l = l.rstrip(".,")
        if "acast.com/privacy" in l or l in seen: continue
        seen.add(l); out.append(l)
    return txt, out

def main():
    src = sys.argv[1] if len(sys.argv) > 1 else None
    data = open(src, "rb").read() if src else urllib.request.urlopen(FEED_URL, timeout=60).read()
    items = ET.fromstring(data).findall(".//item")
    if len(items) < 100:
        sys.exit(f"Feeden inneholdt bare {len(items)} episoder – avbryter så siden ikke blir tom.")
    tags, eps, untagged = load_tags(), [], []
    for it in items:
        title = it.findtext("title").strip()
        k = key_of(title)
        desc, links = clean_desc(it.findtext("description"))
        if desc.strip().lower() == title.lower(): desc = ""
        if k in tags:
            codes, kw = tags[k]
        else:
            hay = (title + " " + desc).lower()
            codes = [c for c, words in RULES.items() if any(w in hay for w in words.split())] or ["DIV"]
            kw = ""
            untagged.append(title)
        series = next((name for pat, name in SERIES if re.search(pat, title, re.I)), "")
        # «283. Spirometri», «395,5  Paxlovid», «162 ,5 Morten …», «268 - Meralgia …»
        m = re.match(r"^(\d+)(?:\s*[.,]\s*(\d+))?\s*[-–.]?\s+(.*)$", title)
        label = (m.group(1) + ("," + m.group(2) if m.group(2) else "")) if m else ""
        shown = m.group(3) if m else title
        enc = it.find("enclosure")
        eps.append({
            "n": label, "t": shown.strip() or title, "d": parsedate_to_datetime(it.findtext("pubDate")).date().isoformat(),
            "l": it.findtext("itunes:duration", namespaces=NS) or "", "id": it.findtext("guid"),
            "a": enc.get("url") if enc is not None else "", "th": codes, "k": kw,
            "s": series, "x": desc, "u": links,
        })
    payload = json.dumps({"themes": THEMES, "eps": eps}, ensure_ascii=False, separators=(",", ":"))
    payload = payload.replace("</", "<\\/")
    tpl = open(os.path.join(HERE, "template.html"), encoding="utf-8").read()
    body = tpl.replace("/*DATA*/null", payload)
    os.makedirs(os.path.join(HERE, "dist"), exist_ok=True)
    os.makedirs(os.path.join(HERE, "forhandsvisning"), exist_ok=True)
    open(os.path.join(HERE, "forhandsvisning", "artifact.html"), "w", encoding="utf-8").write(body)
    full = ('<!doctype html>\n<html lang="nb">\n<head>\n<meta charset="utf-8">\n'
            '<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">\n'
            + body.replace("<!--/HEAD-->", "</head>\n<body>", 1) + "\n</body>\n</html>\n")
    open(os.path.join(HERE, "dist", "index.html"), "w", encoding="utf-8").write(full)
    print(f"{len(eps)} episoder, {len(payload)//1024} kB data -> dist/index.html")
    if untagged:
        print(f"\n{len(untagged)} episoder mangler i tags.txt (fikk automatiske temaer):")
        for t in untagged: print("  ", t)

if __name__ == "__main__":
    main()
