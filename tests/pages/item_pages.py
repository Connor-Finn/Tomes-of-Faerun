from playwright.sync_api import Locator, Page

from .guild_hall_page import TomePage


class ItemsPage(TomePage):
    """Browse Tomes › Items: search, filter and star every SRD item and magic item."""

    URL = "/dm/tomes/items"

    def __init__(self, page: Page):
        super().__init__(page)
        self.search_box = page.get_by_label("Search by name")
        self.count = page.get_by_test_id("item-count")
        self.rows = page.get_by_test_id("item-row")
        self.names = self.rows.locator(".monster-name")
        self.empty = page.get_by_test_id("no-items")
        self.folio = page.get_by_test_id("items-folio")
        self.next_leaf = page.get_by_role("button", name="Next page")
        self.clear_filters = page.get_by_role("button", name="Clear the filters")
        self.only_favourites = page.get_by_label("Only my favourites")

    def open(self, path: str = URL) -> "ItemsPage":
        self.page.goto(path)
        return self

    def search(self, text: str) -> "ItemsPage":
        self.search_box.fill(text)
        return self

    def filter(self, label: str, option: str) -> "ItemsPage":
        """label: "Kind", "Category", "Rarity" or "Sort by"."""
        self.page.get_by_label(label, exact=True).select_option(label=option)
        return self

    def row(self, name: str) -> Locator:
        return self.rows.filter(has=self.page.get_by_role("link", name=name, exact=True))

    def star(self, name: str) -> Locator:
        """The favourite toggle on an item's row (aria-pressed says whether it's on)."""
        return self.page.get_by_role("button", name=f"Favourite {name}", exact=True)

    def open_item(self, name: str) -> "ItemPage":
        self.page.get_by_role("link", name=name, exact=True).click()
        return ItemPage(self.page)


class ItemPage(TomePage):
    """One item written out in full, with its favourite star and the characters who carry it."""

    def __init__(self, page: Page):
        super().__init__(page)
        self.block = page.get_by_test_id("item-block")
        self.item_line = page.get_by_test_id("item-line")
        self.text = page.get_by_test_id("item-text")
        self.contents = page.get_by_test_id("item-contents")
        self.back = page.get_by_role("link", name="Back to the items")
        self.missing = page.get_by_test_id("item-missing")
        self.star = self.block.get_by_test_id("favourite-star")
        self.carried_by = page.get_by_test_id("carried-by")

    def open_item(self, index: str) -> "ItemPage":
        self.page.goto(f"/dm/tomes/items/{index}")
        return self

    def line(self, key: str) -> Locator:
        """key: cost, weight, damage, range, thrown, properties, armor-class, strength, stealth,
        speed, carrying-capacity, variants, sold-as"""
        return self.page.get_by_test_id(f"item-{key}").locator("dd")


class ItemPicker:
    """The builder's Extra items picker, on the Equipment page."""

    def __init__(self, page: Page):
        self.page = page
        self.root = page.get_by_test_id("item-picker")
        self.search_box = self.root.get_by_label("Search items")
        self.kind = self.root.get_by_label("Kind of item")
        self.only_favourites = self.root.get_by_label("Only my favourites")
        self.results = self.root.get_by_test_id("catalogue-item")
        self.result_names = self.results.locator(".spell-name")
        self.added = self.root.get_by_test_id("added-item")
        self.reader = self.root.get_by_test_id("item-reader")

    def search(self, text: str) -> "ItemPicker":
        self.search_box.fill(text)
        return self

    def add(self, name: str) -> None:
        self.root.get_by_role("button", name=f"Add {name}", exact=True).click()

    def read(self, name: str) -> None:
        self.root.get_by_role("button", name=f"Read {name}", exact=True).click()

    def quantity(self, name: str) -> Locator:
        return self.root.get_by_label(f"How many {name}")

    def remove(self, name: str) -> None:
        self.root.get_by_role("button", name=f"Remove {name}", exact=True).click()
