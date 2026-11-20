# Maratha Command

A turn-based operational wargame of the Mughal-Maratha War, inspired by *Unity of Command* and written in Python with pygame.

March 1700: Chhatrapati Rajaram has died and Emperor Aurangzeb is besieging Satara. You command Maharani Tarabai's Marathas against the AI-controlled Mughal Empire across the Deccan for 16 monthly turns (March 1700 to June 1701).

## Running

Requires Python 3.9+.

```
pip install -r requirements.txt
python main.py
```

## How to win

Capture Mughal cities, forts and camps to earn victory points, and hold your own forts (losing one costs you its points). At the end of turn 16:

| Victory points | Result |
| --- | --- |
| 9 or more | Decisive Victory |
| 5 to 8 | Victory |
| 2 to 4 | Marginal Victory |
| Less than 2 | Defeat |

Capturing every Mughal stronghold wins immediately. Losing every Maratha stronghold, or every Maratha unit, loses immediately.

## Rules in brief

- **Supply.** Supply flows out from friendly cities, camps and forts and is blocked by enemy units and their zones of control. A unit that starts a turn out of supply fights at reduced strength and loses a move; after two turns it starts losing strength every turn. Each fort keeps its own garrison supplied. Units in supply that did not fight recover one strength step per turn.
- **Zones of control.** Moving next to an enemy unit ends a unit's movement, except for Maratha light horse.
- **Combat.** Hovering over an enemy shows the odds and expected losses before you attack. Defence is multiplied by terrain, cities, camps and fort walls. Every other friendly unit next to the defender adds +20% to the attack (up to +60%). A defender beaten badly in the open falls back, and the attacker advances into the hex it leaves.
- **Monsoon (June to September).** Rivers are harder to cross and to supply across, Mughal units lose a move, and Mughal siege guns lose 40% of their attack.

## Units

| Unit | Side | Moves | Attack | Defence | Special |
| --- | --- | --- | --- | --- | --- |
| Light Horse | Maratha | 6 | 4 | 3 | Ignores zones of control, can move after attacking, evades strong attacks, lives off Mughal land, +50% attack against siege guns and elephants |
| Mavalas | Maratha | 4 | 3 | 5 | Moves quickly through hills and ghats, +30% defence there outside forts |
| Heavy Cavalry | Mughal | 4 | 6 | 4 | |
| Musketeers | Mughal | 3 | 4 | 5 | |
| Siege Guns | Mughal | 2 | 6 | 2 | Weakens fort walls, takes few losses when bombarding |
| War Elephants | Mughal | 3 | 7 | 4 | +30% attack in the open, -30% in rough terrain |

## Controls

| Input | Action |
| --- | --- |
| Left click | Select a unit, move it, or attack a highlighted enemy |
| Right drag or arrow keys | Pan the map |
| Mouse wheel | Zoom |
| Z | Undo last move (until you fight or capture) |
| N | Next unit with actions left |
| S | Cycle the supply overlay (off, Maratha, Mughal) |
| C | Centre on the selected unit |
| Space / Enter | End turn |
| R | New campaign (after the game ends) |
| Esc | Deselect, or quit from the end screen |

## Code layout

| File | Contents |
| --- | --- |
| `main.py` | Game loop, input handling and turn sequencing |
| `game/data.py` | Map, terrain, unit types, scenario setup and reinforcements |
| `game/state.py` | Rules: movement, zones of control, supply, combat and scoring |
| `game/ai.py` | Mughal AI |
| `game/render.py` | Drawing the map, counters, side panel and overlays |
| `game/hexgrid.py` | Hex grid maths |
