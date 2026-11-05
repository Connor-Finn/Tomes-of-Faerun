"""Page objects for level roadmaps: planning them in the Character Manager, and following them
(plus the backup copy) on a character in a campaign."""
from __future__ import annotations

import re

from playwright.sync_api import Locator, Page

from .guild_hall_page import TomePage


class RoadmapsPage(TomePage):
    """Character Manager › a character › Roadmaps: the list, and a form to start one."""

    def __init__(self, page: Page):
        super().__init__(page)
        self.new_name = page.get_by_role("textbox", name="New roadmap")
        self.start_button = page.get_by_role("button", name="Start a roadmap")
        self.cards = page.get_by_test_id("roadmap-card")
        self.empty = page.get_by_test_id("no-roadmaps")
        self.unavailable = page.get_by_test_id("roadmaps-unavailable")

    def open(self, character_id: int) -> "RoadmapsPage":
        self.page.goto(f"/play/characters/c/{character_id}/roadmaps")
        return self

    def start(self, name: str) -> "RoadmapPage":
        self.new_name.fill(name)
        self.start_button.click()
        return RoadmapPage(self.page)

    def card(self, name: str) -> Locator:
        return self.cards.filter(has=self.page.get_by_role("link", name=name, exact=True))


class RoadmapPage(TomePage):
    """One roadmap: its levels as milestones, with plan / re-plan / remove controls."""

    def __init__(self, page: Page):
        super().__init__(page)
        self.levels = page.get_by_test_id("roadmap-levels").locator("> li")
        self.plan_next = page.get_by_test_id("plan-next-level")
        self.name = page.get_by_role("textbox", name="Name", exact=True)
        self.rename_button = page.get_by_role("button", name="Rename")
        self.delete_button = page.get_by_role("button", name="Delete roadmap")
        self.followers = page.get_by_test_id("roadmap-followers")
        self.dialog = page.get_by_role("dialog")

    def open(self, character_id: int, roadmap_id: int) -> "RoadmapPage":
        self.page.goto(f"/play/characters/c/{character_id}/roadmaps/{roadmap_id}")
        return self

    def level(self, n: int) -> Locator:
        return self.page.get_by_test_id(f"roadmap-level-{n}")


class InstanceRoadmapPanel:
    """A campaign › Your character: the roadmap and backup controls under the hit points."""

    def __init__(self, page: Page):
        self.page = page
        self.roadmap = page.get_by_test_id("instance-roadmap")
        self.roadmap_select = self.roadmap.get_by_role("combobox", name="Roadmap")
        self.follow_button = self.roadmap.get_by_role("button", name="Follow", exact=True)
        self.following = page.get_by_test_id("following")
        self.stop_button = page.get_by_role("button", name="Stop following")
        self.level_up = self.roadmap.get_by_role("link", name=re.compile("with the roadmap"))
        self.ends = page.get_by_test_id("roadmap-ends")
        self.backup = page.get_by_test_id("instance-backup")
        self.backup_summary = page.get_by_test_id("backup-summary")
        self.save_backup = page.get_by_role("button", name="Save a backup")
        self.restore = page.get_by_role("button", name="Restore backup")
        self.back_up_again = page.get_by_role("button", name="Back up again")
        self.delete_backup = page.get_by_role("button", name="Delete backup")
        self.dialog = page.get_by_role("dialog")
        self.keep_backup = self.dialog.get_by_role("checkbox")

    def follow(self, name: str, keep_backup: bool = True) -> None:
        option = self.roadmap_select.locator("option", has_text=name).first
        self.roadmap_select.select_option(value=option.get_attribute("value"))
        self.follow_button.click()
        self.keep_backup.set_checked(keep_backup)
        self.dialog.get_by_role("button", name="Follow the roadmap").click()
