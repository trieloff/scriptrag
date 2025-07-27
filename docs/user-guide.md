# ScriptRAG User Guide for Scriptwriters

## Introduction

ScriptRAG is a powerful tool designed specifically for screenwriters to analyze,
search, and understand their scripts using advanced AI technology. This guide will
help you get started with the ScriptRAG API to enhance your writing workflow.

## Getting Started

### What You'll Need

1. **Your Script**: In Fountain format (.Fountain or .txt file)
2. **API Access**: The ScriptRAG server running (usually at `http://localhost:8000`)
3. **HTTP Client**: A web browser, Postman, or any programming language

### Quick Start

The easiest way to explore ScriptRAG is through the interactive documentation:

1. Open your web browser
2. Navigate to: `http://localhost:8000/api/v1/docs`
3. You'll see an interactive interface to try all API features

## Core Features for Writers

### 1. Upload Your Script

Start by uploading your screenplay to ScriptRAG for analysis.

**Option A: Upload Fountain Text**

```bash
curl -X POST http://localhost:8000/api/v1/scripts/upload \
  -H "Content-Type: application/json" \
  -d '{
    "title": "My Amazing Script",
    "content": "Your fountain content here...",
    "author": "Your Name"
  }'
```

**Option B: Upload Fountain File**

```bash
curl -X POST http://localhost:8000/api/v1/scripts/upload-file \
  -F "file=@my_script.fountain"
```

Save the returned `script_id` - you'll need it for other operations.

### 2. Enable Semantic Search

Generate AI embeddings to enable powerful semantic search:

```bash
curl -X POST http://localhost:8000/api/v1/embeddings/scripts/{script_id}/generate \
  -H "Content-Type: application/json" \
  -d '{"regenerate": false}'
```

This process analyzes your script's meaning and context, enabling searches like
"find romantic scenes" or "tense confrontations."

### 3. Search Your Script

#### Text Search

Find specific words or phrases:

```bash
# Find all mentions of "coffee"
curl -X POST http://localhost:8000/api/v1/search/scenes \
  -H "Content-Type: application/json" \
  -d '{
    "query": "coffee",
    "script_id": "your-script-id"
  }'
```

#### Semantic Search

Find scenes by meaning, not just keywords:

```bash
# Find romantic scenes
curl -X POST http://localhost:8000/api/v1/search/similar \
  -H "Content-Type: application/json" \
  -d '{
    "query": "romantic moment between two characters",
    "script_id": "your-script-id",
    "threshold": 0.7
  }'
```

#### Character Search

Find all scenes featuring a specific character:

```bash
curl http://localhost:8000/api/v1/search/scenes/by-character/JOHN?script_id=your-script-id
```

### 4. Analyze Character Relationships

Understand how your characters interact:

```bash
curl -X POST http://localhost:8000/api/v1/graphs/characters \
  -H "Content-Type: application/json" \
  -d '{
    "character_name": "PROTAGONIST",
    "script_id": "your-script-id",
    "depth": 2
  }'
```

This returns a network showing:

- Which characters interact most
- The strength of relationships
- Character scene presence

### 5. Visualize Your Script Structure

#### Timeline View

See how your script progresses:

```bash
curl -X POST http://localhost:8000/api/v1/graphs/timeline \
  -H "Content-Type: application/json" \
  -d '{
    "script_id": "your-script-id",
    "group_by": "act"
  }'
```

#### Location Map

Understand your location usage:

```bash
curl http://localhost:8000/api/v1/graphs/scripts/{script_id}/locations
```

## Practical Use Cases

### Use Case 1: Character Arc Analysis

**Goal**: Track a character's journey through the script

1. Search for all scenes with your character:

   ```bash
   curl http://localhost:8000/api/v1/search/scenes/by-character/SARAH?script_id=abc123
   ```

2. Analyze their relationships:

   ```bash
   curl -X POST http://localhost:8000/api/v1/graphs/characters \
     -H "Content-Type: application/json" \
     -d '{"character_name": "SARAH", "script_id": "abc123"}'
   ```

3. Search for emotional moments:

   ```bash
   curl -X POST http://localhost:8000/api/v1/search/similar \
     -H "Content-Type: application/json" \
     -d '{
       "query": "Sarah showing vulnerability or emotional growth",
       "script_id": "abc123"
     }'
   ```

### Use Case 2: Pacing Analysis

**Goal**: Check if your script has good rhythm

1. Get scene distribution:

   ```bash
   curl http://localhost:8000/api/v1/scripts/abc123
   ```

2. Find action sequences:

   ```bash
   curl -X POST http://localhost:8000/api/v1/search/similar \
     -H "Content-Type: application/json" \
     -d '{
       "query": "fast-paced action or chase sequences",
       "script_id": "abc123"
     }'
   ```

3. Find quiet moments:

   ```bash
   curl -X POST http://localhost:8000/api/v1/search/similar \
     -H "Content-Type: application/json" \
     -d '{
       "query": "quiet contemplative character moments",
       "script_id": "abc123"
     }'
   ```

### Use Case 3: Dialogue Consistency

**Goal**: Ensure character voices are consistent

1. Find all dialogue for a character:

   ```bash
   curl http://localhost:8000/api/v1/search/scenes/by-character/DETECTIVE?script_id=abc123
   ```

2. Search for specific speech patterns:

   ```bash
   curl -X POST http://localhost:8000/api/v1/search/scenes \
     -H "Content-Type: application/json" \
     -d '{
       "query": "investigation clues evidence",
       "character": "DETECTIVE",
       "script_id": "abc123"
     }'
   ```

### Use Case 4: Theme Exploration

**Goal**: Track thematic elements

1. Search for thematic scenes:

   ```bash
   curl -X POST http://localhost:8000/api/v1/search/similar \
     -H "Content-Type: application/json" \
     -d '{
       "query": "scenes exploring themes of redemption and forgiveness",
       "script_id": "abc123"
     }'
   ```

2. Find symbolic moments:

   ```bash
   curl -X POST http://localhost:8000/api/v1/search/similar \
     -H "Content-Type: application/json" \
     -d '{
       "query": "symbolic or metaphorical imagery",
       "script_id": "abc123"
     }'
   ```

## Working with Results

### Understanding Search Results

Search results include:

- **Scene ID**: Unique identifier
- **Scene Number**: Position in script
- **Heading**: Scene location/time
- **Snippet**: Relevant excerpt
- **Score**: Relevance score (0-1)

### Understanding Graph Data

Graph results contain:

- **Nodes**: Characters, locations, or scenes
- **Edges**: Relationships between nodes
- **Weights**: Strength of relationships

## Tips for Better Results

### 1. Semantic Search Queries

**Good Queries**:

- "tense confrontation between protagonist and antagonist"
- "moments of comic relief"
- "scenes showing character growth"
- "establishing shots of the city"

**Less Effective**:

- Single words like "good" or "bad"
- Very specific dialogue (use text search instead)
- Technical terms not in your script

### 2. Adjusting Search Sensitivity

- **Higher threshold** (0.8-0.9): Very similar scenes only
- **Medium threshold** (0.6-0.7): Reasonably related scenes
- **Lower threshold** (0.4-0.5): Loosely related scenes

### 3. Combining Search Types

For comprehensive analysis, combine:

1. Text search for specific elements
2. Semantic search for thematic content
3. Character search for arc tracking

## Troubleshooting

### "No results found"

- Check your script_id is correct
- For semantic search, ensure embeddings are generated
- Try lowering the threshold or broadening your query

### "Embeddings not generated"

- Run the embedding generation endpoint
- Wait for completion (check status endpoint)
- Larger scripts take more time

### "Script not found"

- Verify the script was uploaded successfully
- Use the list scripts endpoint to see all available scripts
- Check you're using the correct script_id

## Advanced Features

### Scene Editing

Update scenes directly through the API:

```bash
curl -X PATCH http://localhost:8000/api/v1/scenes/{scene_id} \
  -H "Content-Type: application/json" \
  -d '{
    "content": "Updated scene content..."
  }'
```

### Script Comparison

Compare character presence across scripts:

1. Upload multiple scripts
2. Generate embeddings for each
3. Search for similar themes across all scripts

### Export Integration

While direct export isn't available via API, you can:

1. Retrieve full script data
2. Process with your preferred tools
3. Export to Final Draft, PDF, etc.

## Best Practices

1. **Regular Uploads**: Upload new drafts to track changes
2. **Consistent Naming**: Use clear, versioned script titles
3. **Meaningful Searches**: Use descriptive queries for semantic search
4. **Explore Relationships**: Don't just search - analyze connections
5. **Iterative Refinement**: Adjust queries based on results

## Next Steps

- Explore the [API Reference](./api-reference.md) for detailed endpoint documentation
- Check the [Developer Guide](./developer-guide.md) to build custom tools
- Visit the interactive docs at `/api/v1/docs` to experiment
