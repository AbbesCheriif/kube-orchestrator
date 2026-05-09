# Governance

This document describes how the kube-orchestrator project is governed.

---

## Project Roles

### Maintainer

The maintainer has full authority over the project, including:

- Merging pull requests into `develop` and `main`
- Cutting releases and publishing to PyPI
- Setting the project roadmap
- Enforcing the Code of Conduct

**Current maintainer:**

| Name                    | GitHub                                          |
|-------------------------|-------------------------------------------------|
| Cherif ABBES            | [AbbesCheriif](https://github.com/AbbesCheriif) |

### Contributor

Anyone who has had at least one pull request merged into the project.
Contributors are listed in the [AUTHORS](./AUTHORS) file.

Contributors may:

- Open issues and pull requests
- Participate in design discussions
- Review pull requests (reviews are welcome from everyone)

### User

Anyone who uses the library. Users are encouraged to:

- Report bugs via GitHub Issues
- Request features via GitHub Issues
- Ask questions via GitHub Discussions

---

## Decision Making

Most decisions are made informally through GitHub Issues and Pull Request
discussions.

For significant changes (breaking API changes, new major dependencies,
architectural decisions), the maintainer will:

1. Open a GitHub Issue labeled `discussion` or `RFC`
2. Allow at least **7 days** for community feedback
3. Make a final decision and document the rationale in the issue

---

## Release Process

Releases follow [Semantic Versioning](https://semver.org/):

| Version bump | When                                              |
|--------------|---------------------------------------------------|
| `PATCH`      | Bug fixes, dependency updates (e.g. `1.0.1`)     |
| `MINOR`      | New features, new resource managers (e.g. `1.1.0`) |
| `MAJOR`      | Breaking API changes (e.g. `2.0.0`)              |

### Steps to release

1. Ensure all tests pass on `develop`
2. Update `CHANGELOG.md` — move `[Unreleased]` to the new version
3. Merge `develop` → `main`
4. Create and push a Git tag: `git tag v1.x.x && git push origin v1.x.x`
5. The CI/CD pipeline publishes to PyPI automatically via Trusted Publishing

---

## Becoming a Maintainer

If you are an active contributor and are interested in becoming a co-maintainer,
open an issue and start a conversation. Maintainership is granted based on:

- Track record of quality contributions
- Understanding of the codebase
- Availability to review PRs and respond to issues
