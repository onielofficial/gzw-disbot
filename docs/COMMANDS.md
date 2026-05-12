# Command reference

All commands are slash commands. Most accept fuzzy autocomplete on text fields.

## Lookups

| Command                           | Purpose                                       |
|-----------------------------------|-----------------------------------------------|
| `/help`                           | Briefing embed listing every command.         |
| `/task search query:<text>`       | Find a task by name / slug.                   |
| `/task list trader: type: faction: limit:` | Filter the full task list.            |
| `/key search query:<text>`        | Find a key.                                   |
| `/key list region: limit:`        | List keys, optionally per region.             |
| `/place search query:<id|name>`   | POI / objective lookup. `1373` works.         |
| `/place list region: group: limit:` | Filter POIs.                                |
| `/lz`                             | List all Landing Zones.                       |
| `/cop`                            | List Combat Outposts.                         |
| `/trader info name:<n>`           | Vendor dossier.                               |
| `/faction info name:<n>`          | Faction dossier (PMC or hostile).             |
| `/faction list type:`             | List PMCs or hostiles.                        |
| `/search query:<text> limit:`     | Universal fuzzy search.                       |
| `/map`                            | Link to gzwtacmap.com + cache stats.          |

## Personal tracker (per-user, ephemeral replies)

| Command                                       | Purpose                                      |
|-----------------------------------------------|----------------------------------------------|
| `/track me`                                   | Show your operator status (HUD with bars).   |
| `/track set kind: target: status:`            | Mark a task or key. `kind` = task or key.    |
| `/track faction name:`                        | Set your operator's PMC.                     |
| `/track reset`                                | Wipe your tracker data.                      |

`/track set` value matrix:

| kind | status                         | what it does                               |
|------|--------------------------------|--------------------------------------------|
| task | done / in_progress / abandoned | upserts task progress                      |
| key  | owned                          | adds the key to your wallet                |
| key  | drop / lost                    | removes the key from your wallet           |

## Admin / Owner

| Command     | Purpose                                              |
|-------------|------------------------------------------------------|
| `/refresh`  | Force a re-scrape of gzwtacmap.com, replace snapshot. |
| `/ping`     | Latency check.                                       |

## Examples

```text
/task search query:incognito
/task list trader:Gunny type:main limit:10
/key search query:tiger
/place search query:1373
/lz
/track set kind:task target:incognito status:done
/track set kind:key target:tiger-bay-armory status:owned
/track me
/search query:tiger
```
