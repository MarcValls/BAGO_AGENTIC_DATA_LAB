# Game workflow

Load this reference for game design, implementation, debugging, or packaging. Keep the current engine, controls, art direction, and target platform unless the user asks to change them.

## Establish the game target

Identify the core player action, target platforms, input devices, session length, performance budget, online/offline needs, save expectations, and the intended first playable slice. If a project already exists, inspect its engine and project structure before recommending a migration. For a new project with no engine choice, compare only engines that fit the requested platforms and available environment; do not assume Godot, Unity, Unreal, or a web stack is installed.

## First playable slice

Prefer a small loop that can be run and evaluated: launch, reach gameplay, perform the core action, observe feedback, and return/restart. Keep input, simulation, presentation, content, and persistence responsibilities clear without imposing an architecture disproportionate to the game.

## Game-specific checks

- Input mapping, rebinding where needed, keyboard/controller/touch behavior, focus, pause, resume, and window loss.
- Frame pacing and memory on the requested target; distinguish editor performance from exported build performance.
- Collision/physics, timing, random seeds, and deterministic behavior where the game or multiplayer model depends on them.
- Save/load, version migration, corruption/failure behavior, and platform-specific storage.
- Scene/state transitions, restart, death/complete states, UI scaling, subtitles/audio controls where applicable, and accessibility options.
- Asset provenance, licenses, attribution, import settings, and redistribution rights. Do not download, purchase, or publish assets without authorization.
- Network authority, trust boundaries, matchmaking, anti-cheat, and reconnect behavior when online play is in scope.

## Evidence

Tests and a successful export do not prove that the game is playable. When runtime access exists, launch the exact target build and exercise the requested loop with the relevant input. Record platform, build identity, and observed states. If no engine/runtime/device is available, report source/build evidence separately and leave gameplay validation `NOT_RUN`.
