"""
CARD GRAPHICS RECOMMENDATIONS FOR PAN'S TRIAL
==============================================

The Pan's Trial code is designed to work with any card graphics format.
Here are the best options for getting card assets:

"""

BEST OPTIONS FOR YOUR PROJECT
==============================

1. PLAYING CARD GRAPHICS (Best Match for Code)
   
   Option A: Kenney.nl - Free Assets
   └─ Website: https://kenney.nl/
   └─ Asset: "Playing Cards"
   └─ Format: PNG (works perfectly with Pillow)
   └─ License: CC0 (completely free)
   └─ Size: 140x190 pixels per card
   └─ Coverage: Full 52-card deck
   └─ Quality: High, professional
   └─ Recommendation: ⭐⭐⭐⭐⭐ BEST CHOICE
   
   How to use with Pan's Trial:
   1. Download the "Card" asset pack from Kenney.nl
   2. Extract PNGs to assets/cards/
   3. Load with Pillow in board_renderer.py:
   
     from PIL import Image
     card_image = Image.open(f"assets/cards/{rank}_{suit}.png")


2. CARD DECK GRAPHICS (Vector/SVG)
   
   Option B: SVGCards - Free Vector Cards
   └─ GitHub: https://github.com/htdebeer/SVGCards
   └─ Format: SVG (can convert to PNG with CairoSVG)
   └─ License: CC0 (free)
   └─ Coverage: Full deck + custom suits
   └─ Quality: Professional vector graphics
   └─ Recommendation: ⭐⭐⭐⭐ (extra setup needed)
   
   How to use with Pan's Trial:
   1. Clone or download SVGCards
   2. Convert SVG to PNG using CairoSVG (already installed):
   
     import cairosvg
     cairosvg.svg2png(
         url="assets/cards/Hearts_2.svg",
         write_to="assets/cards/hearts_2.png",
         output_width=140,
         output_height=190
     )
   
   3. Then load PNGs as in Option A


3. OPEN SOURCE GAME ASSETS
   
   Option C: OpenGameArt.org
   └─ Website: https://opengameart.org/
   └─ Search: "playing cards" or "card deck"
   └─ License: Various (check each asset)
   └─ Quality: Medium to high
   └─ Recommendation: ⭐⭐⭐⭐ (check licenses)
   
   Popular assets:
   • "Standard Playing Card Deck" by spasticallylawful
   • "Card Suits" by Redshrike
   • Various deck designs with different styles


4. PIXABAY / UNSPLASH (Photorealistic)
   
   Option D: Stock Image Sites
   └─ Website: pixabay.com, unsplash.com
   └─ Search: "playing card deck"
   └─ License: Free for commercial use
   └─ Quality: High (photorealistic)
   └─ Recommendation: ⭐⭐⭐ (needs manual processing)
   
   Note: May need to crop/process images to extract individual cards


5. ITCH.IO - Indie Game Assets
   
   Option E: Itch.io Game Assets
   └─ Website: https://itch.io/game-assets/tag-cards
   └─ License: Varies (many free options)
   └─ Quality: Medium to high
   └─ Recommendation: ⭐⭐⭐⭐ (great variety)
   
   Search for:
   • "Card deck" or "playing cards"
   • Filter by "Free" or "Pay What You Want"


═══════════════════════════════════════════════════════════════════════

RECOMMENDED WORKFLOW
====================

Step 1: Choose Graphics
   → Download from Kenney.nl (easiest, highest quality)

Step 2: Organize Files
   Structure:
   assets/
   └── cards/
       ├── hearts_2.png
       ├── hearts_3.png
       ├── ... (all 52 cards)
       ├── diamonds_2.png
       ├── clubs_2.png
       └── spades_2.png

Step 3: Name Convention
   Use: {suit}_{rank}.png
   Examples:
   - hearts_2.png (2 of Hearts)
   - hearts_k.png (King of Hearts)
   - spades_a.png (Ace of Spades)
   - clubs_10.png (10 of Clubs)

Step 4: Load in Code
   ```python
   from PIL import Image
   
   def load_card_image(suit, rank):
       filename = f"assets/cards/{suit}_{rank}.png"
       return Image.open(filename)
   
   # Usage
   image = load_card_image("hearts", "2")
   ```

Step 5: Integrate with Rendering
   In board_renderer.py:
   ```python
   def render_card(self, surface, card, x, y):
       image = self.load_card_image(card.suit.value, card.rank.name.lower())
       image = pygame.image.fromstring(...)
       surface.blit(image, (x, y))
   ```

═══════════════════════════════════════════════════════════════════════

KENNEY.NL SETUP GUIDE (RECOMMENDED)
===================================

1. Go to: https://kenney.nl/assets/playing-cards

2. Download the asset pack

3. Extract to your project:
   Pans_Trial/assets/cards/

4. Files you'll have:
   - card_back.png (card back design)
   - card_clubs_2.png through card_spades_a.png

5. Rename if needed to match your convention:
   mv card_clubs_2.png clubs_2.png
   (or write a script to batch rename)

6. Update board_renderer.py to load and display:

   ```python
   from PIL import Image
   import pygame
   
   def _render_card_image(self, surface, card, x, y):
       """Render card with image."""
       try:
           filename = f"assets/cards/card_{card.suit.value}_{card.rank.name.lower()}.png"
           image = Image.open(filename)
           # Convert PIL image to pygame
           mode = image.mode
           size = image.size
           data = image.tobytes()
           pygame_image = pygame.image.fromstring(data, size, mode)
           surface.blit(pygame_image, (x, y))
       except:
           # Fallback to text rendering if image not found
           pass
   ```

═══════════════════════════════════════════════════════════════════════

INTEGRATION WITH CURRENT CODE
==============================

Current Status:
- ✓ board_renderer.py renders card text (rank + suit)
- ✓ Code structure ready for image integration
- ✓ Pillow and CairoSVG already installed

To Add Graphics:
1. Update _render_card_info() in board_renderer.py
2. Add image loading and display
3. Keep text fallback for debugging

Implementation difficulty: EASY
Expected time: 30 minutes

Example Enhancement:
```python
# In board_renderer.py

def _render_card_image(self, surface, card, x, y, width, height):
    """Try to render card image, fallback to text."""
    try:
        # Load image
        suit_name = card.suit.value
        rank_name = card.rank.name.lower()
        path = f"assets/cards/{suit_name}_{rank_name}.png"
        image = Image.open(path)
        
        # Resize to cell size
        image = image.resize((width, height))
        
        # Convert and blit
        pygame_image = pygame.image.fromstring(...)
        surface.blit(pygame_image, (x, y))
    except FileNotFoundError:
        # Fallback: render text
        self._render_card_info(surface, card, x, y)

# Update _render_cells to use it
def _render_cells(self, surface, board, suit_roles):
    for row in range(self.GRID_HEIGHT):
        for col in range(self.GRID_WIDTH):
            # ... existing code ...
            
            if cell_content.card is not None:
                # Try image first
                self._render_card_image(surface, card, x, y, w, h)
            # ... rest of code ...
```

═══════════════════════════════════════════════════════════════════════

QUICK DECISION MATRIX
=====================

Situation                          → Recommended Option
─────────────────────────────────────────────────────
"I want it now"                    → Kenney.nl (Option A)
"I want vector graphics"           → SVGCards (Option B)
"I want variety of styles"         → OpenGameArt (Option C)
"I want photorealistic"            → Pixabay (Option D)
"I have limited budget"            → All options are free
"I need immediate use"             → Kenney.nl cards are ready-to-use PNG

═══════════════════════════════════════════════════════════════════════

MY RECOMMENDATION: KENNEY.NL
============================

Why Kenney.nl?
✓ Free (CC0 License)
✓ High quality professional graphics
✓ PNG format (perfect for Pillow)
✓ 52 cards + card back
✓ Standard playing card design
✓ No setup/conversion needed
✓ Works immediately

Time to integrate: ~30 minutes
Quality: Excellent
Cost: Free

═══════════════════════════════════════════════════════════════════════

NEXT STEPS
==========

1. Download graphics from Kenney.nl
2. Extract to assets/cards/
3. Update board_renderer.py to load images
4. Test the rendering

Would you like me to:
A) Help integrate Kenney.nl graphics into the code?
B) Write a batch-rename script for file organization?
C) Update board_renderer.py with image loading?

Just let me know!

═══════════════════════════════════════════════════════════════════════
"""

# Save this file as reference
print(__doc__)
