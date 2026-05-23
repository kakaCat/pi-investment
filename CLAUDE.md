# pi-investment Project Guide

## gstack Configuration

This project uses [gstack](https://github.com/garrytan/gstack) - Garry Tan's AI development toolkit with 53 specialized skills.

### Browser Usage
- **Always use `/browse` skill from gstack for all web browsing**
- **Never use `mcp__claude-in-chrome__*` tools**

### Available gstack Skills

#### Planning & Strategy
- `/office-hours` - Six forcing questions before coding
- `/plan-ceo-review` - Product strategy review
- `/plan-eng-review` - Architecture and technical review
- `/plan-design-review` - Design system review
- `/plan-devex-review` - Developer experience audit
- `/autoplan` - Automated CEO → design → eng review

#### Design
- `/design-consultation` - Build complete design system
- `/design-shotgun` - Generate multiple mockup variants
- `/design-html` - Convert mockups to production HTML
- `/design-review` - Audit and fix design issues

#### Development & Review
- `/review` - Find production bugs, auto-fix obvious ones
- `/investigate` - Systematic root-cause debugging
- `/codex` - Independent code review from OpenAI Codex

#### Testing & QA
- `/qa` - Test app in real browser, find and fix bugs
- `/qa-only` - Pure bug report without code changes
- `/devex-review` - Live DX audit with TTHW timing
- `/cso` - OWASP Top 10 + STRIDE security audit

#### Shipping & Deployment
- `/ship` - Sync, test, push, open PR
- `/land-and-deploy` - Merge PR, wait for CI/deploy, verify
- `/canary` - Post-deploy monitoring
- `/document-release` - Update all docs after shipping

#### Browser & Automation
- `/browse` - Real Chromium browser control
- `/open-gstack-browser` - Launch AI-controlled browser
- `/pair-agent` - Share browser with multiple AI agents
- `/setup-browser-cookies` - Import cookies from Chrome/Arc/Brave/Edge

#### Utilities
- `/retro` - Weekly engineering retrospective
- `/learn` - Manage gstack learning across sessions
- `/careful` - Warn before destructive commands
- `/freeze` - Lock edits to one directory
- `/guard` - Full safety mode
- `/gstack-upgrade` - Self-updater

#### iOS Testing
- `/ios-qa` - Drive real iPhone over USB
- `/ios-fix`, `/ios-design-review`, `/ios-clean`, `/ios-sync` - iOS-specific workflows

## Project Overview

TypeScript-based AI stock investment advisor using DeepSeek model.

### Key Technologies
- **Runtime**: Node.js with TypeScript
- **AI Model**: DeepSeek
- **Data Sources**: AkShare-TS, Tushare MCP
- **Architecture**: Service layer with tool registry pattern

### Important Notes
- Economic data: Use WebSearch/WebFetch for external sources
- ML Pipeline: Python backtesting in `ml-pipeline/`, TS integration via quant-tools
- Agent Behavior: DeepSeek processes one tool at a time
