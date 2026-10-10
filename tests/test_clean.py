from jobsearcher.pipeline import clean as C

HTML = """
<html><head><script>var x = 1;</script><style>p{}</style></head>
<body>
<nav><a href="/">Hjem</a> | <a href="/jobb">Jobb</a></nav>
<h2>Om stillingen</h2>
<p>Vi søker en <strong>nyutdannet utvikler</strong> til teamet vårt.</p>
<ul><li>Python</li><li>TypeScript</li></ul>
<p>Del annonsen</p>
<footer>Copyright</footer>
</body></html>
"""


def test_html_to_markdown_strips_chrome():
    md = C.html_to_markdown(HTML)
    assert "## Om stillingen" in md
    assert "**nyutdannet utvikler**" in md
    assert "- Python" in md
    assert "var x" not in md and "Hjem" not in md and "Copyright" not in md
    assert "Del annonsen" not in md


def test_plain_text_passthrough():
    assert C.html_to_markdown("Linje 1\n\n\n\nLinje 2") == "Linje 1\n\nLinje 2"
    assert C.html_to_markdown("   ") is None
    assert C.html_to_markdown(None) is None


ABOUT = ("Fjordbølge Teknologi er et selskap med 40 ansatte som lager programvare for havbruk. "
         "Vi holder til i lyse lokaler og har sosiale arrangementer hver måned.")


def test_shorten_boilerplate():
    text = f"Vi søker en utvikler.\n\n{ABOUT}"
    others = [f"Annen annonse.\n\n{ABOUT}", f"Tredje.\n\n{ABOUT}"]
    out = C.shorten_boilerplate(text, others, min_ads=3)
    assert C.BOILERPLATE_MARKER in out
    assert out.startswith("Vi søker en utvikler.")
    assert "sosiale arrangementer" not in out
    # Seen in only two ads (this + one): kept.
    assert C.shorten_boilerplate(text, others[:1], min_ads=3) == text


def test_truncate_for_budget_keeps_intro_and_priority():
    filler = "\n\n".join(f"Avsnitt {i} om kantina og fotballaget. " * 6 for i in range(30))
    text = (
        "Intro: Vi søker en junior utvikler.\n\n"
        + filler
        + "\n\n**Kvalifikasjoner**\n\n- Bachelor i informatikk\n- Kjennskap til Python"
        + "\n\nSøknadsfrist: 1. november"
    )
    out = C.truncate_for_budget(text, max_tokens=300)
    assert len(out) <= 300 * C.CHARS_PER_TOKEN + 50
    assert out.startswith("Intro: Vi søker")
    assert "Bachelor i informatikk" in out
    assert "Søknadsfrist" in out
    assert out.endswith(C.CUT_MARKER)
    assert C.GAP_MARKER in out


def test_truncate_short_text_unchanged():
    assert C.truncate_for_budget("kort tekst", 100) == "kort tekst"
    assert C.truncate_for_budget(None, 100) == ""
