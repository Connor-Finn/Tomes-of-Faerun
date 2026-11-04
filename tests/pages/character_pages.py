import re

from playwright.sync_api import Locator, Page, expect

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


class BuilderPage:
    """The character builder: Standard build tabs or the Easy build wizard."""

    def __init__(self, page: Page):
        self.page = page
        self.root = page.get_by_test_id("builder")
        self.heading = page.get_by_role("heading", level=1)
        self.status = page.get_by_test_id("builder-status")
        self.save_button = self.root.get_by_role("button", name=re.compile(r"^Save"))
        self.errors = page.get_by_test_id("builder-errors")
        self.step_title = page.locator("#step-title")
        self.next_button = page.get_by_role("button", name=re.compile(r"^Next"))
        self.back_button = page.get_by_role("button", name="← Back")

    def open_new(self, mode: str = "standard") -> "BuilderPage":
        self.page.goto(f"/play/characters/new?mode={mode}")
        self.wait_for_check()
        return self

    def wait_for_check(self) -> None:
        expect(self.status).not_to_have_text("Checking the rules…")

    def tab(self, name: str) -> Locator:
        return self.page.get_by_role("tab", name=re.compile(rf"^{re.escape(name)}"))

    def go_to(self, tab: str) -> "BuilderPage":
        self.tab(tab).click()
        return self

    def tab_mark(self, key: str) -> Locator:
        return self.page.get_by_test_id(f"tab-mark-{key}")

    def choose_card(self, value: str) -> None:
        """Pick a class, race, subrace, background or subclass card by its index."""
        with self.page.expect_response("**/api/characters/check"):
            self.page.get_by_test_id(f"choice-{value}").click()

    def slot(self, slot_id: str) -> Locator:
        return self.page.locator(f"[data-slot='{slot_id}']")

    def chip(self, slot_id: str, label: str) -> Locator:
        return self.slot(slot_id).get_by_role("button", name=label, exact=True)

    def pick(self, slot_id: str, *labels: str) -> None:
        for label in labels:
            with self.page.expect_response("**/api/characters/check"):
                self.chip(slot_id, label).click()

    def add_spell(self, slot_id: str, name: str) -> None:
        slot = self.slot(slot_id)
        slot.get_by_label("Search spells").fill(name)
        with self.page.expect_response("**/api/characters/check"):
            slot.get_by_test_id("catalogue-spell").filter(has=self.page.locator(".spell-name", has_text=name)) \
                .get_by_role("button", name=f"Add {name}", exact=True).click()

    def set_standard_array(self, **scores: int) -> None:
        self.page.get_by_label("Standard array").check()
        names = {"str": "Strength", "dex": "Dexterity", "con": "Constitution",
                 "int": "Intelligence", "wis": "Wisdom", "cha": "Charisma"}
        for key, value in scores.items():
            self.page.get_by_label(f"{names[key]} score").select_option(str(value))

    def next_until(self, title: str) -> "BuilderPage":
        """Easy build: press Next until the wizard reaches the step called `title`."""
        for _ in range(10):
            if self.step_title.inner_text() == title:
                return self
            self.next_button.click()
        raise AssertionError(f"No step called {title}")

    def save(self) -> None:
        self.wait_for_check()
        self.save_button.click()
