# Project Presentation Guide

## How To Talk About These Projects

The goal is not to sound more technical than necessary.

The goal is to make a recruiter, hiring manager, or technical reviewer understand:

- what problem you were solving
- what you personally built
- what was difficult
- how you handled reliability and tradeoffs

Use simple language first. Add technical depth only if they ask.

Good rule:

- first answer in business language
- second layer in system language
- third layer in implementation detail

Do not start with terms like `MCP`, `multi-agent`, `orchestration`, or `degradation strategy` unless you can explain them in plain English right after.

## Your Best Two Projects

### 1. AutoJobAgent

**Short version**

AutoJobAgent is an AI-assisted job application platform. It helps users analyze resumes, match jobs, generate tailored resumes and cover letters, and manage the application workflow in one place.

**What I built**

- Built backend and frontend workflow logic for resume analysis, resume optimization, and generated application materials.
- Worked on structured resume editing flows, PDF generation, history management, and authentication.
- Added fallback logic so the system would not lose important resume data when LLM output was incomplete.
- Supported manual review for low-confidence cases instead of forcing everything into full automation.

**Main difficulty**

The hardest problem was reliability. LLM output could be incomplete or badly structured, which meant a generated resume might lose education, projects, or contact details.

**How I solved it**

I combined LLM output with deterministic parsing from the original resume text. If the LLM result was incomplete, the system tried to recover key sections before generating the final PDF. I also blocked obviously broken outputs instead of pretending the generation was successful.

**Why it matters**

This made the system much more usable in practice, because users care more about data integrity and workflow reliability than raw AI generation quality.

**Best concise wording**

I usually describe this as a workflow product, not just an AI feature demo. The value came from combining automation with structured fallbacks and human review.

## 2. Xiaohongshu Content Operations Platform

**Short version**

This project is a Xiaohongshu-focused content operations platform. It supports content creation, publishing workflows, comment monitoring, lead tracking, and basic analytics for different operating modes.

**What I built**

- Worked on the platform structure across the web workbench, automation modules, and lead/comment workflow design.
- Built or integrated publishing-related automation, comment monitoring, and lead management logic.
- Designed data models for posts, comments, leads, templates, and operational status with Supabase.
- Added fallback thinking so the workflow could switch from automation to manual handling when needed.

**Main difficulty**

The difficult part was not only generating content. It was making the workflow still usable when automation could not safely continue because of platform constraints or unstable browser behavior.

**How I solved it**

I used a layered workflow design. Where automation could work, it supported publishing and monitoring. Where it could not, the system could fall back to copy-package based manual handling and operator review instead of failing completely.

**What is already implemented**

- Xiaohongshu-specific web workbench
- publishing-related automation modules
- comment monitoring logic
- comment intent classification
- leads and comments data model
- dashboard and lead management pages

**What I would say carefully**

Some modules were implemented as working components, while some web-side end-to-end flows were still being integrated. So I would describe it as a strong working prototype with implemented core modules, not as a fully polished production system.

## Which Style Works Best

Use this style:

- clear
- direct
- slightly conversational
- easy to follow

Do not use this style:

- too academic
- too buzzword-heavy
- too many internal names
- too many low-level details too early

### Better

I built a job application workflow tool that combines resume optimization, job matching, and generated materials. One key issue was that AI output could be incomplete, so I added fallback parsing and validation before generating the final resume.

### Worse

I architected a multi-agent orchestration framework with advanced structured output recovery, schema repair, and failure-aware generation for downstream HR optimization tasks.

The second version sounds more technical, but it is worse unless the reviewer already asked for architecture depth.

## What To Say First

When someone says, "Tell me about this project," use this order:

1. What the product does
2. What problem it solves
3. What you personally built
4. The hardest technical issue
5. The tradeoff or result

## 1-Minute Version

### AutoJobAgent

AutoJobAgent is an AI-assisted job application platform. It helps users analyze resumes, match jobs, generate tailored resumes and cover letters, and manage application workflows. I worked across backend and frontend, especially on resume optimization, PDF generation, workflow logic, and reliability improvements. One hard problem was that LLM output could be incomplete, so I added deterministic fallback extraction and validation to preserve important resume data. I see it as a workflow product where reliability matters as much as AI capability.

### Xiaohongshu Content Operations Platform

This project is a Xiaohongshu content operations platform for content generation, publishing workflows, comment monitoring, and lead management. I worked on the system structure, automation modules, and the operational data flow. A key challenge was keeping the workflow usable when automation was unstable or risky, so I designed it with fallback and manual-review thinking instead of assuming full automation would always work. I describe it as an operations system with strong implemented modules, not just an AI demo.

## 3 Strong Questions You Should Be Ready For

### AutoJobAgent

**Q: What was the hardest part?**

The hardest part was making AI-generated resume output reliable enough for real use. A pretty result is not enough if the system drops core candidate information.

**Q: Why not fully automate everything?**

Because low-confidence cases should not be silently automated. Manual review is often the safer product decision.

**Q: What did you personally change?**

I worked on the resume optimizer flow, structured editing, fallback extraction, output validation, and the related frontend experience.

### Xiaohongshu Project

**Q: Did you really implement the Xiaohongshu-specific part?**

Yes. The project includes Xiaohongshu-specific publishing automation, comment monitoring, web workbench flows, and comment or lead related data structures.

**Q: Is it fully end to end?**

The core modules are implemented, but I would present it honestly as a strong working prototype rather than a fully productionized system.

**Q: What was your technical focus there?**

My focus was workflow architecture, automation reliability, comment and lead handling, and how to keep the system usable under platform constraints.

## Final Advice

You should sound understandable first, capable second, and technical third.

If the reviewer is non-technical, clarity wins.
If the reviewer is technical, clarity still wins first, then depth.

Your current projects are already good enough.

What will make the difference is whether you explain them like a real builder instead of someone listing tools.
