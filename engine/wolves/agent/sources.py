"""Static source tier registry: graded context for relevance ranking, never a
deterministic gate. Tier 1 official bodies, federations and wires; tier 2 the
market's quality press, sports daily of record, public broadcaster or
rights-holder; tier 3 aggregators, tabloid rumour desks and engagement farms.
Unknown domains stay None and are judged on content.

Tiers grade NEWS reliability (lineups, injuries, squad facts), not transfer
rumours: the Spanish and Italian sports dailies are tier 2 on facts while
their rumour desks would grade 3. Tier-2 entries anchor on paper-of-record or
public-broadcaster standing; tier-3 entries anchor on the crowd-maintained
transfer-source reliability guides, Football Transfer League accuracy
tracking, or churn-network ownership. Promotion and demotion should follow
the relevance feedback ledger, not vibes."""

from __future__ import annotations

from urllib.parse import urlparse

SOURCE_TIERS: dict[str, int] = {
    # Wires and agencies
    "reuters.com": 1,
    "apnews.com": 1,
    "afp.com": 1,
    "efe.com": 1,
    "ansa.it": 1,
    "english.kyodonews.net": 1,
    "en.yna.co.kr": 1,
    "aps.sn": 1,
    # Confederations and FIFA
    "fifa.com": 1,
    "uefa.com": 1,
    "conmebol.com": 1,
    "concacaf.com": 1,
    "the-afc.com": 1,
    "cafonline.com": 1,
    "oceaniafootball.com": 1,
    # Federations
    "thefa.com": 1,
    "englandfootball.com": 1,
    "scottishfa.co.uk": 1,
    "faw.cymru": 1,
    "fff.fr": 1,
    "dfb.de": 1,
    "rfef.es": 1,
    "figc.it": 1,
    "fpf.pt": 1,
    "knvb.nl": 1,
    "rbfa.be": 1,
    "hns-cff.hr": 1,
    "dbu.dk": 1,
    "svenskfotboll.se": 1,
    "fotball.no": 1,
    "cbf.com.br": 1,
    "afa.com.ar": 1,
    "auf.org.uy": 1,
    "fcf.com.co": 1,
    "ecuafutbol.org": 1,
    "fmf.mx": 1,
    "ussoccer.com": 1,
    "canadasoccer.com": 1,
    "jfa.jp": 1,
    "kfa.or.kr": 1,
    "footballaustralia.com.au": 1,
    "saff.com.sa": 1,
    "qfa.qa": 1,
    "frmf.ma": 1,
    "fsfoot.sn": 1,
    "thenff.com": 1,
    "ghanafa.org": 1,
    "faf.dz": 1,
    "ftf.tn": 1,
    "mlssoccer.com": 1,
    # UK and Ireland
    "bbc.co.uk": 1,
    "bbc.com": 1,
    "theguardian.com": 2,
    "thetimes.com": 2,
    "thetimes.co.uk": 2,
    "telegraph.co.uk": 2,
    "theathletic.com": 2,
    "skysports.com": 2,
    "independent.co.uk": 2,
    "heraldscotland.com": 2,
    "dailyrecord.co.uk": 3,
    "walesonline.co.uk": 3,
    "dailymail.co.uk": 3,
    "thesun.co.uk": 3,
    "mirror.co.uk": 3,
    "express.co.uk": 3,
    "dailystar.co.uk": 3,
    "90min.com": 3,
    "caughtoffside.com": 3,
    "teamtalk.com": 3,
    "footballinsider247.com": 3,
    "football365.com": 3,
    "givemesport.com": 3,
    "sportbible.com": 3,
    "talksport.com": 3,
    # France
    "lequipe.fr": 2,
    "rmcsport.bfmtv.com": 2,
    "ouest-france.fr": 2,
    "leparisien.fr": 2,
    "footmercato.net": 3,
    "le10sport.com": 3,
    "foot01.com": 3,
    "butfootballclub.fr": 3,
    # Germany
    "kicker.de": 2,
    "sportschau.de": 2,
    "sueddeutsche.de": 2,
    "skysport.de": 2,
    "bild.de": 3,
    "sport1.de": 3,
    "spox.com": 3,
    # Spain
    "elpais.com": 2,
    "marca.com": 2,
    "as.com": 2,
    "relevo.com": 2,
    "mundodeportivo.com": 2,
    "cadenaser.com": 2,
    "sport.es": 3,
    "donbalon.com": 3,
    "diariogol.com": 3,
    "fichajes.net": 3,
    "elnacional.cat": 3,
    "okdiario.com": 3,
    # Italy
    "gazzetta.it": 2,
    "corrieredellosport.it": 2,
    "sport.sky.it": 2,
    "gianlucadimarzio.com": 2,
    "tuttosport.com": 3,
    "tuttomercatoweb.com": 3,
    "calciomercato.com": 3,
    # Portugal
    "record.pt": 2,
    "abola.pt": 2,
    "ojogo.pt": 2,
    "publico.pt": 2,
    "maisfutebol.iol.pt": 2,
    # Netherlands
    "vi.nl": 2,
    "nos.nl": 2,
    "ad.nl": 2,
    "telegraaf.nl": 2,
    "espn.nl": 2,
    # Belgium
    "sporza.be": 2,
    "hln.be": 2,
    "nieuwsblad.be": 2,
    "rtbf.be": 2,
    # Croatia and Balkans
    "sportske.jutarnji.hr": 2,
    "vecernji.hr": 2,
    "index.hr": 2,
    "24sata.hr": 3,
    "mozzartsport.com": 2,
    # Scandinavia
    "aftonbladet.se": 2,
    "fotbollskanalen.se": 2,
    "expressen.se": 3,
    "vg.no": 2,
    "nrk.no": 2,
    "tv2.no": 2,
    "dr.dk": 2,
    "tipsbladet.dk": 2,
    "bold.dk": 3,
    "ekstrabladet.dk": 3,
    # Brazil
    "ge.globo.com": 2,
    "globo.com": 2,
    "uol.com.br": 2,
    "espn.com.br": 2,
    "lance.com.br": 2,
    # Argentina
    "ole.com.ar": 2,
    "tycsports.com": 2,
    "lanacion.com.ar": 2,
    "clarin.com": 2,
    "infobae.com": 3,
    # Uruguay
    "elpais.com.uy": 2,
    "elobservador.com.uy": 2,
    "tenfield.com.uy": 2,
    # Colombia
    "eltiempo.com": 2,
    "futbolred.com": 2,
    "elespectador.com": 2,
    "noticiascaracol.com": 2,
    "winsports.co": 2,
    # Ecuador
    "eluniverso.com": 2,
    "elcomercio.com": 2,
    "studiofutbol.com.ec": 2,
    "futbolecuador.com": 3,
    # Mexico
    "espn.com.mx": 2,
    "tudn.com": 2,
    "record.com.mx": 2,
    "eluniversal.com.mx": 2,
    "mediotiempo.com": 3,
    # USA and Canada
    "espn.com": 2,
    "nytimes.com": 2,
    "cbssports.com": 2,
    "foxsports.com": 2,
    "si.com": 3,
    "tsn.ca": 2,
    "sportsnet.ca": 2,
    # Stats platforms: scores and lineups are reliable, editorial is thin
    "fotmob.com": 3,
    "sofascore.com": 3,
    "flashscore.com": 3,
    # Japan
    "gekisaka.jp": 2,
    "nikkansports.com": 2,
    "number.bunshun.jp": 2,
    "japantimes.co.jp": 2,
    "soccer-king.jp": 3,
    # South Korea
    "sports.chosun.com": 2,
    "spotvnews.co.kr": 2,
    "interfootball.co.kr": 3,
    "xportsnews.com": 3,
    # Australia and New Zealand
    "abc.net.au": 2,
    "smh.com.au": 2,
    "foxsports.com.au": 2,
    "optussport.com.au": 2,
    "theroar.com.au": 3,
    "stuff.co.nz": 2,
    # Gulf and Iran
    "arabnews.com": 2,
    "arriyadiyah.com": 2,
    "beinsports.com": 2,
    "aljazeera.com": 2,
    "alkass.net": 2,
    "kooora.com": 3,
    "varzesh3.com": 2,
    "tasnimnews.com": 2,
    "tehrantimes.com": 3,
    # Africa
    "filgoal.com": 2,
    "english.ahram.org.eg": 2,
    "yallakora.com": 3,
    "hespress.com": 2,
    "le360.ma": 2,
    "lematin.ma": 2,
    "wiwsport.com": 2,
    "completesports.com": 2,
    "punchng.com": 2,
    "brila.net": 2,
    "allnigeriasoccer.com": 3,
    "owngoalnigeria.com": 3,
    "graphic.com.gh": 2,
    "ghanasoccernet.com": 3,
    "footballghana.com": 3,
    "sport-ivoire.ci": 2,
    "dzfoot.com": 2,
    "competition.dz": 2,
    "elheddaf.com": 3,
    "camfoot.com": 2,
    "sportnewsafrica.com": 2,
    "africanews.com": 2,
    # Injury, lineup and squad-data specialists
    "premierinjuries.com": 2,
    "physioroom.com": 2,
    "transfermarkt.com": 2,
    "transfermarkt.co.uk": 2,
    "whoscored.com": 2,
    "fantasyfootballscout.co.uk": 2,
    # Global aggregators and engagement farms
    "goal.com": 3,
    "bleacherreport.com": 3,
    "sportskeeda.com": 3,
    "tribuna.com": 3,
    "footballtransfers.com": 3,
    "onefootball.com": 3,
    "essentiallysports.com": 3,
}

OFFICIAL_BODY_HOSTS = frozenset(
    {
        "fifa.com",
        "uefa.com",
        "conmebol.com",
        "concacaf.com",
        "the-afc.com",
        "cafonline.com",
        "oceaniafootball.com",
        "thefa.com",
        "englandfootball.com",
        "scottishfa.co.uk",
        "faw.cymru",
        "fff.fr",
        "dfb.de",
        "rfef.es",
        "figc.it",
        "fpf.pt",
        "knvb.nl",
        "rbfa.be",
        "hns-cff.hr",
        "dbu.dk",
        "svenskfotboll.se",
        "fotball.no",
        "cbf.com.br",
        "afa.com.ar",
        "auf.org.uy",
        "fcf.com.co",
        "ecuafutbol.org",
        "fmf.mx",
        "ussoccer.com",
        "canadasoccer.com",
        "jfa.jp",
        "kfa.or.kr",
        "footballaustralia.com.au",
        "saff.com.sa",
        "qfa.qa",
        "frmf.ma",
        "fsfoot.sn",
        "thenff.com",
        "ghanafa.org",
        "faf.dz",
        "ftf.tn",
    }
)


def source_domain(url: str) -> str:
    host = urlparse(url).netloc.lower()
    return host.removeprefix("www.")


def source_tier(url: str) -> int | None:
    domain = source_domain(url)
    while domain:
        tier = SOURCE_TIERS.get(domain)
        if tier is not None:
            return tier
        _, _, domain = domain.partition(".")
    return None


def official_body_source(url: str) -> bool:
    domain = source_domain(url)
    return any(domain == allowed or domain.endswith(f".{allowed}") for allowed in OFFICIAL_BODY_HOSTS)
