from playwright.sync_api import Locator, Page

from .guild_hall_page import TomePage


class BestiaryPage(TomePage):
    """Browse Tomes › Bestiary: search and filter every SRD monster."""

    URL = "/dm/tomes/bestiary"

    def __init__(self, page: Page):
        super().__init__(page)
        self.search_box = page.get_by_label("Search by name")
        self.count = page.get_by_test_id("monster-count")
        self.rows = page.get_by_test_id("monster-row")
        self.names = self.rows.locator(".monster-name")
        self.empty = page.get_by_test_id("no-monsters")
        self.folio = page.get_by_test_id("bestiary-folio")
        self.next_leaf = page.get_by_role("button", name="Next page")
        self.prev_leaf = page.get_by_role("button", name="Previous page")
        self.clear_filters = page.get_by_role("button", name="Clear the filters")

    def open(self, path: str = URL) -> "BestiaryPage":
        self.page.goto(path)
        return self

    def search(self, text: str) -> "BestiaryPage":
        self.search_box.fill(text)
        return self

    def filter(self, label: str, option: str) -> "BestiaryPage":
        """label: "Creature type", "Size", "Lowest CR", "Highest CR", "My environment" or "Sort by"."""
        self.page.get_by_label(label, exact=True).select_option(label=option)
        return self

    def row(self, name: str) -> Locator:
        return self.rows.filter(has=self.page.get_by_role("link", name=name, exact=True))

    def open_monster(self, name: str) -> "MonsterPage":
        self.page.get_by_role("link", name=name, exact=True).click()
        return MonsterPage(self.page)


class MonsterPage(TomePage):
    """One monster: its stat block, plus the controls for saving it."""

    def __init__(self, page: Page):
        super().__init__(page)
        self.stat_block = page.get_by_test_id("stat-block")
        self.back = page.get_by_role("link", name="Back to the bestiary")
        self.missing = page.get_by_test_id("monster-missing")
        # Saving to a collection
        self.saved_in = page.get_by_test_id("saved-in")
        self.collection = page.get_by_label("Collection", exact=True)
        self.new_collection_name = page.get_by_label("New collection name")
        self.role = page.get_by_label("Role", exact=True)
        self.how_many = page.get_by_label("How many", exact=True)
        self.add_button = page.get_by_role("button", name="Add to collection")
        self.save_error = page.get_by_test_id("save-error")
        # Environments
        self.environments = page.get_by_test_id("monster-environments")
        self.new_environment = page.get_by_label("New environment", exact=True)
        self.add_environment_button = page.get_by_role("button", name="Add environment")

    def open_monster(self, index: str) -> "MonsterPage":
        self.page.goto(f"/dm/tomes/bestiary/{index}")
        return self

    def line(self, key: str) -> Locator:
        """key: ac, hp, speed, saving-throws, skills, damage-immunities, senses, languages, challenge..."""
        return self.page.get_by_test_id(f"monster-{key}").locator("dd")

    def ability(self, short: str) -> Locator:
        return self.page.get_by_test_id(f"monster-{short.lower()}")

    def section(self, name: str) -> Locator:
        """name: traits, actions, reactions, legendary-actions"""
        return self.page.get_by_test_id(f"monster-{name}")

    def add_to_collection(self, collection: str | None = None, *, new: str | None = None,
                          role: str = "No role", count: int = 1) -> None:
        """Pick an existing collection by name, or pass new="Name" to start one."""
        if new is not None:
            self.collection.select_option(label="New collection…")
            self.new_collection_name.fill(new)
        elif collection is not None:
            self.collection.select_option(label=collection)
        self.role.select_option(label=role)
        self.how_many.fill(str(count))
        self.add_button.click()

    def environment(self, name: str) -> Locator:
        return self.environments.get_by_role("checkbox", name=name)

    def create_environment(self, name: str) -> None:
        self.new_environment.fill(name)
        self.add_environment_button.click()


class CollectionsPage(TomePage):
    """Browse Tomes › Monster collections."""

    URL = "/dm/tomes/collections"

    def __init__(self, page: Page):
        super().__init__(page)
        self.new_name = page.get_by_label("New collection", exact=True)
        self.start_button = page.get_by_role("button", name="Start collection")
        self.name_error = page.get_by_test_id("error-name")
        self.cards = page.get_by_test_id("collection-card")
        self.empty = page.get_by_test_id("no-collections")

    def open(self, path: str = URL) -> "CollectionsPage":
        self.page.goto(path)
        return self

    def start(self, name: str) -> "CollectionPage":
        self.new_name.fill(name)
        self.start_button.click()
        return CollectionPage(self.page)

    def card(self, name: str) -> Locator:
        return self.cards.filter(has=self.page.get_by_role("link", name=name, exact=True))

    def open_collection(self, name: str) -> "CollectionPage":
        self.card(name).get_by_role("link", name=name, exact=True).click()
        return CollectionPage(self.page)


class CollectionPage(TomePage):
    """One collection: its monsters grouped by role, counts, XP and DM notes."""

    def __init__(self, page: Page):
        super().__init__(page)
        self.totals = page.get_by_test_id("collection-totals")
        self.entries = page.get_by_test_id("collection-entry")
        self.empty = page.get_by_test_id("empty-collection")
        self.rename_button = page.get_by_role("button", name="Rename")
        self.name_box = page.get_by_label("Collection name")
        self.save_name_button = page.get_by_role("button", name="Save name")
        self.delete_button = page.get_by_role("button", name="Delete collection")
        self.dialog = page.get_by_role("dialog")
        self.notes = page.get_by_label("DM notes")
        self.save_notes_button = page.get_by_role("button", name="Save notes")

    def group(self, role: str) -> Locator:
        """role: boss, elite, minion or none"""
        return self.page.get_by_test_id(f"role-group-{role}")

    def entry(self, monster: str) -> Locator:
        return self.entries.filter(has=self.page.get_by_role("link", name=monster, exact=True))

    def set_count(self, monster: str, count: int) -> None:
        box = self.page.get_by_label(f"How many {monster}")
        with self.page.expect_response(lambda r: r.request.method == "PATCH"):
            box.fill(str(count))
            box.press("Enter")

    def set_role(self, monster: str, role: str) -> None:
        with self.page.expect_response(lambda r: r.request.method == "PATCH"):
            self.page.get_by_label(f"Role of {monster}").select_option(label=role)

    def remove(self, monster: str) -> None:
        self.page.get_by_role("button", name=f"Remove {monster}").click()

    def rename(self, name: str) -> None:
        self.rename_button.click()
        self.name_box.fill(name)
        self.save_name_button.click()

    def delete(self) -> None:
        self.delete_button.click()
        self.dialog.get_by_role("button", name="Delete", exact=True).click()


class EnvironmentsPage(TomePage):
    """Browse Tomes › Environments: the DM's own map of where monsters live."""

    URL = "/dm/tomes/environments"

    def __init__(self, page: Page):
        super().__init__(page)
        self.new_name = page.get_by_label("New environment", exact=True)
        self.add_button = page.get_by_role("button", name="Add environment")
        self.name_error = page.get_by_test_id("error-name")
        self.cards = page.get_by_test_id("environment-card")
        self.empty = page.get_by_test_id("no-environments")
        self.dialog = page.get_by_role("dialog")

    def open(self, path: str = URL) -> "EnvironmentsPage":
        self.page.goto(path)
        return self

    def create(self, name: str) -> "EnvironmentsPage":
        self.new_name.fill(name)
        self.add_button.click()
        return self

    def card(self, name: str) -> Locator:
        return self.cards.filter(has=self.page.get_by_role("heading", name=name, exact=True))

    def take_out(self, monster: str, environment: str) -> None:
        self.page.get_by_role("button", name=f"Take {monster} out of {environment}").click()

    def delete(self, name: str) -> None:
        self.card(name).get_by_role("button", name=f"Delete {name}").click()
        self.dialog.get_by_role("button", name="Delete", exact=True).click()
