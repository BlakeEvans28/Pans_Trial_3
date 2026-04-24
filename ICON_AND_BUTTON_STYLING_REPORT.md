# Icon Display and Button Styling Analysis Report

## Non-Title Screens: Icon and Graphics Display

This report analyzes all non-title screens (excluding the Start/Menu screen) to identify where icons are displayed and the current button/graphics styling approach.

---

## Screen-by-Screen Summary

### 1. **How To Play Screen**
**File:** `ui/screen_manager.py` (lines 445-667)

**Icons/Graphics Displayed:**
- None (text-based content)
- Two-column layout of discussion cards with borders

**Button Styling:**
- Single "Back" button at bottom
- **Currently uses:** Wood button styling via `_render_wood_button()` method
- Wood texture from `Pan_Icon.png` (cropped plank area)
- Hover effect with brightened text
- Supports enabled/disabled states with overlay veil

**Current Approach:** Minimalist - focuses on text content with single navigation button

---

### 2. **Settings Screen**
**File:** `ui/screen_manager.py` (lines 668-991)

**Icons/Graphics Displayed:**
- None (text-based labels)
- Optional warning box for missing art assets (Trap.png, Ballista.png, Stone_Wall.jpg)

**Button Styling:**
- 6 setting option buttons + 1 Back button
- **Currently uses:** Wood button styling for ALL buttons via `_render_wood_button()`
- Buttons include:
  - Display (Fullscreen/Windowed toggle)
  - Text Size (Small/Normal/Large)
  - Animation Speed (Slow/Normal/Fast)
  - Sound Volume (Muted/50%/100%)
  - Tutorial Tips (On/Off)
  - Reset Tutorial Cycle
  - Back

**Current Approach:** Fully styled with wood buttons throughout

**Styling Details:**
- Wood texture from cropped `Pan_Icon.png`
- Title-style serif font for button text
- Hover state: brighter text color
- Disabled state: overlay veil with reduced opacity

---

### 3. **Coin Flip Screen**
**File:** `ui/screen_manager.py` (lines 992-1084)

**Icons/Graphics Displayed:**
- Animated coin circle (2-second animation)
- Circle displays "P1" or "P2" label based on winner
- No suit or card icons

**Visual Elements:**
- Circle filled with player color: Red (208, 84, 84) for P1 or Blue (84, 118, 216) for P2
- Golden border around circle
- Text label in title font

**Current Approach:** Simple animated visual, no button styling needed (automatic)

---

### 4. **Draft Screen**
**File:** `ui/screen_manager.py` (lines 1085-1708)

**Icons/Graphics Displayed:**

#### Draft Cards Grid (6x2 or 3x4 compact):
- Colored card backgrounds based on suit/family
- **Text-based suit display** (NOT vector icons):
  - Rank name (Ten, Queen, King)
  - Family name (Hearts, Diamonds, Clubs, Spades)
- "Taken" placeholder for picked cards

#### Player Hand Panels (showing drafted cards):
- Bottom two panels show Player 1 and Player 2 trial hands
- Each card shows rank and suit as text
- Color-coded accents for each player

#### Draft Value Legend:
- Shows rank values in text form:
  - "Ten: 10"
  - "Queen: 11"
  - "King: 12"

**Button Styling:**
- All interactive elements are rendered manually as colored rectangles
- **No wood button styling used**
- Colored backgrounds based on card family:
  - Pastel versions of family colors for available cards
  - Muted/grayed out for taken cards
- Border colors match family or player accent colors

**Current Approach:** Custom colored card styling, no wood buttons

**Note:** This is a missed opportunity - suit icons could be added to draft cards to visually enhance them, similar to Jack Reveal Screen.

---

### 5. **Jack Reveal Screen**
**File:** `ui/screen_manager.py` (lines 1534-1708)

**Icons/Graphics Displayed:**

#### Omen Cards (4 cards in 2x2 or 4x1 grid):
- **Suit icons** displayed via `draw_suit_icon()` function
- Shows:
  - Text label: "Omen"
  - **Suit icon (vector-drawn)**
  - Family name (Colors, Stones, Grails, Cups)
  - Role name (Walls, Traps, Ballista, Weapons)

#### Shuffling Animation:
- Currently active reveal shows cycling suit icon
- Uses `_cycling_suit()` to rapidly cycle through suits
- Color tone indicates shuffling state (190, 190, 220) vs complete (220, 220, 220)

#### Player Cards Section:
- Two cards shown at bottom (P1 and P2 player cards)
- **Suit icons displayed** via `draw_suit_icon()`
- Shows King rank and suit

**Button Styling:**
- Card containers use custom rectangles with borders
- Bg color: (62, 68, 88) for unrevealed
- Border color: (130, 136, 156)
- **No wood button styling used**

**Current Approach:** Visual hierarchy with suit icons, custom card rendering

---

### 6. **Game Over Screen**
**File:** `ui/screen_manager.py` (lines 1709-1887)

**Icons/Graphics Displayed:**
- None (text-based content)
- Match summary text (if provided)

**Button Styling:**
- Two buttons at bottom:
  - "Play Again"
  - "Main Menu"
- **Currently uses:** Wood button styling via `_render_wood_button()`
- Wood texture from `Pan_Icon.png`
- Hover effect with brightened text
- Located at bottom of screen with small vertical spacing

**Current Approach:** Clean finish with dual navigation options

---

### 7. **Game Screen - Gameplay Popups & UI Elements** (During Active Game)
**File:** `ui/game_screen.py`

#### 7A. **Restructure Selection Popup** (lines 2429-2476)
**Icons/Graphics Displayed:**
- **Suit icons** displayed on each suit button via `draw_suit_icon()`
  - Position: Left side of button at (rect.x + 18px, rect.centery)
  - Size: scaled(10, 6)
- Role name displayed below suit name

**Button Styling:**
- Four suit selection buttons (one per color)
- **Currently uses:** Wood button styling via `_render_game_wood_button()`
- Wood texture from base Screen class
- Selected state: highlighted with brighter text
- Button shows:
  - Suit icon (left side)
  - Family name (center)
  - Role (bottom)

**Current Approach:** Wood-styled buttons with suit icons

---

#### 7B. **Plane Shift Direction Popup** (lines 2477-2511)
**Icons/Graphics Displayed:**
- None (text-based directional labels)

**Button Styling:**
- Four direction buttons:
  - "Shift Up"
  - "Shift Left"
  - "Shift Right"
  - "Shift Down"
- **Currently uses:** Wood button styling via `_render_game_wood_button()`

**Current Approach:** Clean wood buttons with directional text

---

#### 7C. **Plane Shift Confirmation Popup** (lines 2512-2554)
**Icons/Graphics Displayed:**
- Board preview showing affected row/column
- Directional arrow or highlight (visual, not icon)

**Button Styling:**
- Two confirmation buttons:
  - "Apply Shift"
  - "Change Direction"
- **Currently uses:** Wood button styling via `_render_game_wood_button()`

**Current Approach:** Clear confirmation workflow with wood buttons

---

#### 7D. **Other Popups (No Icon Display)**
- Request popup: Text-based, wood buttons
- Hand inspect popup: Card display, no suit icons (text-based)
- Steal Life popup: Card pair display, no suit icons
- Damage popup: Damage card display, text-based

---

#### 7E. **Suit Role Legend** (lines 2851-2895)
**Icons/Graphics Displayed:**
- **Suit icons** displayed for each of 4 colors via `draw_suit_icon()`
- Position: Left of family name in vertical list (desktop) or 2x2 grid (compact)
- Size: scaled(12, 7) desktop / scaled(8, 5) compact
- Shows: Suit icon + Family name + Role text

**Button Styling:**
- **Currently uses:** Custom chip rendering (NOT wood buttons)
- Chips styled with:
  - Background: (30, 34, 46)
  - Border: (92, 104, 124)
  - No hover/interactive state

**Opportunity for Enhancement:** Could be upgraded to wood button styling or interactive hover states

---

#### 7F. **Color Hierarchy Strip** (lines 2894-2934)
**Icons/Graphics Displayed:**
- **Suit icons** displayed for each color in Phase 2 hierarchy via `draw_suit_icon()`
- Position: Inside colored chip at (rect.x + 15px, rect.centery)
- Size: scaled(8, 5)
- Shows: Suit icon + Family name
- Indicates color strength order (Strong → Weak)

**Button Styling:**
- **Currently uses:** Custom chip rendering (NOT wood buttons)
- Chips styled with:
  - Background: (42, 46, 60)
  - Border: (180, 180, 190)
  - Rounded corners
- No interactive/hover state

**Opportunity for Enhancement:** Could be styled as individual wood buttons or upgraded to interactive state

---

## Icon Usage Summary

### Vector Suit Icons (via `draw_suit_icon()`)
- **Used in:** Jack Reveal Screen, Restructure Popup, Suit Role Legend, Color Hierarchy Strip
- **Not used in:** Draft Screen (text-based suit names instead)
- **Size range:** scaled(8, 5) to scaled(18, 10) depending on context
- **Color:** Default (card suit color) or themed (190, 190, 220 for shuffling animation)

### Vector Icons NOT Used (Opportunities)
1. Draft Screen - Cards could display suit icons alongside rank/family names
2. Suit Role Legend - Only shows icons, no interactive wood button styling
3. Color Hierarchy Strip - Chip icons could be styled as wood buttons

---

## Button Styling Summary

### Wood Button Styling (Currently Used)
- **How To Play Screen:** Back button
- **Settings Screen:** All 7 buttons
- **Game Over Screen:** Play Again + Main Menu buttons
- **Game Screen Popups:** Restructure suit buttons, Plane Shift direction buttons, Plane Shift confirmation buttons

**Wood Button Features:**
- Wood texture from `Pan_Icon.png` (cropped plank section)
- Title-style serif font
- Hover state: Brighter text (255, 246, 214) vs normal (246, 236, 204)
- Disabled state: Text dimmed (156, 150, 136) + semi-transparent overlay veil
- Shadow effect on text (3px offset with dark brown)
- Rounded corners

### Custom Styling (Currently Used)
- **Draft Screen:** Colored card backgrounds with family-based colors
- **Jack Reveal Screen:** Card containers with custom borders (no wood texture)
- **Suit Role Legend:** Chip containers with dark background
- **Color Hierarchy Strip:** Chip containers with dark background + light borders

---

## Opportunities for Wood Button Styling Application

### High Priority (Would Enhance Visual Consistency)
1. **Suit Role Legend** - Convert chips to wood buttons
   - Would create visual hierarchy and indicate interactivity
   - Currently feels flat compared to game popups

2. **Color Hierarchy Strip** - Convert chips to wood buttons
   - Would unify with other in-game UI styling
   - Could enable hover states for role information

### Medium Priority (Enhancement Only)
3. **Draft Screen Cards** - Add suit icons to card displays
   - Currently only shows text-based suit names
   - Jack Reveal uses suit icons for visual appeal
   - Would require space management in compact layout

### Low Priority (Polish)
4. **Jack Reveal Screen** - Consider wood button styling for omen cards
   - Currently uses custom card styling
   - Cards are informational only (no selection)
   - Current styling works well for the animation sequence

---

## Recommendations

### For Immediate Implementation
- **Suit Role Legend:** Apply wood button styling to create depth and affordance
- **Color Hierarchy Strip:** Convert to wood button styling for consistency with popups

### For Future Enhancement
- **Draft Screen:** Add suit icons alongside current text displays
- **Draft Screen Player Cards:** Add suit icons for visual richness
- **Standardization:** Ensure all interactive elements use wood button styling
- **Hover States:** Add interactive feedback (color/glow) to non-button icons

---

## Files Requiring Modification (If Changes Made)

1. `ui/game_screen.py` - Lines 2851-2895 (Suit Role Legend), Lines 2894-2934 (Color Hierarchy Strip)
2. `ui/screen_manager.py` - Lines 1534-1708 (Jack Reveal Screen) - optional polish
3. `ui/screen_manager.py` - Lines 1085-1708 (Draft Screen) - optional enhancement

---

## Technical Notes

- All wood button rendering uses `_render_wood_button()` or `_render_game_wood_button()` methods
- Suit icons use `draw_suit_icon()` from `ui/suit_icons.py`
- Wood texture caching available via `_wood_icon_cache` dictionary
- Font scaling respects window size and text scale setting
