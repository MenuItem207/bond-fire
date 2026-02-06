# Text Rendering Timeline - Visual Explanation

## Before Fix (Glitchy)
```
Time  Frame  Display            Status
─────────────────────────────────────────────────────
 0ms   1    [     FIRE     ]    Text entering from right
10ms   2    [    FIRE      ]    Text scrolling
20ms   3    [   FIRE       ]    
...
90ms  10    [      FIRE    ]    Text halfway across
100ms 11    [       FIR    ]    
110ms 12    [        F     ]    Text almost off left edge
120ms 13    [             ]    Text completely off ❌ NEW TEXT APPEARS!
        →   [  WAITING    ]    ← GLITCH: Overlap during transition!
125ms 14    [  WAITIN      ]
135ms 15    [  WAITI       ]
```

**Problem:** New text appears before old text fully exits = glitchy overlap


## After Fix (Smooth) ✅
```
Time  Frame  Display            Status
─────────────────────────────────────────────────────
 0ms   1    [     FIRE     ]    Text entering from right
10ms   2    [    FIRE      ]    Text scrolling normally
20ms   3    [   FIRE       ]    
...
90ms  10    [      FIRE    ]    Text halfway across
100ms 11    [       FIR    ]    
110ms 12    [        F     ]    
120ms 13    [             ]    Old text COMPLETELY OFF ✓
                              
        ← SYSTEM WAITS HERE ←   New text is queued
        ← isTextFullyVisible ← Text ready to transition
        
130ms 14    [    WAITING   ]    New text enters (fast scroll)
140ms 15    [   WAITING    ]    Fast scroll continues
150ms 16    [  WAITING     ]    
160ms 17    [ WAITING      ]    New text now fully visible
170ms 18    [WAITING       ]    Resume normal scroll speed
...
```

**Solution:** Old text MUST completely exit before new text appears = NO OVERLAP


## State Change Diagram

```
┌─────────────────────────────────────────┐
│  EVENT: State Changes (e.g., FIRE→PARTY)│
└────────────┬────────────────────────────┘
             │
             ↓
    ┌────────────────────┐
    │ Check Conditions?  │
    │ 1. Text matches    │
    │    current state   │
    │ 2. Text fully      │
    │    visible onscreen│
    └─────┬──────────┬───┘
          │          │
         NO         YES
          │          │
          ↓          ↓
    ┌──────────┐  ┌─────────────────────┐
    │  WAIT    │  │ QUEUE NEW TEXT      │
    │ Until    │  │ stateText = "PARTY!"│
    │ ready    │  │ shouldSpeedUpToExit │
    │          │  │ = true              │
    └────┬─────┘  └──────────┬──────────┘
         │                  │
         └──────┬───────────┘
                ↓
        ┌──────────────────┐
        │ Speed Up Scroll  │
        │ (fast mode x3)   │
        └────────┬─────────┘
                 ↓
        ┌──────────────────┐
        │ Old Text Exits   │
        │ (Right → Left)   │
        └────────┬─────────┘
                 ↓
        ┌──────────────────┐
        │ Switch Text      │
        │ FIRE → PARTY     │
        └────────┬─────────┘
                 ↓
        ┌──────────────────┐
        │ New Text Enters  │
        │ (Still fast)     │
        └────────┬─────────┘
                 ↓
        ┌──────────────────┐
        │ Text Becomes     │
        │ Visible (Fully)  │
        └────────┬─────────┘
                 ↓
        ┌──────────────────┐
        │ Resume Normal    │
        │ Scroll Speed     │
        └────────┬─────────┘
                 ↓
        ┌──────────────────┐
        │ Ready for Next   │
        │ State Change     │
        └──────────────────┘
```


## Scroll Position Values

### Example: 10-character text ("WAITING..." = 60 pixels wide)

```
Position 1: Text entering from right edge
─────────────────────────────────────────────
scrollX = 32         (right edge of matrix)
textRightEdge = 32 + 60 = 92
Status: ENTERING

Position 2: Text fully visible on screen
─────────────────────────────────────────────
scrollX = 0          (left aligned)
textRightEdge = 0 + 60 = 60
Status: READABLE ← isTextFullyVisible = true

Position 3: Text exiting to left
─────────────────────────────────────────────
scrollX = -40        (partially off left)
textRightEdge = -40 + 60 = 20
Status: EXITING

Position 4: Text completely off left edge
─────────────────────────────────────────────
scrollX = -65        (completely off)
textRightEdge = -65 + 60 = -5
Status: GONE ← SWITCH TO NEW TEXT
```

### Visibility Logic
```cpp
// Text is fully visible when:
// - At least partially on screen (textRightEdge > 0)
// - AND matches current state (scrollingText == stateText)
// - AND entered from right edge (scrollX has moved left from width)

if (textRightEdge > 0 && scrollingText == stateText) {
  isTextFullyVisible = true;
}

// Text has exited when:
if (textRightEdge <= 0) {
  isTextFullyVisible = false;  // Ready for next change
}
```


## Key Improvements

| Aspect             | Before                | After                |
| ------------------ | --------------------- | -------------------- |
| Text overlap       | ❌ Frequent            | ✅ Never              |
| Smooth transitions | ❌ Glitchy             | ✅ Professional       |
| State response     | ⚠️ Immediate but messy | ✅ Responsive + Clean |
| Text visibility    | ❌ Interrupted         | ✅ Complete           |
| User experience    | ❌ Confusing           | ✅ Clear              |

## Summary
The fix ensures text ALWAYS fully renders from right to left and completely exits before any new text can appear. This prevents overlap, glitches, and provides a smooth, professional appearance.
