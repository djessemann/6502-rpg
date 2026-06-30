# NES RPG Framework

A contract, a method, and a set of engine patterns for building a small,
content-driven NES RPG in 6502 assembly — kept disciplined enough that the
project stays buildable and verifiable as it scales, whether a person or a
coding agent (e.g. Claude Code) does the work.

It is deliberately minimal: **the art and content are the ambition; the engine
and mechanics stay small and rigid.**

## Use it
1. Copy this `framework/` into a new repo.
2. Copy `PROJECT.template.md` → `PROJECT.md` and fill in your game's choices.
3. Read `METHOD.md` before working; obey `HARDWARE.md` always.
4. Build subsystems from `PATTERNS.md`, one at a time, verifying each.
5. Keep a project `ARCHITECTURE.md` that describes *your* engine as you build it.

(For Claude Code: make the project `CLAUDE.md` import the binding docs so they
are always in context — e.g. a line `@framework/HARDWARE.md` and
`@framework/METHOD.md` — then add only this game's specifics.)

## Documents — each has one job
| File | Job | Changes |
|------|-----|---------|
| `METHOD.md`       | How to work: build order, scope, verify loop, toolchain | rarely |
| `HARDWARE.md`     | NES/6502 contract + traps. **Binding.** Mapper-independent | rarely |
| `PATTERNS.md`     | Reusable engine recipes (how to build each subsystem) | as patterns are added |
| `ASSETS.md`       | For artists/writers: NES art limits + how to author content | rarely |
| `PROJECT.md`      | *This game's* choices + current scope | per phase |
| `ARCHITECTURE.md` | How *this* engine actually works now (code map) | when a subsystem changes |

## The one rule for all docs
State the **current truth**, not history. One fact in one place (rule →
HARDWARE, mechanism → PATTERNS/ARCHITECTURE, scope → PROJECT). **Name the
function instead of duplicating its code** (code drifts; names don't). Update
the doc in the same commit that changes the behavior.
