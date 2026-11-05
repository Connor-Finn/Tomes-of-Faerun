import re

from playwright.sync_api import Locator, Page, expect

from .guild_hall_page import TomePage


class DmCampaignsPage(TomePage):
    """DM Mode › Campaigns › Your campaigns: the campaigns you run, and a form to start one."""

    URL = "/dm/campaigns/campaigns"

    def __init__(self, page: Page):
        super().__init__(page)
        self.new_name = page.get_by_role("textbox", name="New campaign", exact=True)
        self.start_button = page.get_by_role("button", name="Start campaign")
        self.name_error = page.get_by_test_id("error-name")
        self.cards = page.get_by_test_id("campaign-card")
        self.empty = page.get_by_test_id("no-campaigns")

    def open(self, path: str = URL) -> "DmCampaignsPage":
        self.page.goto(path)
        return self

    def start(self, name: str) -> "CampaignTomePage":
        self.new_name.fill(name)
        self.start_button.click()
        return CampaignTomePage(self.page)

    def card(self, name: str) -> Locator:
        return self.cards.filter(has=self.page.get_by_role("link", name=name, exact=True))


class CampaignTomePage(TomePage):
    """One campaign, opened as a tome. The DM's edition has Overview, Party, Session log, Encounters
    and DM notes; the players' edition has Overview, Your character, Party and Session log."""

    def __init__(self, page: Page):
        super().__init__(page)
        self.status = self.tome.get_by_test_id("campaign-status")
        self.missing = page.get_by_test_id("campaign-missing")
        # Overview (DM)
        self.name = page.get_by_label("Name", exact=True)
        self.status_select = page.get_by_label("Status")
        self.description = page.get_by_label("Setting and story")
        self.save_overview = page.get_by_role("button", name="Save overview")
        self.delete_button = page.get_by_role("button", name="Delete campaign")
        # Overview (player)
        self.overview_dm = page.get_by_test_id("overview-dm")
        self.overview_text = page.get_by_test_id("overview-description")
        # Party
        self.attached_party = page.get_by_test_id("attached-party")
        self.party_select = page.get_by_role("combobox", name="Party", exact=True)
        self.attach_party_button = page.get_by_role("button", name="Attach party")
        self.player_cards = page.get_by_test_id("player-card")
        # Session log
        self.session_date = page.get_by_label("Played on")
        self.session_title = page.get_by_label("Title", exact=True)
        self.session_summary = page.get_by_label("What happened")
        self.add_session_button = page.get_by_role("button", name="Add to the log")
        self.save_session_button = page.get_by_role("button", name="Save session")
        self.sessions = page.get_by_test_id("session-entry")
        self.session_titles = self.sessions.locator(".session-title")
        self.no_sessions = page.get_by_test_id("no-sessions")
        # Encounters
        self.collection_select = page.get_by_label("Monster collection")
        self.add_encounter_button = page.get_by_role("button", name="Add encounter")
        self.encounters = page.get_by_test_id("encounter")
        self.encounter_totals = page.get_by_test_id("encounter-totals")
        self.no_encounters = page.get_by_test_id("no-encounters")
        # DM notes
        self.dm_notes = page.get_by_role("textbox", name="DM notes", exact=True)
        self.save_notes = page.get_by_role("button", name="Save notes")

    def open_dm(self, campaign_id: int, page: str = "overview") -> "CampaignTomePage":
        self.page.goto(f"/dm/campaigns/c/{campaign_id}/{page}")
        return self

    def open_player(self, campaign_id: int, page: str = "overview") -> "CampaignTomePage":
        self.page.goto(f"/play/campaigns/c/{campaign_id}/{page}")
        return self

    def attach_party(self, name: str) -> "CampaignTomePage":
        self.party_select.select_option(label=name)
        self.attach_party_button.click()
        return self

    def player_card(self, player: str) -> Locator:
        return self.player_cards.filter(has=self.page.locator(".player-name", has_text=player))

    def add_session(self, title: str, played_on: str, summary: str = "") -> "CampaignTomePage":
        self.session_date.fill(played_on)
        self.session_title.fill(title)
        self.session_summary.fill(summary)
        # Wait for the save: the form clears itself afterwards, so typing the next one too soon gets wiped.
        with self.page.expect_response(lambda r: r.request.method == "POST" and r.url.endswith("/sessions")):
            self.add_session_button.click()
        expect(self.session_title).to_have_value("")
        return self

    def edit_session(self, title: str) -> "CampaignTomePage":
        self.page.get_by_role("button", name=f"Edit {title}").click()
        return self

    def add_encounter(self, collection: str) -> "CampaignTomePage":
        self.collection_select.select_option(label=collection)
        self.add_encounter_button.click()
        return self

    def encounter(self, collection: str) -> Locator:
        return self.encounters.filter(has=self.page.get_by_role("link", name=collection, exact=True))

    def take_off(self, collection: str) -> "CampaignTomePage":
        self.page.get_by_role("button", name=f"Take {collection} off the campaign").click()
        return self


class PartiesPage(TomePage):
    """The Parties page, in either mode. A DM forms parties and invites players; a player accepts,
    declines and leaves."""

    DM_URL = "/dm/campaigns/parties"
    PLAYER_URL = "/play/campaigns/parties"

    def __init__(self, page: Page):
        super().__init__(page)
        # DM
        self.new_name = page.get_by_role("textbox", name="New party", exact=True)
        self.form_button = page.get_by_role("button", name="Form party")
        self.party_cards = page.get_by_test_id("party-card")
        self.invite_email = page.get_by_role("textbox", name="Invite a player by email")
        self.invite_button = page.get_by_role("button", name="Send invitation")
        self.invite_error = page.get_by_test_id("error-email")
        self.members = page.get_by_test_id("member")
        self.invited = page.get_by_test_id("invited")
        self.disband_button = page.get_by_role("button", name="Disband party")
        # Player
        self.invitations = page.get_by_test_id("invitation")
        self.no_parties = page.get_by_test_id("no-parties")

    def open_dm(self) -> "PartiesPage":
        self.page.goto(self.DM_URL)
        return self

    def open_player(self) -> "PartiesPage":
        self.page.goto(self.PLAYER_URL)
        return self

    def form(self, name: str) -> "PartiesPage":
        self.new_name.fill(name)
        self.form_button.click()
        return self

    def invite(self, email: str) -> "PartiesPage":
        self.invite_email.fill(email)
        self.invite_button.click()
        return self

    def accept(self, party: str) -> "PartiesPage":
        self.page.get_by_role("button", name=f"Accept the invitation to {party}").click()
        return self

    def decline(self, party: str) -> "PartiesPage":
        self.page.get_by_role("button", name=f"Decline the invitation to {party}").click()
        return self

    def leave(self, party: str) -> "PartiesPage":
        self.page.get_by_role("button", name=f"Leave {party}").click()
        self.page.get_by_role("dialog").get_by_role("button", name="Leave").click()
        return self


class CampaignCharacterPage(CampaignTomePage):
    """Player Mode › a campaign › Your character (and the DM's read-only view of it)."""

    def __init__(self, page: Page):
        super().__init__(page)
        self.bring_form = page.get_by_test_id("bring-character")
        self.bring_button = page.get_by_role("button", name="Bring this character")
        self.no_ready = page.get_by_test_id("no-ready-characters")
        self.instance = page.get_by_test_id("instance")
        self.hp_bar = page.get_by_test_id("hp-bar")
        self.current_hp = page.get_by_label("Current HP")
        self.temp_hp = page.get_by_label("Temporary HP")
        self.update_hp = page.get_by_role("button", name="Update HP")
        self.long_rest = page.get_by_role("button", name="Long rest")
        self.level_up = page.get_by_role("link", name=re.compile(r"^Level up to \d+$"))
        self.level_controls = page.get_by_test_id("level-controls")
        self.xp_total = page.get_by_test_id("xp-total")
        self.xp_gained = page.get_by_label("XP gained")
        self.add_xp_button = page.get_by_role("button", name="Add XP")
        self.levels_owed = page.get_by_test_id("levels-owed")
        self.level_up_blocked = page.get_by_test_id("level-up-blocked")
        self.leave_button = page.get_by_role("button", name="Leave with this character")
        self.dm_notes = page.get_by_test_id("dm-notes")
        self.dm_note = page.get_by_test_id("dm-note")
        self.origin = page.get_by_test_id("instance-origin")
        self.warnings = page.get_by_test_id("sheet-warnings")
        self.inventory_items = page.get_by_test_id("inventory-item")
        self.used_items = page.get_by_test_id("used-items")
        self.spells_to_copy = page.get_by_test_id("spells-to-copy")
        # DM view
        self.manage = page.get_by_role("link", name="Manage in the control panel")

    def bring(self, character: str) -> "CampaignCharacterPage":
        self.page.get_by_role("radio", name=re.compile(f"^{character}")).check()
        self.bring_button.click()
        return self

    def tab(self, name: str) -> "CampaignCharacterPage":
        """name: Sheet, Spellbook, Inventory or Features"""
        self.page.get_by_role("tab", name=name).click()
        return self

    def stat(self, key: str) -> Locator:
        return self.page.get_by_test_id(f"stat-{key}").locator(".stat-value")

    def add_xp(self, amount: int) -> "CampaignCharacterPage":
        self.xp_gained.fill(str(amount))
        self.add_xp_button.click()
        return self

    def item(self, name: str) -> Locator:
        return self.inventory_items.filter(has=self.page.get_by_role("button", name=name, exact=True))

    def set_hp(self, current: int, temp: int = 0) -> "CampaignCharacterPage":
        self.current_hp.fill(str(current))
        self.temp_hp.fill(str(temp))
        self.update_hp.click()
        return self


class LevelUpPage:
    """Player Mode › a campaign › Your character › Level up: one level, the new picks and hit points."""

    def __init__(self, page: Page):
        self.page = page
        self.root = page.get_by_test_id("level-up")
        self.heading = page.get_by_role("heading", level=1)
        self.changes = page.get_by_test_id("level-up-changes")
        self.roadmap_note = page.get_by_test_id("level-up-roadmap")
        self.no_picks = page.get_by_test_id("no-picks")
        self.subclass = page.get_by_test_id("level-up-subclass")
        self.picks_left = page.get_by_test_id("picks-left")
        self.lock_notice = page.get_by_test_id("lock-notice")
        self.errors = page.get_by_test_id("level-up-errors")
        self.blocked = page.get_by_test_id("level-up-blocked")
        self.confirm_button = page.get_by_role("button", name=re.compile(r"^Level up to \d+$"))
        self.not_now = page.get_by_role("link", name="Not now")

    def open(self, campaign_id: int) -> "LevelUpPage":
        self.page.goto(f"/play/campaigns/c/{campaign_id}/character/level-up")
        return self

    def hp_option(self, method: str) -> Locator:
        """method: average, roll or max"""
        return self.page.get_by_test_id(f"hp-{method}")

    def choose_hp(self, method: str) -> "LevelUpPage":
        """method: average, roll or max. The radio sits under its card, so click the card."""
        self.hp_option(method).click()
        expect(self.hp_option(method).get_by_role("radio")).to_be_checked()
        return self

    def roll_hp(self) -> "LevelUpPage":
        self.page.get_by_role("button", name=re.compile(r"^Roll a d\d+$")).click()
        return self

    def choose_subclass(self, name: str) -> "LevelUpPage":
        self.subclass.locator("label", has_text=name).click()
        return self

    def slot(self, slot_id: str) -> Locator:
        return self.page.get_by_test_id(f"level-up-slot-{slot_id}")

    def confirm(self) -> None:
        self.confirm_button.click()


class ControlPanelPage(CampaignTomePage):
    """DM Mode › a campaign › Control panel: campaign rules, and each player's level, items, spells and notes."""

    def __init__(self, page: Page):
        super().__init__(page)
        self.rules_form = page.get_by_role("form", name="Campaign rules")
        self.save_rules = page.get_by_role("button", name="Save rules")
        self.players = page.get_by_test_id("control-player")
        # One player
        self.level_panel = page.get_by_test_id("level-panel")
        self.level = page.get_by_role("spinbutton", name="Level", exact=True)
        self.set_level_button = page.get_by_role("button", name="Set level")
        self.xp = page.get_by_role("spinbutton", name="XP", exact=True)
        self.set_xp_button = page.get_by_role("button", name="Set XP")
        self.item_search = page.get_by_role("searchbox", name="Give an item")
        self.item_quantity = page.get_by_label("How many")
        self.inventory = page.get_by_test_id("dm-inventory-item")
        self.spell_search = page.get_by_role("searchbox", name="Grant a spell")
        self.granted = page.get_by_test_id("granted-spell")
        self.note_box = page.get_by_role("textbox", name="Your note")
        self.send_note_button = page.get_by_role("button", name="Send note")
        self.notes = page.get_by_test_id("dm-note")

    def open(self, campaign_id: int, instance_id: int | None = None) -> "ControlPanelPage":
        return self.open_dm(campaign_id, f"control/{instance_id}" if instance_id else "control")

    def set_levelling(self, label: str) -> "ControlPanelPage":
        self.rules_form.locator("label.choice-card", has_text=label).click()
        return self

    def hp_method(self, label: str) -> Locator:
        return self.rules_form.get_by_role("checkbox", name=label, exact=True)

    def manage(self, character: str) -> "ControlPanelPage":
        self.page.get_by_role("link", name=f"Manage {character}").click()
        return self

    def set_level(self, level: int) -> "ControlPanelPage":
        self.level.fill(str(level))
        self.set_level_button.click()
        return self

    def give(self, item: str, quantity: int = 1) -> "ControlPanelPage":
        self.item_quantity.fill(str(quantity))
        self.item_search.fill(item)
        self.page.get_by_role("button", name=f"Give {item}", exact=True).click()
        return self

    def grant(self, spell: str) -> "ControlPanelPage":
        self.spell_search.fill(spell)
        self.page.get_by_role("button", name=f"Grant {spell}", exact=True).click()
        return self

    def send_note(self, text: str) -> "ControlPanelPage":
        self.note_box.fill(text)
        self.send_note_button.click()
        return self
