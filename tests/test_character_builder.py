"""The character builder: Standard build (free tabs) and Easy build (guided wizard).

The builder only shows what the rules engine answers, so these tests check the experience:
filling in a whole character, denied options being refused (Standard) or hidden (Easy), drafts,
and editing an existing character.
"""
import re

from playwright.sync_api import Page, expect

from conftest import API_HEADERS
from pages import BuilderPage, CharacterPage, CreateCharacterPage


def test_build_a_complete_fighter_in_standard_build(logged_in_page: Page):
    b = BuilderPage(logged_in_page).open_new("standard")
    expect(b.heading).to_have_text("A new character")
    expect(b.tab("Name and level")).to_have_attribute("aria-selected", "true")

    logged_in_page.get_by_label("Character name").fill("Brenna Stoutarm")
    logged_in_page.get_by_label("Alignment").select_option(label="Neutral Good")
    b.wait_for_check()
    expect(b.tab_mark("basics")).to_have_text(re.compile("✓"))

    b.go_to("Class").choose_card("fighter")
    b.pick("class:proficiency-0", "Athletics", "Survival")
    b.pick("feature:fighter-fighting-style", "Defense")

    b.go_to("Race").choose_card("dwarf")
    b.choose_card("hill-dwarf")
    b.pick("trait:tool-proficiency", "Smith's Tools")

    b.go_to("Ability scores")
    b.set_standard_array(str=15, dex=10, con=14, int=8, wis=13, cha=12)
    expect(logged_in_page.get_by_test_id("score-con")).to_have_text("16")   # 14 + dwarf 2

    b.go_to("Background").choose_card("acolyte")
    b.pick("background:languages", "Giant", "Orc")

    b.go_to("Equipment")
    for slot_id, label in [("equipment:class-0", "(a) Chain Mail"),
                           ("equipment:class-1", "(a) A martial weapon and Shield"),
                           ("equipment:class-2", "(b) 2 × Handaxe"),
                           ("equipment:class-3", "(b) Explorer's Pack"),
                           ("equipment:background-0", "Amulet")]:
        b.pick(slot_id, label)
    b.pick("equipment:class-1:a0", "Warhammer")
    expect(logged_in_page.get_by_test_id("builder-ac")).to_contain_text("Armour class 19")  # 16 + shield 2 + Defense 1

    b.go_to("Review")
    expect(logged_in_page.get_by_test_id("review-complete")).to_be_visible()
    expect(b.status).to_have_text("Complete: ready to play.")
    b.save()

    sheet = CharacterPage(logged_in_page)
    expect(logged_in_page).to_have_url(re.compile(r"/play/characters/c/\d+/sheet$"))
    expect(logged_in_page.get_by_test_id("flash-success")).to_have_text("Brenna Stoutarm is ready for adventure.")
    expect(sheet.title).to_have_text("Brenna Stoutarm")
    expect(sheet.draft_notice).to_have_count(0)
    expect(sheet.stat("ac")).to_have_text("19")
    expect(sheet.stat("hp")).to_have_text("14")   # d10 + CON 3 + Dwarven Toughness 1


def test_standard_build_shows_denied_options_and_refuses_them(logged_in_page: Page):
    b = BuilderPage(logged_in_page).open_new("standard")
    b.go_to("Class").choose_card("wizard")
    b.go_to("Spells")
    sacred_flame = b.chip("spells:cantrips", "Sacred Flame")
    expect(sacred_flame).to_have_class(re.compile("denied"))
    sacred_flame.click()
    expect(b.slot("spells:cantrips").get_by_test_id("slot-denied")).to_have_text(
        "You can't take Sacred Flame: It isn't on your class's spell list.")
    expect(sacred_flame).to_have_attribute("aria-pressed", "false")


def test_easy_build_hides_options_you_cant_take(logged_in_page: Page):
    b = BuilderPage(logged_in_page).open_new("easy")
    expect(b.step_title).to_have_text("Class")
    b.choose_card("wizard")
    b.next_button.click()                      # Race
    b.next_button.click()                      # Ability scores
    b.next_button.click()                      # Background
    b.next_button.click()                      # Spells
    expect(b.step_title).to_have_text("Spells")
    expect(b.chip("spells:cantrips", "Fire Bolt")).to_be_visible()
    expect(b.chip("spells:cantrips", "Sacred Flame")).to_have_count(0)
    expect(b.slot("spells:cantrips")).to_contain_text("options you can't take are hidden")
    # Help is open by default in Easy build
    expect(b.slot("spells:cantrips").get_by_test_id("help-text")).to_contain_text("Cantrips are spells")
    b.back_button.click()
    expect(b.step_title).to_have_text("Background")


def test_easy_build_skips_spells_for_classes_without_them(logged_in_page: Page):
    b = BuilderPage(logged_in_page).open_new("easy")
    b.choose_card("fighter")
    steps = logged_in_page.get_by_role("list", name="Steps")
    expect(steps).not_to_contain_text("Spells")


def test_easy_build_creates_characters_up_to_level_3(logged_in_page: Page):
    b = BuilderPage(logged_in_page).open_new("easy").next_until("Name and level")
    levels = logged_in_page.get_by_label("Starting level").locator("option")
    expect(levels).to_have_text(["Level 1", "Level 2", "Level 3"])

    standard = BuilderPage(logged_in_page).open_new("standard")
    expect(logged_in_page.get_by_label("Starting level").locator("option")).to_have_count(20)
    expect(standard.heading).to_be_visible()


def test_spell_picker_search_add_and_remove(logged_in_page: Page):
    b = BuilderPage(logged_in_page).open_new("standard")
    b.go_to("Class").choose_card("wizard")
    b.go_to("Spells")
    for spell in ["Magic Missile", "Shield", "Sleep", "Mage Armor", "Detect Magic", "Find Familiar"]:
        b.add_spell("spells:spellbook", spell)
    book = b.slot("spells:spellbook")
    expect(book.get_by_test_id("slot-count")).to_have_text(re.compile(r"Pick 6 · 6 chosen"))
    expect(book.get_by_test_id("picked").get_by_role("listitem")).to_have_count(6)

    # The book is full: a seventh spell is refused until one is removed
    book.get_by_label("Search spells").fill("Burning Hands")
    book.get_by_role("button", name="Add Burning Hands", exact=True).click()
    expect(book.get_by_test_id("slot-denied")).to_have_text("You can pick 6. Remove one first.")
    with logged_in_page.expect_response("**/api/characters/check"):
        book.get_by_role("button", name="Remove Sleep").click()
    b.add_spell("spells:spellbook", "Burning Hands")
    expect(book.get_by_test_id("picked")).to_contain_text("Burning Hands")
    expect(book.get_by_test_id("picked")).not_to_contain_text("Sleep")

    # Higher-level spells are listed but refused at level 1
    book.get_by_label("Search spells").fill("Fireball")
    book.get_by_role("button", name="Add Fireball", exact=True).click()
    expect(book.get_by_test_id("slot-denied")).to_have_text("You can't take Fireball: You can't cast level 3 spells yet.")


def test_point_buy_counts_points(logged_in_page: Page):
    b = BuilderPage(logged_in_page).open_new("easy")
    b.next_button.click()
    b.next_button.click()
    logged_in_page.get_by_label("Point buy").check()
    points = logged_in_page.get_by_test_id("points-left")
    expect(points).to_have_text("27 of 27 points left")
    for _ in range(7):
        logged_in_page.get_by_role("button", name="Raise Strength").click()
    expect(logged_in_page.get_by_test_id("base-str")).to_have_text("15")
    expect(points).to_have_text("18 of 27 points left")
    expect(logged_in_page.get_by_role("button", name="Raise Strength")).to_be_disabled()   # 15 is the most


def test_rule_breaking_scores_are_flagged_on_their_tab(logged_in_page: Page):
    b = BuilderPage(logged_in_page).open_new("standard")
    b.go_to("Ability scores")
    b.set_standard_array(str=15, dex=15, con=13, int=12, wis=10, cha=8)
    b.wait_for_check()
    expect(b.tab_mark("abilities")).to_have_text(re.compile("!"))
    expect(b.errors).to_contain_text("The standard array is 15, 14, 13, 12, 10 and 8")
    b.save_button.click()
    expect(b.errors).to_contain_text("The standard array")
    expect(logged_in_page).to_have_url(re.compile(r"/play/characters/new"))


def test_unfinished_characters_save_as_drafts(logged_in_page: Page):
    b = BuilderPage(logged_in_page).open_new("standard")
    logged_in_page.get_by_label("Character name").fill("Someday")
    b.go_to("Class").choose_card("rogue")
    b.go_to("Review")
    expect(logged_in_page.get_by_test_id("review-missing")).to_contain_text("Choose a race.")
    logged_in_page.get_by_test_id("review-missing").get_by_role("button", name="Race").first.click()
    expect(b.tab("Race")).to_have_attribute("aria-selected", "true")
    b.save()
    expect(logged_in_page.get_by_test_id("flash-success")).to_have_text("Someday was saved as a draft.")
    sheet = CharacterPage(logged_in_page)
    expect(sheet.draft_notice).to_be_visible()
    sheet.draft_notice.get_by_role("link", name="Continue building").click()
    expect(logged_in_page).to_have_url(re.compile(r"/play/characters/c/\d+/edit$"))
    expect(BuilderPage(logged_in_page).heading).to_have_text("Editing Someday")


def test_edit_a_character_from_a_template(logged_in_page: Page):
    character = CreateCharacterPage(logged_in_page).open().use_template("Aldric Vane")
    expect(character.title).to_have_text("Aldric Vane")
    logged_in_page.get_by_role("link", name="Edit in the builder").click()
    b = BuilderPage(logged_in_page)
    b.wait_for_check()
    expect(b.root).to_contain_text("Easy build")          # the template's build mode
    expect(b.status).to_have_text("Complete: ready to play.")
    b.next_until("Name and level")
    logged_in_page.get_by_label("Character name").fill("Sir Aldric")
    b.save()
    expect(character.title).to_have_text("Sir Aldric")
    expect(logged_in_page.get_by_test_id("flash-success")).to_have_text("Sir Aldric is ready for adventure.")


def test_builder_for_someone_elses_character(logged_in_page: Page):
    logged_in_page.goto("/play/characters/c/999999/edit")
    expect(logged_in_page.get_by_test_id("character-missing")).to_contain_text("Character not found.")


def test_create_page_links_to_both_build_modes(logged_in_page: Page):
    CreateCharacterPage(logged_in_page).open()
    logged_in_page.get_by_role("link", name="Start an Easy build").click()
    expect(logged_in_page).to_have_url(re.compile(r"/play/characters/new\?mode=easy$"))
    expect(BuilderPage(logged_in_page).root).to_contain_text("Easy build")
    logged_in_page.go_back()
    logged_in_page.get_by_role("link", name="Start a Standard build").click()
    expect(BuilderPage(logged_in_page).tab("Class")).to_be_visible()


def test_builder_fits_a_phone(browser, browser_context_args, user):
    from pages import LoginPage
    context = browser.new_context(**{**browser_context_args, "viewport": {"width": 375, "height": 740}})
    page = context.new_page()
    LoginPage(page).open(next_path="/play/characters/new?mode=standard").login(user["email"], user["password"])
    b = BuilderPage(page)
    b.wait_for_check()
    b.go_to("Class").choose_card("wizard")
    b.go_to("Spells")
    overflow = page.evaluate("document.documentElement.scrollWidth - document.documentElement.clientWidth")
    assert overflow <= 0
    context.close()


def test_check_endpoint_is_what_the_builder_uses(logged_in_page: Page):
    """The builder never decides a rule: the same answer comes straight from the API."""
    response = logged_in_page.request.post("/api/characters/check", headers=API_HEADERS,
                                           data={"build": {"class": "wizard"}, "build_mode": "easy"})
    slot = next(s for s in response.json()["slots"] if s["id"] == "spells:cantrips")
    denied = {o["label"] for o in slot["options"] if o.get("denied")}
    assert "Sacred Flame" in denied and "Fire Bolt" not in denied


def test_switching_class_drops_the_old_class_skill_picks(logged_in_page: Page):
    """Regression: every class's skill choice is the same slot, so a Rogue's Insight used to stay
    hidden in the Barbarian's skills ("2 chosen" with one visible) and block the character."""
    b = BuilderPage(logged_in_page).open_new("standard")
    b.go_to("Class").choose_card("rogue")
    b.pick("class:proficiency-0", "Insight", "Stealth")
    expect(b.slot("class:proficiency-0").get_by_test_id("slot-count")).to_contain_text("2 chosen")

    b.choose_card("barbarian")
    skills = b.slot("class:proficiency-0")
    expect(skills.get_by_test_id("slot-count")).to_contain_text("0 chosen")
    expect(skills.get_by_test_id("slot-error")).to_have_count(0)
    expect(skills.get_by_test_id("unavailable-pick")).to_have_count(0)

    b.pick("class:proficiency-0", "Athletics", "Perception")
    expect(skills.get_by_test_id("slot-count")).to_contain_text("2 chosen")
    expect(skills.get_by_test_id("slot-error")).to_have_count(0)
    expect(b.errors).to_have_count(0)
