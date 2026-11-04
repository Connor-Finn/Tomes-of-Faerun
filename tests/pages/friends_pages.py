"""Page objects for friends, the public-party notice board and the DM's join requests."""
from __future__ import annotations

from playwright.sync_api import Locator, Page

from .guild_hall_page import TomePage


class FriendsPage(TomePage):
    """Player Mode › Campaigns › Friends: search for adventurers, answer requests, see your friends."""

    URL = "/play/campaigns/friends"

    def __init__(self, page: Page):
        super().__init__(page)
        self.search = page.get_by_role("searchbox", name="Find adventurers by name")
        self.results = page.get_by_test_id("person")
        self.no_results = page.get_by_test_id("no-people")
        self.requests = page.get_by_test_id("friend-request")
        self.sent = page.get_by_test_id("sent-request")
        self.friends = page.get_by_test_id("friend")
        self.no_friends = page.get_by_test_id("no-friends")
        self.dialog = page.get_by_role("dialog")

    def open(self, path: str = URL) -> "FriendsPage":
        self.page.goto(path)
        return self

    def find(self, name: str) -> "FriendsPage":
        self.search.fill(name)
        return self

    def result(self, name: str) -> Locator:
        return self.results.filter(has_text=name)

    def add(self, name: str) -> "FriendsPage":
        """Search for someone and send them a friend request."""
        self.find(name)
        self.page.get_by_role("button", name=f"Add {name} as a friend").click()
        return self

    def accept(self, name: str) -> "FriendsPage":
        self.requests.filter(has_text=name).get_by_role("button", name=f"Accept {name}'s friend request").click()
        return self

    def decline(self, name: str) -> "FriendsPage":
        self.page.get_by_role("button", name=f"Decline {name}'s friend request").click()
        return self

    def cancel(self, name: str) -> "FriendsPage":
        self.page.get_by_role("button", name=f"Cancel your friend request to {name}").click()
        return self

    def unfriend(self, name: str) -> "FriendsPage":
        self.page.get_by_role("button", name=f"Remove {name} from your friends").click()
        self.dialog.get_by_role("button", name="Remove friend").click()
        return self


class FindPartyPage(TomePage):
    """Player Mode › Campaigns › Find a party: the notice board of public parties."""

    URL = "/play/campaigns/find"

    def __init__(self, page: Page):
        super().__init__(page)
        self.search = page.get_by_role("searchbox", name="Search by party, description or Dungeon Master")
        self.parties = page.get_by_test_id("public-party")
        self.empty = page.get_by_test_id("no-public-parties")
        self.dialog = page.get_by_role("dialog")
        self.note = self.dialog.get_by_role("textbox", name="A note for the Dungeon Master (optional)")

    def open(self, path: str = URL) -> "FindPartyPage":
        self.page.goto(path)
        return self

    def party(self, name: str) -> Locator:
        return self.parties.filter(has=self.page.get_by_role("heading", name=name, exact=True))

    def ask_to_join(self, name: str, note: str = "") -> "FindPartyPage":
        self.party(name).get_by_role("button", name=f"Ask to join {name}").click()
        if note:
            self.note.fill(note)
        self.dialog.get_by_role("button", name="Send request").click()
        return self

    def withdraw(self, name: str) -> "FindPartyPage":
        self.page.get_by_role("button", name=f"Withdraw your request to join {name}").click()
        return self


class JoinRequestsPage(TomePage):
    """DM Mode › Campaigns › Join requests: everyone waiting to join one of your parties."""

    URL = "/dm/campaigns/requests"

    def __init__(self, page: Page):
        super().__init__(page)
        self.requests = page.get_by_test_id("join-request")
        self.empty = page.get_by_test_id("no-requests")

    def open(self, path: str = URL) -> "JoinRequestsPage":
        self.page.goto(path)
        return self

    def request(self, name: str) -> Locator:
        return self.requests.filter(has_text=name)

    def accept(self, name: str) -> "JoinRequestsPage":
        self.page.get_by_role("button", name=f"Accept {name}").click()
        return self

    def decline(self, name: str) -> "JoinRequestsPage":
        self.page.get_by_role("button", name=f"Decline {name}").click()
        return self
