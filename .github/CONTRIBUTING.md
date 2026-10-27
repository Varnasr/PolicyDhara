# Contributing to PolicyDhara

Thank you for your interest in contributing to PolicyDhara. This project is an auto-updating tracker of Indian development policies across 22 sectors, and community contributions keep it accurate and useful.

## Table of Contents

- [Getting started](#getting-started)
- [Development setup](#development-setup)
- [Types of contributions](#types-of-contributions)
- [Code contributions](#code-contributions)
- [Adding policy sources](#adding-policy-sources)
- [Sector expansions](#sector-expansions)
- [Style guidelines](#style-guidelines)
- [Submitting changes](#submitting-changes)
- [Community](#community)

## Getting started

1. Fork the repository on GitHub.
2. Clone your fork locally.
3. Create a new branch from `main` for your work.
4. Make your changes, commit, and push to your fork.
5. Open a pull request against the `main` branch of this repository.

## Development setup

PolicyDhara is built with Astro (frontend), Python (data pipeline) and TypeScript (utilities and interactivity).

### Prerequisites

- Node.js 18+ and npm
- Python 3.10+
- pip (or a virtual environment manager such as `venv` or `conda`)

### Installation

```bash
# Clone your fork
git clone https://github.com/<your-username>/PolicyDhara.git
cd PolicyDhara

# Install Node.js dependencies
npm install

# Install Python dependencies
pip install -r requirements.txt

# Start the Astro development server
npm run dev
```

### Running the data pipeline

```bash
# Fetch and classify policy data
python scripts/fetch_policies.py

# Verify the output
python scripts/validate_data.py
```

## Types of contributions

### Code contributions

- Frontend (Astro/TypeScript/CSS): improvements to the static site, search functionality, analytics dashboards, and email digest templates.
- Backend (Python): improvements to the data fetching pipeline, classification logic, scheduling, and data validation.
- Infrastructure: GitHub Actions workflows, CI/CD improvements, deployment scripts, and dependency management.

### Adding policy sources

PolicyDhara currently fetches from 20+ official government sources. To add a new source:

1. Identify the official URL and confirm it provides structured or scrapable policy data.
2. Create a new fetcher in `/scripts/sources/` following the existing patterns.
3. Add the source configuration to the sources manifest file.
4. Include appropriate error handling, rate limiting, and retry logic.
5. Write tests to verify the fetcher works correctly.
6. Document the source in your pull request description.

### Sector expansions

PolicyDhara tracks policies across 22 sectors. To propose a new sector:

1. Open an issue using the **Feature Request** template that explains the sector and why it matters.
2. Identify at least two official sources that publish policies for this sector.
3. If approved, implement the sector classification rules in the classifier module.
4. Add corresponding frontend components (filters, sector pages).
5. Update the sector documentation and metadata.

### Data quality

- Report incorrect, missing, or outdated policy data using the **Data Issue** template.
- Help verify and validate policy entries against official sources.
- Improve classification accuracy by reviewing sector assignments.

## Style guidelines

### Python

- Follow [PEP 8](https://peps.python.org/pep-0008/) conventions.
- Use type hints for function signatures.
- Write docstrings for all public functions and classes.
- Format code with `black` and lint with `ruff`.

### TypeScript and JavaScript

- Use TypeScript wherever possible.
- Follow the existing ESLint configuration.
- Use Prettier for formatting.

### Astro components

- Follow the existing component structure in `/src/`.
- Keep components focused and composable.
- Use scoped styles where possible.

### CSS

- Follow the existing naming conventions.
- Prefer utility classes and design tokens where established.
- Ensure responsive design across breakpoints.

### Commits

- Write clear, short commit messages.
- Use the imperative mood, for example "Add source fetcher for MoHFW".
- Reference related issues in commit messages where applicable.

## Submitting changes

1. Ensure your code passes all existing tests and linting.
2. Run the Astro build (`npm run build`) and verify there are no errors.
3. Run the data pipeline and confirm it completes without errors.
4. Open a pull request using the provided template.
5. Describe your changes clearly and link any related issues.
6. Be responsive to review feedback.

## Community

PolicyDhara is part of the ImpactMojo Learning Platform stack. We want an inclusive, respectful community. Please read our [Code of Conduct](CODE_OF_CONDUCT.md) before participating.

For questions, suggestions, or discussions, reach out at **hello@impactmojo.in**.

---

Thank you for helping make Indian development policy tracking easier to access and easier to check.
