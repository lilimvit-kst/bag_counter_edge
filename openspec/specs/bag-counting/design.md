# Bag Counting Design

## Current implementation

`src/main.py` orchestrates the current frame loop:

1. read frame;
2. detect bags;
3. update tracks;
4. estimate/classify volume once per track when possible;
5. evaluate directed tripwire crossing;
6. evaluate handover;
7. call `_count_bag()` once qualified;
8. persist `BagEvent` and schedule clip extraction.

`src/pipeline/tripwire.py` calculates a horizontal line from `TRIPWIRE_Y_RATIO` and recognizes only top-to-bottom crossing. `src/pipeline/handover_logic.py` uses the configured ROI and `HANDOVER_DISAPPEAR_FRAMES`.

## Highest-risk invariant

Any detector/tracker replacement must prove that one physical bag does not generate multiple persistent count events under short occlusion, worker handover, or temporary re-detection.
