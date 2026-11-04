"""The Bestiary in the browser: searching monsters, reading stat blocks, collections and environments."""
import re

from playwright.sync_api import Page, expect

from conftest import API_HEADERS
from pages import (BestiaryPage, CollectionPage, CollectionsPage, EnvironmentsPage, GuildHallPage, MonsterPage,
                   TomePage)

SRD_MONSTERS = 334


def api_post(page: Page, url: str, **data) -> dict:
    """Set up data with the browser's own session (fast, no clicking)."""
    response = page.request.post(url, data=data, headers=API_HEADERS)
    assert response.ok, response.text()
    return response.json()


# ------------------------------------------------------------------ browsing
def test_find_the_bestiary_from_the_guild_hall(logged_in_page: Page):
    hall = GuildHallPage(logged_in_page).open().switch_to("dm")
    tome = hall.open_tome("Browse Tomes")
    tome.go_to("Bestiary")
    expect(logged_in_page).to_have_url(re.compile(r"/dm/tomes/bestiary$"))
    bestiary = BestiaryPage(logged_in_page)
    expect(bestiary.page_title).to_have_text("Bestiary")
    expect(bestiary.count).to_have_text(f"{SRD_MONSTERS} monsters")
    expect(bestiary.rows).to_have_count(25)
    expect(bestiary.names.first).to_have_text("Aboleth")


def test_search_by_name(logged_in_page: Page):
    bestiary = BestiaryPage(logged_in_page).open().search("red dragon")
    expect(bestiary.count).to_have_text("5 monsters")
    expect(bestiary.names).to_have_text(
        ["Adult Red Dragon", "Ancient Red Dragon", "Half-Red Dragon Veteran", "Red Dragon Wyrmling", "Young Red Dragon"])
    expect(logged_in_page).to_have_url(re.compile(r"q=red\+dragon"))  # the search is in the URL, so it can be shared


def test_a_search_with_no_matches(logged_in_page: Page):
    bestiary = BestiaryPage(logged_in_page).open().search("beholder")  # not in the SRD
    expect(bestiary.empty).to_contain_text("No monster in the tome matches that")
    expect(bestiary.count).to_have_text("0 monsters")


def test_filter_by_type_and_challenge_rating(logged_in_page: Page):
    bestiary = BestiaryPage(logged_in_page).open()
    bestiary.filter("Creature type", "Dragon").filter("Lowest CR", "20").filter("Sort by", "Challenge rating")
    expect(bestiary.count).to_have_text(re.compile(r"^\d+ monsters$"))
    expect(bestiary.names.first).to_have_text(re.compile("Ancient"))
    for cr in bestiary.rows.get_by_test_id("monster-cr").all_inner_texts():
        assert int(cr) >= 20
    expect(logged_in_page).to_have_url(re.compile(r"type=dragon.*cr_min=20|cr_min=20.*type=dragon"))

    bestiary.clear_filters.click()
    expect(bestiary.count).to_have_text(f"{SRD_MONSTERS} monsters")


def test_filters_survive_a_reload(logged_in_page: Page):
    BestiaryPage(logged_in_page).open("/dm/tomes/bestiary?type=undead&size=tiny")
    bestiary = BestiaryPage(logged_in_page)
    expect(bestiary.names).to_have_text(["Will-o'-Wisp"])
    expect(logged_in_page.get_by_label("Creature type")).to_have_value("undead")
    expect(logged_in_page.get_by_label("Size")).to_have_value("tiny")


def test_turn_the_bestiary_pages(logged_in_page: Page):
    bestiary = BestiaryPage(logged_in_page).open()
    expect(bestiary.folio).to_have_text("Leaf 1 of 14")
    expect(bestiary.prev_leaf).to_be_disabled()
    first = bestiary.names.first.inner_text()

    bestiary.next_leaf.click()
    expect(bestiary.folio).to_have_text("Leaf 2 of 14")
    expect(bestiary.names.first).not_to_have_text(first)
    expect(logged_in_page).to_have_url(re.compile(r"page=2"))

    logged_in_page.go_back()
    expect(bestiary.folio).to_have_text("Leaf 1 of 14")


# ------------------------------------------------------------------ stat blocks
def test_read_a_stat_block(logged_in_page: Page):
    monster = BestiaryPage(logged_in_page).open().search("adult red").open_monster("Adult Red Dragon")
    expect(logged_in_page).to_have_url(re.compile(r"/dm/tomes/bestiary/adult-red-dragon$"))
    expect(monster.page_title).to_have_text("Adult Red Dragon")
    expect(monster.current_entry).to_have_text("Bestiary")  # still in the Bestiary chapter
    expect(monster.stat_block.locator(".creature-line")).to_have_text("Huge dragon, chaotic evil")
    expect(monster.line("ac")).to_have_text("19 (natural armor)")
    expect(monster.line("hp")).to_have_text("256 (19d12+133)")
    expect(monster.line("speed")).to_have_text("40 ft., climb 40 ft., fly 80 ft.")
    expect(monster.ability("str")).to_have_text("27 (+8)")
    expect(monster.ability("dex")).to_have_text("10 (+0)")
    expect(monster.line("saving-throws")).to_have_text("Dex +6, Con +13, Wis +7, Cha +11")
    expect(monster.line("skills")).to_have_text("Perception +13, Stealth +6")
    expect(monster.line("damage-immunities")).to_have_text("fire")
    expect(monster.line("senses")).to_have_text("blindsight 60 ft., darkvision 120 ft., passive Perception 23")
    expect(monster.line("challenge")).to_have_text("17 (18,000 XP)")
    expect(monster.section("traits")).to_contain_text("Legendary Resistance (3/Day).")
    expect(monster.section("actions")).to_contain_text("Fire Breath (Recharge 5–6).")
    expect(monster.section("legendary-actions")).to_contain_text("Wing Attack (Costs 2 Actions).")


def test_back_to_the_bestiary_keeps_the_search(logged_in_page: Page):
    bestiary = BestiaryPage(logged_in_page).open().search("hobgoblin")
    expect(bestiary.count).to_have_text("1 monster")
    monster = bestiary.open_monster("Hobgoblin")
    monster.back.click()
    expect(logged_in_page).to_have_url(re.compile(r"/dm/tomes/bestiary\?q=hobgoblin$"))
    expect(bestiary.search_box).to_have_value("hobgoblin")
    expect(bestiary.names).to_have_text(["Hobgoblin"])


def test_an_unknown_monster_shows_a_blank_page(logged_in_page: Page):
    monster = MonsterPage(logged_in_page).open_monster("tarrasque-jr")
    expect(monster.missing).to_contain_text("No such monster")


# ------------------------------------------------------------------ collections
def test_a_new_dm_has_no_collections(logged_in_page: Page):
    collections = CollectionsPage(logged_in_page).open()
    expect(collections.empty).to_contain_text("No collections yet")


def test_save_a_monster_to_a_new_collection(logged_in_page: Page):
    monster = MonsterPage(logged_in_page).open_monster("goblin")
    expect(monster.saved_in).to_have_count(0)
    monster.add_to_collection(new="Warlock boss dungeon", role="Minion", count=4)
    expect(logged_in_page.get_by_test_id("flash-success").last).to_have_text("Goblin was added to Warlock boss dungeon.")
    expect(monster.saved_in).to_contain_text("Warlock boss dungeon 4 × Minion")

    # Adding more of the same monster adds to the count
    monster.add_to_collection("Warlock boss dungeon", role="Minion", count=2)
    expect(logged_in_page.get_by_test_id("flash-success").last).to_have_text("Warlock boss dungeon now has 6 × Goblin.")
    expect(monster.saved_in).to_contain_text("6 × Minion")

    monster.saved_in.get_by_role("link", name="Warlock boss dungeon").click()
    collection = CollectionPage(logged_in_page)
    expect(collection.page_title).to_have_text("Warlock boss dungeon")
    expect(collection.totals).to_have_text("6 monsters · 300 XP in all")
    expect(collection.group("minion").get_by_role("heading")).to_have_text("Minions")
    expect(collection.group("minion")).to_contain_text("Goblin")


def test_a_new_collection_needs_a_name(logged_in_page: Page):
    monster = MonsterPage(logged_in_page).open_monster("orc")
    monster.add_to_collection(new="")
    expect(monster.save_error).to_have_text("Give the collection a name.")


def test_build_an_encounter_with_minions_and_a_boss(logged_in_page: Page):
    collection = CollectionsPage(logged_in_page).open().start("The Hollow Crypt")
    expect(logged_in_page).to_have_url(re.compile(r"/dm/tomes/collections/\d+$"))
    expect(collection.page_title).to_have_text("The Hollow Crypt")
    expect(collection.empty).to_be_visible()
    collection_id = logged_in_page.url.rsplit("/", 1)[1]

    # Fill it through the API, then manage it in the browser
    for monster, role, count in [("skeleton", "minion", 6), ("ghoul", "none", 2), ("wight", "boss", 1)]:
        api_post(logged_in_page, f"/api/bestiary/collections/{collection_id}/monsters",
                 monster=monster, role=role, count=count)
    logged_in_page.reload()
    # 6 skeletons (50 XP), 2 ghouls (200 XP), 1 wight (700 XP)
    expect(collection.totals).to_have_text("9 monsters · 1,400 XP in all")
    expect(collection.group("boss")).to_contain_text("Wight")
    expect(collection.group("none").get_by_role("heading")).to_have_text("Without a role")

    collection.set_role("Ghoul", "Elite")
    expect(collection.group("elite")).to_contain_text("Ghoul")
    expect(collection.group("none")).to_have_count(0)

    collection.set_count("Skeleton", 10)
    expect(collection.totals).to_have_text("13 monsters · 1,600 XP in all")

    collection.remove("Wight")
    expect(logged_in_page.get_by_test_id("flash-info").last).to_have_text("Wight was removed from The Hollow Crypt.")
    expect(collection.group("boss")).to_have_count(0)
    expect(collection.totals).to_have_text("12 monsters · 900 XP in all")


def test_the_collection_list_shows_totals_and_roles(logged_in_page: Page):
    body = api_post(logged_in_page, "/api/bestiary/collections", name="Ambush on the road")
    cid = body["collection"]["id"]
    api_post(logged_in_page, f"/api/bestiary/collections/{cid}/monsters", monster="bandit", role="minion", count=5)
    api_post(logged_in_page, f"/api/bestiary/collections/{cid}/monsters", monster="bandit-captain", role="boss")

    collections = CollectionsPage(logged_in_page).open()
    card = collections.card("Ambush on the road")
    expect(card.get_by_test_id("collection-totals")).to_have_text("6 monsters · 575 XP")
    expect(card).to_contain_text("5 minions")
    expect(card).to_contain_text("1 boss")


def test_collection_names_must_be_unique(logged_in_page: Page):
    collections = CollectionsPage(logged_in_page).open()
    collections.start("Goblin warren")
    collections.open()
    collections.new_name.fill("goblin warren")
    collections.start_button.click()
    expect(collections.name_error).to_have_text("You already have a collection with that name.")


def test_rename_write_notes_and_delete_a_collection(logged_in_page: Page):
    collection = CollectionsPage(logged_in_page).open().start("Lair draft")
    collection.rename("Dragon's lair")
    expect(collection.page_title).to_have_text("Dragon's lair")

    expect(collection.save_notes_button).to_be_disabled()  # nothing to save yet
    collection.notes.fill("The dragon sleeps on the hoard. Kobolds keep watch.")
    collection.save_notes_button.click()
    expect(logged_in_page.get_by_test_id("flash-success").last).to_have_text("Notes saved.")
    logged_in_page.reload()
    expect(collection.notes).to_have_value("The dragon sleeps on the hoard. Kobolds keep watch.")

    collection.delete_button.click()
    expect(collection.dialog).to_contain_text("Delete Dragon's lair?")
    collection.dialog.get_by_role("button", name="Keep it").click()
    expect(collection.dialog).to_be_hidden()

    collection.delete()
    expect(logged_in_page).to_have_url(re.compile(r"/dm/tomes/collections$"))
    expect(logged_in_page.get_by_test_id("flash-info").last).to_have_text("Dragon's lair was deleted.")
    expect(CollectionsPage(logged_in_page).empty).to_be_visible()


def test_someone_elses_collection_is_not_found(logged_in_page: Page, other_api):
    theirs = other_api.post("/api/bestiary/collections", data={"name": "Secret plans"}).json()["collection"]
    TomePage(logged_in_page).open(f"/dm/tomes/collections/{theirs['id']}")
    expect(logged_in_page.get_by_test_id("collection-missing")).to_contain_text("Collection not found")


# ------------------------------------------------------------------ environments
def test_sort_monsters_into_an_environment(logged_in_page: Page):
    monster = MonsterPage(logged_in_page).open_monster("drow")
    monster.create_environment("Underdark")
    expect(monster.environment("Underdark")).to_be_checked()
    expect(logged_in_page.get_by_test_id("flash-success").last).to_have_text("Drow lives in Underdark.")

    monster.open_monster("roper")
    monster.environment("Underdark").check()
    expect(logged_in_page.get_by_test_id("flash-success").last).to_have_text("Roper lives in Underdark.")

    environments = EnvironmentsPage(logged_in_page).open()
    card = environments.card("Underdark")
    expect(card).to_contain_text("2 monsters")
    expect(card.get_by_role("link", name="Drow")).to_be_visible()

    card.get_by_role("link", name="Browse in the bestiary").click()
    bestiary = BestiaryPage(logged_in_page)
    expect(bestiary.count).to_have_text("2 monsters in Underdark")
    expect(bestiary.names).to_have_text(["Drow", "Roper"])
    expect(logged_in_page.get_by_label("My environment")).to_have_value(re.compile(r"\d+"))


def test_take_a_monster_out_and_delete_an_environment(logged_in_page: Page):
    env = api_post(logged_in_page, "/api/bestiary/environments", name="Haunted swamp")["environment"]
    logged_in_page.request.put(f"/api/bestiary/environments/{env['id']}/monsters/will-o-wisp", headers=API_HEADERS)

    environments = EnvironmentsPage(logged_in_page).open()
    expect(environments.card("Haunted swamp")).to_contain_text("1 monster")
    environments.take_out("Will-o'-Wisp", "Haunted swamp")
    expect(logged_in_page.get_by_test_id("flash-info").last).to_have_text("Will-o'-Wisp was taken out of Haunted swamp.")
    expect(environments.card("Haunted swamp")).to_contain_text("0 monsters")

    environments.delete("Haunted swamp")
    expect(environments.empty).to_be_visible()


def test_an_empty_environment_says_how_to_fill_it(logged_in_page: Page):
    env = api_post(logged_in_page, "/api/bestiary/environments", name="Feywild")["environment"]
    bestiary = BestiaryPage(logged_in_page).open(f"/dm/tomes/bestiary?environment={env['id']}")
    expect(bestiary.empty).to_contain_text("Nothing lives in Feywild yet")


def test_environment_names_must_be_unique(logged_in_page: Page):
    environments = EnvironmentsPage(logged_in_page).open().create("Desert")
    expect(environments.card("Desert")).to_be_visible()
    environments.create("DESERT")
    expect(environments.name_error).to_have_text("You already have an environment with that name.")
