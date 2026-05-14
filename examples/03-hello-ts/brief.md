# Project Brief: hello-ts — Typed Greeting CLI

A small TypeScript command-line program that prints a personalised greeting,
demonstrating typed argument parsing and modern ESM module conventions.

## Goals
- Show a working TypeScript CLI runnable with `ts-node` or compiled with `tsc`.
- Demonstrate typed argument handling without heavy framework overhead.
- Include a brief test suite using Node's built-in test runner.

## Users
- TypeScript learners looking for a minimal but idiomatic CLI starting point.
- Teams evaluating TypeScript for internal tooling.

## Use Cases
- `npx ts-node src/index.ts --name Alice` prints `Hello, Alice!`.
- `npx ts-node src/index.ts --name Alice --lang es` prints `Hola, Alice!`.
- `npm test` runs the unit test suite.

## MVP Scope
- `src/index.ts` with typed CLI parsing (minimist or native `process.argv`).
- Greeting logic extracted to `src/greet.ts` with an exported `greet()` function.
- Supported languages: `en` (default), `es`, `fr`, `zh`.
- Test file `src/greet.test.ts` with at least 6 assertions.
- `package.json` with `build`, `start`, and `test` scripts.

## Non-Goals
- Interactive prompts or readline input.
- Internationalisation beyond four hard-coded languages.
- Publishing to npm.

Delivery boundary: Single `package.json` workspace, no runtime dependencies beyond
`minimist` (optional) and `typescript` as a dev dependency.
