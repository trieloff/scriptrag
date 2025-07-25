# AI Agent Guidelines for ScriptRAG

This document contains guidelines and rules for AI agents working on the ScriptRAG project. Following these guidelines ensures consistency and adds character to our development process.

## 📝 Commit Message Guidelines

### Rule 1: Semantic Commits with Movie Quotes

All commit messages MUST follow the semantic-commit format AND include a fitting, memorable movie quote that relates to the change being made.

#### Format

```text
<type>(<scope>): <subject>

<body>

"<movie quote>" - <character>, <movie> (<year>)
```

#### Semantic Commit Types

- `feat`: A new feature
- `fix`: A bug fix
- `docs`: Documentation only changes
- `style`: Changes that do not affect the meaning of the code (white-space, formatting, etc)
- `refactor`: A code change that neither fixes a bug nor adds a feature
- `perf`: A code change that improves performance
- `test`: Adding missing tests or correcting existing tests
- `build`: Changes that affect the build system or external dependencies
- `ci`: Changes to CI configuration files and scripts
- `chore`: Other changes that don't modify src or test files
- `revert`: Reverts a previous commit

#### Examples

```text
feat(parser): add fountain screenplay parser integration

Integrated the fountain parser library to handle screenplay format parsing.
This enables the system to read and understand standard fountain files.

"Roads? Where we're going, we don't need roads." - Doc Brown, Back to the Future (1985)
```

```text
fix(database): resolve connection timeout in graph queries

Fixed SQLite connection timeout by implementing proper connection pooling
and retry logic for long-running graph traversal operations.

"Houston, we have a problem." - Jim Lovell, Apollo 13 (1995)
```

```text
docs(readme): update installation instructions for uv

Added detailed steps for installing with uv package manager and
clarified Python version requirements.

"Help me, Obi-Wan Kenobi. You're my only hope." - Princess Leia, Star Wars (1977)
```

```text
refactor(llm): simplify embedding generation pipeline

Streamlined the embedding generation process by removing redundant
transformations and implementing batch processing.

"I love it when a plan comes together." - Hannibal, The A-Team (2010)
```

```text
test(scene): add comprehensive scene ordering tests

Added test coverage for temporal, logical, and script-based scene
ordering algorithms.

"I'll be back." - The Terminator, The Terminator (1984)
```

#### Movie Quote Selection Guidelines

1. **Relevance**: The quote should relate to the nature of the change:
   - Bug fixes: Use quotes about problems, mistakes, or solutions
   - Features: Use quotes about creation, innovation, or new beginnings
   - Refactoring: Use quotes about transformation or improvement
   - Documentation: Use quotes about communication or understanding

2. **Memorability**: Choose quotes that are widely recognized and memorable

3. **Appropriateness**: Keep quotes professional and workplace-appropriate

4. **Variety**: Try to use quotes from different genres and eras of cinema

5. **Context**: For a screenwriting tool, film quotes are particularly fitting

#### Great Quote Sources by Commit Type

**For Features:**

- "If you build it, he will come." - Field of Dreams
- "To infinity and beyond!" - Toy Story
- "Life finds a way." - Jurassic Park

**For Fixes:**

- "We're gonna need a bigger boat." - Jaws
- "I've got a bad feeling about this." - Star Wars (multiple)
- "Fasten your seatbelts. It's going to be a bumpy night." - All About Eve

**For Refactoring:**

- "I feel the need... the need for speed!" - Top Gun
- "Nobody puts Baby in a corner." - Dirty Dancing
- "There is no spoon." - The Matrix

**For Documentation:**

- "Explain it to me like I'm five." - Philadelphia (adapted)
- "You can't handle the truth!" - A Few Good Men
- "Show me the money!" - Jerry Maguire

**For Tests:**

- "Are you not entertained?" - Gladiator
- "I'll have what she's having." - When Harry Met Sally
- "There's no crying in baseball!" - A League of Their Own

---

## 🎬 Why Movie Quotes?

ScriptRAG is a screenwriting assistant, making movie quotes a natural fit for our commit messages. They add personality to our git history while maintaining the semantic commit format's clarity and usefulness. Plus, they make reviewing git logs more enjoyable!

## 📚 Future Guidelines

This document will be expanded with additional guidelines as the project evolves. Check back regularly for updates.

---

*"After all, tomorrow is another day!" - Scarlett O'Hara, Gone with the Wind (1939)*
