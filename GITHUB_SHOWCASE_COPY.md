# GitHub Showcase Copy

Use the snippets below for your public GitHub repository, LinkedIn project section, or interview prep notes.

## Repository Description

AI-assisted job application platform for resume tailoring, job discovery, manual review workflows, and generated application materials.

## Short GitHub About Blurb

Built a full-stack AI job search system with FastAPI, React, browser automation, resume optimization, PDF generation, and human-in-the-loop review workflows.

## Pinned Project Summary

AutoJobAgent is a full-stack product prototype that combines job discovery, resume tailoring, application material generation, and operator-facing review workflows in one system. It uses FastAPI for orchestration, React for the product UI, and an LLM-backed resume engine with deterministic fallback parsing to preserve critical resume data during optimization.

## Resume Project Bullet

Built an AI-assisted job application platform with FastAPI and React that automated job discovery, generated tailored resumes and cover letters, and supported human-in-the-loop review with real-time task tracking.

## LinkedIn Project Description

Built a full-stack AI-assisted job application platform that combines resume parsing, role-specific resume optimization, job search automation, manual-review workflows, and generated application materials. The system uses FastAPI, React, browser automation, WebSockets, PDF generation, and LLM-backed resume processing with deterministic fallback logic to preserve critical candidate data.

## Interview Introduction

This project started as a job search automation tool, but I treated it as a product and systems engineering exercise. The hard part was not just generating resumes with an LLM. It was making the workflow reliable: preserving key resume fields, handling fragile browser automation, keeping the human in control for borderline decisions, and exposing enough observability in the UI for the operator to trust the system.

## Technical Highlights

- FastAPI backend with modular route groups for auth, jobs, resume optimization, history, materials, and market intelligence
- React and TypeScript frontend with dashboard, optimizer, resume library, and analytics pages
- Resume optimization engine with structured editing plus fallback extraction for contact data, education, projects, skills, and work eligibility
- Real-time task updates over WebSockets
- Browser automation and scraping workflow for job discovery and application support
- PDF generation pipeline backed by HTML templates

## What To Emphasize In Interviews

1. This is a workflow product, not just a script.
2. The difficult work was reliability under messy real-world inputs.
3. The architecture balances automation with explicit manual review.
4. The resume optimizer required deterministic guards around LLM output.
5. The project shows product thinking, backend systems work, and frontend implementation in one codebase.
