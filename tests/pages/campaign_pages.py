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
        self.level_up = page.get_by_role("link", name="Level up or change")
        self.leave_button = page.get_by_role("button", name="Leave with this character")
        self.dm_note = page.get_by_test_id("dm-note")
        self.origin = page.get_by_test_id("instance-origin")
        # DM view
        self.note_box = page.get_by_label(re.compile(r"^Your note to "))
        self.save_note = page.get_by_role("button", name="Save note")

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

    def set_hp(self, current: int, temp: int = 0) -> "CampaignCharacterPage":
        self.current_hp.fill(str(current))
        self.temp_hp.fill(str(temp))
        self.update_hp.click()
        return self
