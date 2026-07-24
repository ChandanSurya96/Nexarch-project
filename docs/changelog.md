# Changelog

**Purpose:** Chronological record of major features, architectural changes, and releases. Format follows [Keep a Changelog](https://keepachangelog.com) conventions. See [decisions.md](./decisions.md) for the *reasoning* behind entries here — this file is the *what and when*, that one is the *why*.

---

## [Unreleased]

### Added
- Initial `/docs` knowledge base created: README, vision, roadmap, architecture, database, api, broker-integrations, design-system, security, development-guide, product-requirements, decisions, changelog, and the `/docs/product` subfolder (user-personas, user-journey, feature-backlog, competitor-analysis, market-research, monetization, go-to-market, success-metrics, user-feedback).
- Database schema designed (not yet migrated/implemented).
- API contract designed (not yet implemented).
- Broker/Account Aggregator integration strategy researched and documented, including two open risks requiring founder/legal attention before public launch (see [decisions.md](./decisions.md) ADR-010, ADR-011).

### Notes
- **No application code has been written yet.** Per the founding process, this is intentional — Phase 1 implementation begins after founder review of this documentation set. See [roadmap.md](./roadmap.md).

---

## Template for Future Entries

```
## [Version or Date] — Short Description

### Added
- New features

### Changed
- Changes to existing functionality

### Fixed
- Bug fixes

### Deprecated
- Soon-to-be-removed features

### Removed
- Removed features

### Security
- Vulnerability fixes, dependency updates with security relevance
```
