"""Page objects for the online features: publishing characters and the party chat."""
from __future__ import annotations

from playwright.sync_api import Locator, Page

from .guild_hall_page import TomePage


class PublishPage(TomePage):
    """Character Manager › Publish a character: share a fixed copy, and manage what you've published."""

    URL = "/play/characters/publish"

    def __init__(self, page: Page):
        super().__init__(page)
        self.character = page.get_by_label("Character", exact=True)
        self.description = page.get_by_label("Description for other players (optional)")
        self.publish_button = page.get_by_role("button", name="Publish…")
        self.character_error = page.get_by_test_id("error-character")
        self.nothing_to_publish = page.get_by_test_id("nothing-to-publish")
        self.roadmap_note = page.get_by_test_id("roadmap-note")
        self.mine = page.get_by_test_id("my-published")
        self.none_published = page.get_by_test_id("no-published")
        self.dialog = page.get_by_role("dialog")

    def open(self, path: str = URL) -> "PublishPage":
        self.page.goto(path)
        return self

    def publish(self, character: str, description: str = "") -> "PublishPage":
        """Pick a character (by the start of its option text), describe it, and confirm."""
        option = self.character.locator("option", has_text=character).first
        self.character.select_option(value=option.get_attribute("value"))
        if description:
            self.description.fill(description)
        self.publish_button.click()
        self.dialog.get_by_role("button", name="Publish", exact=True).click()
        return self

    def published(self, name: str) -> Locator:
        return self.mine.filter(has=self.page.get_by_role("heading", name=name, exact=True))

    def unpublish(self, name: str) -> "PublishPage":
        self.published(name).get_by_role("button", name=f"Unpublish {name}").click()
        self.dialog.get_by_role("button", name="Unpublish").click()
        return self


class PublishedCharactersPage(TomePage):
    """Character Manager › Create a character › Published characters: copy someone else's template."""

    URL = "/play/characters/create/published"

    def __init__(self, page: Page):
        super().__init__(page)
        self.search = page.get_by_role("searchbox", name="Search by name or author")
        self.class_filter = page.get_by_role("combobox", name="Class")
        self.cards = page.get_by_test_id("published-card")
        self.empty = page.get_by_test_id("no-published")

    def open(self, path: str = URL) -> "PublishedCharactersPage":
        self.page.goto(path)
        return self

    def card(self, name: str) -> Locator:
        return self.cards.filter(has=self.page.get_by_role("heading", name=name, exact=True))

    def use(self, name: str) -> None:
        self.card(name).get_by_role("button", name=f"Use this character: {name}").click()


class PartyChat:
    """The enchanted-parchment chat on a party's page (the DM's and the players' pages share it)."""

    def __init__(self, page: Page):
        self.page = page
        self.root = page.get_by_test_id("party-chat")
        self.log = page.get_by_role("log", name="Party chat messages")
        self.messages = self.log.get_by_test_id("chat-message")
        self.bodies = self.log.get_by_test_id("chat-body")
        self.authors = self.log.get_by_test_id("chat-author")
        self.empty = page.get_by_test_id("chat-empty")
        self.unread_mark = page.get_by_test_id("chat-unread")
        self.writing = page.get_by_test_id("chat-writing")
        self.box = page.get_by_role("textbox", name="Your message")
        self.write_button = self.root.get_by_role("button", name="Write", exact=True)
        self.error = page.get_by_test_id("chat-error")
        self.older = page.get_by_role("button", name="Turn back the page")
        self.dialog = page.get_by_role("dialog")

    def open_player(self, party_id: int) -> "PartyChat":
        self.page.goto(f"/play/campaigns/parties/{party_id}")
        return self

    def open_dm(self, party_id: int) -> "PartyChat":
        self.page.goto(f"/dm/campaigns/parties/{party_id}")
        return self

    def write(self, text: str) -> "PartyChat":
        self.box.fill(text)
        self.write_button.click()
        return self

    def message(self, text: str) -> Locator:
        return self.messages.filter(has=self.page.get_by_test_id("chat-body").filter(has_text=text))

    def strike(self, text: str) -> "PartyChat":
        message = self.message(text)
        message.hover()
        message.get_by_role("button", name="Strike out").click()
        self.dialog.get_by_role("button", name="Strike out").click()
        return self
