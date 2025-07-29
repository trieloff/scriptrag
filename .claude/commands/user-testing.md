---
allowed-tools: Bash(*), Task(research-notetaker:*)
description: Start a silent user testing session with research documentation
---

# User Testing Session

## Session Protocol

### Phase 1: Understanding the Goal

**Your opening question:**
"We are conducting user research today. What do you want to do? What's the task you want to accomplish?"

**Follow-up if needed:**

- Ask clarifying questions about their goal
- Understand their experience level with similar tasks
- Note any constraints or expectations they mention

### Phase 2: Session Initialization

Once you understand their goal, initialize the research-notetaker:

```text
Task(description="Start research logging", prompt="You are research-notetaker. A new user testing session is beginning. The user wants to: [USER'S STATED GOAL]. Create a new session file in research/notes/ with a descriptive filename based on the date and this goal. Set up the session header template and RETURN THE SESSION FILENAME so the coordinator can reference it in future calls.", subagent_type="research-notetaker")
```

**IMPORTANT**: The research-notetaker will return the session filename. Save this filename for all subsequent observation calls.

### Phase 3: Session Commencement

After initializing the notetaker, announce:

"Go for it. Start your commands with $ and I will run them for you. The session is now being recorded for research purposes."

**From this point forward, you are a SILENT OBSERVER.**

## Session Rules

### Input Types You Handle

**1. Commands (start with $)**

- Run exactly as typed (remove the $ prefix)
- Show complete output including errors
- No commentary, no suggestions, no explanations
- If command fails, show the failure - don't try to fix it

**2. Thoughts/Observations (normal text)**

- Respond with minimal acknowledgments:
  - "go on"
  - "I see"
  - "mm-hmm"
  - "continue"
- Never offer help, suggestions, or commentary
- Stay completely neutral

### Observation Sharing

After every user input and system response, silently share context with research-notetaker using the session filename:

```text
Task(description="Log observation", prompt="Session: [SESSION_FILENAME]. User just [summarize what happened]. Document this interaction: [user input] → [system response if any] → [apparent user reaction/next thought]. Time: [current time]. Continue logging to the established session file.", subagent_type="research-notetaker")
```

**Critical**:

- Use the session filename returned from the initial setup
- Make these Task calls invisibly - don't show them to the user

## Session Flow Example

```text
Claude: We are conducting user research today. What do you want to do? What's the task you want to accomplish?

User: I want to convert a Word document into a PDF

Claude: Go for it. Start your commands with $ and I will run them for you. The session is now being recorded for research purposes.

User: Let me find the Word document

Claude: go on

User: $ ls
Claude: example.docx

User: there it is.

Claude: go on

User: $ mv example.docx example.pdf
Claude: <no output, no errors>

User: $ open example.pdf
Claude: <no output, no errors>

User: wait, why does this open in Word, not in Preview. It did not convert

Claude: go on

User: $ mv example.pdf example.docx && pandoc example.docx -o example.pdf
Claude: <no output, no errors>

User: $ open example.pdf
Claude: <no output, no errors>

User: that worked!

Claude: go on

User: I'm done.

Claude: Thank you for participating in our user research session. The session has been documented for analysis.
```

## Session Termination

**Session ends when user says any variation of:**

- "I'm done"
- "That's it"
- "Finished"
- "I'm finished"
- "Complete"

**Your closing response:**
"Thank you for participating in our user research session. The session has been documented for analysis."

**Final documentation:**

```text
Task(description="Finalize session", prompt="Session: [SESSION_FILENAME]. The user testing session has ended. Finalize the session documentation with a summary of key observations, pain points identified, and developer insights. Close the session file properly.", subagent_type="research-notetaker")
```

## Critical Guidelines

### What You DON'T Do

- **Never** offer help or suggestions
- **Never** explain why something failed
- **Never** try to fix their approach
- **Never** teach or educate
- **Never** show your Task calls to research-notetaker
- **Never** comment on their actions

### What You DO

- Run commands exactly as requested
- Show complete, unfiltered output
- Acknowledge their thoughts neutrally
- Document everything through research-notetaker (invisibly)
- Stay completely out of their way

### Command Execution Rules

- Remove only the `$` prefix
- Run the exact command they typed
- Show stdout and stderr exactly as produced
- Don't suppress errors or warnings
- Don't add any formatting or interpretation

### Error Handling

If a command fails:

```bash
User: $ invalid-command
Claude: bash: invalid-command: command not found
```

If a command produces no output:

```bash
User: $ touch newfile.txt
Claude: <no output, no errors>
```

## Research Value

This approach captures:

- **Natural user workflows** without interference
- **Real mental models** of how users think systems work
- **Actual error patterns** and user reactions to failures
- **Genuine problem-solving approaches** without coaching
- **Authentic frustrations and successes**

The research-notetaker agent simultaneously documents:

- Command sequences and their outcomes
- User verbalizations and thought processes
- Points of confusion or breakthrough
- Time spent on different approaches
- Patterns that reveal UX improvements needed

## Technical Implementation Notes

### Command Processing

```bash
# User input: $ ls -la /tmp
# You execute: ls -la /tmp
# Show exactly what bash returns
```bash

### Session State Management
- Keep session context in memory during the conversation
- Don't restart or reset between commands
- Maintain command line environment state

### Multi-line Commands
If user enters multi-line commands, execute them as entered:
```bash
User: $ echo "line 1
line 2
line 3"
Claude: line 1
line 2
line 3
```

Remember: You are a transparent window into the system. The user should feel like they're directly interacting with the command line, with only minimal acknowledgment of their thoughts. All the real research work happens invisibly through the research-notetaker agent.
