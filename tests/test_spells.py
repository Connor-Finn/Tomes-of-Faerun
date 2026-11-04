"""The spell catalogue in the browser: searching, reading spells, favourites, and spells on characters."""
import re

from playwright.sync_api import Page, expect

from builds import autofill, blank
from conftest import API_HEADERS
from pages import BuilderPage, CharacterPage, GuildHallPage, SpellPage, SpellsPage

SRD_SPELLS = 319


def star_via_api(page: Page, *indexes: str) -> None:
    """Star spells with the browser's own session (fast setup, no clicking)."""
    for index in indexes:
        assert page.request.put(f"/api/spells/favourites/{index}", headers=API_HEADERS).ok


def create_wizard(page: Page, name: str = "Mira", **prefer: list[str]) -> dict:
    def check(build: dict) -> dict:
        return page.request.post("/api/characters/check", data={"build": build}, headers=API_HEADERS).json()
    build = autofill(check, blank(name=name, **{"class": "wizard"}), prefer=prefer)
    response = page.request.post("/api/characters", data={"build": build}, headers=API_HEADERS)
    assert response.status == 201, response.text()
    return response.json()["character"]


# ------------------------------------------------------------------ browsing
def test_find_the_spells_from_the_guild_hall(logged_in_page: Page):
    hall = GuildHallPage(logged_in_page).open().switch_to("dm")
    hall.open_tome("Browse Tomes").go_to("Spells")
    expect(logged_in_page).to_have_url(re.compile(r"/dm/tomes/spells$"))
    spells = SpellsPage(logged_in_page)
    expect(spells.page_title).to_have_text("Spells")
    expect(spells.count).to_have_text(f"{SRD_SPELLS} spells")
    expect(spells.rows).to_have_count(25)
    expect(spells.names.first).to_have_text("Acid Arrow")
    expect(spells.folio).to_have_text("Leaf 1 of 13")


def test_search_by_name(logged_in_page: Page):
    spells = SpellsPage(logged_in_page).open().search("fire")
    expect(spells.count).to_have_text("7 spells")
    expect(spells.names).to_have_text(["Delayed Blast Fireball", "Faerie Fire", "Fire Bolt", "Fire Shield",
                                       "Fire Storm", "Fireball", "Wall of Fire"])
    expect(logged_in_page).to_have_url(re.compile(r"q=fire"))


def test_filter_by_level_and_class(logged_in_page: Page):
    spells = SpellsPage(logged_in_page).open().filter("Level", "Cantrip").filter("Class", "Wizard")
    expect(spells.count).to_have_text("14 spells")
    expect(spells.row("Fire Bolt")).to_be_visible()
    expect(spells.row("Sacred Flame")).to_have_count(0)  # a cleric cantrip
    for level in spells.rows.get_by_test_id("spell-level").all_inner_texts():
        assert level == "Cantrip"

    spells.clear_filters.click()
    expect(spells.count).to_have_text(f"{SRD_SPELLS} spells")


def test_rituals_and_concentration(logged_in_page: Page):
    spells = SpellsPage(logged_in_page).open()
    spells.rituals_only.check()
    expect(spells.count).to_have_text("29 spells")
    expect(spells.row("Detect Magic").locator("abbr[title=Ritual]")).to_be_visible()
    spells.filter("Concentration", "No concentration")
    expect(spells.row("Detect Magic")).to_have_count(0)  # it needs concentration
    expect(spells.row("Comprehend Languages")).to_be_visible()


def test_filters_survive_a_reload(logged_in_page: Page):
    spells = SpellsPage(logged_in_page).open("/dm/tomes/spells?school=necromancy&level=9")
    expect(spells.names).to_have_text(["Astral Projection", "True Resurrection"])
    logged_in_page.reload()
    expect(logged_in_page.get_by_label("School")).to_have_value("necromancy")
    expect(logged_in_page.get_by_label("Level", exact=True)).to_have_value("9")
    expect(spells.names).to_have_text(["Astral Projection", "True Resurrection"])


# ------------------------------------------------------------------ reading a spell
def test_read_a_spell(logged_in_page: Page):
    spell = SpellsPage(logged_in_page).open().search("fireball").open_spell("Fireball")
    expect(logged_in_page).to_have_url(re.compile(r"/dm/tomes/spells/fireball$"))
    expect(spell.page_title).to_have_text("Fireball")
    expect(spell.current_entry).to_have_text("Spells")  # still in the Spells chapter
    expect(spell.spell_line).to_have_text("3rd-level evocation")
    expect(spell.line("casting-time")).to_have_text("1 action")
    expect(spell.line("range")).to_have_text("150 feet (20-foot sphere)")
    expect(spell.line("components")).to_have_text("V, S, M (a tiny ball of bat guano and sulfur)")
    expect(spell.line("duration")).to_have_text("Instantaneous")
    expect(spell.text).to_contain_text("A bright streak flashes from your pointing finger")
    expect(spell.line("higher-level")).to_contain_text("At Higher Levels.")
    expect(spell.line("saving-throw")).to_have_text("DEX (half on a success)")
    expect(spell.line("damage")).to_contain_text("8d6 (slot 3)")
    expect(spell.line("classes")).to_have_text("Sorcerer, Wizard")

    spell.back.click()  # back to the search you came from
    expect(logged_in_page).to_have_url(re.compile(r"/dm/tomes/spells\?q=fireball$"))


def test_concentration_and_tables_are_written_out(logged_in_page: Page):
    spell = SpellPage(logged_in_page).open_spell("confusion")
    expect(spell.line("duration")).to_have_text("Concentration, up to 1 minute")
    table = spell.text.get_by_role("table")
    expect(table.get_by_role("columnheader")).to_have_text(["d10", "Behavior"])
    expect(table.locator("tbody tr")).to_have_count(4)


def test_a_missing_spell(logged_in_page: Page):
    spell = SpellPage(logged_in_page).open_spell("wish-for-more-wishes")
    expect(spell.missing).to_contain_text("No such spell")


# ------------------------------------------------------------------ favourites
def test_star_spells_and_show_only_favourites(logged_in_page: Page):
    spells = SpellsPage(logged_in_page).open().search("fire")
    expect(spells.star("Fireball")).to_have_attribute("aria-pressed", "false")
    with logged_in_page.expect_response("**/api/spells/favourites/fireball"):
        spells.star("Fireball").click()
    expect(spells.star("Fireball")).to_have_attribute("aria-pressed", "true")
    with logged_in_page.expect_response("**/api/spells/favourites/fire-bolt"):
        spells.star("Fire Bolt").click()

    spells.search_box.fill("")
    spells.only_favourites.check()
    expect(spells.only_favourites).to_be_checked()
    expect(logged_in_page.get_by_text("Only my favourites (2)")).to_be_visible()
    expect(spells.names).to_have_text(["Fire Bolt", "Fireball"])

    # Unstarring takes it off the favourites page, and it stays off after a reload
    with logged_in_page.expect_response("**/api/spells/favourites/fire-bolt"):
        spells.star("Fire Bolt").click()
    expect(spells.names).to_have_text(["Fireball"])
    logged_in_page.reload()
    expect(spells.names).to_have_text(["Fireball"])


def test_no_favourites_yet(logged_in_page: Page):
    spells = SpellsPage(logged_in_page).open("/dm/tomes/spells?favourites=1")
    expect(spells.empty).to_contain_text("You haven't starred any spells yet")


def test_star_a_spell_from_its_page(logged_in_page: Page):
    spell = SpellPage(logged_in_page).open_spell("shield")
    expect(spell.star).to_have_text("☆ Add to favourites")
    spell.star.click()
    expect(logged_in_page.get_by_test_id("flash-success")).to_have_text("Shield is one of your favourites.")
    expect(spell.star).to_have_text("★ Favourite")
    expect(spell.star).to_have_attribute("aria-pressed", "true")


# ------------------------------------------------------------------ spells and characters
def test_a_spell_shows_which_characters_know_it(logged_in_page: Page):
    mira = create_wizard(logged_in_page, "Mira", **{"spells:spellbook": ["magic-missile"]})
    spell = SpellPage(logged_in_page).open_spell("magic-missile")
    expect(spell.known_by.get_by_role("listitem")).to_have_text("Mira Spellbook")
    spell.known_by.get_by_role("link", name="Mira").click()
    expect(logged_in_page).to_have_url(re.compile(rf"/play/characters/c/{mira['id']}/spellbook$"))

    SpellPage(logged_in_page).open_spell("fireball")
    expect(spell.known_by).to_contain_text("None of your characters has learned it yet.")


def test_read_spells_in_a_characters_spellbook(logged_in_page: Page):
    mira = create_wizard(logged_in_page, "Mira", **{"spells:spellbook": ["magic-missile"]})
    star_via_api(logged_in_page, "magic-missile")
    CharacterPage(logged_in_page).open_character(mira["id"], "spellbook")
    spell = logged_in_page.get_by_test_id("spell").filter(has_text="Magic Missile")
    expect(spell.get_by_role("button", name="Favourite Magic Missile")).to_have_attribute("aria-pressed", "true")

    spell.get_by_role("button", name="Magic Missile", exact=True).click()
    expect(spell.get_by_test_id("spell-reader")).to_contain_text("You create three glowing darts of magical force.")
    spell.get_by_role("button", name="Magic Missile", exact=True).click()
    expect(spell.get_by_test_id("spell-reader")).to_have_count(0)

    logged_in_page.get_by_role("link", name="Change spells").click()
    expect(logged_in_page).to_have_url(re.compile(rf"/play/characters/c/{mira['id']}/edit\?section=spells$"))
    expect(BuilderPage(logged_in_page).tab("Spells")).to_have_attribute("aria-selected", "true")


def test_favourites_come_first_in_the_builder(logged_in_page: Page):
    star_via_api(logged_in_page, "sleep", "shield")
    b = BuilderPage(logged_in_page).open_new("standard")
    b.go_to("Class").choose_card("wizard")
    b.go_to("Spells")
    book = b.slot("spells:spellbook")
    names = book.get_by_test_id("catalogue-spell").locator(".spell-name")
    expect(names.nth(0)).to_have_text("Shield")
    expect(names.nth(1)).to_have_text("Sleep")

    book.get_by_label("Only my favourites").check()
    expect(names).to_have_text(["Shield", "Sleep"])

    # Star another one right there in the builder
    book.get_by_label("Only my favourites").uncheck()
    book.get_by_label("Search spells").fill("Magic Missile")
    with logged_in_page.expect_response("**/api/spells/favourites/magic-missile"):
        book.get_by_role("button", name="Favourite Magic Missile").click()
    book.get_by_label("Search spells").fill("")
    book.get_by_label("Only my favourites").check()
    expect(names).to_have_text(["Magic Missile", "Shield", "Sleep"])


def test_read_a_spell_before_adding_it_in_the_builder(logged_in_page: Page):
    b = BuilderPage(logged_in_page).open_new("standard")
    b.go_to("Class").choose_card("wizard")
    b.go_to("Spells")
    book = b.slot("spells:spellbook")
    book.get_by_label("Search spells").fill("Sleep")
    book.get_by_role("button", name="Read Sleep").click()
    reader = book.get_by_test_id("spell-reader")
    expect(reader).to_contain_text("This spell sends creatures into a magical slumber.")
    expect(reader.get_by_test_id("spell-line")).to_have_text("1st-level enchantment")
    book.get_by_role("button", name="Close Sleep").click()
    expect(reader).to_have_count(0)
