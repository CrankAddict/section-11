# Contributing to Section 11

Thanks for wanting to help. This project is an open, evidence‑based protocol for AI endurance coaching.

## Ways to contribute
- Fix bugs or improve scripts
- Improve docs or examples
- Propose protocol/content changes (reports, decision trees, prompts)
- Share research or references that strengthen decisions

## How to propose changes
- Open an issue for ideas, bugs, or questions
- Open a pull request for concrete changes
- Keep PRs small and focused
- sync.py changes should include test output showing the change works
- Scripts added under `examples/` should include worked-example output showing the script run against the relevant sample data in `examples/json-examples/` and the values it produces
- Keep PR descriptions, documentation, code comments, and commit messages in English
 

## Ground rules
- Stay deterministic and explainable: recommendations must be traceable to data and rules
- No hidden data flows or external services without clear docs
- New session templates must include YAML metadata (`id`, `domain`, `is_hard_session`, `work_minutes`, `est_total_minutes`) and the 6 standard prose fields used in `examples/workout-library/WORKOUT_REFERENCE.md` (zones, structure, duration, coaching notes, select when, and optionally position note)
- Be respectful and evidence‑based in discussions

## License
Contributions fall under the project's [MIT](LICENSE) license.
