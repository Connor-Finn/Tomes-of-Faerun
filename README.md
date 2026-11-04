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
| Character builder and sheets    | 🛠 Planned   |
| Bestiary                        | 🛠 Planned   |
| Spell catalogue and spellbooks  | 🛠 Planned   |
| Items and equipment             | 🛠 Planned   |
| Campaigns                       | 🛠 Planned   |
| Parties, sharing and messaging  | 🛠 Planned   |
| Solo text adventure             | 🛠 Planned   |

## Tech stack

- **Front end:** React 18, TypeScript, React Router, Vite
- **Back end:** Python, Flask (JSON API), SQLAlchemy, SQLite
- **Testing:** Playwright for Python with pytest (page objects, fixtures, storage state, API tests, parallel runs)
- **CI:** GitHub Actions builds the app and runs the whole suite on every push and pull request

```
backend/     Flask API (one blueprint per area: auth, account, admin, dev tools)
frontend/    React app (pages, components, API client)
tests/       Playwright tests and page objects
```

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
- **Data-driven tests** with `pytest.mark.parametrize` for form validation
- **API tests** with Playwright's `APIRequestContext`, including security checks (CSRF header, open redirects,
  no password hashes in responses)
- **Multiple browser contexts** in one test (an admin bans a user who then can't log in)

## Security notes

The API uses cookie sessions. State-changing requests must send an `X-Requested-With` header, which other websites
can't add to cross-site requests, so forged form posts are refused. Logins lock for 15 minutes after 5 failed attempts,
and error messages never reveal whether an email is registered.

The `/__test__/*` routes and the dev mailbox exist only for testing. Set `DEV_TOOLS=0` (and a real `SECRET_KEY`)
in any deployed environment.

## Legal

Tomes of Faerun is unofficial fan content. It is not affiliated with or endorsed by Wizards of the Coast.
Rules content is from the System Reference Document 5.1, licensed under
[CC BY 4.0](https://creativecommons.org/licenses/by/4.0/).
