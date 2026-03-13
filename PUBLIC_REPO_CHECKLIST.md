# Public GitHub Release Checklist

Use this checklist before pushing `AutoJobAgent` to a public GitHub repository.

## 1. Secrets

- Rotate any key that was ever stored in `.env`
- Rotate Gemini / Google API keys
- Rotate JWT secrets
- Rotate SMTP app passwords

Why:

- Removing files from the current Git index does not erase old local commit history
- If those commits are pushed, the secrets are still exposed

## 2. Publish From A Clean History

Recommended:

1. Create a new empty GitHub repository
2. Copy this sanitized working tree into it, or create an orphan branch
3. Make a fresh initial commit
4. Push only the clean history

Avoid:

- Pushing the full existing Git history if it ever contained `.env`, resumes, databases, or generated outputs

## 3. Keep Out Of The Public Repo

- `.env`
- `data/uploads/`
- `data/outputs/`
- `data/status/`
- `data/sessions/`
- `data/browser_profiles/`
- `data/*.db`
- generated resumes / cover letters / PDFs
- user histories and cached analyses

## 4. Keep In The Public Repo

- `backend/`
- `core/`
- `frontend/`
- `data/templates/`
- `tests/`
- `.env.example`
- `README.md`

## 5. Best Demo Assets To Add Later

- 3 to 6 sanitized screenshots
- 1 short architecture diagram
- 1 sample walkthrough GIF for the dashboard and resume optimizer

## 6. Final Verification

Run before pushing:

```bash
git status
git ls-files | rg '^data/'
git ls-files | rg '^\\.env$'
git ls-files | rg 'users\\.db|resume\\.pdf|cover_letter|analysis_cache'
```

Expected result:

- only `data/templates/` remains tracked under `data/`
- `.env` is not tracked
- no generated user materials are tracked
