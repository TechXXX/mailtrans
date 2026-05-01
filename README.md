# mailtrans

`mailtrans` is a small Python automation that watches a Gmail inbox, finds matching unread emails, translates them into Dutch with an LLM provider, forwards the translated version, and then marks the original message as read.

## What It Does

The script in [`translatorv2.py`](/Users/kalter/Documents/CODEX/mailtrans/translatorv2.py) does the following:

1. Authenticates to Gmail with the Gmail API.
2. Searches for unread messages from the current month.
3. Checks whether all configured target addresses appear in the `To` or `Cc` fields.
4. Extracts the email body, preferring HTML when available.
5. Removes common newsletter and footer noise.
6. Translates the content into Dutch with the configured LLM provider.
7. Forwards the translated email to the configured recipients.
8. Marks the original Gmail message as read.

## Current Model Configuration

The script now supports both OpenAI and DeepSeek through environment variables.

Default behavior:

- `LLM_PROVIDER=openai`
- `OPENAI_MODEL=gpt-3.5-turbo`

If you run this project through GitHub Actions, GitHub uses whichever provider and model are configured through repository secrets or workflow environment variables, because the workflow simply runs:

```bash
python translatorv2.py
```

The workflow is defined in [`.github/workflows/translate.yml`](/Users/kalter/Documents/CODEX/mailtrans/.github/workflows/translate.yml).

## Switching Between OpenAI And DeepSeek

You can switch providers without editing Python code.

### OpenAI

```env
LLM_PROVIDER=openai
OPENAI_API_KEY=your_openai_api_key_here
OPENAI_MODEL=gpt-3.5-turbo
```

### DeepSeek

```env
LLM_PROVIDER=deepseek
DEEPSEEK_API_KEY=your_deepseek_api_key_here
DEEPSEEK_MODEL=deepseek-v4-flash
DEEPSEEK_BASE_URL=https://api.deepseek.com
```

When `LLM_PROVIDER=deepseek`, the script uses the OpenAI-compatible DeepSeek API endpoint at `https://api.deepseek.com`.

You can switch back and forth any time by changing `.env` or the GitHub Actions secrets/environment values.

### GitHub website toggle

For manual runs on GitHub, the workflow now includes a provider dropdown in the Actions UI.

Use:

1. Open the `Actions` tab.
2. Select `Run Gmail Translator`.
3. Click `Run workflow`.
4. Choose `openai` or `deepseek` from the `llm_provider` dropdown.
5. Start the run.

Manual runs use the dropdown selection for that run only.

Scheduled hourly runs still use the repository variable `LLM_PROVIDER`, so set that variable to whichever provider you want as the default background behavior.

Manual runs also support optional test inputs:

- `test_subject_contains`
- `test_from`

That means you can trigger a one-off GitHub test run for a specific email directly from the Actions page without editing repository variables each time.

## Test One Email

The script also supports a test mode for translating one chosen email by subject and/or sender.

In test mode:

- the normal `TARGET_EMAILS` recipient check is skipped
- the translated result is forwarded only to `baskalter@hotmail.com` by default
- the forwarded subject includes the provider name, for example `Translated (DEEPSEEK, NLD): ...`
- the original email is not marked as read unless you explicitly enable that
- retry behavior is shorter by default so failed API calls do not look stuck during testing

### Test by subject

Add these to `.env` for a one-email test:

```env
TEST_SUBJECT_CONTAINS=your subject text here
TEST_FORWARD_TO=baskalter@hotmail.com
TEST_MARK_READ=false
```

### Test by sender

```env
TEST_FROM=sender@example.com
TEST_FORWARD_TO=baskalter@hotmail.com
TEST_MARK_READ=false
```

### Test by subject and sender together

```env
TEST_SUBJECT_CONTAINS=your subject text here
TEST_FROM=sender@example.com
TEST_FORWARD_TO=baskalter@hotmail.com
TEST_MARK_READ=false
```

The script will search for matching messages, take the most recent match returned by Gmail, translate it, and forward only that translation to your test address.

### GitHub test run

From the GitHub website:

1. Open `Actions`.
2. Select `Run Gmail Translator`.
3. Click `Run workflow`.
4. Choose `deepseek` or `openai`.
5. Optionally fill in `test_subject_contains`.
6. Optionally fill in `test_from`.
7. Start the run.

If either test field is filled in, the workflow runs in test mode and forwards only the matching translation to `baskalter@hotmail.com` unless you changed `TEST_FORWARD_TO`.

### Test retry tuning

You can also control retry behavior with:

```env
TRANSLATION_MAX_RETRIES=3
TRANSLATION_RETRY_DELAY_SECONDS=20
```

These are especially useful for GitHub testing so a transient API failure does not pause the run for 10 minutes.

When you are done testing, remove `TEST_SUBJECT_CONTAINS` and `TEST_FROM` from `.env` to return to normal mailbox processing.

## Files

- [`translatorv2.py`](/Users/kalter/Documents/CODEX/mailtrans/translatorv2.py): main translation and forwarding script
- [`requirements.txt`](/Users/kalter/Documents/CODEX/mailtrans/requirements.txt): Python dependencies
- [`.github/workflows/translate.yml`](/Users/kalter/Documents/CODEX/mailtrans/.github/workflows/translate.yml): scheduled GitHub Actions workflow
- `translatorv2.py.bak*`: older backup copies of the script

## Requirements

- Python 3.11 or newer recommended
- A Gmail account with Gmail API access enabled
- Google OAuth client credentials
- An OpenAI or DeepSeek API key

## Local Setup

### 1. Install dependencies

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Create `.env`

Create a `.env` file in the project root:

```env
LLM_PROVIDER=openai
OPENAI_API_KEY=your_openai_api_key_here
OPENAI_MODEL=gpt-3.5-turbo
```

Example DeepSeek `.env`:

```env
LLM_PROVIDER=deepseek
DEEPSEEK_API_KEY=your_deepseek_api_key_here
DEEPSEEK_MODEL=deepseek-v4-pro
DEEPSEEK_BASE_URL=https://api.deepseek.com
```

### 3. Add Google credentials

Place your Gmail OAuth credentials file in the project root as:

```text
credentials.json
```

On first local run, the script will open a browser-based OAuth flow and create:

```text
token.json
```

## Running Locally

Run:

```bash
python translatorv2.py
```

The script will:

- load the configured provider settings from `.env`
- authenticate with Gmail
- scan unread messages from the current month
- translate matching emails into Dutch
- forward them
- remove the `UNREAD` label from the original messages

## GitHub Actions Setup

This repo includes an hourly workflow in [`.github/workflows/translate.yml`](/Users/kalter/Documents/CODEX/mailtrans/.github/workflows/translate.yml).

To make it work on GitHub, add these repository secrets:

- `GOOGLE_CREDS`: the full contents of `credentials.json`
- `GOOGLE_TOKEN`: the full contents of `token.json`

For OpenAI:

- `OPENAI_API_KEY`: your OpenAI API key

For DeepSeek:

- `DEEPSEEK_API_KEY`: your DeepSeek API key

Then set the default provider and optional model selection in repository variables, for example:

```yaml
env:
  LLM_PROVIDER: openai
  OPENAI_MODEL: gpt-3.5-turbo
```

or:

```yaml
env:
  LLM_PROVIDER: deepseek
  DEEPSEEK_MODEL: deepseek-v4-pro
  DEEPSEEK_BASE_URL: https://api.deepseek.com
```

The workflow restores those files at runtime and then executes the script.

## Matching Logic

The script currently only processes an email when every address in `TARGET_EMAILS` is present somewhere in the combined `To` and `Cc` headers.

Those addresses are currently hardcoded in [`translatorv2.py`](/Users/kalter/Documents/CODEX/mailtrans/translatorv2.py#L21):

- `baskalter@gmail.com`
- `kalter44@hotmail.com`
- `eric.kalter@gmail.com`
- `sparkimark@hotmail.com`

Translated emails are forwarded to the addresses in `FORWARD_TO`, currently defined in [`translatorv2.py`](/Users/kalter/Documents/CODEX/mailtrans/translatorv2.py#L27).

## Notes And Caveats

- The script can make many LLM API requests for a single email because it translates both the cleaned full text and multiple individual HTML elements.
- Retry behavior is intentionally aggressive: it can wait up to 10 minutes between retries for certain API errors.
- The script is currently tuned for HTML-heavy newsletter-style emails.
- There are no automated tests in this repository yet.

## Security Notes

- Do not commit `.env`, `credentials.json`, or `token.json`.
- Treat Gmail OAuth credentials and tokens as sensitive secrets.
- Store secrets in GitHub Actions using repository secrets, not committed files.

## Possible Next Improvements

- Move configuration such as target emails and forward recipients into environment variables.
- Add structured logging so failures are easier to debug in GitHub Actions.
- Reduce duplicate translation calls to lower cost and speed up processing.
- Add tests around message filtering and cleanup behavior.
