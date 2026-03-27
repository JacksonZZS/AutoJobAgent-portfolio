# Project Overview Notes

This file contains concise, reusable descriptions of the public project.

## AutoJobAgent

### Short Overview

AutoJobAgent is an AI-assisted job application platform that combines resume analysis, role matching, application material generation, and manual-review workflows in one product.

### What The Product Covers

- resume upload, parsing, and profile extraction
- job discovery and fit scoring
- tailored resume and cover letter generation
- manual review for borderline decisions
- resume version management and history tracking
- market intelligence views built from collected job data

### Engineering Focus

- full-stack product development across `FastAPI`, `React`, and `TypeScript`
- LLM-backed resume processing with deterministic fallback logic
- browser automation and scraping integrated into user-facing workflows
- real-time task tracking with observable workflow state
- PDF generation for resumes and related materials

### Why The Project Is Interesting

The core challenge was reliability. The product had to deal with incomplete LLM output, fragile automation, and workflows where full automation was not always the right choice. The system therefore combines automation with validation, fallback parsing, and explicit manual-review checkpoints.

### Current Positioning

AutoJobAgent is best presented as a working full-stack product prototype focused on workflow depth, systems integration, and reliability. It is not framed as a polished SaaS deployment template.
