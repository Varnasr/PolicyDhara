# PolicyDhara

[![Website](https://img.shields.io/badge/Website-varnasr.github.io%2FPolicyDhara-blue)](https://varnasr.github.io/PolicyDhara)
[![License: MIT](https://img.shields.io/badge/Code-MIT-green.svg)](LICENSE)
[![GitHub Actions](https://img.shields.io/badge/Auto--Update-Every%206%20Hours-brightgreen?logo=github-actions)](https://github.com/Varnasr/PolicyDhara/actions)
[![GitHub Last Commit](https://img.shields.io/github/last-commit/Varnasr/PolicyDhara)](https://github.com/Varnasr/PolicyDhara/commits/master)
[![Part of ImpactMojo](https://img.shields.io/badge/Part%20of-ImpactMojo-orange)](https://www.impactmojo.in)

**Auto-updating tracker of Indian development policy across 22 sectors — fetching from ~350 official sources concurrently every 6 hours via GitHub Actions, with a news filter and a policy-forward homepage.**

📋 [Roadmap](ROADMAP.md) · 📝 [Blog](https://varnasr.github.io/PolicyDhara/blog)

A complement to [impactmojo.in](https://impactmojo.in) and the [OpenStacks for Change](https://github.com/Varnasr/OpenStacks-for-Change) ecosystem.

**Live at [varnasr.github.io/PolicyDhara](https://varnasr.github.io/PolicyDhara)**

---

## About

PolicyDhara (पॉलिसीधारा — "Policy Stream") provides a living, searchable archive of Indian development policy. It aggregates policy documents, schemes, legislation, budget allocations, and analysis from official government portals and research institutions — automatically refreshed every 6 hours.

It is designed for researchers, journalists, advocates, and practitioners who need to track policy developments across India's complex governance landscape without manually monitoring dozens of government portals.

---

## What It Tracks

- Central and state government policies, schemes, and legislation
- Union Budget allocations and fiscal policy statements
- Parliament bills, session data, and legislative productivity
- Notifications, gazette circulars, and executive orders
- Think tank analysis and international development body reports

---

## 22 Sectors Covered

| Cluster | Sectors |
|---------|---------|
| **Social** | Education, Health, Gender, Social Protection, Nutrition |
| **Economy** | Finance, Agriculture, Labour, Infrastructure, Digital |
| **Environment** | Climate, Water, Energy, Environment |
| **Governance** | Democracy, Legal, Defence, Urban, Rural |
| **International** | Trade, Foreign Policy, Development Cooperation |

---

## Data Sources (~380 configured)

The pipeline fetches from ~350 sources concurrently. A few high-value ones:

| Source | Type |
|--------|------|
| [PIB (Press Information Bureau)](https://pib.gov.in) | Government press releases |
| [PRS Legislative Research](https://prsindia.org) | Bills, acts, and parliament analysis |
| [India Code](https://indiacode.nic.in) | Legislation database |
| [eGazette of India](https://egazette.nic.in) | Official gazette notifications |
| [NITI Aayog](https://niti.gov.in) | Policy reports and flagship scheme updates |
| [RBI](https://rbi.org.in) | Monetary policy, financial sector regulation |
| [Supreme Court of India](https://sci.gov.in) | Landmark judgements |
| [ORF](https://orfonline.org) | Strategic policy analysis |
| [CPR India](https://cprindia.org) | Governance and accountability research |
| [ICRIER](https://icrier.org) | Trade, investment, and economic policy |
| [World Bank India](https://worldbank.org/en/country/india) | Development policy assessments |
| [UNDP India](https://undp.org/india) | SDG and human development updates |

---

## Architecture

```
┌──────────────────────────────────────────────────────┐
│              GitHub Actions (every 6 hours)           │
│                                                        │
│  update-policies.yml                                   │
│  ├── Fetch ~350 sources concurrently (RSS/API/scrape) │
│  ├── Filter news noise + cap media at 40%             │
│  ├── Classify by sector (22 categories)               │
│  ├── Deduplicate and detect amendments                │
│  ├── Commit updated data to repository                │
│  └── Trigger GitHub Pages rebuild                     │
└──────────────────────────────────────────────────────┘
                         │
              GitHub Pages (static hosting)
                         │
┌──────────────────────────────────────────────────────┐
│              varnasr.github.io/PolicyDhara            │
│  ├── Searchable policy database                       │
│  ├── Sector filters (22 categories)                   │
│  ├── Source attribution for every entry               │
│  └── Email digest for subscribers                     │
└──────────────────────────────────────────────────────┘
```

---

## Automation Schedule

| Task | Frequency | Mechanism |
|------|-----------|-----------|
| Policy data refresh | Every 6 hours | `update-policies.yml` (GitHub Actions) |
| Site deploy | On data commit | `deploy.yml` (GitHub Pages) |
| PyPI package publish | On release | `publish-pypi.yml` |
| Newsletter (optional) | On data refresh | `scripts/send_newsletter.py` (Buttondown) |
| Telegram alerts (optional) | On data refresh | `scripts/push_telegram.py` |

### Optional integrations

Both run as best-effort steps in `update-policies.yml` and skip silently if the relevant secrets are not set.

**Buttondown newsletter** — set `BUTTONDOWN_API_KEY` as a GitHub Secret.

**Telegram alerts** for high-priority new policies — set:

- `TELEGRAM_BOT_TOKEN` — from [@BotFather](https://t.me/BotFather) (`/newbot`)
- `TELEGRAM_CHAT_ID` — channel `@username` (e.g. `@policydhara`) or numeric chat id

Add the bot as an administrator on the channel with "Post Messages" permission. Test locally with `python3 scripts/push_telegram.py --dry-run`.

---

## Local Development

```bash
git clone https://github.com/Varnasr/PolicyDhara.git
cd PolicyDhara

# Python pipeline
pip install -r scripts/requirements.txt
python3 scripts/fetch_all.py            # fetch + filter + classify
python3 scripts/check_source_health.py  # bucket every source (WORKS/REDUNDANT/SHELL/DEAD)

# Astro site
npm install
npm run dev      # local dev server
npm run build    # production build (Astro + Pagefind)

# Run the test suite
python3 -m pytest tests/
```

---

## Tech Stack

| Layer | Technology | Purpose |
|-------|-----------|---------|
| Data Pipeline | Python | Concurrent fetching, news filter, classification, dedup |
| Automation | GitHub Actions | Scheduled data refresh (6-hourly) and deploy |
| Frontend | Astro 7 | Static searchable site (+ Pagefind search) |
| Hosting | GitHub Pages | Auto-deploy from repository |
| Package | PyPI (`policydhara`) | Python library for the policy data pipeline |

---

## Related Repositories

- [ImpactMojo](https://github.com/Varnasr/ImpactMojo) — Main platform (PolicyDhara is embedded)
- [PolicyStack](https://github.com/Varnasr/PolicyStack) — OpenStacks policy data layer
- [INDIA-DATA](https://github.com/Varnasr/INDIA-DATA) — Bihar electoral data analysis
- [someperspective](https://github.com/Varnasr/someperspective) — India's political economy analysis

---

## License

MIT License — see [LICENSE](LICENSE) for details.

---

## Contact

- **Platform:** [impactmojo.in](https://www.impactmojo.in)
- **GitHub:** [github.com/Varnasr](https://github.com/Varnasr)
