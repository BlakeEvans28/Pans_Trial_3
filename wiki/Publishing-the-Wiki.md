# Publishing the Wiki

The files in this folder are named to match GitHub wiki conventions. GitHub stores wiki pages in a separate repository ending in `.wiki.git`, so publishing is mostly a matter of copying these files into that repo.

## What GitHub Expects

- `Home.md` becomes the wiki landing page.
- `_Sidebar.md` becomes the shared navigation sidebar.
- Every other `*.md` file becomes a wiki page.

## Publish Steps

1. Enable the Wiki feature in the GitHub repository settings if it is not already enabled.
2. Clone the wiki repo:

```powershell
git clone https://github.com/<owner>/<repo>.wiki.git
```

3. Copy the contents of this local `wiki/` folder into the root of the cloned wiki repo.
4. Commit and push:

```powershell
git add .
git commit -m "Add initial Pan's Trial wiki"
git push
```

## Suggested Local Workflow

Keep this repo folder as the source-of-truth draft set, then refresh the live GitHub wiki whenever the docs need an update.

That gives you:

- normal repo review for docs
- versioned wiki source
- easy reuse in reports or README updates

## Optional Additions

If you want richer wiki presentation later, you can also add:

- `_Footer.md`
- image folders copied into the wiki repo
- page-specific screenshots
- changelog or release-history pages

## Important Note

The GitHub wiki is not automatically synced with this project folder. After editing these files locally, you still need to copy them into the `.wiki.git` repository and push the changes.
