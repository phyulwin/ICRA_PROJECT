# Cultural Reference Director

Implementation details for the persistent Library and structured Directing Notes workflow are documented in [docs/directing_library_implementation.md](docs/directing_library_implementation.md).

### Turn screenplay moments into a shared visual language.

**Live demo:** [cultural-reference-web-602486879299.us-central1.run.app](https://cultural-reference-web-602486879299.us-central1.run.app)

## About

Cultural Reference Director is an AI-powered filmmaking assistant that analyzes screenplay scenes and discovers relevant cultural references: memes, viral internet moments, reaction media, film and television moments, anime-style references, and other recognizable visual material. It helps filmmakers move from a written scene to concrete creative inspiration without losing the original dramatic or comedic intent.

Directors often know the exact effect they want, but describing the performance, reaction, physical action, timing, or visual reference can be difficult. Cultural Reference Director bridges that gap:

**written screenplay → scene understanding → cultural references → creative inspiration**

The application identifies which scenes are actually good candidates for a reference, searches real web sources, and explains why ranked results fit. It is designed to give creative teams a more precise starting point for discussing the moment they want to make.

## How It Works

1. Upload a screenplay in PDF, TXT, or Fountain format.
2. The application detects individual scenes.
3. Each scene is analyzed for tone, characters, emotions, actions, dramatic or comedic mechanisms, visual characteristics, and reference opportunities.
4. Choose a scene that needs creative inspiration.
5. Search for relevant real-world cultural references.
6. Review ranked matches and the reasons they fit the scene.
7. Adjust search preferences, find alternatives, and select references to keep in the workspace.

## Features

### Screenplay Intelligence

- PDF, TXT, and Fountain screenplay upload
- Automatic scene detection
- Scene-by-scene Gemini analysis
- Tone and emotion identification
- Character intentions
- Important actions and visual characteristics
- Comedic and dramatic mechanisms
- Reference-opportunity detection, so references are not forced onto every scene

### Cultural Reference Discovery

- Real web-based cultural references retrieved through Parallel Search
- Memes, reaction media, and viral internet-culture moments
- Film, television, anime, GIF, TikTok, Instagram, YouTube, and other source categories where returned by the search
- Source-linked results with direct URLs rather than fabricated references
- Honest handling of partial searches and rejected candidates

### Intelligent Reference Matching

References are evaluated across qualities such as:

- Situation
- Emotion
- Acting and performance
- Visual similarity
- Comedic or dramatic timing
- Recognizability
- Cultural relevance

The application returns deterministic ranked matches, score breakdowns, source metadata, and an explanation of why each reference fits the performance or scene.

### Search Refinement

The scene workspace currently supports filters for:

- Reference type, including memes, internet culture, film/TV, anime, and TikTok
- Era, including the 2000s, 2010s, 2020s, and current references
- Acting, situation, visual, timing, or all matching priorities
- Mainstream-to-niche obscurity
- Result count and additional searches for alternatives

## Example

**Screenplay moment:**

> A character confidently denies eating the missing cake while chocolate frosting is visibly covering their shirt.

Instead of searching for articles about lying, Cultural Reference Director looks for visual cultural moments involving caught-in-the-act reactions, guilty expressions, awkward realization, and similar comedic timing. The result is a more useful creative vocabulary for directing the performance.

## Who It Is For

Cultural Reference Director is built for directors, filmmakers, screenwriters, content creators, pre-production teams, and creative groups looking for a shared visual vocabulary.

## Product Philosophy

Cultural Reference Director does not replace creative decision-making. It acts as a visual and cultural brainstorming partner for requests such as:

> “Give me that moment where someone realizes they’ve been caught.”

The goal is to turn that abstract direction into concrete, traceable references that a creative team can discuss together.

# Project Setup

[Project Setup](docs\PROJECT_SETUP.md)

## License

This project is licensed under the Apache License 2.0. See the `LICENSE` file for details.
