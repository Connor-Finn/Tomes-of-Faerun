"""The items catalogue in the browser: searching, reading items, favourites, and items on characters."""
import re

from playwright.sync_api import Page, expect

from builds import aldric
from conftest import API_HEADERS
from pages import BuilderPage, CharacterPage, GuildHallPage, ItemPage, ItemPicker, ItemsPage

SRD_ITEMS = 476


def star_via_api(page: Page, *indexes: str) -> None:
    """Star items with the browser's own session (fast setup, no clicking)."""
    for index in indexes:
        assert page.request.put(f"/api/items/favourites/{index}", headers=API_HEADERS).ok


def create_aldric(page: Page, **items: int) -> dict:
    build = {**aldric(), "items": {k.replace("_", "-"): v for k, v in items.items()}}
    response = page.request.post("/api/characters", data={"build": build}, headers=API_HEADERS)
    assert response.status == 201, response.text()
    return response.json()["character"]


# ------------------------------------------------------------------ browsing
def test_find_the_items_from_the_guild_hall(logged_in_page: Page):
    hall = GuildHallPage(logged_in_page).open().switch_to("dm")
    hall.open_tome("Browse Tomes").go_to("Items")
    expect(logged_in_page).to_have_url(re.compile(r"/dm/tomes/items$"))
    items = ItemsPage(logged_in_page)
    expect(items.page_title).to_have_text("Items")
    expect(items.count).to_have_text(f"{SRD_ITEMS} items")
    expect(items.rows).to_have_count(25)
    expect(items.names.first).to_have_text("Abacus")
    expect(items.folio).to_have_text("Leaf 1 of 20")


def test_search_shows_gear_and_magic_together(logged_in_page: Page):
    items = ItemsPage(logged_in_page).open().search("rope")
    expect(items.count).to_have_text("4 items")
    expect(items.names).to_have_text(["Rope of Climbing", "Rope of Entanglement", "Rope, hempen (50 feet)", "Rope, silk (50 feet)"])
    # Magic items show their rarity, equipment its price
    expect(items.row("Rope of Climbing").get_by_test_id("item-value")).to_have_text("Uncommon")
    expect(items.row("Rope, hempen (50 feet)").get_by_test_id("item-value")).to_have_text("1 gp")
    expect(logged_in_page).to_have_url(re.compile(r"q=rope"))


def test_filter_by_kind_category_and_rarity(logged_in_page: Page):
    items = ItemsPage(logged_in_page).open().filter("Kind", "Magic items").filter("Category", "Ring").filter("Rarity", "Legendary")
    expect(items.count).to_have_text("5 items")
    expect(items.row("Ring of Three Wishes")).to_be_visible()
    expect(items.row("Ring of Invisibility").locator("abbr[title='Requires attunement']")).to_be_visible()

    # Rarity only applies to magic items, so it goes away with them
    items.filter("Kind", "Equipment")
    expect(logged_in_page.get_by_label("Rarity", exact=True)).to_have_count(0)
    expect(logged_in_page).not_to_have_url(re.compile(r"rarity="))

    items.clear_filters.click()
    expect(items.count).to_have_text(f"{SRD_ITEMS} items")


def test_sort_by_cost_survives_a_reload(logged_in_page: Page):
    items = ItemsPage(logged_in_page).open("/dm/tomes/items?kind=equipment&category=weapon&sort=cost")
    expect(items.names.first).to_have_text("Dart")  # 5 cp
    logged_in_page.reload()
    expect(logged_in_page.get_by_label("Sort by")).to_have_value("cost")
    expect(logged_in_page.get_by_label("Category", exact=True)).to_have_value("weapon")
    expect(items.names.first).to_have_text("Dart")


# ------------------------------------------------------------------ reading an item
def test_read_a_weapon(logged_in_page: Page):
    item = ItemsPage(logged_in_page).open().search("longsword").open_item("Longsword")
    expect(logged_in_page).to_have_url(re.compile(r"/dm/tomes/items/longsword$"))
    expect(item.page_title).to_have_text("Longsword")
    expect(item.current_entry).to_have_text("Items")
    expect(item.item_line).to_have_text("Martial Melee weapon")
    expect(item.line("cost")).to_have_text("15 gp")
    expect(item.line("damage")).to_have_text("1d8 slashing (1d10 two-handed)")
    expect(item.line("properties")).to_have_text("Versatile")

    item.back.click()
    expect(logged_in_page).to_have_url(re.compile(r"/dm/tomes/items\?q=longsword$"))


def test_read_armour_and_a_pack(logged_in_page: Page):
    item = ItemPage(logged_in_page).open_item("chain-mail")
    expect(item.line("armor-class")).to_have_text("16")
    expect(item.line("strength")).to_contain_text("13 or higher")
    expect(item.line("stealth")).to_have_text("Disadvantage")

    item.open_item("explorers-pack")
    expect(item.contents.get_by_role("listitem")).to_contain_text(["1 × Backpack", "10 × Torch"])


def test_read_a_magic_item(logged_in_page: Page):
    item = ItemPage(logged_in_page).open_item("bag-of-holding")
    expect(item.item_line).to_have_text("Wondrous item, uncommon")
    expect(item.text).to_contain_text("This bag has an interior space considerably larger than its outside dimensions")
    expect(item.block).to_have_class(re.compile(r"\bmagic\b"))

    item.open_item("armor")
    expect(item.line("variants")).to_have_text("Armor, +1, Armor, +2, Armor, +3")


def test_a_missing_item(logged_in_page: Page):
    item = ItemPage(logged_in_page).open_item("sword-of-a-thousand-truths")
    expect(item.missing).to_contain_text("No such item")


# ------------------------------------------------------------------ favourites
def test_star_items_and_show_only_favourites(logged_in_page: Page):
    items = ItemsPage(logged_in_page).open().search("rope")
    with logged_in_page.expect_response("**/api/items/favourites/rope-of-climbing"):
        items.star("Rope of Climbing").click()
    expect(items.star("Rope of Climbing")).to_have_attribute("aria-pressed", "true")
    with logged_in_page.expect_response("**/api/items/favourites/rope-silk-50-feet"):
        items.star("Rope, silk (50 feet)").click()

    items.search_box.fill("")
    items.only_favourites.check()
    expect(logged_in_page.get_by_text("Only my favourites (2)")).to_be_visible()
    expect(items.names).to_have_text(["Rope of Climbing", "Rope, silk (50 feet)"])

    with logged_in_page.expect_response("**/api/items/favourites/rope-of-climbing"):
        items.star("Rope of Climbing").click()
    expect(items.names).to_have_text(["Rope, silk (50 feet)"])
    logged_in_page.reload()
    expect(items.names).to_have_text(["Rope, silk (50 feet)"])


def test_no_favourite_items_yet(logged_in_page: Page):
    items = ItemsPage(logged_in_page).open("/dm/tomes/items?favourites=1")
    expect(items.empty).to_contain_text("You haven't starred any items yet")


def test_star_an_item_from_its_page(logged_in_page: Page):
    item = ItemPage(logged_in_page).open_item("potion-of-healing")
    expect(item.star).to_have_text("☆ Add to favourites")
    item.star.click()
    expect(logged_in_page.get_by_test_id("flash-success")).to_have_text("Potion of Healing is one of your favourites.")
    expect(item.star).to_have_text("★ Favourite")


# ------------------------------------------------------------------ items and characters
def test_an_item_shows_which_characters_carry_it(logged_in_page: Page):
    aldric_ = create_aldric(logged_in_page, bag_of_holding=1)
    item = ItemPage(logged_in_page).open_item("bag-of-holding")
    expect(item.carried_by.get_by_role("listitem")).to_have_text("Aldric Vane carried, added by you")
    item.carried_by.get_by_role("link", name="Aldric Vane").click()
    expect(logged_in_page).to_have_url(re.compile(rf"/play/characters/c/{aldric_['id']}/inventory$"))

    item.open_item("ring-of-three-wishes")
    expect(item.carried_by).to_contain_text("None of your characters carries one yet.")


def test_add_items_in_the_builder(logged_in_page: Page):
    star_via_api(logged_in_page, "potion-of-healing")
    character = create_aldric(logged_in_page)
    logged_in_page.goto(f"/play/characters/c/{character['id']}/edit?section=equipment")
    builder = BuilderPage(logged_in_page)
    expect(builder.tab("Equipment")).to_have_attribute("aria-selected", "true")
    picker = ItemPicker(logged_in_page)
    expect(picker.added).to_have_count(0)

    # Favourites come first
    expect(picker.result_names.first).to_have_text("Potion of Healing")
    picker.only_favourites.check()
    expect(picker.result_names).to_have_text(["Potion of Healing"])
    picker.only_favourites.uncheck()

    picker.search("bag of holding")
    picker.read("Bag of Holding")
    expect(picker.reader).to_contain_text("This bag has an interior space")
    with logged_in_page.expect_response("**/api/characters/check"):
        picker.add("Bag of Holding")
    picker.search("torch")
    with logged_in_page.expect_response("**/api/characters/check"):
        picker.add("Torch")
    with logged_in_page.expect_response("**/api/characters/check"):
        picker.quantity("Torch").fill("5")
    expect(picker.added).to_have_text([re.compile("Bag of Holding"), re.compile("Torch")])

    builder.save()
    expect(logged_in_page.get_by_test_id("flash-success")).to_be_visible()

    sheet = CharacterPage(logged_in_page).open_character(character["id"], "inventory")
    rows = logged_in_page.get_by_test_id("inventory-item")
    bag = rows.filter(has_text="Bag of Holding")
    expect(bag).to_contain_text("Added by you")
    expect(bag).to_contain_text("Wondrous Items, uncommon")
    # (the dungeoneer's pack mentions torches too, so find the row by its item button)
    torch = rows.filter(has=logged_in_page.get_by_role("button", name="Torch", exact=True))
    expect(torch.get_by_role("cell").nth(2)).to_have_text("5")
    expect(rows.filter(has_text="Longsword")).not_to_contain_text("Added by you")  # the starting kit
    expect(sheet.page_title).to_have_text("Inventory")


def test_remove_an_added_item(logged_in_page: Page):
    character = create_aldric(logged_in_page, potion_of_healing=2)
    logged_in_page.goto(f"/play/characters/c/{character['id']}/edit?section=equipment")
    picker = ItemPicker(logged_in_page)
    expect(picker.added).to_have_count(1)
    expect(picker.quantity("Potion of Healing")).to_have_value("2")
    with logged_in_page.expect_response("**/api/characters/check"):
        picker.remove("Potion of Healing")
    expect(picker.added).to_have_count(0)
    BuilderPage(logged_in_page).save()
    expect(logged_in_page.get_by_test_id("flash-success")).to_be_visible()
    CharacterPage(logged_in_page).open_character(character["id"], "inventory")
    expect(logged_in_page.get_by_test_id("inventory-item").filter(has_text="Potion of Healing")).to_have_count(0)


def test_read_items_in_a_characters_inventory(logged_in_page: Page):
    character = create_aldric(logged_in_page, bag_of_holding=1)
    star_via_api(logged_in_page, "longsword")
    CharacterPage(logged_in_page).open_character(character["id"], "inventory")
    sword = logged_in_page.get_by_test_id("inventory-item").filter(has_text="Longsword")
    expect(sword.get_by_role("button", name="Favourite Longsword")).to_have_attribute("aria-pressed", "true")

    reader = logged_in_page.get_by_test_id("inventory-reader")
    sword.get_by_role("button", name="Longsword", exact=True).click()
    expect(reader.get_by_test_id("item-reader")).to_contain_text("1d8 slashing")
    sword.get_by_role("button", name="Longsword", exact=True).click()
    expect(reader).to_have_count(0)

    logged_in_page.get_by_role("link", name="Change items").click()
    expect(logged_in_page).to_have_url(re.compile(rf"/play/characters/c/{character['id']}/edit\?section=equipment$"))
    expect(BuilderPage(logged_in_page).tab("Equipment")).to_have_attribute("aria-selected", "true")


def test_easy_build_starts_the_picker_on_equipment(logged_in_page: Page):
    b = BuilderPage(logged_in_page).open_new("easy")
    b.choose_card("fighter")
    b.next_until("Equipment")
    picker = ItemPicker(logged_in_page)
    expect(picker.kind).to_have_value("equipment")
    expect(picker.root.get_by_test_id("help-text").first).to_contain_text("magic item your Dungeon Master gave you")
