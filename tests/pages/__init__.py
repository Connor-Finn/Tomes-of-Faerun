"""Page Object Model: one class per page, wrapping its locators and actions.

Tests then read like user stories ("login_page.login(...)") and when the UI
changes you fix ONE class instead of fifty tests.
"""
from .login_page import LoginPage
from .signup_page import SignupPage
from .guild_hall_page import GuildHallPage, TomePage
from .character_pages import BuilderPage, CharacterPage, CreateCharacterPage, MyCharactersPage
from .bestiary_pages import BestiaryPage, CollectionPage, CollectionsPage, EnvironmentsPage, MonsterPage

__all__ = ["LoginPage", "SignupPage", "GuildHallPage", "TomePage", "MyCharactersPage", "CreateCharacterPage",
           "CharacterPage", "BuilderPage", "BestiaryPage", "MonsterPage", "CollectionsPage", "CollectionPage",
           "EnvironmentsPage"]
