from playwright.sync_api import Locator, Page

from .guild_hall_page import TomePage


class MyCharactersPage(TomePage):
    """Character Manager › My characters."""

    URL = "/play/characters/my-characters"

    def __init__(self, page: Page):
        super().__init__(page)
        self.cards = page.get_by_test_id("character-card")
        self.empty = page.get_by_test_id("no-characters")
        self.create_link = page.get_by_role("link", name="Create a character").last

    def open(self, path: str = URL) -> "MyCharactersPage":
        self.page.goto(path)
        return self

    def card(self, name: str) -> Locator:
        return self.cards.filter(has=self.page.get_by_role("link", name=name, exact=True))

    def open_character(self, name: str) -> "CharacterPage":
        self.card(name).get_by_role("link", name=name, exact=True).click()
        return CharacterPage(self.page)


class CreateCharacterPage(TomePage):
    """Character Manager › Create a character."""

    URL = "/play/characters/create"

    def __init__(self, page: Page):
        super().__init__(page)
        self.templates = page.get_by_test_id("template-card")

    def open(self, path: str = URL) -> "CreateCharacterPage":
        self.page.goto(path)
        return self

    def use_template(self, name: str) -> "CharacterPage":
        self.templates.filter(has_text=name).get_by_role("button", name="Use this character").click()
        return CharacterPage(self.page)


class CharacterPage(TomePage):
    """One character, shown as its own tome: sheet, spellbook, inventory, features, notes..."""

    def __init__(self, page: Page):
        super().__init__(page)
        self.sheet = page.get_by_test_id("character-sheet")
        self.draft_notice = page.get_by_test_id("draft-notice")
        self.build_mode = page.get_by_role("group", name="Build mode")
        self.delete_button = page.get_by_role("button", name="Delete character")
        self.delete_dialog = page.get_by_role("dialog")

    def open_character(self, character_id: int, chapter: str = "sheet") -> "CharacterPage":
        self.page.goto(f"/play/characters/c/{character_id}/{chapter}")
        return self

    def stat(self, key: str) -> Locator:
        """key: ac, hp, speed, initiative, proficiency, passive-perception"""
        return self.page.get_by_test_id(f"stat-{key}").locator(".stat-value")

    def ability(self, key: str) -> Locator:
        return self.page.get_by_test_id(f"ability-{key}")

    def set_build_mode(self, label: str) -> None:
        with self.page.expect_response(lambda r: r.request.method == "PATCH" and "/api/characters/" in r.url):
            self.build_mode.get_by_label(label).check()

    def note(self, label: str) -> Locator:
        return self.page.get_by_label(label, exact=True)

    def delete(self) -> None:
        self.delete_button.click()
        self.delete_dialog.get_by_role("button", name="Delete").filter(has_text="Delete").last.click()
