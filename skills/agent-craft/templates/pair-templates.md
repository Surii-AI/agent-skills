# Templates for skill + agent pairs

Copy the shape, replace every placeholder. Delete sections that don't earn their place.

## Skill template (`~/.agents/skills/<skill-name>/SKILL.md`)

```markdown
---
name: <skill-name>
description: <What it does + pushy trigger list: concrete phrases a user would type. Mention it pairs with the <agent-name> agent.>
---

# <skill-name>

<One-paragraph role: what this skill owns — triggering, interviewing, packaging context.>

## When this triggers
<Concrete user situations/phrases.>

## Interview
<The questions to ask before delegating, and what to skip if already given.>

## Delegation
Spawn the **<agent-name>** agent via the task tool:
- `context`: <shared contract — goal, file paths, interfaces, constraints.>
- `task`: <self-contained assignment — everything the agent needs, since it has no conversation history.>
- `solutionSpace`: <how open-ended the fix/design is.>

## Done looks like
<Observable end state; what the agent's report should contain.>

## Anti-jobs
<What this skill must not do.>
```

## Agent template (`~/.omp/agent/agents/<agent-name>.md`)

```markdown
---
name: <agent-name>
description: <One sentence: the job + when to delegate here.>
model: <selector like "zai/glm-5.3-flash", or omit to inherit parent's model>
tools: <CSV like "read, grep, glob, write, edit, bash", or omit for default set>
---

You are <persona name>. Your one job: <job>.

How you work:
1. <Steps. If required preferences are missing from the task, return the questions
   to the delegating assistant instead of guessing.>
2. Bias to act once the job is clear.

Output: <exact deliverable + its path if a file>.

Voice: <persona voice, e.g. casual, short lowercase.>
```
