from playwright.sync_api import Locator, Page


class TavernPage:
    """The hub: a Player / Dungeon Master mode switch and a shelf of tomes."""

    URL = "/tavern"

    def __init__(self, page: Page):
        self.page = page
        self.heading = page.get_by_role("heading", name="The Tavern", level=1)
        self.player_mode = page.get_by_role("radio", name="Player Mode")
        self.dm_mode = page.get_by_role("radio", name="Dungeon Master Mode")
        self.shelf_heading = page.locator("#shelf-heading")
        self.covers = page.get_by_test_id("tome-cover")

    def open(self) -> "TavernPage":
        self.page.goto(self.URL)
        return self

    def switch_to(self, mode: str) -> "TavernPage":
        """mode is "player" or "dm"."""
        (self.dm_mode if mode == "dm" else self.player_mode).check()
        return self

    def tome(self, title: str) -> Locator:
        return self.covers.filter(has=self.page.locator(".book-title", has_text=title))

    def open_tome(self, title: str) -> "TomePage":
        self.tome(title).click()
        return TomePage(self.page)


class TomePage:
    """Any section shown as a tome: contents on the left leaf, the open page on the right."""

    def __init__(self, page: Page):
        self.page = page
        self.tome = page.get_by_test_id("tome")
        self.title = page.get_by_role("heading", level=1)
        self.contents = page.get_by_role("navigation", name="Table of contents")
        # Chapter titles without their roman numerals ("I.", "II."...)
        self.entries = self.contents.get_by_role("link").locator(".toc-title")
        self.current_entry = self.contents.locator("[aria-current=page] .toc-title")
        self.page_title = page.locator("#page-title")
        self.folio = page.get_by_test_id("folio")
        self.next_page = page.get_by_role("navigation", name="Turn the page").locator("a[rel=next]")
        self.prev_page = page.get_by_role("navigation", name="Turn the page").locator("a[rel=prev]")
        self.breadcrumbs = page.get_by_role("navigation", name="Breadcrumb")

    def open(self, path: str) -> "TomePage":
        self.page.goto(path)
        return self

    def go_to(self, chapter: str) -> "TomePage":
        self.contents.get_by_role("link", name=chapter).click()
        return self
