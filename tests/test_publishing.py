"""Publishing characters: share one as a template, and copy what other players published.

The main story uses two browsers: the author publishes in one, and another player finds the
character and copies it in the other.
"""
from __future__ import annotations

import re
import uuid

import pytest
from playwright.sync_api import Browser, Page, expect

from builds import aldric, blank
from conftest import API_HEADERS
from pages import CharacterPage, LoginPage
from pages.sharing_pages import PublishedCharactersPage, PublishPage


def post(page: Page, url: str, data: dict | None = None, method: str = "post") -> dict:
    response = getattr(page.request, method)(url, data=data or {}, headers=API_HEADERS)
    assert response.ok, response.text()
    return response.json()


def give_character(page: Page, name: str = "Aldric Vane") -> dict:
    return post(page, "/api/characters", {"build": {**aldric(), "name": name}})["character"]


@pytest.fixture
def hero() -> str:
    """A name only this test uses: published characters are visible to every test's players."""
    return f"Sir Corwin {uuid.uuid4().hex[:6]}"


@pytest.fixture
def reader(create_user) -> dict:
    return create_user(name="Bryn Ashdown")


@pytest.fixture
def reader_page(browser: Browser, browser_context_args: dict, reader: dict) -> Page:
    """A second player in their own browser. `logged_in_page` is the author."""
    context = browser.new_context(**browser_context_args)
    page = context.new_page()
    LoginPage(page).open().login(reader["email"], reader["password"])
    expect(page).to_have_url(re.compile(r"/guild-hall$"))
    yield page
    context.close()


# ------------------------------------------------------------------ the whole story
def test_publish_a_character_and_another_player_copies_it(
        logged_in_page: Page, reader_page: Page, user: dict, hero: str):
    give_character(logged_in_page, hero)
    author = PublishPage(logged_in_page).open()
    expect(author.none_published).to_be_visible()

    author.character.select_option(label=f"{hero}: Level 1 Human Fighter")
    expect(author.roadmap_note).to_contain_text(f"{hero} has no roadmaps.")
    author.description.fill("Holds the line so your casters don't have to.")
    author.publish_button.click()
    expect(author.dialog).to_contain_text(f"editing {hero} later won't change it")
    author.dialog.get_by_role("button", name="Publish", exact=True).click()

    expect(logged_in_page.get_by_test_id("flash-success").last).to_have_text(
        f"{hero} is published. Other players can now start from it.")
    expect(author.published(hero)).to_contain_text("Holds the line")
    expect(author.published(hero).get_by_test_id("published-facts")).to_contain_text("Not copied yet")

    # In the other player's browser: Create a character › Published by other players
    reader_page.goto("/play/characters/create")
    reader_page.get_by_role("link", name="Browse published characters").click()
    browse = PublishedCharactersPage(reader_page)
    expect(browse.page_title).to_have_text("Published characters")
    card = browse.card(hero)
    expect(card).to_contain_text("Level 1 Human Fighter · Acolyte")
    expect(card.get_by_test_id("published-author")).to_have_text(f"Published by {user['name']}")
    browse.use(hero)

    expect(reader_page).to_have_url(re.compile(r"/play/characters/c/\d+/sheet$"))
    expect(reader_page.get_by_test_id("flash-success").last).to_have_text(f"{hero} joined your characters.")
    expect(CharacterPage(reader_page).title).to_have_text(hero)

    # Back with the author: the copy is counted
    logged_in_page.reload()
    expect(author.published(hero).get_by_test_id("published-facts")).to_contain_text("Copied once")


def test_a_published_character_is_a_fixed_copy(logged_in_page: Page, reader_page: Page, hero: str):
    character = give_character(logged_in_page, hero)
    post(logged_in_page, "/api/published", {"character_id": character["id"]})
    post(logged_in_page, f"/api/characters/{character['id']}", {"name": f"{hero} the Bold"}, method="patch")

    browse = PublishedCharactersPage(reader_page).open()
    expect(browse.card(hero)).to_have_count(1)
    expect(browse.card(f"{hero} the Bold")).to_have_count(0)


def test_your_own_publications_are_marked(logged_in_page: Page, hero: str):
    character = give_character(logged_in_page, hero)
    post(logged_in_page, "/api/published", {"character_id": character["id"]})
    browse = PublishedCharactersPage(logged_in_page).open()
    expect(browse.card(hero).get_by_test_id("published-author")).to_have_text("Published by you")


def test_publish_from_the_character_sheet(logged_in_page: Page, hero: str):
    character = give_character(logged_in_page, hero)
    CharacterPage(logged_in_page).open_character(character["id"])
    logged_in_page.get_by_role("link", name="Publish", exact=True).click()
    publish = PublishPage(logged_in_page)
    expect(publish.page_title).to_have_text("Publish a character")
    expect(publish.character).to_have_value(str(character["id"]))


# ------------------------------------------------------------------ rules
def test_drafts_cannot_be_published(logged_in_page: Page):
    post(logged_in_page, "/api/characters", {"build": blank(name="Half-written")})
    publish = PublishPage(logged_in_page).open()
    expect(publish.nothing_to_publish).to_contain_text("Finish one of your drafts first.")
    expect(publish.publish_button).to_have_count(0)


def test_choose_a_character_before_publishing(logged_in_page: Page):
    give_character(logged_in_page)
    publish = PublishPage(logged_in_page).open()
    publish.publish_button.click()
    expect(publish.character_error).to_have_text("Choose one of your finished characters.")
    expect(publish.dialog).to_have_count(0)


def test_the_same_character_cannot_be_published_twice_unchanged(logged_in_page: Page, hero: str):
    give_character(logged_in_page, hero)
    publish = PublishPage(logged_in_page).open().publish(hero)
    expect(publish.mine).to_have_count(1)
    publish.publish(hero)
    expect(publish.character_error).to_have_text(f"{hero} is already published exactly as it is now.")
    expect(publish.mine).to_have_count(1)


def test_unpublishing_keeps_copies_players_made(logged_in_page: Page, reader_page: Page, hero: str):
    character = give_character(logged_in_page, hero)
    published = post(logged_in_page, "/api/published", {"character_id": character["id"]})["published"]
    post(reader_page, "/api/characters", {"published": published["id"]})

    PublishPage(logged_in_page).open().unpublish(hero)
    expect(logged_in_page.get_by_test_id("flash-info").last).to_contain_text("Copies other players made are still theirs.")

    browse = PublishedCharactersPage(reader_page).open()
    expect(browse.card(hero)).to_have_count(0)
    reader_page.goto("/play/characters/my-characters")
    expect(reader_page.get_by_test_id("character-card")).to_contain_text(hero)


def test_search_and_filter_published_characters(logged_in_page: Page, create_user):
    unique = create_user()["email"].split("@")[0][-6:]  # keeps this test's names apart from other tests'
    give_character(logged_in_page, f"Corwin {unique}")
    give_character(logged_in_page, f"Dellan {unique}")
    for c in logged_in_page.request.get("/api/characters").json()["characters"]:
        if unique in c["name"]:
            post(logged_in_page, "/api/published", {"character_id": c["id"]})

    browse = PublishedCharactersPage(logged_in_page).open()
    browse.search.fill(unique)
    expect(browse.cards).to_have_count(2)
    browse.search.fill(f"Dellan {unique}")
    expect(browse.cards).to_have_count(1)
    browse.search.fill(unique)
    browse.class_filter.select_option(label="Wizard")
    expect(browse.empty).to_have_text("No published characters match.")
    browse.class_filter.select_option(label="Fighter")
    expect(browse.cards).to_have_count(2)
