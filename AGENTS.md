# AGENTS

<skills_system priority="1">

## Available Skills

<!-- SKILLS_TABLE_START -->
<usage>
When users ask you to perform tasks, check if any of the available skills below can help complete the task more effectively. Skills provide specialized capabilities and domain knowledge.

How to use skills:
- Invoke: `npx openskills read <skill-name>` (run in your shell)
  - For multiple: `npx openskills read skill-one,skill-two`
- The skill content will load with detailed instructions on how to complete the task
- Base directory provided in output for resolving bundled resources (references/, scripts/, assets/)

Usage notes:
- Only use skills listed in <available_skills> below
- Do not invoke a skill that is already loaded in your context
- Each skill invocation is stateless
</usage>

<available_skills>

<skill>
<name>antislop</name>
<description>Universal writing style that suppresses detectable AI writing patterns across all content types. Apply whenever writing, editing, or reviewing any prose — emails, blog posts, reports, social content, technical writing, sales materials. This is an ambient style, not a task-specific tool. Trigger any time the user asks to write, rewrite, edit, polish, or review text of any kind.</description>
<location>project</location>
</skill>

<skill>
<name>antislop-audit</name>
<description>Audits text for AI slop patterns and returns a slop score (0-100) plus a violations list. Use when the user asks to check, audit, review, grade, or score text for AI patterns, AI slop, or writing quality. Also trigger when the user pastes text and asks "does this pass?", "is this sloppy?", "flag the AI patterns", or similar. Companion to the antislop writing style skill. Zero exceptions — flag every violation regardless of perceived intent or satire.</description>
<location>project</location>
</skill>

</available_skills>
<!-- SKILLS_TABLE_END -->

</skills_system>
