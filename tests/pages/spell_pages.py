from playwright.sync_api import Locator, Page

from .guild_hall_page import TomePage


class SpellsPage(TomePage):
    """Browse Tomes › Spells: search, filter and star every SRD spell."""

    URL = "/dm/tomes/spells"

    def __init__(self, page: Page):
        super().__init__(page)
        self.search_box = page.get_by_label("Search by name")
        self.count = page.get_by_test_id("spell-count")
        self.rows = page.get_by_test_id("spell-row")
        self.names = self.rows.locator(".monster-name")
        self.empty = page.get_by_test_id("no-spells")
        self.folio = page.get_by_test_id("spells-folio")
        self.next_leaf = page.get_by_role("button", name="Next page")
        self.clear_filters = page.get_by_role("button", name="Clear the filters")
        self.rituals_only = page.get_by_label("Rituals only")
        self.only_favourites = page.get_by_label("Only my favourites")

    def open(self, path: str = URL) -> "SpellsPage":
        self.page.goto(path)
        return self

    def search(self, text: str) -> "SpellsPage":
        self.search_box.fill(text)
        return self

    def filter(self, label: str, option: str) -> "SpellsPage":
        """label: "Level", "School", "Class", "Concentration" or "Sort by"."""
        self.page.get_by_label(label, exact=True).select_option(label=option)
        return self

    def row(self, name: str) -> Locator:
        return self.rows.filter(has=self.page.get_by_role("link", name=name, exact=True))

    def star(self, name: str) -> Locator:
        """The favourite toggle button on a spell's row (aria-pressed says whether it's on)."""
        return self.page.get_by_role("button", name=f"Favourite {name}", exact=True)

    def open_spell(self, name: str) -> "SpellPage":
        self.page.get_by_role("link", name=name, exact=True).click()
        return SpellPage(self.page)


class SpellPage(TomePage):
    """One spell written out in full, with its favourite star and the characters who know it."""

    def __init__(self, page: Page):
        super().__init__(page)
        self.block = page.get_by_test_id("spell-block")
        self.spell_line = page.get_by_test_id("spell-line")
        self.text = page.get_by_test_id("spell-text")
        self.back = page.get_by_role("link", name="Back to the spells")
        self.missing = page.get_by_test_id("spell-missing")
        self.star = self.block.get_by_test_id("favourite-star")
        self.known_by = page.get_by_test_id("known-by")

    def open_spell(self, index: str) -> "SpellPage":
        self.page.goto(f"/dm/tomes/spells/{index}")
        return self

    def line(self, key: str) -> Locator:
        """key: casting-time, range, components, duration, classes, subclasses, damage, healing,
        saving-throw, attack, higher-level"""
        locator = self.page.get_by_test_id(f"spell-{key}")
        return locator if key == "higher-level" else locator.locator("dd")
