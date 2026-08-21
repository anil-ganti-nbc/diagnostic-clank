# Phase 0 remediation PR heads

Checked against GitHub at `2026-08-21T08:01:44Z`. These are the 13 scoped
Phase 0 remediation PRs; unrelated open PRs are intentionally omitted. Every
required check reported `SUCCESS`. The `advisory / full-style-format` failure
on code repositories is non-blocking and remains visible; it is not an
operator gate. All entries are still draft PRs.

| Repository | PR | Head SHA | URL | Required CI | Engineering gate |
|---|---:|---|---|---|---|
| watch-clank | #7 | `48ae5200712260324b3805182ad56c1848a04f06` | https://github.com/anil-ganti-nbc/watch-clank/pull/7 | PASS | COMPLETE |
| diagnostic-clank | #6 | `8017f86270a9bf5fbd9bf5a0393ca6d7997a76ef` | https://github.com/anil-ganti-nbc/diagnostic-clank/pull/6 | PASS | COMPLETE |
| clank-architecture | #2 | `c52456b9261246a203e4e392045db87f6bc82bbc` | https://github.com/anil-ganti-nbc/clank-architecture/pull/2 | PASS | COMPLETE |
| smartwatch-clank | #16 | `5d7b92ae6412a61bf17e2b1f277f293b62869247` | https://github.com/anil-ganti-nbc/smartwatch-clank/pull/16 | PASS | COMPLETE |
| korean-tech-wire | #4 | `d88787b57d24431b776fb53e811b13699b5c827b` | https://github.com/anil-ganti-nbc/korean-tech-wire/pull/4 | PASS | COMPLETE |
| feature-phone-clank | #10 | `889c88ceafc194880f48de368baee386bb8da5d1` | https://github.com/anil-ganti-nbc/feature-phone-clank/pull/10 | PASS | COMPLETE |
| unified-clank-platform | #2 | `f4e4f6a6c3a2b64683f0fa029185dd1266b13ca9` | https://github.com/anil-ganti-nbc/unified-clank-platform/pull/2 | PASS | COMPLETE |
| tablet-clank | #2 | `c46c38a36a267e5810c2ec50eb3b287272840641` | https://github.com/anil-ganti-nbc/tablet-clank/pull/2 | PASS | COMPLETE |
| chinese-tech-wire | #5 | `382d70315ddf6cb161a82be3143828f8549a0f1b` | https://github.com/anil-ganti-nbc/chinese-tech-wire/pull/5 | PASS | COMPLETE |
| smartphone-clank | #8 | `92c2b042295967535138aea64e01f67a18f1e1df` | https://github.com/anil-ganti-nbc/smartphone-clank/pull/8 | PASS | COMPLETE |
| semiconductor-intelligence | #3 | `c4d0cf0f73b9d61bf460339212739627d0a5f930` | https://github.com/anil-ganti-nbc/semiconductor-intelligence/pull/3 | PASS; Windows PASS | COMPLETE |
| free-game-tracker | #2 | `c7764b931e6405b8affd5d1908deaeb4a4c6fa5b` | https://github.com/anil-ganti-nbc/free-game-tracker/pull/2 | PASS | COMPLETE |
| oem-radar | #3 | `9da47c28d8a0fd39257a922fa82c8cba734b6f71` | https://github.com/anil-ganti-nbc/oem-radar/pull/3 | PASS | COMPLETE |

`Semiconductor Intelligence PR #3` no longer has a pending Windows result:
`platform / windows` completed successfully. A human operator still must
complete the separate native Task Scheduler evidence gate in
`SEMINT_WINDOWS_VERIFICATION_RECORD.json`.
