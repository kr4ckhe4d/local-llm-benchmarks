# Tasks

Status: `[ ]` todo, `[~]` partial (finish first), `[x]` done. One task per session.
Each task must meet its **Done when** before it is ticked. Add new tasks at the right place when you find
work that is missing; split tasks that are too big (T05 -> T05a, T05b).
All tasks also require: `{{VERIFY_ALL}}` exits 0 (once there is something to verify).

- [ ] **T01 Scaffold.** {{project skeleton, the verification tool's inputs (views/fixtures), test contract}}
  Done when: {{VERIFY_ALL}} exits 0.
- [ ] **T02 ...** {{one session of work: a coherent feature that can be verified on its own}}
  Done when: {{observable, checkable result}}
- [ ] **TNN Final review.** Run every acceptance check in project.md, write README.md, map each required
  element to the evidence that shows it in the handoff.
  Done when: all acceptance checks pass this session; then call `goal_complete`.
