# Story Shape Theory for Screenplay Analysis

## 1. Theoretical Foundation

### 1.1 Vonnegut's Original Theory

Kurt Vonnegut developed his Shape of Stories theory in 1946 while studying anthropology at the University of Chicago. His fundamental insight was that stories have shapes that can be drawn on graph paper, and that these shapes reveal as much about a culture as its artifacts.

The system employs two axes:

- **Y-axis (GI-Axis)**: Good fortune to ill fortune
- **X-axis**: Beginning to end of story

Vonnegut believed that "there's no reason these shapes couldn't be fed into computers" - a prediction that proved remarkably prescient.

### 1.2 The 6 Canonical Shapes

Based on Vonnegut's original work and validated by Reagan et al. (2016), six fundamental story shapes emerge:

1. **"Rags to Riches"** - Continuous rise in emotional valence
2. **"Man in Hole"** - Fall then rise
3. **"Cinderella"** - Rise, fall, then rise
4. **"Tragedy"** - Continuous fall in emotional valence
5. **"Oedipus"** - Fall, rise, then fall
6. **"Icarus"** - Rise then fall

### 1.3 Mathematical Representation

Stories can be represented as emotional trajectories over time:

- **f(t)**: Emotional valence function over story time t
- **Positive values**: Good fortune/happiness
- **Negative values**: Ill fortune/sadness
- **Derivatives**: Rate of emotional change (tension/release)

## 2. Screenplay Application

### 2.1 Scene-Level Analysis

In screenplay context, each scene contributes to the overall emotional arc:

```
Scene Valence = Σ(character_fortune + plot_advancement + emotional_tone)
```

Key considerations:

- **Opening scenes**: Establish baseline emotional state
- **Turning points**: Major slope changes in the arc
- **Climax**: Peak emotional intensity (positive or negative)
- **Resolution**: Final emotional state

### 2.2 Character Fortune Tracking

Characters experience individual arcs that contribute to the overall story shape:

1. **Protagonist Arc**: Primary driver of story shape
2. **Antagonist Arc**: Often inverse of protagonist
3. **Supporting Character Arcs**: Provide texture and subplots
4. **Ensemble Dynamics**: Multiple intersecting arcs

### 2.3 Genre Considerations

Different genres favor specific story shapes:

- **Comedy**: Predominantly "Man in Hole" and "Cinderella"
- **Drama**: Full spectrum, often "Oedipus" or complex combinations
- **Tragedy**: "Tragedy" and "Icarus" shapes
- **Romance**: "Boy Meets Girl" (variant of "Man in Hole")
- **Action**: Often "Man in Hole" with multiple cycles

## 3. Implementation Guidelines

### 3.1 Valence Calculation Methods

#### Sentiment Analysis Approach (Reagan et al., 2016)

1. **Window-based analysis**: 10,000 word sliding Windows
2. **Hedonometer scoring**: Emotional content rating
3. **Smoothing**: Apply moving average to reduce noise

#### Scene-based Approach for Screenplays

1. **Scene classification**: Rate each scene (-1 to +1)
2. **Character state tracking**: Monitor protagonist fortune
3. **Weighted averaging**: Consider scene importance/duration

### 3.2 Pattern Matching Approaches

#### Template Matching

- Define reference curves for each canonical shape
- Calculate similarity metrics (e.g., DTW, correlation)
- Identify best-fit shape and variations

#### Machine Learning

- Feature extraction: slope changes, peaks, valleys
- Classification models: SVM, neural networks
- Clustering: discover non-canonical patterns

### 3.3 Edge Case Handling

1. **Multiple Protagonists**: Weighted average or separate tracking
2. **Non-linear Narratives**: Reconstruct chronological order
3. **Ambiguous Endings**: Consider audience interpretation
4. **Experimental Structures**: May not fit canonical shapes

## 4. ASCII Visual Representations

### 4.1 Basic Story Shapes

```
1. Rags to Riches (Rise)

   Good |     _____
        |    /
        |   /
        |  /
   Bad  |_/________
        Begin    End

2. Man in Hole (Fall-Rise)

   Good |_    ___
        | \  /
        |  \/
        |
   Bad  |________
        Begin    End

3. Cinderella (Rise-Fall-Rise)

   Good |   /\    /
        |  /  \  /
        | /    \/
        |/
   Bad  |________
        Begin    End

4. Tragedy (Fall)

   Good |\
        | \
        |  \
        |   \____
   Bad  |________
        Begin    End

5. Oedipus (Fall-Rise-Fall)

   Good |\    /\
        | \  /  \
        |  \/    \
        |         \
   Bad  |__________
        Begin    End

6. Icarus (Rise-Fall)

   Good |    /\
        |   /  \
        |  /    \
        | /      \
   Bad  |________
        Begin    End
```

### 4.2 Complex Patterns

```
Double Man in Hole (Popular Pattern)

   Good |_  _  _  _
        | \/ \/ \/
        |
   Bad  |__________
        Begin    End

Cinderella + Tragedy (Popular Combination)

   Good |   /\  
        |  /  \  /\
        | /    \/  \
        |/          \
   Bad  |____________
        Begin    End
```

## 5. Computational Implementation

### 5.1 Data Structures

```python
class StoryShape:
    """Represents a story's emotional trajectory"""

    def __init__(self):
        self.scenes = []  # List of (time, valence) tuples
        self.shape_type = None
        self.complexity = 0

class Scene:
    """Individual scene with emotional valence"""

    def __init__(self, scene_number, valence, characters, duration):
        self.scene_number = scene_number
        self.valence = valence  # -1.0 to 1.0
        self.characters = characters
        self.duration = duration
```

### 5.2 Analysis Pipeline

1. **Parse Screenplay**: Extract scenes, dialogue, action
2. **Scene Analysis**: Calculate emotional valence per scene
3. **Trajectory Construction**: Build time-series data
4. **Shape Classification**: Match to canonical patterns
5. **Visualization**: Generate arc diagrams

### 5.3 Integration with ScriptRAG

The Story Shape Mentor will:

- Analyze uploaded screenplays for their emotional arc
- Suggest improvements based on genre expectations
- Identify pacing issues and emotional dead zones
- Compare against successful films in same genre
- Provide revision suggestions for better emotional impact

## 6. Research References

### Primary Sources

1. Vonnegut, K. (1981). "Palm Sunday: An Autobiographical Collage"
2. Reagan, A. J., et al. (2016). "The emotional arcs of stories are dominated by six basic shapes." EPJ Data Science, 5(1), 31.
3. Boyd, R. L., Blackburn, K. G., & Pennebaker, J. W. (2020). "The narrative arc: Revealing core narrative structures through text analysis." Science Advances, 6(32).

### Additional Resources

1. Kim, E., et al. (2017). "Computational analysis of narrative structure"
2. Computational Story Lab, University of Vermont
3. Project Gutenberg emotional arc analysis dataset

## 7. Future Enhancements

1. **Real-time Analysis**: Analyze as screenplay is written
2. **Genre-specific Models**: Refined patterns for each genre
3. **Cultural Variations**: Story shapes across different cultures
4. **Audience Response Prediction**: Correlate shapes with success
5. **Interactive Visualization**: D3.js-based arc explorer
6. **Multi-dimensional Analysis**: Beyond simple good/bad fortune

---

*This document serves as the theoretical foundation for implementing the Story Shape Mentor in ScriptRAG. It combines Vonnegut's intuitive insights with modern computational approaches to provide screenwriters with data-driven feedback on their narrative structures.*
