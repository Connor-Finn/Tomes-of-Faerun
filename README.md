# Tomes of Faerun

**A D&D adventure tool.** Build characters, browse spells, monsters and items, run campaigns with your party,
and practise the rules in a solo text adventure. Rules content comes from the free
[D&D 5e System Reference Document](https://www.dndbeyond.com/srd) via the [D&D 5e API](https://www.dnd5eapi.co/).

[![CI](https://github.com/Connor-Finn/Tomes-of-Faerun/actions/workflows/ci.yml/badge.svg)](https://github.com/Connor-Finn/Tomes-of-Faerun/actions/workflows/ci.yml)

It's also a showcase of end-to-end testing with **Playwright**: every feature ships with browser and API tests
that run on every push.

## Features

| Feature                         | Status       |
|---------------------------------|--------------|
| Accounts (sign-up, email verification, login, lockout, password reset, profile, avatar, admin) | ✅ Done |
| Rules data API (SRD spells, monsters, classes, races, equipment, magic items) | ✅ Done |
| Guild Hall hub, Player / Dungeon Master modes, tome layout | ✅ Done |
| Character rules engine and API (every SRD rule checked on the server) | ✅ Done |
| My characters, character sheets, premade templates, build mode | ✅ Done |
| Character builder: Standard (free tabs, levels 1 to 20) and Easy (guided tutorial, levels 1 to 3) | ✅ Done |
| Level roadmaps and publishing characters | 🛠 Planned |
| Bestiary: stat blocks, monster collections (minion / elite / boss), environments | ✅ Done |
| Spell catalogue (search, filters, full rules text), favourite spells, readable character spellbooks | ✅ Done |
| Items catalogue (equipment and magic items, search, filters, full descriptions), favourite items, adding items to characters | ✅ Done |
| Campaigns: overview, session log, encounters from your bestiary, private DM notes | ✅ Done |
| Parties: DMs invite players by email, players accept or decline | ✅ Done |
| Characters in campaigns: each player brings a copy (an instance) that levels up and tracks hit points; the DM reads it and leaves notes | ✅ Done |
| Party chat, friend requests, public parties and sharing characters | 🛠 Planned |
| Solo text adventure             | 🛠 Planned   |

## Tech stack

- **Front end:** React 18, TypeScript, React Router, Vite
- **Back end:** Python, Flask (JSON API), SQLAlchemy, SQLite
- **Testing:** Playwright for Python with pytest (page objects, fixtures, storage state, API tests, parallel runs)
- **CI:** GitHub Actions builds the app and runs the whole suite on every push and pull request

```
backend/     Flask API (one blueprint per area: auth, account, admin, rules, dev tools)
frontend/    React app (pages, components, API client)
tests/       Playwright tests and page objects
```

## How the app is laid out

After logging in you arrive at **the Guild Hall**. Pick **Player Mode** or **Dungeon Master Mode**, then take a tome
off the shelf. Each section is a tome: a table of contents on the left page and the open chapter on the right.

| Mode | Tomes |
|------|-------|
| Player | Campaigns, Character Manager, Solo Adventure (sealed for now) |
| Dungeon Master | Campaigns, Browse Tomes, Create Solo Adventure and Create Homebrew (both sealed for now) |

Every section, chapter and route is generated from one list in `frontend/src/lib/sections.tsx`. Chapters that aren't
built yet show what's planned for them.

## Run it locally

You need Python 3.11+ and Node 20+.

```bash
# 1. Back end
python -m venv .venv
source .venv/bin/activate            # Windows: .\.venv\Scripts\Activate.ps1
pip install -r backend/requirements.txt -r backend/requirements-dev.txt

# 2. Front end
cd frontend
npm install
npm run build                        # Flask serves the built app from frontend/dist
cd ..

# 3. Start
python backend/run.py                # http://127.0.0.1:5000
python backend/run.py --reset        # wipe the database and re-seed it
```

For front-end work with hot reload, run `python backend/run.py` and `npm run dev` (in `frontend/`) side by side and
open http://localhost:5173. Vite forwards API calls to Flask.

### Demo accounts

| Account                 | Password       | Notes                              |
|-------------------------|----------------|------------------------------------|
| admin@example.com       | Admin123!      | Admin: can open `/admin/users`     |
| user@example.com        | Password123!   | Regular adventurer                 |
| banned@example.com      | Password123!   | Login is refused (suspended)       |
| unverified@example.com  | Password123!   | Hasn't verified their email        |

No real email is sent. Verification and reset emails appear in the dev mailbox at **/mailbox**.

## Run the tests

The tests start their own copy of the app on a random port with a throwaway database, so nothing needs to be
running. Build the front end first (`npm run build` in `frontend/`), then:

```bash
python -m playwright install chromium    # once
pytest                                   # everything, headless
pytest -n 4                              # 4 tests in parallel
pytest -m api                            # only the API tests
pytest tests/test_login.py --headed --slowmo 500   # watch the browser
pytest --tracing on                      # record a trace for every test
playwright show-trace test-results/<test-folder>/trace.zip
```

When a test fails, a screenshot and trace are saved in `test-results/`, and CI uploads them as a build artifact.

### Testing patterns used

- **Page objects** (`tests/pages/`) so a UI change means fixing one class, not fifty tests
- **API-driven setup**: each test creates its own user through a test-only endpoint, which keeps tests independent
  and safe to run in parallel
- **Storage state**: the admin logs in once per run and every admin test reuses that session
- **Waiting on network**: `page.expect_response(...)` for actions in a single-page app that don't reload the page
- **Data-driven tests** with `pytest.mark.parametrize` for form validation and for every section of the app
- **Keyboard and mobile checks**: the mode switch works with arrow keys, and pages never scroll sideways at phone width
- **Rules tests without a browser**: `test_character_rules.py` checks one D&D rule per test against the engine
  directly, and a helper finishes builds for every class at levels 1 and 20 to prove each can be completed
- **API tests** with Playwright's `APIRequestContext`, including security checks (CSRF header, open redirects,
  no password hashes in responses)
- **Multiple browser contexts** in one test (an admin bans a user who then can't log in)

## Rules data

The SRD content ships with the app in `backend/tof/rules/data/` (the same data the free
[D&D 5e API](https://www.dnd5eapi.co) serves), so the app works offline and tests are deterministic.
Refresh it with `python backend/scripts/sync_rules.py`.

| Endpoint | What it does |
|----------|--------------|
| `GET /api/rules` | Every category with its entry count |
| `GET /api/rules/<category>?q=&page=&per_page=` | Search and page through a category (`spells`, `monsters`, `classes`, `races`, `equipment`, `magic-items`, …) |
| `GET /api/rules/<category>/<index>` | One full entry, e.g. `/api/rules/spells/fireball` |

Catalogue filters: spells take `level`, `school`, `class`, `ritual`, `concentration` and `sort=level`. Monsters take
`type`, `size`, `cr_min`, `cr_max` and `sort=cr`. Equipment takes `category`. Magic items take `rarity`, `category` and
`include_variants`. Add `facets=1` to get the filter options, and `order=desc` to reverse the sort.

The items catalogue (`GET /api/items`, logged in) puts equipment and magic items in one list. It takes `q`, `kind`
(`equipment` or `magic`), `category`, `rarity`, `attunement`, `favourites=1` and `sort` (`name`, `category`, `cost`,
`rarity`). `GET /api/items/<index>` adds which of your characters carry the item, and
`PUT`/`DELETE /api/items/favourites/<index>` star and unstar it.

## Characters

A character is stored as its **build**: only the player's decisions (race, class, level, ability scores and one list
of picks per choice). The rules engine in `backend/tof/characters/engine.py` works out everything else (hit points,
armour class, skills, attacks, spell slots) from the build and the SRD data on every read, so a sheet can't drift
out of step with the rules.

The engine also lists every choice a build still has to make, with its options and the reason any option is
denied (*"You're already proficient (Acolyte)"*, *"You can't cast level 2 spells yet"*). The builder shows those
answers instead of re-implementing the rules: Easy build hides denied options and Standard build shows them,
but either way the server refuses an illegal pick. A legal but unfinished build saves as a draft.

House rules for now: ability scores by standard array or point buy, hit points take the fixed average after level 1,
starting equipment comes from the class and background, and no multiclassing. Players can add any item from the
items catalogue on top of the starting kit (the build's `items`, index to quantity); the sheet marks those as added.

| Endpoint | What it does |
|----------|--------------|
| `GET /api/characters/options` | Races, classes, backgrounds and alignments for the builder's first choices |
| `GET /api/characters/templates` | Premade characters to start from (`backend/tof/premades/`) |
| `POST /api/characters/check` | Check a build without saving it: open choices, errors and the sheet |
| `GET` / `POST /api/characters` | Your characters / create one from a build or a template |
| `GET` / `PATCH` / `DELETE /api/characters/<id>` | One character with its sheet; change it; delete it |

## Security notes

The API uses cookie sessions. State-changing requests must send an `X-Requested-With` header, which other websites
can't add to cross-site requests, so forged form posts are refused. Logins lock for 15 minutes after 5 failed attempts,
and error messages never reveal whether an email is registered.

The `/__test__/*` routes and the dev mailbox exist only for testing. Set `DEV_TOOLS=0` (and a real `SECRET_KEY`)
in any deployed environment.

## Legal

Tomes of Faerun is unofficial fan content. It is not affiliated with or endorsed by Wizards of the Coast.
Rules content is from the System Reference Document 5.1 by Wizards of the Coast LLC, licensed under
[CC BY 4.0](https://creativecommons.org/licenses/by/4.0/). The data files come from
[5e-bits/5e-database](https://github.com/5e-bits/5e-database) (MIT License).
