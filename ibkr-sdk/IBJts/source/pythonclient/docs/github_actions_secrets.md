# GitHub Actions Configuration

Use these commands from a workstation with `gh` authenticated to the target repository. They align with the Sengoku Decision Cockpit wheel build pipeline.

```bash
# Required: path to the staged pythonclient directory on the runner
gh secret set IB_API_SOURCE_DIR --body "/opt/ibkr-sdk/IBJts/source/pythonclient"

# Optional: version gate for build_wheel.py
gh variable set IB_API_VERSION --body "10.37.02"

# Optional: artefact publishing credentials
gh secret set IB_API_UPLOAD_URL --body "https://<your-wheelhouse>/"
gh secret set IB_API_UPLOAD_USERNAME --body "<username>"
gh secret set IB_API_UPLOAD_PASSWORD --body "<password-or-token>"
```

If you prefer the web UI, navigate to **Repository → Settings → Secrets and variables → Actions** and add the entries above.

> Tip: when working with multiple environments, consider setting these values at the organization level so all repositories share the same runner configuration.
